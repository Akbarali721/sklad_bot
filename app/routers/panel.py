# app/routers/panel.py
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from ..security import current_user_required
from ..models import Role

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/panel", tags=["panel"])

@router.get("/")
def panel_index(request: Request, user=Depends(current_user_required)):
    tpl = "panel/admin_home.html" if user.role == Role.admin else "panel/dealer_home.html"
    return templates.TemplateResponse(tpl, {"request": request, "user": user})
