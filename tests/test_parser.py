import json
from pathlib import Path

import pytest

from app.parsers.wb import extract_article, parse_card

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_in_stock_card():
    data = parse_card(load("card_v4.json"), "381583713")
    assert data["name"] == "Шины зимние R16 215 65 98 T W02"
    assert data["price"] == 5444.0          # копейки переведены в рубли
    assert data["old_price"] == 7541.0      # цена до скидки
    assert data["stock"] == 45              # общий остаток по всем складам
    assert data["rating"] == 4.9
    assert data["feedbacks"] == 806
    assert data["url"].endswith("/catalog/381583713/detail.aspx")


def test_out_of_stock_card_has_no_price():
    data = parse_card(load("card_v4_out_of_stock.json"), "150983009")
    assert data["price"] is None
    assert data["old_price"] is None
    assert data["stock"] == 0


def test_other_article_is_not_taken():
    assert parse_card(load("card_v4.json"), "1") is None


def test_stock_falls_back_to_warehouses_sum():
    raw = load("card_v4.json")
    del raw["products"][0]["totalQuantity"]
    assert parse_card(raw, "381583713")["stock"] == 19


@pytest.mark.parametrize(
    "text, article",
    [
        ("381583713", "381583713"),
        ("  381583713 ", "381583713"),
        ("https://www.wildberries.ru/catalog/381583713/detail.aspx?targetUrl=MI", "381583713"),
        ("https://www.wildberries.ru/catalog/381583713/feedbacks", "381583713"),
        ("шины", None),
        ("", None),
    ],
    ids=["digits", "spaces", "link", "feedbacks-link", "text", "empty"],
)
def test_extract_article(text, article):
    assert extract_article(text) == article
