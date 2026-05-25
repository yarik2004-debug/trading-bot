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
    "max_distance_pct": 10.0,
    "orderbook_depth": 200,
    "min_big_volume": {
        "BTC/USDT":  80_000,
        "ETH/USDT":  20_000,
        "SOL/USDT":  80_000,
        "BNB/USDT":  20_000,
        "XRP/USDT":   5_000,
    },
    "imbalance_ratio": 1.6,
    "min_exchanges_confirm": 1,
    "analyze_interval": 30,
    "signal_cooldown_minutes": 30,
}

# --- Уровни уведомлений ---
SIGNAL_LEVELS = {
    "strong":  "🔥 СИЛЬНЫЙ",   # подтверждено 2+ биржами
    "medium":  "⚡ СРЕДНИЙ",   # подтверждено 1 биржами
    "weak":    "💡 СЛАБЫЙ",    # подтверждено 1 биржей
}
