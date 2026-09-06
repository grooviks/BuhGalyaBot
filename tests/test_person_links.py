from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from buhgalya.models import Person
from buhgalya.services import debts


@pytest.mark.asyncio
async def test_link_telegram_username_normalizes_at_sign_and_case() -> None:
    person = Person(id=uuid4(), workspace_id=uuid4(), name="Иван")
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[person, None])

    result = await debts.link_telegram_username(
        session,
        workspace_id=person.workspace_id,
        person_name=person.name,
        telegram_username="@Ivan_Example",
    )

    assert result is person
    assert person.telegram_username == "ivan_example"
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_link_telegram_username_rejects_duplicate_link() -> None:
    person = Person(id=uuid4(), workspace_id=uuid4(), name="Иван")
    another_person = Person(id=uuid4(), workspace_id=person.workspace_id, name="Пётр")
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[person, another_person])

    with pytest.raises(ValueError, match="уже привязан"):
        await debts.link_telegram_username(
            session,
            workspace_id=person.workspace_id,
            person_name=person.name,
            telegram_username="@petr",
        )

    session.flush.assert_not_awaited()
