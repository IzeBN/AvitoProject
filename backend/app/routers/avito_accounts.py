"""
Роутер управления Avito аккаунтами.

GET    /api/v1/avito-accounts                    — список аккаунтов организации
POST   /api/v1/avito-accounts                    — добавить аккаунт
PATCH  /api/v1/avito-accounts/{id}               — обновить имя аккаунта
DELETE /api/v1/avito-accounts/{id}               — удалить аккаунт
POST   /api/v1/avito-accounts/{id}/refresh-token — принудительно обновить OAuth токен
GET    /api/v1/avito-accounts/{id}/balance       — баланс аккаунта через Avito API
POST   /api/v1/avito-accounts/{id}/webhooks/setup — настроить вебхуки
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.auth import User
from app.repositories.avito_account import AvitoAccountRepository
from app.schemas.avito_account import (
    AvitoAccountCreate,
    AvitoAccountResponse,
    AvitoAccountUpdate,
    BalanceResponse,
    WebhookSetupResponse,
)
from app.services.avito_accounts import AvitoAccountService

router = APIRouter(prefix="/avito-accounts", tags=["avito-accounts"])


def _get_service(
    db: AsyncSession,
    request: Request,
) -> AvitoAccountService:
    from app.config import get_settings

    settings = get_settings()
    repo = AvitoAccountRepository(db)
    avito_client = request.app.state.avito_client
    base_url = str(request.base_url).rstrip("/")
    return AvitoAccountService(
        repo=repo,
        avito_client=avito_client,
        encryption_key=settings.encryption_key_bytes,
        base_url=base_url,
    )


# ===========================================================================
# List & create
# ===========================================================================


@router.get(
    "",
    response_model=list[AvitoAccountResponse],
    summary="Список Avito аккаунтов организации",
)
async def list_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AvitoAccountResponse]:
    repo = AvitoAccountRepository(db)
    accounts = await repo.get_all_with_webhooks(current_user.org_id)
    return [
        AvitoAccountResponse.from_account(
            a,
            webhooks_active=any(ep.is_active for ep in a.webhook_endpoints),
        )
        for a in accounts
    ]


@router.post(
    "",
    response_model=AvitoAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить Avito аккаунт",
    description=(
        "Шифрует client_id и client_secret, верифицирует учётные данные через Avito API, "
        "настраивает вебхук эндпоинт."
    ),
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def create_account(
    body: AvitoAccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> AvitoAccountResponse:
    svc = _get_service(db, request)
    account = await svc.create_account(
        org_id=current_user.org_id,
        client_id=body.client_id,
        client_secret=body.client_secret,
    )
    await db.commit()
    return AvitoAccountResponse.from_account(account, webhooks_active=True)


# ===========================================================================
# Update
# ===========================================================================


@router.patch(
    "/{account_id}",
    response_model=AvitoAccountResponse,
    summary="Обновить имя аккаунта",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def update_account(
    account_id: uuid.UUID,
    body: AvitoAccountUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AvitoAccountResponse:
    repo = AvitoAccountRepository(db)
    account = await repo.get_by_id_org(current_user.org_id, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avito аккаунт не найден",
        )
    update_data = body.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(account, key, value)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    endpoints = await AvitoAccountRepository(db).get_endpoints_for_account(account.id)
    return AvitoAccountResponse.from_account(
        account,
        webhooks_active=any(ep.is_active for ep in endpoints),
    )


# ===========================================================================
# Delete
# ===========================================================================


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить Avito аккаунт",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def delete_account(
    account_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> None:
    svc = _get_service(db, request)
    await svc.delete_account(current_user.org_id, account_id)
    await db.commit()


# ===========================================================================
# Token refresh
# ===========================================================================


@router.post(
    "/{account_id}/refresh-token",
    status_code=status.HTTP_200_OK,
    summary="Принудительно обновить OAuth токен",
    description="Инвалидирует кешированный токен и получает новый от Avito.",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def refresh_token(
    account_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> None:
    repo = AvitoAccountRepository(db)
    account = await repo.get_by_id_org(current_user.org_id, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avito аккаунт не найден",
        )

    avito_client = request.app.state.avito_client
    # Инвалидируем кешированный токен
    await avito_client._invalidate_token(account)
    # Получаем новый токен
    try:
        await avito_client._get_token(account)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось обновить токен: {exc}",
        ) from exc


# ===========================================================================
# Balance
# ===========================================================================


@router.get(
    "/{account_id}/balance",
    response_model=BalanceResponse,
    summary="Баланс Avito аккаунта",
)
async def get_balance(
    account_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> BalanceResponse:
    svc = _get_service(db, request)
    data = await svc.get_balance(current_user.org_id, account_id)
    return BalanceResponse(
        bonus=data.get("bonus", 0),
        real=data.get("real", 0),
        total=data.get("total", 0),
    )


# ===========================================================================
# Webhooks setup
# ===========================================================================


@router.post(
    "/{account_id}/webhooks/setup",
    response_model=WebhookSetupResponse,
    summary="Настроить вебхуки Avito",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def setup_webhooks(
    account_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> WebhookSetupResponse:
    from app.schemas.avito_account import WebhookEndpointResponse

    svc = _get_service(db, request)
    endpoints = await svc.setup_webhooks(current_user.org_id, account_id)
    await db.commit()
    return WebhookSetupResponse(
        endpoints=[WebhookEndpointResponse.model_validate(ep) for ep in endpoints]
    )
