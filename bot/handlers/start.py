# bot/handlers/start.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from urllib.parse import quote

router = Router()

WEB_BASE = "https://your-host"        # prod domeningiz (lokalda http://127.0.0.1:8000)
ADMIN_NEXT = "/admin"
DEALER_NEXT = "/dealer/start"

@router.message(F.text == "/start")
async def start(m: Message):
    user = m.from_user
    tg_id = user.id
    full_name = (user.full_name or "").strip()

    # admin va dealer tugmalari (misol sifatida)
    kb = InlineKeyboardBuilder()
    kb.button(
        text="👨‍💼 Admin panel",
        url=f"{WEB_BASE}/auth/set?tg_id={tg_id}&full_name={quote(full_name)}&next={quote(ADMIN_NEXT)}"
    )
    kb.button(
        text="🧑‍🔧 Diler panel",
        url=f"{WEB_BASE}/auth/set?tg_id={tg_id}&full_name={quote(full_name)}&next={quote(DEALER_NEXT)}"
    )
    kb.adjust(1, 1)

    await m.answer(
        "Salom! Kerakli panelni tanlang.\n"
        "⚠️ Eslatma: faqat bazada ro‘yxatga olingan ID’lar kira oladi.",
        reply_markup=kb.as_markup()
    )
