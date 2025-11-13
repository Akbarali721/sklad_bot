# app/routers/dealer.py
from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, models
from fastapi.templating import Jinja2Templates
from ..security import dealer_required

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/dealer", tags=["dealer"])


@router.get("/start")
def dealer_start(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(dealer_required),
):
    districts = crud.list_districts(db)
    return templates.TemplateResponse(
        "dealer/select_district.html",
        {"request": request, "districts": districts, "user": user},
    )


@router.get("/shops")
def dealer_shops(
    request: Request,
    district_id: int = Query(...),
    db: Session = Depends(get_db),
    user=Depends(dealer_required),
):
    shops = crud.list_shops_by_district(db, district_id)
    return templates.TemplateResponse(
        "dealer/select_shop.html",
        {"request": request, "shops": shops, "district_id": district_id, "user": user},
    )


@router.get("/deliver")
def deliver_get(
    request: Request,
    district_id: int,
    shop_id: int,
    db: Session = Depends(get_db),
    user=Depends(dealer_required),
):
    products = crud.list_products(db, only_active=True)
    return templates.TemplateResponse(
        "dealer/deliver.html",
        {
            "request": request,
            "district_id": district_id,
            "shop_id": shop_id,
            "products": products,
            "user": user,
        },
    )


@router.post("/deliver")
def deliver_post(
    request: Request,
    district_id: int = Form(...),
    shop_id: int = Form(...),
    product_id: int = Form(...),
    qty_kg: str = Form(...),
    unit_price_override: str = Form(""),   # hozir ishlatmaymiz, lekin parametr qoldirdik
    pay_kind: str = Form("naqd"),         # "naqd" | "terminal" | "qarz"
    db: Session = Depends(get_db),
    user=Depends(dealer_required),
):
    # ——— Miqdorni floatga o'tkazish
    try:
        qty = float((qty_kg or "0").replace(",", ".").strip())
    except ValueError:
        qty = 0.0

    product = db.get(models.Product, product_id)
    if product is None:
        return RedirectResponse(url="/dealer/start", status_code=303)

    # ——— Ombor qoldig'ini tekshirish
    balance = crud.stock_balance_for_product(db, product_id)
    if qty <= 0:
        error = "Miqdor > 0 bo'lishi kerak."
    elif qty > balance + 1e-9:
        error = f"Omborda yetarli qoldiq yo'q. Qoldiq: {balance:.3f} kg"
    else:
        error = None

    if error:
        products = crud.list_products(db, only_active=True)
        return templates.TemplateResponse(
            "dealer/deliver.html",
            {
                "request": request,
                "district_id": district_id,
                "shop_id": shop_id,
                "products": products,
                "error": error,
                "user": user,
            },
        )

    # ——— Narxni aniqlash
    # Dealer narxga aralashmasin: asosan product.price_per_kg ishlatamiz
    unit_price = product.price_per_kg
    if unit_price is None:
        txt = (unit_price_override or "").replace(",", ".").strip()
        unit_price = float(txt) if txt else 0.0

    if unit_price <= 0:
        products = crud.list_products(db, only_active=True)
        return templates.TemplateResponse(
            "dealer/deliver.html",
            {
                "request": request,
                "district_id": district_id,
                "shop_id": shop_id,
                "products": products,
                "error": "Narx > 0 bo'lishi kerak.",
                "user": user,
            },
        )

    # ——— Delivery yozuvi
    delivery = crud.create_delivery(
        db,
        district_id=district_id,
        shop_id=shop_id,
        product_id=product_id,
        qty_kg=qty,
        unit_price=unit_price,
        pay_kind=pay_kind,
    )

    # ——— Ombordan chiqimni qayd etamiz (ledger)
    crud.add_chiqim(
        db,
        product_id=product_id,
        qty_kg=qty,
        shop_id=shop_id,
        note=f"Delivery #{delivery.id}",
    )

    # --- YANGI QISM: do'kon balansi uchun tranzaksiya yozish ---
    total_sum = qty * unit_price

    # Siz aytgandek:
    #  - Naqd / Terminal => balansga + (payment)
    #  - Qarz           => balansdan - (sale)
    if pay_kind in ("naqd", "terminal"):
        crud.add_shop_tx(
            db,
            shop_id=shop_id,
            kind=models.TxKind.payment,
            amount=total_sum,
            note=f"Delivery #{delivery.id} ({pay_kind})",
        )
    elif pay_kind == "qarz":
        crud.add_shop_tx(
            db,
            shop_id=shop_id,
            kind=models.TxKind.sale,
            amount=total_sum,
            note=f"Delivery #{delivery.id} (qarz)",
        )
    # --- YANGI QISM TUGADI ---

    return templates.TemplateResponse(
        "dealer/success.html",
        {
            "request": request,
            "delivery": delivery,
            "product": product,
            "user": user,
            "total_sum": total_sum,
            "pay_kind": pay_kind,
        },
    )
