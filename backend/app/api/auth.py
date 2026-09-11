"""Google OAuth login endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, google_client
from app.config import get_settings
from app.db import get_session
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    settings = get_settings()
    if not settings.has_google_oauth:
        raise HTTPException(status_code=503, detail="Google OAuth no configurado todavía")
    redirect_uri = str(request.url_for("auth_callback"))
    return await google_client().authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def callback(request: Request, session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    try:
        token = await google_client().authorize_access_token(request)
    except Exception as exc:
        logger.warning("oauth callback failed: {}", exc)
        raise HTTPException(status_code=400, detail="Login con Google falló") from exc

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").strip().lower()
    google_sub = userinfo.get("sub")
    if not email or not google_sub:
        raise HTTPException(status_code=400, detail="Google no devolvió email/sub")

    if not settings.public_signup and email not in settings.allowed_emails_set:
        logger.warning("oauth: rejected email not in allowlist: {}", email)
        raise HTTPException(status_code=403, detail="Este email no tiene acceso a FinTrack")

    result = await session.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            google_sub=google_sub,
            email=email,
            name=userinfo.get("name") or email,
            picture_url=userinfo.get("picture"),
        )
        session.add(user)
        await session.flush()
        logger.info("new user registered: {}", email)
    else:
        user.name = userinfo.get("name") or user.name
        user.picture_url = userinfo.get("picture") or user.picture_url

    await session.commit()
    request.session["user_id"] = user.id
    return RedirectResponse(url="/")


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture_url": current_user.picture_url,
    }


@router.post("/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"status": "logged_out"}
