import logging
from typing import Optional

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from .alerts import price_alert_text, price_changed_enough, stock_alert_text, stock_event
from .config import COLLECT_INTERVAL_MINUTES, PRICE_ALERT_MIN_PERCENT
from .db import get_session
from .models import Product, Snapshot, User
from .parsers import WBParser

log = logging.getLogger(__name__)


def make_snapshot(product_id: int, data: dict) -> Snapshot:
    return Snapshot(
        product_id=product_id,
        price=data["price"],
        old_price=data.get("old_price"),
        stock=data["stock"],
        rating=data["rating"],
        feedbacks=data.get("feedbacks"),
        position=data.get("position"),
    )


async def collect_once(bot: Bot) -> None:
    """Один обход всех активных товаров: срез в базу + алерты подписчикам."""
    db: Session = get_session()
    try:
        products = db.query(Product).filter(Product.is_active.is_(True), Product.marketplace == "wb").all()
        if not products:
            return
        fresh = await WBParser().fetch_products(p.external_id for p in products)

        messages = []
        for product in products:
            data = fresh.get(product.external_id)
            if not data:
                continue
            last: Optional[Snapshot] = (
                db.query(Snapshot)
                .filter(Snapshot.product_id == product.id)
                .order_by(Snapshot.created_at.desc())
                .first()
            )
            db.add(make_snapshot(product.id, data))
            if last is None:
                continue

            if price_changed_enough(last.price, data["price"], PRICE_ALERT_MIN_PERCENT):
                messages.append(price_alert_text(product.id, product.name, product.url, last.price, data["price"]))
            event = stock_event(last.stock, data["stock"])
            if event:
                messages.append(stock_alert_text(product.id, product.name, product.url,
                                                 event, data["stock"], data["price"]))
        db.commit()
        log.info("обход: товаров %s, получено %s, уведомлений %s",
                 len(products), sum(1 for v in fresh.values() if v), len(messages))

        if messages:
            users = db.query(User).filter(User.is_subscribed.is_(True)).all()
            for text in messages:
                for user in users:
                    try:
                        await bot.send_message(user.telegram_id, text, disable_web_page_preview=True)
                    except Exception as exc:  # заблокировал бота и т. п. — остальным всё равно шлём
                        log.warning("не доставлено %s: %s", user.telegram_id, exc)
    finally:
        db.close()


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        collect_once,
        "interval",
        minutes=COLLECT_INTERVAL_MINUTES,
        args=[bot],
        id="collect_job",
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler
