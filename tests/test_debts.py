from uuid import uuid4

from buhgalya.services.debts import DebtView


def test_balance_is_initial_amount_minus_partial_repayments() -> None:
    debt = DebtView(
        id=uuid4(),
        person_id=uuid4(),
        person_name="Иван",
        amount_rub=1_500,
        repaid_rub=600,
    )

    assert debt.balance_rub == 900


def test_overpayment_is_visible_as_negative_debt_balance() -> None:
    debt = DebtView(
        id=uuid4(),
        person_id=uuid4(),
        person_name="Иван",
        amount_rub=1_500,
        repaid_rub=1_600,
    )

    assert debt.balance_rub == -100
