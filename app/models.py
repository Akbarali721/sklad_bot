from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, func, Enum as SAEnum
from sqlalchemy.orm import relationship
from .database import Base
import enum

class Role(str, enum.Enum):
    admin = "admin"
    dealer = "dealer"

class MoveKind(str, enum.Enum):
    kirim = "kirim"   # omborga kirim (admin kiritadi)
    chiqim = "chiqim" # ombordan chiqim (diler yetkazadi)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(String(32), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=True)
    role = Column(SAEnum(Role), nullable=False, default=Role.dealer)
    created_at = Column(DateTime, server_default=func.now())



class District(Base):
    __tablename__ = "districts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    shops = relationship("Shop", back_populates="district", cascade="all, delete-orphan")

class Shop(Base):
    __tablename__ = "shops"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    district = relationship("District", back_populates="shops")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    kind = Column(String(120), nullable=True)
    brand = Column(String(120), nullable=True)
    price_per_kg = Column(Float, nullable=True)  # NULL bo‘lishi mumkin
    in_price_per_pack = Column(Float, nullable=True)
    out_price_per_pack = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class Delivery(Base):
    __tablename__ = "deliveries"
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty_kg = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)  # so'm/kg
    total = Column(Float, nullable=False)
    pay_kind = Column(String(50), nullable=False, default="naqd")
    created_at = Column(DateTime, server_default=func.now())


class StockMove(Base):
    """
    Ombor harakati: har bir yozuv kirim/chiqim.
    Joriy qoldiq = SUM(kirim) - SUM(chiqim).
    chiqim bo'lsa, shop_id to'ldiriladi (qaysi do'konga ketgani).
    """
    __tablename__ = "stock_moves"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    kind = Column(SAEnum(MoveKind), nullable=False)
    qty_kg = Column(Float, nullable=False)
    shop_id = Column(Integer, ForeignKey("shops.id"), nullable=True, index=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("Product")
    shop = relationship("Shop")

# === Balans tranzaksiyalari (do'kon uchun) ===
class TxKind(str, enum.Enum):
    sale = "sale"       # qarzga berilgan tovar summasi (bizga qarzi OShadi)
    payment = "payment" # do'kon to'lovi (qarz KAMAYADI)

class ShopTransaction(Base):
    __tablename__ = "shop_transactions"
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(SAEnum(TxKind), nullable=False)
    amount = Column(Float, nullable=False)  # so'mda
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    shop = relationship("Shop")
