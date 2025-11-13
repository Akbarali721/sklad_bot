# app/routers/admin.py
from fastapi import APIRouter, Depends, Request, Form, Path, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud
from .. import models
from fastapi.templating import Jinja2Templates
from ..security import admin_required  # ⬅️ Guard
from datetime import datetime, timedelta

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/admin", tags=["admin"])

# ——— Dashboard
@router.get("/")
def admin_index(request: Request, user=Depends(admin_required)):
    return templates.TemplateResponse("admin/index.html", {"request": request, "user": user})

# ——— Districts
@router.get("/districts")
def districts_get(request: Request, db: Session = Depends(get_db), user=Depends(admin_required)):
    districts = crud.list_districts(db)
    return templates.TemplateResponse(
        "admin/districts.html",
        {"request": request, "districts": districts, "user": user},
    )

@router.post("/districts")
def districts_post(
    name: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    if name.strip():
        crud.create_district(db, name)
    return RedirectResponse(url="/admin/districts", status_code=303)

# ——— Shops (list + filter + pagination)
@router.get("/shops")
def shops_get(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    district_id: int | None = Query(None),
):
    districts = crud.list_districts(db)
    total = crud.count_shops(db, district_id=district_id)
    shops = crud.list_shops_paginated(db, page=page, size=size, district_id=district_id)
    total_pages = (total + size - 1) // size if total else 1
    return templates.TemplateResponse(
        "admin/shops.html",
        {
            "request": request,
            "districts": districts,
            "shops": shops,
            "page": page,
            "size": size,
            "total": total,
            "total_pages": total_pages,
            "district_id": district_id,
            "user": user,
        },
    )

@router.post("/shops")
def shops_post(
    name: str = Form(...),
    district_id: int = Form(...),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    crud.create_shop(db, name=name, district_id=district_id)
    return RedirectResponse(url="/admin/shops", status_code=303)

# ——— Products (list + create)
@router.get("/products")
def products_get(request: Request, db: Session = Depends(get_db), user=Depends(admin_required)):
    products = crud.list_products(db, only_active=False)
    return templates.TemplateResponse(
        "admin/products.html",
        {"request": request, "products": products, "user": user},
    )

@router.post("/products")
def products_post(
    name: str = Form(...),
    kind: str = Form(""),
    brand: str = Form(""),
    price_per_kg: str = Form(""),
    in_price_per_pack: str = Form(""),
    out_price_per_pack: str = Form(""),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    def to_float_or_none(v: str):
        v = (v or "").strip().replace(",", ".")
        return float(v) if v else None

    crud.create_product(
        db,
        name=name,
        kind=kind,
        brand=brand,
        price_per_kg=to_float_or_none(price_per_kg),
        in_price_per_pack=to_float_or_none(in_price_per_pack),
        out_price_per_pack=to_float_or_none(out_price_per_pack),
        is_active=is_active,
    )
    return RedirectResponse(url="/admin/products", status_code=303)

# ——— Products inline edit (price / active)
@router.post("/products/{product_id}/price")
def products_update_price(
    product_id: int = Path(...),
    price_per_kg: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    txt = (price_per_kg or "").strip().replace(",", ".")
    price = float(txt) if txt else None
    crud.update_product_price(db, product_id, price)
    return RedirectResponse(url="/admin/products", status_code=303)

@router.post("/products/{product_id}/active")
def products_update_active(
    product_id: int = Path(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    crud.set_product_active(db, product_id, is_active)
    return RedirectResponse(url="/admin/products", status_code=303)


@router.get("/stock")
def stock_get(request: Request, db: Session = Depends(get_db), user=Depends(admin_required)):
    products = crud.list_products(db, only_active=True)
    balances = {p.id: crud.stock_balance_for_product(db, p.id) for p in products}
    return templates.TemplateResponse("admin/stock.html", {
        "request": request,
        "products": products,
        "balances": balances,
        "user": user,
    })

@router.post("/stock/kirim")
def stock_kirim(
    product_id: int = Form(...),
    qty_kg: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    qty = float((qty_kg or "0").replace(",", "."))
    if qty <= 0:
        # qayta ko'rsatish uchun redirect o‘rniga sahifa ham qaytarish mumkin
        return templates.TemplateResponse("admin/stock.html", {
            "request": Request, "error": "Kirim miqdori > 0 bo'lishi kerak."
        })
    crud.add_kirim(db, product_id=product_id, qty_kg=qty, note=note.strip() or None)
    return RedirectResponse(url="/admin/stock", status_code=303)

@router.get("/monitor")
def admin_monitor(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
    district_id: int | None = Query(None),
    shop_id: int | None = Query(None),
    days: int = Query(7, ge=1, le=90),
):
    # vaqt oraliği: oxirgi N kun (UTC naive)
    end = datetime.now().replace(microsecond=0)
    start = end - timedelta(days=days)

    districts = crud.list_districts(db)
    shops = []
    if district_id:
        shops = crud.list_shops_by_district(db, district_id)

    by_shop = crud.deliveries_agg_by_shop(db, start, end, district_id, shop_id)
    by_pay = crud.deliveries_agg_paykind(db, start, end, district_id, shop_id)
    last_rows = crud.deliveries_list_with_details(db, start, end, district_id, shop_id, limit=200)

    by_product_in_shop = []
    if shop_id:
        by_product_in_shop = crud.deliveries_agg_by_product_in_shop(db, start, end, shop_id)

    # umumiy kartalar uchun yig'indilar
    total_cnt = sum(r.cnt for r in by_shop)
    total_qty = sum(r.sum_qty for r in by_shop)
    total_sum = sum(r.sum_total for r in by_shop)

    return templates.TemplateResponse("admin/monitor.html", {
        "request": request,
        "user": user,
        "districts": districts,
        "shops": shops,
        "district_id": district_id,
        "shop_id": shop_id,
        "days": days,
        "start": start, "end": end,
        "by_shop": by_shop,
        "by_pay": by_pay,
        "last_rows": last_rows,
        "by_product_in_shop": by_product_in_shop,
        "total_cnt": total_cnt,
        "total_qty": total_qty,
        "total_sum": total_sum,
    })

@router.post("/products/{product_id}/delete")
def products_delete(
    product_id: int = Path(...),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    from sqlalchemy.exc import IntegrityError
    ok = False
    try:
        ok = crud.delete_product(db, product_id)
    except IntegrityError:
        # FK bog'liqlik mavjud - o'chirish mumkin emas
        return RedirectResponse(url="/admin/products?error=linked", status_code=303)
    # agar topilmasa ham qaytamiz
    return RedirectResponse(url="/admin/products", status_code=303)


# ——— Balanslar ro'yxati
@router.get("/balances")
def balances_get(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
    district_id: int | None = Query(None),
):
    items = crud.list_balances(db, district_id=district_id)
    districts = crud.list_districts(db)
    return templates.TemplateResponse(
        "admin/balances.html",
        {"request": request, "items": items, "districts": districts, "district_id": district_id}
    )

# ——— Shop bo'yicha tranzaksiyalar
@router.get("/shops/{shop_id}/tx")
def shop_txs_get(
    request: Request,
    shop_id: int = Path(...),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    shop = db.get(models.Shop, shop_id)
    if not shop:
        return RedirectResponse(url="/admin/shops", status_code=303)
    txs = crud.list_shop_txs(db, shop_id=shop_id, limit=500)
    balance = crud.shop_balance(db, shop_id=shop_id)
    return templates.TemplateResponse(
        "admin/shop_txs.html",
        {"request": request, "shop": shop, "txs": txs, "balance": balance}
    )

@router.post("/shops/{shop_id}/tx/sale")
def shop_tx_sale(
    shop_id: int = Path(...),
    amount: float = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    crud.add_shop_tx(db, shop_id=shop_id, kind=models.TxKind.sale, amount=amount, note=note)
    return RedirectResponse(url=f"/admin/shops/{shop_id}/tx", status_code=303)

@router.post("/shops/{shop_id}/tx/payment")
def shop_tx_payment(
    shop_id: int = Path(...),
    amount: float = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    crud.add_shop_tx(db, shop_id=shop_id, kind=models.TxKind.payment, amount=amount, note=note)
    return RedirectResponse(url=f"/admin/shops/{shop_id}/tx", status_code=303)
