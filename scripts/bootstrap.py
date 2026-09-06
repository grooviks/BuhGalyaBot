"""Create the first workspace and grant a Telegram account write access."""

import argparse
import asyncio

from sqlalchemy import select

from buhgalya.db import SessionFactory
from buhgalya.models import AllowedActor, Chat, Workspace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--actor-id", required=True, type=int, help="Telegram numeric user ID")
    parser.add_argument("--chat-id", type=int, help="Optional Telegram chat ID for the workspace")
    return parser.parse_args()


async def bootstrap(args: argparse.Namespace) -> None:
    async with SessionFactory() as session:
        workspace = Workspace(name=args.workspace_name)
        session.add(workspace)
        await session.flush()

        actor = await session.scalar(
            select(AllowedActor).where(AllowedActor.telegram_user_id == args.actor_id)
        )
        if actor is None:
            session.add(AllowedActor(telegram_user_id=args.actor_id))

        if args.chat_id is not None:
            session.add(Chat(id=args.chat_id, workspace_id=workspace.id))

        await session.commit()

    print(f"Workspace created: {workspace.id}")
    print("Set DEFAULT_WORKSPACE_ID to this value in .env.")


if __name__ == "__main__":
    asyncio.run(bootstrap(parse_args()))
