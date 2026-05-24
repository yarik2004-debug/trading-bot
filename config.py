# ============================================
#   КОНФИГУРАЦИЯ ТРЕЙДИНГ-БОТА
# ============================================

# --- Telegram ---
TELEGRAM_TOKEN = "8689855787:AAEki5wsLj4RCcz_PTp9eY-z4327zagc7o4"       # от @BotFather
TELEGRAM_CHAT_ID = "567270778"  # ваш личный chat_id

# --- Монеты для мониторинга ---
SYMBOLS = {
    "BTC/USDT": {
        "binance": "btcusdt",
        "bybit":   "BTCUSDT",
        "okx":     "BTC-USDT",
    },
    "ETH/USDT": {
        "binance": "ethusdt",
        "bybit":   "ETHUSDT",
        "okx":     "ETH-USDT",
    },
    "SOL/USDT": {
        "binance": "solusdt",
        "bybit":   "SOLUSDT",
        "okx":     "SOL-USDT",
    },
    "BNB/USDT": {
        "binance": "bnbusdt",
        "bybit":   "BNBUSDT",
        "okx":     "BNB-USDT",
    },
    "XRP/USDT": {
        "binance": "xrpusdt",
        "bybit":   "XRPUSDT",
        "okx":     "XRP-USDT",
    },
}

# --- Биржи и их WebSocket адреса ---
EXCHANGES = {
    "binance": {
        "ws_url": "wss://stream.binance.com:9443/ws",
        "enabled": True,
    },
    "bybit": {
        "ws_url": "wss://stream.bybit.com/v5/public/spot",
        "enabled": True,
    },
    "okx": {
        "ws_url": "wss://ws.okx.com:8443/ws/v5/public",
        "enabled": True,
    },
}

# --- Параметры анализа ---
ANALYSIS = {
    # Минимальный объём чтобы считать уровень "крупным" (в USDT)
    "min_big_volume": {
        "BTC/USDT": 500_000,   # 500к USDT
        "ETH/USDT": 200_000,   # 200к USDT
        "SOL/USDT":  50_000,   # 50к USDT
        "BNB/USDT":  50_000,   # 50к USDT
        "XRP/USDT":  30_000,   # 30к USDT
    },

    # Сколько уровней стакана анализируем (глубина)
    "orderbook_depth": 50,

    # Коэффициент дисбаланса для сигнала
    # (если объём покупок / объём продаж > этого числа — сигнал вниз, и наоборот)
    "imbalance_ratio": 1.8,

    # Минимум бирж которые должны подтвердить сигнал
    "min_exchanges_confirm": 2,

    # Как часто анализировать (в секундах)
    "analyze_interval": 30,

    # Не слать одинаковый сигнал по одной монете чаще чем (в минутах)
    "signal_cooldown_minutes": 10,
}

# --- Уровни уведомлений ---
SIGNAL_LEVELS = {
    "strong":  "🔥 СИЛЬНЫЙ",   # подтверждено 3+ биржами
    "medium":  "⚡ СРЕДНИЙ",   # подтверждено 2 биржами
    "weak":    "💡 СЛАБЫЙ",    # подтверждено 1 биржей
}
