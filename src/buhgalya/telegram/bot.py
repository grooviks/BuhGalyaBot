import asyncio
from uuid import UUID

import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from loguru import logger

from buhgalya.app_logging import configure_logging
from buhgalya.config import get_settings


def require_workspace() -> UUID:
    workspace_id = get_settings().default_workspace_id
    if workspace_id is None:
        raise RuntimeError("DEFAULT_WORKSPACE_ID is required for the Telegram bot")
    return workspace_id


def command_args(command: CommandObject | None, expected: int) -> list[str] | None:
    parts = command.args.split() if command and command.args else []
    return parts if len(parts) == expected else None


def person_label(item: dict) -> str:
    username = item.get("telegram_username")
    return f"{item['person_name']} (@{username})" if username else item["person_name"]


async def api_request(
    message: Message, method: str, path: str, **kwargs: object
) -> dict | list | None:
    actor_id = message.from_user.id if message.from_user else 0
    headers = {"X-Actor-Telegram-ID": str(actor_id)}
    try:
        async with httpx.AsyncClient(
            base_url=str(get_settings().api_base_url), timeout=10
        ) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
    except httpx.RequestError:
        logger.warning("Telegram API request failed before receiving a response: method={}", method)
        await message.answer("Сервис учёта сейчас недоступен. Попробуйте ещё раз через минуту.")
        raise RuntimeError("API request failed") from None
    if response.is_error:
        logger.warning(
            "Telegram API request failed: method={} status={}", method, response.status_code
        )
        detail = response.json().get("detail", "Не удалось выполнить операцию")
        await message.answer(f"Ошибка: {detail}")
        raise RuntimeError("API request failed")
    if response.status_code == 204:
        return None
    return response.json()


async def start(message: Message) -> None:
    await message.answer("BuhGalyaBot: /debt_add <имя> <сумма>, /debt_repay <id> <сумма>, /debts")


async def debt_add(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 2)
    if parts is None or not parts[1].isdigit() or int(parts[1]) <= 0:
        await message.answer("Использование: /debt_add <имя> <целые_рубли>")
        return
    try:
        debt = await api_request(
            message,
            "POST",
            f"/v1/workspaces/{require_workspace()}/debts",
            json={"person_name": parts[0], "amount_rub": int(parts[1])},
        )
    except RuntimeError:
        return
    await message.answer(
        f"Долг добавлен: {person_label(debt)} — {debt['balance_rub']} ₽ (ID: {debt['id']})"
    )


async def debt_repay(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 2)
    if parts is None or not parts[1].isdigit() or int(parts[1]) <= 0:
        await message.answer("Использование: /debt_repay <id_долга> <целые_рубли>")
        return
    try:
        debt = await api_request(
            message,
            "POST",
            f"/v1/debts/{parts[0]}/repayments",
            json={"amount_rub": int(parts[1])},
        )
    except RuntimeError:
        return
    await message.answer(f"Возврат записан. {person_label(debt)}: остаток {debt['balance_rub']} ₽.")


async def debt_edit(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 2)
    if parts is None or not parts[1].isdigit() or int(parts[1]) <= 0:
        await message.answer("Использование: /debt_edit <id_долга> <целые_рубли>")
        return
    try:
        debt = await api_request(
            message,
            "PATCH",
            f"/v1/debts/{parts[0]}",
            json={"amount_rub": int(parts[1])},
        )
    except RuntimeError:
        return
    await message.answer(f"Сумма долга обновлена. Остаток: {debt['balance_rub']} ₽.")


async def debt_delete(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 1)
    if parts is None:
        await message.answer("Использование: /debt_delete <id_долга>")
        return
    try:
        await api_request(message, "DELETE", f"/v1/debts/{parts[0]}")
    except RuntimeError:
        return
    await message.answer("Долг удалён из текущего списка. История сохранена.")


async def debts(message: Message) -> None:
    try:
        result = await api_request(message, "GET", f"/v1/workspaces/{require_workspace()}/debts")
    except RuntimeError:
        return
    active = [debt for debt in result if debt["balance_rub"] > 0]
    if not active:
        await message.answer("Активных долгов нет.")
        return
    lines = ["Активные долги:"]
    lines.extend(
        f"• {person_label(debt)}: {debt['balance_rub']} ₽ (ID: {debt['id']})" for debt in active
    )
    await message.answer("\n".join(lines))


