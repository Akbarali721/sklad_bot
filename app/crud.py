from sqlalchemy.orm import Session
from sqlalchemy import select, func
from . import models
from .models import User, Role
from datetime import datetime



def get_user_by_tg_id(db: Session, tg_id: str) -> User | None:
    return db.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()


def ensure_user(db: Session, tg_id: str, full_name: str | None = None, role: Role | None = None) -> User:
    u = get_user_by_tg_id(db, tg_id)
    if u:
        return u
    u = User(tg_id=str(tg_id), full_name=full_name, role=role or Role.dealer)
    db.add(u); db.commit(); db.refresh(u)
    return u


# District
def create_district(db: Session, name: str) -> models.District:
    d = models.District(name=name.strip())
    db.add(d); db.commit(); db.refresh(d); return d

def list_districts(db: Session):
    return db.execute(select(models.District).order_by(models.District.name)).scalars().all()

# Shop
def create_shop(db: Session, name: str, district_id: int) -> models.Shop:
    s = models.Shop(name=name.strip(), district_id=district_id)
    db.add(s); db.commit(); db.refresh(s); return s

def list_shops_by_district(db: Session, district_id: int):
    return db.execute(
        select(models.Shop).where(models.Shop.district_id == district_id).order_by(models.Shop.name)
    ).scalars().all()

# Product
def create_product(db: Session, name: str, kind: str | None, brand: str | None,
                   price_per_kg: float | None, in_price_per_pack: float | None,
                   out_price_per_pack: float | None, is_active: bool=True):
    p = models.Product(
        name=name.strip(),
        kind=(kind or "").strip() or None,
        brand=(brand or "").strip() or None,
        price_per_kg=price_per_kg,
        in_price_per_pack=in_price_per_pack,
        out_price_per_pack=out_price_per_pack,
        is_active=is_active,
    )
    db.add(p); db.commit(); db.refresh(p); return p

def list_products(db: Session, only_active: bool = True):
    stmt = select(models.Product)
    if only_active:
        stmt = stmt.where(models.Product.is_active == True)  # noqa
    return db.execute(stmt.order_by(models.Product.name)).scalars().all()

# Delivery
def create_delivery(db: Session, district_id: int, shop_id: int, product_id: int,
                    qty_kg: float, unit_price: float, pay_kind: str):
    total = qty_kg * unit_price
    d = models.Delivery(
        district_id=district_id, shop_id=shop_id, product_id=product_id,
        qty_kg=qty_kg, unit_price=unit_price, total=total, pay_kind=pay_kind
    )
    db.add(d); db.commit(); db.refresh(d); return d


def update_product_price(db: Session, product_id: int, price_per_kg: float | None):
    p = db.get(models.Product, product_id)
    if not p:
        return None
    p.price_per_kg = price_per_kg
    db.commit()
    db.refresh(p)
    return p

def set_product_active(db: Session, product_id: int, active: bool):
    p = db.get(models.Product, product_id)
    if not p:
        return None
    p.is_active = active
    db.commit()
    db.refresh(p)
    return p

def count_shops(db: Session, district_id: int | None = None) -> int:
    stmt = select(func.count(models.Shop.id))
    if district_id:
        stmt = stmt.where(models.Shop.district_id == district_id)
    return db.execute(stmt).scalar_one()

def list_shops_paginated(db: Session, page: int = 1, size: int = 10, district_id: int | None = None):
    offset = (page - 1) * size
    stmt = select(models.Shop).order_by(models.Shop.created_at.desc())
    if district_id:
        stmt = stmt.where(models.Shop.district_id == district_id)
    return db.execute(stmt.offset(offset).limit(size)).scalars().all()

