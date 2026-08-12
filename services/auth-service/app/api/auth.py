from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from reminder_common.security import require_principal, utc_now
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import RefreshToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUser,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenPair,
)
from app.services.auth import (
    find_refresh,
    hash_password,
    issue_pair,
    revoke_family,
    user_by_email,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


async def db(request: Request):  # type: ignore[no-untyped-def]
    async with request.app.state.session_factory() as session:
        yield session


Session = Annotated[AsyncSession, Depends(db)]


def view(user: User) -> CurrentUser:
    return CurrentUser.model_validate(user, from_attributes=True)


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, session: Session) -> TokenPair:
    user = await user_by_email(session, str(body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User account is disabled")
    user.last_login_at = utc_now()
    access, refresh, _ = await issue_pair(session, user)
    await session.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, session: Session) -> TokenPair:
    old = await find_refresh(session, body.refresh_token)
    if old is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    if old.revoked_at is not None:
        await revoke_family(session, old.family_id)
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected")
    if old.expires_at <= utc_now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")
    user = await session.get(User, old.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication no longer valid")
    old.revoked_at = utc_now()
    access, new_refresh, replacement = await issue_pair(session, user, old.family_id)
    old.replaced_by_id = replacement.id
    await session.commit()
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, session: Session) -> None:
    token = await find_refresh(session, body.refresh_token)
    if token is not None:
        await revoke_family(session, token.family_id)
        await session.commit()


@router.get("/me", response_model=CurrentUser)
async def me(request: Request, session: Session) -> CurrentUser:
    principal = require_principal(request)
    user = await session.get(User, principal.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication no longer valid")
    return view(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: ChangePasswordRequest, request: Request, session: Session) -> None:
    principal = require_principal(request)
    user = await session.get(User, principal.user_id)
    if user is None or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    await session.commit()
