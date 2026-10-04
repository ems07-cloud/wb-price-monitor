"""Данные товара Wildberries по артикулу.

Цены и остатки WB отдаёт только после проверки «вы не бот», которую проходит
настоящий браузер. Поэтому парсер открывает карточку товара в Chromium и
перехватывает ответ API, который запрашивает сама страница
(`/__internal/u-card/cards/v4/detail`). Разбор ответа вынесен в отдельную
функцию `parse_card`, она не зависит от браузера и покрыта тестами.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, Optional

from ..config import WB_BROWSER_TIMEOUT_SEC, WB_SHOW_BROWSER

log = logging.getLogger(__name__)

PRODUCT_URL = "https://www.wildberries.ru/catalog/{article}/detail.aspx"
CARD_API_MARK = "/cards/v4/detail"


def extract_article(text: str) -> Optional[str]:
    """Артикул из числа или ссылки вида .../catalog/12345678/detail.aspx."""
    text = (text or "").strip()
    m = re.search(r"/catalog/(\d+)/", text)
    if m:
        return m.group(1)
    return text if text.isdigit() else None


def parse_card(data: dict, article: str) -> Optional[Dict]:
    """Достаём из ответа WB то, что нужно мониторингу.

    Цены в ответе в копейках: `product` — цена для покупателя,
    `basic` — цена до скидки. У товара без наличия цены нет вовсе.
    """
    products = data.get("products") or (data.get("data") or {}).get("products") or []
    product = next((p for p in products if str(p.get("id")) == str(article)), None)
    if product is None:
        return None

    sizes = product.get("sizes") or []
    prices = [s["price"] for s in sizes if isinstance(s.get("price"), dict) and s["price"].get("product")]
    price = min(p["product"] for p in prices) / 100 if prices else None
    basic = min(p.get("basic") or p["product"] for p in prices) / 100 if prices else None

    stock = product.get("totalQuantity")
    if stock is None:
        stock = sum(st.get("qty", 0) for s in sizes for st in (s.get("stocks") or []))

    return {
        "name": product.get("name") or f"WB {article}",
        "brand": product.get("brand"),
        "price": price,
        "old_price": basic if basic and price and basic > price else None,
        "stock": int(stock),
        "rating": product.get("reviewRating"),
        "feedbacks": product.get("feedbacks"),
        "position": None,
        "url": PRODUCT_URL.format(article=article),
    }


class WBParser:
    """Один запуск браузера на пачку артикулов — так быстрее и бережнее к памяти."""

    async def fetch_products(self, articles: Iterable[str]) -> Dict[str, Optional[Dict]]:
        from playwright.async_api import async_playwright

        articles = [a for a in dict.fromkeys(articles) if a]
        result: Dict[str, Optional[Dict]] = {}
        if not articles:
            return result

        # Без окна WB не пропускает. На десктопе окно уводим за край экрана,
        # на сервере запускаем под виртуальным дисплеем (xvfb-run).
        args = ["--disable-blink-features=AutomationControlled"]
        if not WB_SHOW_BROWSER:
            args.append("--window-position=-2400,0")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, args=args)
            try:
                page = await (await browser.new_context(locale="ru-RU")).new_page()
                for article in articles:
                    result[article] = await self._fetch_one(page, article)
            finally:
                await browser.close()
        return result

    async def _fetch_one(self, page, article: str) -> Optional[Dict]:
        def is_card(resp) -> bool:
            return CARD_API_MARK in resp.url and f"nm={article}" in resp.url

        try:
            async with page.expect_response(is_card, timeout=WB_BROWSER_TIMEOUT_SEC * 1000) as info:
                await page.goto(PRODUCT_URL.format(article=article), wait_until="domcontentloaded")
            resp = await info.value
            if not resp.ok:
                log.warning("WB %s: API ответил %s", article, resp.status)
                return None
            data = parse_card(await resp.json(), article)
            if data is None:
                log.warning("WB %s: товара нет в ответе — артикул неверный или снят с продажи", article)
            return data
        except Exception as exc:  # сеть, таймаут, изменилась вёрстка — товар пропускаем, не падаем
            log.warning("WB %s: не удалось получить данные: %s", article, str(exc).splitlines()[0])
            return None

    async def fetch_product(self, article: str) -> Optional[Dict]:
        return (await self.fetch_products([article])).get(article)