async def person_link(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 2)
    if parts is None or not parts[1].startswith("@"):
        await message.answer("Использование: /person_link <имя> <@telegram_username>")
        return
    try:
        person = await api_request(
            message,
            "POST",
            f"/v1/workspaces/{require_workspace()}/people/link-telegram",
            json={"person_name": parts[0], "telegram_username": parts[1]},
        )
    except RuntimeError:
        return
    await message.answer(f"Связь сохранена: {person['name']} — @{person['telegram_username']}.")


async def fund_create(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 3)
    kind_map = {"monthly": "monthly", "once": "one_time"}
    if parts is None or parts[0] not in kind_map or not parts[2].isdigit() or int(parts[2]) <= 0:
        await message.answer("Использование: /fund_create <monthly|once> <название> <целые_рубли>")
        return
    try:
        fund = await api_request(
            message,
            "POST",
            f"/v1/workspaces/{require_workspace()}/collections",
            json={
                "kind": kind_map[parts[0]],
                "name": parts[1],
                "default_target_rub": int(parts[2]),
            },
        )
    except RuntimeError:
        return
    await message.answer(f"Сбор создан: {fund['name']} (ID: {fund['id']}).")


async def fund_add(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 2) or command_args(command, 3)
    if parts is None or (len(parts) == 3 and (not parts[2].isdigit() or int(parts[2]) <= 0)):
        await message.answer("Использование: /fund_add <id_сбора> <имя> [индивидуальная_сумма]")
        return
    payload = {"person_name": parts[1]}
    if len(parts) == 3:
        payload["target_rub"] = int(parts[2])
    try:
        participant = await api_request(
            message, "POST", f"/v1/collections/{parts[0]}/participants", json=payload
        )
    except RuntimeError:
        return
    await message.answer(
        f"Участник добавлен: {participant['person_name']}, цель {participant['target_rub']} ₽ "
        f"(ID: {participant['id']})."
    )


async def fund_pay(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 2)
    if parts is None or not parts[1].isdigit() or int(parts[1]) <= 0:
        await message.answer("Использование: /fund_pay <id_участника> <целые_рубли>")
        return
    try:
        participant = await api_request(
            message,
            "POST",
            f"/v1/participants/{parts[0]}/payments",
            json={"amount_rub": int(parts[1])},
        )
    except RuntimeError:
        return
    await message.answer(
        f"Платёж записан: {participant['person_name']}; статус: {participant['status']}; "
        f"остаток: {participant['balance_rub']} ₽."
    )


async def fund_status(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 1)
    if parts is None:
        await message.answer("Использование: /fund_status <id_сбора>")
        return
    try:
        fund = await api_request(message, "GET", f"/v1/collections/{parts[0]}/status")
    except RuntimeError:
        return
    lines = [f"{fund['name']} ({fund['period_key']}):"]
    lines.extend(
        f"• {item['person_name']}: {item['paid_rub']}/{item['target_rub']} ₽ — {item['status']}"
        for item in fund["participants"]
    )
    await message.answer("\n".join(lines))


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.message.register(start, Command("start"))
    dispatcher.message.register(debt_add, Command("debt_add"))
    dispatcher.message.register(debt_repay, Command("debt_repay"))
    dispatcher.message.register(debt_edit, Command("debt_edit"))
    dispatcher.message.register(debt_delete, Command("debt_delete"))
    dispatcher.message.register(debts, Command("debts"))
    dispatcher.message.register(person_link, Command("person_link"))
    dispatcher.message.register(fund_create, Command("fund_create"))
    dispatcher.message.register(fund_add, Command("fund_add"))
    dispatcher.message.register(fund_pay, Command("fund_pay"))
    dispatcher.message.register(fund_status, Command("fund_status"))
    return dispatcher


async def main() -> None:
    configure_logging()
    token = get_settings().bot_token
    if token is None:
        logger.error("BOT_TOKEN is not configured")
        raise RuntimeError("BOT_TOKEN is required")
    bot = Bot(token=token.get_secret_value())
    logger.info("Telegram bot polling started")
    try:
        await create_dispatcher().start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Telegram bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
