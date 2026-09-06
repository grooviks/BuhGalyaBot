from uuid import uuid4

from buhgalya.services.debts import DebtView
from buhgalya.telegram.bot import person_label


def test_balance_is_initial_amount_minus_partial_repayments() -> None:
    debt = DebtView(
        id=uuid4(),
        person_id=uuid4(),
        person_name="Иван",
        telegram_username=None,
        amount_rub=1_500,
        repaid_rub=600,
    )

    assert debt.balance_rub == 900


def test_overpayment_is_visible_as_negative_debt_balance() -> None:
    debt = DebtView(
        id=uuid4(),
        person_id=uuid4(),
        person_name="Иван",
        telegram_username=None,
        amount_rub=1_500,
        repaid_rub=1_600,
    )

    assert debt.balance_rub == -100


def test_person_label_includes_username_when_linked() -> None:
    assert person_label({"person_name": "Иван", "telegram_username": "ivan"}) == "Иван (@ivan)"


def test_person_label_uses_name_when_username_is_missing() -> None:
    assert person_label({"person_name": "Иван", "telegram_username": None}) == "Иван"
