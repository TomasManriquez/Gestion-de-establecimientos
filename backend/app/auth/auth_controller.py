from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.config import settings
from app.auth.auth_service import auth_service, require_access
from app.auth.auth_entity import (AccessContext, AccessSummary, LoginRequest, PLATFORM_DATOS, Token,
                                  UserResponse)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_token(user: dict) -> dict:
    """El `sub` es str(_id): estable, nunca el correo ni el username (C6)."""
    access_token = auth_service.create_access_token(
        data={"sub": str(user["_id"]), "role": datos_role(user) or "none"},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


def datos_role(user: dict):
    entry = next((a for a in user.get("access", []) if a.get("platform_id") == PLATFORM_DATOS), None)
    return entry.get("role") if entry else None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=Token)
async def login_for_access_token(payload: LoginRequest):
    """
    JSON Login endpoint. `username` acepta el correo o, mientras dure la compatibilidad, el
    username legado.
    """
    user = await auth_service.authenticate_user(payload.username, payload.password)
    if not user:
        raise _unauthorized()
    return _issue_token(user)

@router.post("/login-form", response_model=Token)
async def login_for_access_token_form(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Form-url-encoded Login endpoint (standard for Swagger UI)
    """
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise _unauthorized()
    return _issue_token(user)

@router.post("/logout")
async def logout():
    # JWT is stateless, so we just acknowledge logout.
    # The client discards the token.
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(ctx: AccessContext = Depends(require_access(None))):
    """Contrato original `{username, full_name, role}` más `id`, `email` y `access` (aditivo).
    `role` es el rol en `datos`, o "none" si el usuario no tiene acceso a esa plataforma."""
    user = ctx.user
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("full_name", "")
    return {
        "username": user.get("username") or user.get("email") or "",
        "full_name": full_name,
        "role": datos_role(user) or "none",
        "id": str(user["_id"]),
        "email": user.get("email"),
        "access": [AccessSummary(platform_id=a["platform_id"], role=a["role"]) for a in user.get("access", [])],
    }
