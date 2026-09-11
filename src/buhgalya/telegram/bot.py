import asyncio
from html import escape
from uuid import UUID

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    Message,
)
from loguru import logger

from buhgalya.app_logging import configure_logging
from buhgalya.config import get_settings

BOT_COMMANDS = [
    BotCommand(command="start", description="Начать работу"),
    BotCommand(command="help", description="Справка и примеры команд"),
    BotCommand(command="debts", description="Список активных долгов"),
    BotCommand(command="debt_add", description="Добавить долг"),
    BotCommand(command="debt_repay", description="Записать возврат долга"),
    BotCommand(command="person_link", description="Связать имя и Telegram username"),
    BotCommand(command="fund_create", description="Создать сбор"),
    BotCommand(command="funds", description="Показать все сборы"),
    BotCommand(command="fund_add", description="Добавить участника сбора"),
    BotCommand(command="fund_add_many", description="Массово добавить участников"),
    BotCommand(command="fund_pay", description="Записать платёж в сбор"),
    BotCommand(command="fund_status", description="Показать статус сбора"),
]


async def set_bot_commands(bot: Bot) -> None:
    for scope in (
        BotCommandScopeDefault(),
        BotCommandScopeAllPrivateChats(),
        BotCommandScopeAllGroupChats(),
    ):
        try:
            await bot.set_my_commands(BOT_COMMANDS, scope=scope, request_timeout=30)
        except TelegramNetworkError:
            logger.warning("Could not register Telegram command menu for scope={}", scope.type)


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
    await message.answer("BuhGalyaBot запущен. Наберите /help для справки.")


