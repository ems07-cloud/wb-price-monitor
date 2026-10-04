import pytest

from app.alerts import money, price_alert_text, price_changed_enough, stock_event


@pytest.mark.parametrize(
    "old, new, expected",
    [
        (1000, 1000, False),     # не изменилась
        (1000, 1005, False),     # 0.5% — меньше порога
        (1000, 1010, True),      # ровно порог
        (1000, 800, True),       # скидка
        (None, 1000, False),     # товар появился — это событие наличия
        (1000, None, False),     # товар закончился — тоже наличие
    ],
    ids=["same", "tiny", "threshold", "drop", "appeared", "gone"],
)
def test_price_changed_enough(old, new, expected):
    assert price_changed_enough(old, new, min_percent=1) is expected


@pytest.mark.parametrize(
    "old, new, event",
    [(5, 0, "ended"), (0, 3, "back"), (5, 3, None), (0, 0, None), (None, 3, None)],
    ids=["ended", "back", "less", "still-none", "first"],
)
def test_stock_event(old, new, event):
    assert stock_event(old, new) == event


def test_money_format():
    assert money(5444.0) == "5 444 ₽"
    assert money(1299.5) == "1 299.50 ₽"
    assert money(None) == "—"


def test_price_drop_text():
    text = price_alert_text(3, "Шины R16", "https://wb/3", 6000, 5444)
    assert text.startswith("📉")
    assert "Было: 6 000 ₽" in text
    assert "Стало: 5 444 ₽" in text
    assert "−556 ₽, 9.3%" in text
