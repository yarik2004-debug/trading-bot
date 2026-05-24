# ============================================
#   СБОРЩИК ДАННЫХ ORDER BOOK
# ============================================

import asyncio
import json
import logging
from datetime import datetime
import websockets
from config import SYMBOLS, EXCHANGES, ANALYSIS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Главное хранилище стаканов
# Структура: orderbooks["BTC/USDT"]["binance"] = {"bids": [...], "asks": [...]}
orderbooks = {}

for symbol in SYMBOLS:
    orderbooks[symbol] = {}
    for exchange in EXCHANGES:
        orderbooks[symbol][exchange] = {"bids": {}, "asks": {}, "updated": None}


# ============================================
#   BINANCE
# ============================================
async def connect_binance():
    depth = ANALYSIS["orderbook_depth"]

    # Формируем подписку на все монеты сразу
    streams = [f"{s['binance']}@depth{depth}@100ms" for s in SYMBOLS.values()]
    url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"

    while True:
        try:
            log.info("Binance: подключаемся...")
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info("Binance: подключено ✓")
                async for raw in ws:
                    data = json.loads(raw)
                    stream = data.get("stream", "")
                    payload = data.get("data", {})

                    # Находим символ по имени потока
                    symbol = next(
                        (sym for sym, cfg in SYMBOLS.items()
                         if cfg["binance"] in stream),
                        None
                    )
                    if not symbol:
                        continue

                    ob = orderbooks[symbol]["binance"]

                    # Обновляем bids (покупки)
                    for price, qty in payload.get("b", []):
                        price, qty = float(price), float(qty)
                        if qty == 0:
                            ob["bids"].pop(price, None)
                        else:
                            ob["bids"][price] = qty

                    # Обновляем asks (продажи)
                    for price, qty in payload.get("a", []):
                        price, qty = float(price), float(qty)
                        if qty == 0:
                            ob["asks"].pop(price, None)
                        else:
                            ob["asks"][price] = qty

                    ob["updated"] = datetime.now()

        except Exception as e:
            log.error(f"Binance ошибка: {e}. Переподключаемся через 5с...")
            await asyncio.sleep(5)


# ============================================
#   BYBIT
# ============================================
async def connect_bybit():
    url = EXCHANGES["bybit"]["ws_url"]
    depth = ANALYSIS["orderbook_depth"]

    while True:
        try:
            log.info("Bybit: подключаемся...")
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info("Bybit: подключено ✓")

                # Подписываемся на все монеты
                topics = [f"orderbook.{depth}.{cfg['bybit']}" for cfg in SYMBOLS.values()]
                await ws.send(json.dumps({
                    "op": "subscribe",
                    "args": topics
                }))

                async for raw in ws:
                    data = json.loads(raw)

                    # Пропускаем служебные сообщения
                    if data.get("op") == "subscribe":
                        continue

                    topic = data.get("topic", "")
                    payload = data.get("data", {})
                    msg_type = data.get("type", "")

                    # Находим символ
                    symbol = next(
                        (sym for sym, cfg in SYMBOLS.items()
                         if cfg["bybit"] in topic),
                        None
                    )
                    if not symbol or not payload:
                        continue

                    ob = orderbooks[symbol]["bybit"]

                    # snapshot — полная замена, delta — обновление
                    if msg_type == "snapshot":
                        ob["bids"] = {float(p): float(q) for p, q in payload.get("b", [])}
                        ob["asks"] = {float(p): float(q) for p, q in payload.get("a", [])}
                    elif msg_type == "delta":
                        for price, qty in payload.get("b", []):
                            price, qty = float(price), float(qty)
                            if qty == 0:
                                ob["bids"].pop(price, None)
                            else:
                                ob["bids"][price] = qty
                        for price, qty in payload.get("a", []):
                            price, qty = float(price), float(qty)
                            if qty == 0:
                                ob["asks"].pop(price, None)
                            else:
                                ob["asks"][price] = qty

                    ob["updated"] = datetime.now()

        except Exception as e:
            log.error(f"Bybit ошибка: {e}. Переподключаемся через 5с...")
            await asyncio.sleep(5)


# ============================================
#   OKX
# ============================================
async def connect_okx():
    url = EXCHANGES["okx"]["ws_url"]

    while True:
        try:
            log.info("OKX: подключаемся...")
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info("OKX: подключено ✓")

                # Подписываемся на все монеты
                args = [{"channel": "books50-l2-tbt", "instId": cfg["okx"]}
                        for cfg in SYMBOLS.values()]
                await ws.send(json.dumps({"op": "subscribe", "args": args}))

                async for raw in ws:
                    data = json.loads(raw)

                    # Пинг-понг для поддержания соединения
                    if data.get("event") == "subscribe":
                        continue
                    if raw == "ping":
                        await ws.send("pong")
                        continue

                    action = data.get("action", "")
                    payload_list = data.get("data", [])

                    if not payload_list:
                        continue

                    payload = payload_list[0]
                    inst_id = payload.get("instId", "")

                    # Находим символ
                    symbol = next(
                        (sym for sym, cfg in SYMBOLS.items()
                         if cfg["okx"] == inst_id),
                        None
                    )
                    if not symbol:
                        continue

                    ob = orderbooks[symbol]["okx"]

                    if action == "snapshot":
                        ob["bids"] = {float(p): float(q) for p, q, *_ in payload.get("bids", [])}
                        ob["asks"] = {float(p): float(q) for p, q, *_ in payload.get("asks", [])}
                    elif action == "update":
                        for price, qty, *_ in payload.get("bids", []):
                            price, qty = float(price), float(qty)
                            if qty == 0:
                                ob["bids"].pop(price, None)
                            else:
                                ob["bids"][price] = qty
                        for price, qty, *_ in payload.get("asks", []):
                            price, qty = float(price), float(qty)
                            if qty == 0:
                                ob["asks"].pop(price, None)
                            else:
                                ob["asks"][price] = qty

                    ob["updated"] = datetime.now()

        except Exception as e:
            log.error(f"OKX ошибка: {e}. Переподключаемся через 5с...")
            await asyncio.sleep(5)


# ============================================
#   ЗАПУСК ВСЕХ БИРЖ ОДНОВРЕМЕННО
# ============================================
async def start_collector():
    log.info("Запускаем сборщик данных...")
    await asyncio.gather(
        connect_binance(),
        connect_bybit(),
        connect_okx(),
    )


def get_orderbook(symbol: str) -> dict:
    """Получить текущий стакан по символу со всех бирж"""
    return orderbooks.get(symbol, {})
