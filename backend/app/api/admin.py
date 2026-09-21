"""Admin panel: self-service access management (allowlist, open signup toggle,
registered users) so managing who can log in doesn't require a deploy.

Admin = the owner (see app.auth.get_current_admin). Everything here is gated
by that dependency — a 403 for anyone else, including other logged-in users."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import get_current_admin
from app.db import session_scope
from app.models.user import User
from app.services import allowlist

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/allowlist")
async def get_allowlist(admin: User = Depends(get_current_admin)) -> dict:
    return {
        "emails": sorted(await allowlist.get_allowed_emails()),
        "public_signup": await allowlist.get_public_signup(),
    }


class EmailIn(BaseModel):
    email: str


@router.post("/allowlist")
async def add_to_allowlist(payload: EmailIn, admin: User = Depends(get_current_admin)) -> dict:
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Email inválido")
    current = await allowlist.get_allowed_emails()
    if email in current:
        raise HTTPException(status_code=400, detail="Ese email ya está en la lista")
    emails = await allowlist.add_email(email)
    return {"emails": sorted(emails)}


@router.delete("/allowlist/{email}")
async def remove_from_allowlist(email: str, admin: User = Depends(get_current_admin)) -> dict:
    email = email.strip().lower()
    if email == admin.email:
        raise HTTPException(status_code=400, detail="No puedes quitarte a ti mismo el acceso")
    emails = await allowlist.remove_email(email)
    return {"emails": sorted(emails)}


class SignupIn(BaseModel):
    enabled: bool


@router.put("/signup")
async def set_signup(payload: SignupIn, admin: User = Depends(get_current_admin)) -> dict:
    """When enabled, ANY Google account can log in — the allowlist is ignored
    entirely. Off by default; use with care."""
    return {"public_signup": await allowlist.set_public_signup(payload.enabled)}


@router.get("/users")
async def list_users(admin: User = Depends(get_current_admin)) -> dict:
    """Read-only: who has actually registered (vs. who's just allowlisted but
    hasn't logged in yet)."""
    async with session_scope() as s:
        rows = (await s.execute(select(User).order_by(User.created_at))).scalars().all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "created_at": u.created_at.isoformat(),
                "last_login_at": u.last_login_at.isoformat(),
                "is_admin": u.id == admin.id,
            }
            for u in rows
        ]
    }