def stock_balance_for_product(db: Session, product_id: int) -> float:
    """
    Joriy qoldiq = SUM(kirim) - SUM(chiqim)
    """
    kirim = db.execute(
        select(func.coalesce(func.sum(models.StockMove.qty_kg), 0.0))
        .where(models.StockMove.product_id == product_id, models.StockMove.kind == models.MoveKind.kirim)
    ).scalar_one()
    chiqim = db.execute(
        select(func.coalesce(func.sum(models.StockMove.qty_kg), 0.0))
        .where(models.StockMove.product_id == product_id, models.StockMove.kind == models.MoveKind.chiqim)
    ).scalar_one()
    return float(kirim) - float(chiqim)

def stock_balances_all(db: Session) -> list[tuple[models.Product, float]]:
    """
    Barcha aktiv mahsulotlar bo'yicha qoldiq ro'yxati.
    """
    products = list_products(db, only_active=True)
    return [(p, stock_balance_for_product(db, p.id)) for p in products]

def add_kirim(db: Session, product_id: int, qty_kg: float, note: str | None = None) -> models.StockMove:
    assert qty_kg > 0
    m = models.StockMove(product_id=product_id, kind=models.MoveKind.kirim, qty_kg=qty_kg, note=note)
    db.add(m); db.commit(); db.refresh(m); return m

def add_chiqim(db: Session, product_id: int, qty_kg: float, shop_id: int, note: str | None = None) -> models.StockMove:
    assert qty_kg > 0
    m = models.StockMove(product_id=product_id, kind=models.MoveKind.chiqim, qty_kg=qty_kg, shop_id=shop_id, note=note)
    db.add(m); db.commit(); db.refresh(m); return m

def deliveries_agg_by_shop(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    district_id: int | None = None,
    shop_id: int | None = None,
):
    d = models.Delivery
    s = models.Shop
    stmt = (
        select(
            s.id.label("shop_id"),
            s.name.label("shop_name"),
            func.count(d.id).label("cnt"),
            func.coalesce(func.sum(d.qty_kg), 0.0).label("sum_qty"),
            func.coalesce(func.sum(d.total), 0.0).label("sum_total"),
        )
        .join(s, s.id == d.shop_id)
        .group_by(s.id, s.name)
        .order_by(func.sum(d.total).desc())
    )
    if start:
        stmt = stmt.where(d.created_at >= start)
    if end:
        stmt = stmt.where(d.created_at < end)
    if district_id:
        stmt = stmt.where(d.district_id == district_id)
    if shop_id:
        stmt = stmt.where(d.shop_id == shop_id)
    return db.execute(stmt).all()

def deliveries_agg_paykind(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    district_id: int | None = None,
    shop_id: int | None = None,
):
    d = models.Delivery
    stmt = (
        select(
            d.pay_kind,
            func.count(d.id).label("cnt"),
            func.coalesce(func.sum(d.qty_kg), 0.0).label("sum_qty"),
            func.coalesce(func.sum(d.total), 0.0).label("sum_total"),
        )
        .group_by(d.pay_kind)
        .order_by(func.sum(d.total).desc())
    )
    if start:
        stmt = stmt.where(d.created_at >= start)
    if end:
        stmt = stmt.where(d.created_at < end)
    if district_id:
        stmt = stmt.where(d.district_id == district_id)
    if shop_id:
        stmt = stmt.where(d.shop_id == shop_id)
    return db.execute(stmt).all()

def deliveries_list_with_details(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    district_id: int | None = None,
    shop_id: int | None = None,
    limit: int = 200,
):
    d = models.Delivery
    s = models.Shop
    p = models.Product
    stmt = (
        select(
            d.id, d.created_at, d.qty_kg, d.unit_price, d.total, d.pay_kind,
            s.name.label("shop_name"),
            p.name.label("product_name"),
        )
        .join(s, s.id == d.shop_id)
        .join(p, p.id == d.product_id)
        .order_by(d.created_at.desc())
        .limit(limit)
    )
    if start:
        stmt = stmt.where(d.created_at >= start)
    if end:
        stmt = stmt.where(d.created_at < end)
    if district_id:
        stmt = stmt.where(d.district_id == district_id)
    if shop_id:
        stmt = stmt.where(d.shop_id == shop_id)
    return db.execute(stmt).all()

