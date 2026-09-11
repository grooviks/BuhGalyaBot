from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from buhgalya.app_logging import configure_logging
from buhgalya.db import get_session
from buhgalya.models import AllowedActor
from buhgalya.services.collections import (
    ParticipantView,
    add_participant,
    add_payment,
    collection_status,
    create_collection,
    list_collections,
)
from buhgalya.services.debts import (
    DebtView,
    active_debts_query,
    add_repayment,
    create_debt,
    debt_view,
    delete_debt,
    link_telegram_username,
    update_debt_amount,
)


class DebtCreateRequest(BaseModel):
    person_name: str = Field(min_length=1, max_length=255)
    amount_rub: int = Field(gt=0)


class RepaymentCreateRequest(BaseModel):
    amount_rub: int = Field(gt=0)


class DebtUpdateRequest(BaseModel):
    amount_rub: int = Field(gt=0)


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(pattern="^(monthly|one_time)$")
    default_target_rub: int | None = Field(default=None, gt=0)


class ParticipantCreateRequest(BaseModel):
    person_name: str = Field(min_length=1, max_length=255)
    target_rub: int | None = Field(default=None, gt=0)


class PaymentCreateRequest(BaseModel):
    amount_rub: int = Field(gt=0)


class TelegramLinkRequest(BaseModel):
    person_name: str = Field(min_length=1, max_length=255)
    telegram_username: str = Field(min_length=2, max_length=33, pattern=r"^@?[A-Za-z0-9_]+$")


class DebtResponse(BaseModel):
    id: UUID
    person_id: UUID
    person_name: str
    telegram_username: str | None
    amount_rub: int
    repaid_rub: int
    balance_rub: int

    @classmethod
    def from_view(cls, debt: DebtView) -> DebtResponse:
        return cls(
            id=debt.id,
            person_id=debt.person_id,
            person_name=debt.person_name,
            telegram_username=debt.telegram_username,
            amount_rub=debt.amount_rub,
            repaid_rub=debt.repaid_rub,
            balance_rub=debt.balance_rub,
        )


class ParticipantResponse(BaseModel):
    id: UUID
    person_name: str
    target_rub: int | None
    paid_rub: int
    balance_rub: int | None
    status: str

    @classmethod
    def from_view(cls, participant: ParticipantView) -> ParticipantResponse:
        return cls(
            id=participant.id,
            person_name=participant.person_name,
            target_rub=participant.target_rub,
            paid_rub=participant.paid_rub,
            balance_rub=participant.balance_rub,
            status=participant.status,
        )


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    kind: str
    default_target_rub: int | None


class CollectionListResponse(CollectionResponse):
    period_key: str


class CollectionStatusResponse(CollectionResponse):
    period_key: str
    participants: list[ParticipantResponse]


class PersonResponse(BaseModel):
    id: UUID
    name: str
    telegram_username: str | None


async def require_actor(
    x_actor_telegram_id: int = Header(alias="X-Actor-Telegram-ID"),
    session: AsyncSession = Depends(get_session),
) -> int:
    actor = await session.scalar(
        select(AllowedActor).where(AllowedActor.telegram_user_id == x_actor_telegram_id)
    )
    if actor is None:
        logger.warning("Unauthorized API request rejected")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    return x_actor_telegram_id


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger.info("API started")
    yield
    logger.info("API stopped")


