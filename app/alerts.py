"""Тексты уведомлений и решение, о чём вообще стоит сообщать.

Чистые функции без базы и сети — их удобно проверять тестами.
"""
from __future__ import annotations

from typing import Optional


def money(value: Optional[float]) -> str:
    if value is None:
        return "—"
    text = f"{value:,.2f}".replace(",", " ").replace(".00", "")
    return f"{text} ₽"


def price_changed_enough(old: Optional[float], new: Optional[float], min_percent: float) -> bool:
    """Цена изменилась заметно. Пропажа цены — это про наличие, а не про цену."""
    if not old or not new or old == new:
        return False
    return abs(new - old) / old * 100 >= min_percent


def stock_event(old_stock: Optional[int], new_stock: Optional[int]) -> Optional[str]:
    """«ended» — товар закончился, «back» — снова появился, иначе None."""
    if old_stock is None or new_stock is None:
        return None
    if old_stock > 0 and new_stock == 0:
        return "ended"
    if old_stock == 0 and new_stock > 0:
        return "back"
    return None


def price_alert_text(product_id: int, name: str, url: str, old: float, new: float) -> str:
    diff = new - old
    arrow = "📈" if diff > 0 else "📉"
    percent = abs(diff) / old * 100
    return (
        f"{arrow} Цена изменилась — товар #{product_id}\n"
        f"{name}\n\n"
        f"Было: {money(old)}\n"
        f"Стало: {money(new)}  ({'+' if diff > 0 else '−'}{money(abs(diff))}, {percent:.1f}%)\n\n"
        f"{url}"
    )


def stock_alert_text(product_id: int, name: str, url: str, event: str, stock: int, price: Optional[float]) -> str:
    if event == "ended":
        head = "⛔ Товар закончился"
        body = "Остаток на складах WB: 0 шт."
    else:
        head = "✅ Товар снова в наличии"
        body = f"Остаток: {stock} шт., цена {money(price)}"
    return f"{head} — #{product_id}\n{name}\n\n{body}\n\n{url}"


def snapshot_text(product_id: int, name: str, url: str, snap) -> str:
    lines = [f"Товар #{product_id}", name, ""]
    if snap.price is None:
        lines.append("Нет в наличии")
    else:
        lines.append(f"Цена: {money(snap.price)}"
                     + (f" (без скидки {money(snap.old_price)})" if snap.old_price else ""))
        lines.append(f"Остаток: {snap.stock} шт.")
    if snap.rating is not None:
        lines.append(f"Рейтинг: {snap.rating} ⭐ ({snap.feedbacks or 0} отзывов)")
    lines += ["", f"Обновлено: {snap.created_at:%d.%m.%Y %H:%M}", url]
    return "\n".join(lines)
