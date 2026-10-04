"""Полный обход на базе в памяти: WB и Telegram подменены, всё остальное — настоящее."""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler
from app.models import Base, Product, Snapshot, User


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))


def fake_parser(answers):
    class Parser:
        async def fetch_products(self, articles):
            return {a: answers.get(a) for a in articles}
    return Parser


def card(price, stock):
    return {"name": "x", "price": price, "old_price": None, "stock": stock,
            "rating": 4.8, "feedbacks": 10, "position": None, "url": "u"}


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(scheduler, "get_session", Session)
    s = Session()
    s.add_all([User(telegram_id=111, is_subscribed=True), User(telegram_id=222, is_subscribed=False)])
    s.add_all([Product(marketplace="wb", external_id="1", name="Шины", url="u1"),
               Product(marketplace="wb", external_id="2", name="Пила", url="u2")])
    s.commit()
    s.add_all([Snapshot(product_id=1, price=6000, stock=10), Snapshot(product_id=2, price=2776, stock=4)])
    s.commit()
    return Session


def run(monkeypatch, answers):
    monkeypatch.setattr(scheduler, "WBParser", fake_parser(answers))
    bot = FakeBot()
    asyncio.run(scheduler.collect_once(bot))
    return bot


def test_price_drop_and_out_of_stock_are_reported(db, monkeypatch):
    bot = run(monkeypatch, {"1": card(5444, 10), "2": card(None, 0)})
    texts = [t for _, t in bot.sent]
    assert len(texts) == 2
    assert {chat for chat, _ in bot.sent} == {111}          # отписанным не пишем
    assert any("Цена изменилась" in t and "Шины" in t for t in texts)
    assert any("закончился" in t and "Пила" in t for t in texts)
    assert db().query(Snapshot).count() == 4                 # срез сохранён по обоим


def test_nothing_changed_means_silence(db, monkeypatch):
    bot = run(monkeypatch, {"1": card(6000, 10), "2": card(2776, 4)})
    assert bot.sent == []


def test_wb_failure_skips_product_without_crash(db, monkeypatch):
    bot = run(monkeypatch, {"1": None, "2": card(2776, 4)})
    assert bot.sent == []
    assert db().query(Snapshot).count() == 3                 # по упавшему товару среза нет