app = FastAPI(title="BuhGalyaBot API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/workspaces/{workspace_id}/debts", response_model=DebtResponse, status_code=201)
async def post_debt(
    workspace_id: UUID,
    payload: DebtCreateRequest,
    actor_id: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> DebtResponse:
    debt = await create_debt(
        session,
        workspace_id=workspace_id,
        person_name=payload.person_name.strip(),
        amount_rub=payload.amount_rub,
        actor_id=actor_id,
    )
    await session.commit()
    logger.info("Debt created")
    return DebtResponse.from_view(debt)


@app.post("/v1/debts/{debt_id}/repayments", response_model=DebtResponse, status_code=201)
async def post_repayment(
    debt_id: UUID,
    payload: RepaymentCreateRequest,
    actor_id: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> DebtResponse:
    try:
        debt = await add_repayment(
            session,
            debt_id=debt_id,
            amount_rub=payload.amount_rub,
            actor_id=actor_id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    await session.commit()
    logger.info("Debt repayment recorded")
    return DebtResponse.from_view(debt)


@app.patch("/v1/debts/{debt_id}", response_model=DebtResponse)
async def patch_debt(
    debt_id: UUID,
    payload: DebtUpdateRequest,
    _: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> DebtResponse:
    try:
        debt = await update_debt_amount(session, debt_id=debt_id, amount_rub=payload.amount_rub)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    await session.commit()
    logger.info("Debt amount updated")
    return DebtResponse.from_view(debt)


@app.delete("/v1/debts/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_debt(
    debt_id: UUID,
    actor_id: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        await delete_debt(session, debt_id=debt_id, actor_id=actor_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    await session.commit()
    logger.info("Debt soft-deleted")


@app.get("/v1/workspaces/{workspace_id}/debts", response_model=list[DebtResponse])
async def get_debts(
    workspace_id: UUID,
    _: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> list[DebtResponse]:
    rows = (await session.execute(active_debts_query(workspace_id))).all()
    return [DebtResponse.from_view(debt_view(row.tuple())) for row in rows]


@app.post("/v1/workspaces/{workspace_id}/people/link-telegram", response_model=PersonResponse)
async def post_telegram_link(
    workspace_id: UUID,
    payload: TelegramLinkRequest,
    _: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> PersonResponse:
    try:
        person = await link_telegram_username(
            session,
            workspace_id=workspace_id,
            person_name=payload.person_name.strip(),
            telegram_username=payload.telegram_username,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    await session.commit()
    logger.info("Telegram username linked to person")
    return PersonResponse.model_validate(person, from_attributes=True)


@app.post(
    "/v1/workspaces/{workspace_id}/collections", response_model=CollectionResponse, status_code=201
)
async def post_collection(
    workspace_id: UUID,
    payload: CollectionCreateRequest,
    actor_id: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> CollectionResponse:
    collection = await create_collection(
        session,
        workspace_id=workspace_id,
        name=payload.name.strip(),
        kind=payload.kind,
        default_target_rub=payload.default_target_rub,
        actor_id=actor_id,
    )
    await session.commit()
    logger.info("Collection created")
    return CollectionResponse.model_validate(collection, from_attributes=True)


@app.get("/v1/workspaces/{workspace_id}/collections", response_model=list[CollectionListResponse])
async def get_collections(
    workspace_id: UUID,
    _: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> list[CollectionListResponse]:
    return [
        CollectionListResponse(
            id=collection.id,
            name=collection.name,
            kind=collection.kind,
            default_target_rub=collection.default_target_rub,
            period_key=round_.period_key,
        )
        for collection, round_ in await list_collections(session, workspace_id)
    ]


@app.post(
    "/v1/collections/{collection_id}/participants",
    response_model=ParticipantResponse,
    status_code=201,
)
async def post_participant(
    collection_id: UUID,
    payload: ParticipantCreateRequest,
    _: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> ParticipantResponse:
    try:
        participant = await add_participant(
            session,
            collection_id=collection_id,
            person_name=payload.person_name.strip(),
            target_rub=payload.target_rub,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    await session.commit()
    logger.info("Collection participant added")
    return ParticipantResponse.from_view(participant)


@app.post(
    "/v1/participants/{participant_id}/payments",
    response_model=ParticipantResponse,
    status_code=201,
)
async def post_collection_payment(
    participant_id: UUID,
    payload: PaymentCreateRequest,
    actor_id: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> ParticipantResponse:
    try:
        participant = await add_payment(
            session, participant_id=participant_id, amount_rub=payload.amount_rub, actor_id=actor_id
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    await session.commit()
    logger.info("Collection payment recorded")
    return ParticipantResponse.from_view(participant)


@app.get("/v1/collections/{collection_id}/status", response_model=CollectionStatusResponse)
async def get_collection_status(
    collection_id: UUID,
    _: int = Depends(require_actor),
    session: AsyncSession = Depends(get_session),
) -> CollectionStatusResponse:
    try:
        collection, round_, participants = await collection_status(session, collection_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CollectionStatusResponse(
        id=collection.id,
        name=collection.name,
        kind=collection.kind,
        default_target_rub=collection.default_target_rub,
        period_key=round_.period_key,
        participants=[ParticipantResponse.from_view(item) for item in participants],
    )
