from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)  # id в Telegram бывают больше 2^31
    is_subscribed = Column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    marketplace = Column(String, nullable=False)  # 'wb'
    external_id = Column(String, nullable=False)  # артикул WB
    name = Column(String, nullable=True)
    url = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    snapshots = relationship("Snapshot", back_populates="product")


class Snapshot(Base):
    """Срез по товару на момент обхода: из них строится история и алерты."""

    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    price = Column(Float, nullable=True)        # None — нет в наличии
    old_price = Column(Float, nullable=True)    # цена до скидки, если есть скидка
    stock = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    feedbacks = Column(Integer, nullable=True)
    position = Column(Integer, nullable=True)   # место в выдаче — задел на будущее

    product = relationship("Product", back_populates="snapshots")
