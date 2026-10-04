"""Проверка без Telegram: python -m app.check 381583713 1339337086

Открывает товары в браузере и печатает то, что увидит бот.
"""
import asyncio
import sys

from .alerts import money
from .parsers import WBParser
from .parsers.wb import extract_article


async def main(args: list[str]) -> int:
    articles = [a for a in (extract_article(x) for x in args) if a]
    if not articles:
        print("Укажите артикулы или ссылки: python -m app.check 381583713")
        return 1
    results = await WBParser().fetch_products(articles)
    for article in articles:
        data = results.get(article)
        if not data:
            print(f"{article}: не удалось получить данные")
            continue
        if data["price"] is None:
            price = "нет в наличии"
        else:
            old = f" (без скидки {money(data['old_price'])})" if data["old_price"] else ""
            price = f"цена {money(data['price'])}{old} · остаток {data['stock']} шт."
        print(f"{article}: {data['name']}")
        print(f"    {price} · рейтинг {data['rating']} · отзывов {data['feedbacks']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
