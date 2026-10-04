import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .alerts import money, snapshot_text
from .config import COLLECT_INTERVAL_MINUTES, TELEGRAM_TOKEN
from .db import get_session, init_db
from .models import Product, Snapshot, User
from .parsers import WBParser
from .parsers.wb import extract_article
from .scheduler import make_snapshot, setup_scheduler

HELP = (
    "Бот следит за товарами Wildberries и пишет, когда меняется цена "
    "или товар заканчивается и снова появляется.\n\n"
    "/add_wb <артикул или ссылка> — начать следить за товаром\n"
    "/list — что отслеживается\n"
    "/last <id> — последние данные по товару\n"
    "/remove <id> — перестать следить\n"
    "/subscribe и /unsubscribe — включить или выключить уведомления\n\n"
    f"Товары обходятся раз в {COLLECT_INTERVAL_MINUTES} мин."
)


def ensure_user(db, telegram_id: int) -> User:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id, is_subscribed=True)
        db.add(user)
        db.commit()
    return user


async def cmd_start(message: Message):
    db = get_session()
    try:
        ensure_user(db, message.from_user.id)
        await message.answer("Привет! " + HELP)
    finally:
        db.close()


async def cmd_subscribe(message: Message):
    db = get_session()
    try:
        ensure_user(db, message.from_user.id).is_subscribed = True
        db.commit()
        await message.answer("Уведомления включены ✅")
    finally:
        db.close()


async def cmd_unsubscribe(message: Message):
    db = get_session()
    try:
        ensure_user(db, message.from_user.id).is_subscribed = False
        db.commit()
        await message.answer("Уведомления выключены ❌")
    finally:
        db.close()


async def cmd_add_wb(message: Message, command: CommandObject):
    article = extract_article(command.args or "")
    if not article:
        await message.answer("Пришлите артикул или ссылку: /add_wb 381583713")
        return

    db = get_session()
    try:
        existing = db.query(Product).filter(Product.external_id == article,
                                            Product.is_active.is_(True)).first()
        if existing:
            await message.answer(f"Этот товар уже отслеживается: #{existing.id}")
            return

        wait = await message.answer("Смотрю товар на Wildberries…")
        data = await WBParser().fetch_product(article)
        if not data:
            await wait.edit_text("Не получилось открыть товар. Проверьте артикул или попробуйте позже.")
            return

        product = Product(marketplace="wb", external_id=article, name=data["name"],
                          url=data["url"], is_active=True)
        db.add(product)
        db.commit()
        db.add(make_snapshot(product.id, data))
        db.commit()

        if data["price"] is None:
            now = "Сейчас нет в наличии — сообщу, когда появится."
        else:
            now = f"Цена: {money(data['price'])}\nОстаток: {data['stock']} шт.\n\n" \
                  "Напишу, когда изменится цена или наличие."
        await wait.edit_text(
            f"Добавлен товар #{product.id}\n{product.name}\n\n{now}",
            disable_web_page_preview=True,
        )
    finally:
        db.close()


async def cmd_list(message: Message):
    db = get_session()
    try:
        products = db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.id).all()
        if not products:
            await message.answer("Пока ничего не отслеживается. Добавьте товар: /add_wb <артикул>")
            return
        lines = ["Отслеживаю:"]
        for p in products:
            last = (db.query(Snapshot).filter(Snapshot.product_id == p.id)
                    .order_by(Snapshot.created_at.desc()).first())
            price = "—" if not last else ("нет в наличии" if last.price is None else money(last.price))
            lines.append(f"#{p.id} · {p.name[:45]} · {price}")
        await message.answer("\n".join(lines))
    finally:
        db.close()


def _product_id(command: CommandObject) -> Optional[int]:
    try:
        return int((command.args or "").strip().lstrip("#"))
    except ValueError:
        return None


async def cmd_last(message: Message, command: CommandObject):
    product_id = _product_id(command)
    if product_id is None:
        await message.answer("Использование: /last <id товара из /list>")
        return
    db = get_session()
    try:
        product = db.get(Product, product_id)
        if not product:
            await message.answer("Товар с таким id не найден.")
            return
        snap = (db.query(Snapshot).filter(Snapshot.product_id == product.id)
                .order_by(Snapshot.created_at.desc()).first())
        if not snap:
            await message.answer("По этому товару ещё нет данных.")
            return
        await message.answer(snapshot_text(product.id, product.name, product.url, snap),
                             disable_web_page_preview=True)
    finally:
        db.close()


async def cmd_remove(message: Message, command: CommandObject):
    product_id = _product_id(command)
    db = get_session()
    try:
        product = db.get(Product, product_id) if product_id is not None else None
        if not product or not product.is_active:
            await message.answer("Использование: /remove <id товара из /list>")
            return
        product.is_active = False
        db.commit()
        await message.answer(f"Больше не слежу за #{product.id} · {product.name}")
    finally:
        db.close()


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not TELEGRAM_TOKEN:
        raise SystemExit("Не задан TELEGRAM_TOKEN — скопируйте .env.example в .env и впишите токен")
    init_db()

    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, Command("start", "help"))
    dp.message.register(cmd_subscribe, Command("subscribe"))
    dp.message.register(cmd_unsubscribe, Command("unsubscribe"))
    dp.message.register(cmd_add_wb, Command("add_wb"))
    dp.message.register(cmd_list, Command("list"))
    dp.message.register(cmd_last, Command("last"))
    dp.message.register(cmd_remove, Command("remove"))

    setup_scheduler(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