async def help_command(message: Message) -> None:
    await message.answer(
        """BuhGalyaBot — команды:

Долги:
/debt_add <имя> <сумма>
/debt_repay <id_долга> <сумма>
/debt_edit <id_долга> <сумма>
/debt_delete <id_долга>
/debts

Люди:
/person_link <имя> <@username>

Сборы:
/fund_create <monthly|once> <название> [сумма]
/fund_add <id_сбора> <имя> [индивидуальная_сумма]
/fund_add_many <id_сбора> <имя1>; <имя2>; <имя3>
/fund_pay <id_участника> <сумма>
/fund_status <id_сбора>

Суммы — целые рубли. Имена и названия пока вводятся одним словом."""
    )


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
    lines = ["<b>Активные долги:</b>"]
    for debt in active:
        name = escape(debt["person_name"])
        username = debt.get("telegram_username")
        person = f"{name} (@{escape(username)})" if username else name
        lines.append(
            f"• <b>{person}</b>: <b>{debt['balance_rub']} ₽</b> "
            f"(ID: <code>{escape(str(debt['id']))}</code>)"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


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
    parts = command.args.split() if command and command.args else []
    kind_map = {"monthly": "monthly", "once": "one_time"}
    valid_amount = len(parts) == 3 and parts[2].isdigit() and int(parts[2]) > 0
    if (
        len(parts) not in (2, 3)
        or parts[0] not in kind_map
        or (len(parts) == 3 and not valid_amount)
    ):
        await message.answer("Использование: /fund_create <monthly|once> <название> [целые_рубли]")
        return
    amount = int(parts[2]) if len(parts) == 3 else None
    try:
        fund = await api_request(
            message,
            "POST",
            f"/v1/workspaces/{require_workspace()}/collections",
            json={
                "kind": kind_map[parts[0]],
                "name": parts[1],
                "default_target_rub": amount,
            },
        )
    except RuntimeError:
        return
    target = f"; цель {amount} ₽" if amount is not None else "; без общей цели"
    await message.answer(f"Сбор создан: {fund['name']}{target} (ID: {fund['id']}).")


async def funds(message: Message) -> None:
    try:
        result = await api_request(
            message, "GET", f"/v1/workspaces/{require_workspace()}/collections"
        )
    except RuntimeError:
        return
    if not result:
        await message.answer("Сборов пока нет.")
        return
    kind_names = {"monthly": "ежемесячный", "one_time": "разовый"}
    lines = ["<b>Сборы:</b>"]
    for fund in result:
        target = (
            f"; цель {fund['default_target_rub']} ₽"
            if fund["default_target_rub"] is not None
            else "; без общей цели"
        )
        lines.append(
            f"• <b>{escape(fund['name'])}</b> "
            f"({kind_names.get(fund['kind'], escape(fund['kind']))}; "
            f"{fund['period_key']}{target})\n"
            f"  ID: <code>{escape(str(fund['id']))}</code>"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


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
        f"Участник добавлен: {participant['person_name']}" +
        (
            f", цель {participant['target_rub']} ₽ "
            if participant["target_rub"] is not None
            else ", без цели "
        )
        +
        f"(ID: {participant['id']})."
    )


async def fund_add_many(message: Message, command: CommandObject) -> None:
    raw = command.args.strip() if command and command.args else ""
    collection_id, separator, names_raw = raw.partition(" ")
    names = [name.strip() for name in names_raw.split(";") if name.strip()] if separator else []
    if not collection_id or not names:
        await message.answer("Использование: /fund_add_many <id_сбора> <имя1>; <имя2>; <имя3>")
        return

    added: list[str] = []
    failed: list[str] = []
    for name in names:
        try:
            participant = await api_request(
                message,
                "POST",
                f"/v1/collections/{collection_id}/participants",
                json={"person_name": name},
            )
        except RuntimeError:
            failed.append(name)
            continue
        added.append(participant["person_name"])

    lines = [f"Добавлено участников: {len(added)}."]
    if added:
        lines.append("Добавлены: " + ", ".join(added))
    if failed:
        lines.append("Не добавлены: " + ", ".join(failed))
    await message.answer("\n".join(lines))


async def fund_pay(message: Message, command: CommandObject) -> None:
    parts = command_args(command, 2)
    if parts is None or not parts[1].isdigit() or int(parts[1]) <= 0:
        await message.answer("Использование: /fund_pay <id_участника> <целые_рубли>")
        return
    try:
        try:
            participant_id = UUID(parts[0])
        except ValueError:
            participant_id = None
        if participant_id is not None:
            participant = await api_request(
                message,
                "POST",
                f"/v1/participants/{participant_id}/payments",
                json={"amount_rub": int(parts[1])},
            )
        else:
            participant = await api_request(
                message,
                "POST",
                f"/v1/workspaces/{require_workspace()}/participants/pay-by-name",
                json={"person_name": parts[0], "amount_rub": int(parts[1])},
            )
    except RuntimeError:
        return
    await message.answer(
        f"Платёж записан: {participant['person_name']}; статус: {participant['status']}; "
        + (
            f"остаток: {participant['balance_rub']} ₽."
            if participant["balance_rub"] is not None
            else "цель не задана."
        )
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
        f"• {item['person_name']}: {item['paid_rub']} ₽"
        + (f"/{item['target_rub']} ₽" if item['target_rub'] is not None else "")
        + f" — {item['status']}"
        for item in fund["participants"]
    )
    await message.answer("\n".join(lines))


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.message.register(start, Command("start"))
    dispatcher.message.register(help_command, Command("help"))
    dispatcher.message.register(debt_add, Command("debt_add"))
    dispatcher.message.register(debt_repay, Command("debt_repay"))
    dispatcher.message.register(debt_edit, Command("debt_edit"))
    dispatcher.message.register(debt_delete, Command("debt_delete"))
    dispatcher.message.register(debts, Command("debts"))
    dispatcher.message.register(person_link, Command("person_link"))
    dispatcher.message.register(fund_create, Command("fund_create"))
    dispatcher.message.register(funds, Command("funds"))
    dispatcher.message.register(fund_add, Command("fund_add"))
    dispatcher.message.register(fund_add_many, Command("fund_add_many"))
    dispatcher.message.register(fund_pay, Command("fund_pay"))
    dispatcher.message.register(fund_status, Command("fund_status"))
    return dispatcher


async def main() -> None:
    configure_logging()
    token = get_settings().bot_token
    if token is None:
        logger.error("BOT_TOKEN is not configured")
        raise RuntimeError("BOT_TOKEN is required")
    proxy_url = get_settings().telegram_proxy_url
    session = AiohttpSession(proxy=proxy_url) if proxy_url else None
    if proxy_url:
        logger.info("Using Telegram proxy")
    bot = Bot(token=token.get_secret_value(), session=session)
    await set_bot_commands(bot)
    logger.info("Telegram bot polling started")
    try:
        await create_dispatcher().start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Telegram bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
