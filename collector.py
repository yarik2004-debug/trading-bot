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
    streams = [f"{cfg['binance']}@depth{depth}@100ms" for cfg in SYMBOLS.values()]
    url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"

    while True:
        try:
            log.info(f"Binance: подключаемся к {url[:60]}...")
            async with websockets.connect(url, ping_interval=20) as ws:
                log.info("Binance: подключено ✓")
                msg_count = 0
                async for raw in ws:
                    data = json.loads(raw)
                    stream = data.get("stream", "")
                    payload = data.get("data", {})

                    msg_count += 1
                    if msg_count <= 3:
                        log.info(f"Binance сообщение #{msg_count}: stream={stream} keys={list(payload.keys())[:5]}")

                    symbol = next(
                        (sym for sym, cfg in SYMBOLS.items() if cfg["binance"] in stream),
                        None
                    )
                    if not symbol:
                        continue

                    ob = orderbooks[symbol]["binance"]
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

                    if msg_count == 50:
                        # Показываем сколько данных набрали
                        for sym in SYMBOLS:
                            b = len(orderbooks[sym]["binance"]["bids"])
                            a = len(orderbooks[sym]["binance"]["asks"])
                            log.info(f"Binance {sym}: bids={b} asks={a}")

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
                topics = [f"orderbook.{depth}.{cfg['bybit']}" for cfg in SYMBOLS.values()]
                await ws.send(json.dumps({"op": "subscribe", "args": topics}))
                log.info(f"Bybit: подписались на {topics}")

                msg_count = 0
                async for raw in ws:
                    data = json.loads(raw)
                    if data.get("op") == "subscribe":
                        log.info(f"Bybit подписка: {data.get('success')} {data.get('ret_msg','')}")
                        continue

                    topic = data.get("topic", "")
                    payload = data.get("data", {})
                    msg_type = data.get("type", "")

                    symbol = next(
                        (sym for sym, cfg in SYMBOLS.items() if cfg["bybit"] in topic),
                        None
                    )
                    if not symbol or not payload:
                        continue

                    ob = orderbooks[symbol]["bybit"]
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
                    msg_count += 1

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

                args = [{"channel": "books50-l2-tbt", "instId": cfg["okx"]}
                        for cfg in SYMBOLS.values()]
                sub_msg = json.dumps({"op": "subscribe", "args": args})
                await ws.send(sub_msg)
                log.info(f"OKX: отправили подписку на {[a['instId'] for a in args]}")

                msg_count = 0
                async for raw in ws:
                    # OKX шлёт текстовый пинг
                    if raw == "ping":
                        await ws.send("pong")
                        continue

                    data = json.loads(raw)
                    msg_count += 1

                    if msg_count <= 5:
                        log.info(f"OKX сообщение #{msg_count}: {str(data)[:150]}")

                    event = data.get("event", "")
                    if event == "subscribe":
                        log.info(f"OKX подписка подтверждена: {data}")
                        continue
                    if event == "error":
                        log.error(f"OKX ошибка подписки: {data}")
                        continue

                    action = data.get("action", "")
                    payload_list = data.get("data", [])
                    if not payload_list:
                        continue

                    payload = payload_list[0]
                    inst_id = payload.get("instId", "")

                    symbol = next(
                        (sym for sym, cfg in SYMBOLS.items() if cfg["okx"] == inst_id),
                        None
                    )
                    if not symbol:
                        continue

                    ob = orderbooks[symbol]["okx"]
                    if action == "snapshot":
                        ob["bids"] = {float(p): float(q) for p, q, *_ in payload.get("bids", [])}
                        ob["asks"] = {float(p): float(q) for p, q, *_ in payload.get("asks", [])}
                        log.info(f"OKX snapshot {symbol}: bids={len(ob['bids'])} asks={len(ob['asks'])}")
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
#   ЗАПУСК
# ============================================
async def start_collector():
    log.info("Запускаем сборщик данных...")
    await asyncio.gather(
        connect_binance(),
        connect_bybit(),
        connect_okx(),
    )


def get_orderbook(symbol: str) -> dict:
    return orderbooks.get(symbol, {})