def deliveries_agg_by_product_in_shop(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    shop_id: int | None = None,
):
    """Bir do'kon ichida mahsulotlar kesimi (qaysi mahsulotdan qancha yetkazilgan)."""
    if not shop_id:
        return []
    d = models.Delivery
    p = models.Product
    stmt = (
        select(
            p.name.label("product_name"),
            func.coalesce(func.sum(d.qty_kg), 0.0).label("sum_qty"),
            func.coalesce(func.sum(d.total), 0.0).label("sum_total"),
        )
        .join(p, p.id == d.product_id)
        .where(d.shop_id == shop_id)
        .group_by(p.name)
        .order_by(func.sum(d.total).desc())
    )
    if start:
        stmt = stmt.where(d.created_at >= start)
    if end:
        stmt = stmt.where(d.created_at < end)
    return db.execute(stmt).all()

def delete_product(db: Session, product_id: int) -> bool:
    """Hard delete product by id.
    Returns True if deleted. Raises IntegrityError if constrained.
    """
    obj = db.get(models.Product, product_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# === Balans / Tranzaksiyalar ===
def add_shop_tx(db: Session, shop_id: int, kind: models.TxKind, amount: float, note: str | None = None):
    tx = models.ShopTransaction(shop_id=shop_id, kind=kind, amount=abs(float(amount)), note=(note or None))
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx

def shop_balance(db: Session, shop_id: int) -> float:
    from sqlalchemy import case
    st = models.ShopTransaction
    total = db.execute(
        select(
            func.coalesce(func.sum(
                case((st.kind == models.TxKind.sale, st.amount), else_=-st.amount)
            ), 0.0)
        ).where(st.shop_id == shop_id)
    ).scalar_one()
    return float(total)

def list_balances(db: Session, district_id: int | None = None):
    from sqlalchemy import case
    s = models.Shop
    st = models.ShopTransaction
    stmt = (
        select(
            s.id, s.name, s.district_id,
            func.coalesce(func.sum(
                case((st.kind == models.TxKind.sale, st.amount), else_=-st.amount)
            ), 0.0).label("balance")
        )
        .join(st, st.shop_id == s.id, isouter=True)
        .group_by(s.id)
        .order_by(s.name)
    )
    if district_id:
        stmt = stmt.where(s.district_id == district_id)
    return db.execute(stmt).all()

def list_shop_txs(db: Session, shop_id: int, limit: int = 200):
    st = models.ShopTransaction
    return db.execute(
        select(st).where(st.shop_id == shop_id).order_by(st.created_at.desc()).limit(limit)
    ).scalars().all()


def add_shop_tx(db: Session, shop_id: int, kind: models.TxKind, amount: float, note: str | None = None):
    tx = models.ShopTransaction(shop_id=shop_id, kind=kind, amount=abs(float(amount)), note=(note or None))
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def shop_balance(db: Session, shop_id: int) -> float:
    from sqlalchemy import case
    st = models.ShopTransaction
    total = db.execute(
        select(
            func.coalesce(func.sum(
                case(
                    (st.kind == models.TxKind.payment, st.amount),   # + to'lov
                    (st.kind == models.TxKind.sale, -st.amount),     # - qarz
                    else_=0.0
                )
            ), 0.0)
        ).where(st.shop_id == shop_id)
    ).scalar_one()
    return float(total)


def list_balances(db: Session, district_id: int | None = None):
    from sqlalchemy import case
    s = models.Shop
    st = models.ShopTransaction
    stmt = (
        select(
            s.id,
            s.name,
            s.district_id,
            func.coalesce(func.sum(
                case(
                    (st.kind == models.TxKind.payment, st.amount),   # +
                    (st.kind == models.TxKind.sale, -st.amount),     # -
                    else_=0.0
                )
            ), 0.0).label("balance"),
        )
        .join(st, st.shop_id == s.id, isouter=True)
        .group_by(s.id)
        .order_by(s.name)
    )
    if district_id:
        stmt = stmt.where(s.district_id == district_id)
    return db.execute(stmt).all()