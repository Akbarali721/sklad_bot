# app/routers/auth.py
from fastapi import APIRouter, Depends, Request, Response, Query
from fastapi.responses import RedirectResponse, PlainTextResponse
from sqlalchemy.orm import Session
from os import getenv
import hmac, hashlib
from ..database import get_db
from ..models import User, Role
from ..security import set_session_cookie, clear_session_cookie
from ..settings import settings

APP_SECRET = settings.APP_SECRET.encode()
ADMIN_TG_IDS = set([x.strip() for x in settings.ADMIN_TG_IDS.split(",") if x.strip()])

router = APIRouter(prefix="/auth", tags=["auth"])


def _sig_for_tg(tg_id: str) -> str:
    return hmac.new(APP_SECRET, tg_id.encode(), hashlib.sha256).hexdigest()


@router.get("/magic")
def magic_login(
        tg_id: str = Query(...),
        sig: str = Query(...),
        db: Session = Depends(get_db),
):
    # 1) imzoni tekshirish
    good = _sig_for_tg(tg_id)
    if not hmac.compare_digest(good, sig):
        return PlainTextResponse("Noto'g'ri imzo", status_code=401)

    # 2) mavjud user bormi?
    user = db.query(User).filter(User.tg_id == tg_id).first()

    # 3) Agar yo'q bo'lsa, yangi yaratamiz: admin bo'lsa ro'yxatdan
    if not user:
        role = Role.admin if tg_id in ADMIN_TG_IDS else Role.dealer
        user = User(tg_id=tg_id, role=role)
        db.add(user);
        db.commit();
        db.refresh(user)

    # 4) Rolga qarab to'g'ri sahifaga yo'naltiramiz
    if user.role == Role.admin:
        redirect_url = "/admin/"  # To'g'ridan-to'g'ri admin paneliga
    else:
        redirect_url = "/dealer/start"  # Dealer lar uchun

    resp = RedirectResponse(url=redirect_url, status_code=303)
    set_session_cookie(resp, user)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(resp)
    return resp


# (ixtiyoriy) Admin uchun link generator – ko'rsatish uchun
@router.get("/make-link")
def make_link(tg_id: str):
    sig = _sig_for_tg(tg_id)
    return {"tg_id": tg_id, "link": f"/auth/magic?tg_id={tg_id}&sig={sig}"}