import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./monitor.db")

# как часто обходить отслеживаемые товары (в минутах)
COLLECT_INTERVAL_MINUTES: int = int(os.getenv("COLLECT_INTERVAL_MINUTES", "15"))

# уведомлять об изменении цены, только если она сдвинулась хотя бы на столько процентов
PRICE_ALERT_MIN_PERCENT: float = float(os.getenv("PRICE_ALERT_MIN_PERCENT", "1"))

# сколько ждать ответа WB по одному товару
WB_BROWSER_TIMEOUT_SEC: int = int(os.getenv("WB_BROWSER_TIMEOUT_SEC", "40"))

# показать окно браузера (для отладки); по умолчанию окно уходит за край экрана
WB_SHOW_BROWSER: bool = os.getenv("WB_SHOW_BROWSER", "false").lower() == "true"
