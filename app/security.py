# app/security.py
import base64, json, hmac, hashlib, time
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Role
from os import getenv
from .settings import settings


APP_SECRET = settings.APP_SECRET.encode()
ADMIN_TG_IDS = set([x.strip() for x in settings.ADMIN_TG_IDS.split(",") if x.strip()])

def _b64(x: bytes) -> str:
    return base64.urlsafe_b64encode(x).decode().rstrip("=")

def _unb64(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def sign_token(payload: dict, ttl_sec: int = 60*60*24*30) -> str:
    # payload: {"user_id": 1, "role": "admin", "exp": ts}
    data = payload.copy()
    data["exp"] = int(time.time()) + ttl_sec
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
    body = _b64(raw)
    sig = _b64(hmac.new(APP_SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"

def verify_token(token: str) -> dict:
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(APP_SECRET, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(good, sig):
            raise ValueError("bad signature")
        data = json.loads(_unb64(body))
        if data.get("exp", 0) < int(time.time()):
            raise ValueError("expired")
        return data
    except Exception:
        raise HTTPException(status_code=401, detail="Sessiya noto‘g‘ri yoki eskirgan")

def set_session_cookie(response, user: User):
    token = sign_token({"user_id": user.id, "role": user.role.value})
    # prod’da secure=True (HTTPS)
    response.set_cookie("session", token, httponly=True, samesite="lax", secure=False, max_age=60*60*24*30, path="/")

def clear_session_cookie(response):
    response.delete_cookie("session", path="/")

def current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get("session")
    if not token:
        return None
    data = verify_token(token)
    user = db.get(User, data["user_id"])
    return user

def current_user_required(user: User | None = Depends(current_user_optional)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Login talab qilinadi")
    return user

def role_required(role: Role):
    def dep(user: User = Depends(current_user_required)):
        if user.role != role:
            raise HTTPException(status_code=403, detail="Ruxsat yo‘q")
        return user
    return dep

admin_required = role_required(Role.admin)
dealer_required = role_required(Role.dealer)
