from uuid import uuid4

import pytest

from buhgalya.services.collections import ParticipantView


@pytest.mark.parametrize(
    ("paid_rub", "expected_status", "expected_balance"),
    [
        (0, "unpaid", 1_000),
        (600, "partial", 400),
        (1_000, "paid", 0),
        (1_200, "overpaid", -200),
    ],
)
def test_participant_payment_status(
    paid_rub: int, expected_status: str, expected_balance: int
) -> None:
    participant = ParticipantView(
        id=uuid4(),
        person_name="Иван",
        target_rub=1_000,
        paid_rub=paid_rub,
    )

    assert participant.status == expected_status
    assert participant.balance_rub == expected_balance
