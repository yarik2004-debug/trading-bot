# ============================================
#   АНАЛИЗАТОР ORDER BOOK
# ============================================

import logging
from datetime import datetime
from config import SYMBOLS, ANALYSIS, SIGNAL_LEVELS

log = logging.getLogger(__name__)


def get_top_levels(orders: dict, side: str, depth: int = 10) -> list:
    reverse = (side == "bids")
    sorted_levels = sorted(orders.items(), key=lambda x: x[0], reverse=reverse)
    return sorted_levels[:depth]


def calc_volume_usdt(price: float, qty: float) -> float:
    return price * qty


def find_big_blocks(orders: dict, side: str, symbol: str, current_price: float) -> list:
    min_vol = ANALYSIS["min_big_volume"][symbol]
    big_blocks = []

    for price, qty in orders.items():
        volume_usdt = calc_volume_usdt(price, qty)
        if volume_usdt >= min_vol:
            distance_pct = abs(price - current_price) / current_price * 100
            big_blocks.append({
                "price":        price,
                "qty":          qty,
                "volume_usdt":  volume_usdt,
                "side":         side,
                "distance_pct": round(distance_pct, 2),
            })

    big_blocks.sort(key=lambda x: x["volume_usdt"], reverse=True)
    return big_blocks


def calc_imbalance(bids: dict, asks: dict, depth: int = 20) -> dict:
    top_bids = get_top_levels(bids, "bids", depth)
    top_asks = get_top_levels(asks, "asks", depth)

    bid_volume = sum(p * q for p, q in top_bids)
    ask_volume = sum(p * q for p, q in top_asks)
    total = bid_volume + ask_volume

    if total == 0:
        return {"bid_pct": 50, "ask_pct": 50, "ratio": 1.0, "dominant": "neutral"}

    bid_pct = bid_volume / total * 100
    ask_pct = ask_volume / total * 100

    if bid_volume > ask_volume:
        ratio = bid_volume / ask_volume if ask_volume > 0 else 999
        dominant = "bids"
    else:
        ratio = ask_volume / bid_volume if bid_volume > 0 else 999
        dominant = "asks"

    return {
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "bid_pct":    round(bid_pct, 1),
        "ask_pct":    round(ask_pct, 1),
        "ratio":      round(ratio, 2),
        "dominant":   dominant,
    }


def get_current_price(bids: dict, asks: dict) -> float:
    if not bids or not asks:
        return 0.0
    best_bid = max(bids.keys())
    best_ask = min(asks.keys())
    return (best_bid + best_ask) / 2


def analyze_exchange(symbol: str, exchange: str, ob: dict):
    bids = ob.get("bids", {})
    asks = ob.get("asks", {})
    updated = ob.get("updated")

    if not bids or not asks or not updated:
        return None

    age = (datetime.now() - updated).total_seconds()
    if age > 60:
        log.warning(f"{exchange} {symbol}: данные устарели ({age:.0f}с)")
        return None

    current_price = get_current_price(bids, asks)
    if current_price == 0:
        return None

    big_bids = find_big_blocks(bids, "bids", symbol, current_price)
    big_asks = find_big_blocks(asks, "asks", symbol, current_price)
    imbalance = calc_imbalance(bids, asks)

    ratio = ANALYSIS["imbalance_ratio"]
    direction = "neutral"

    # ИСПРАВЛЕННАЯ ЛОГИКА:
    # Много покупок (bids) → давление вверх → цена идёт ВВЕРХ
    # Много продаж (asks) → давление вниз → цена идёт ВНИЗ
    if imbalance["dominant"] == "bids" and imbalance["ratio"] >= ratio:
        direction = "up"
    elif imbalance["dominant"] == "asks" and imbalance["ratio"] >= ratio:
        direction = "down"

    return {
        "exchange":  exchange,
        "symbol":    symbol,
        "price":     current_price,
        "big_bids":  big_bids[:3],
        "big_asks":  big_asks[:3],
        "imbalance": imbalance,
        "direction": direction,
    }


def aggregate_signal(symbol: str, exchange_results: list):
    valid = [r for r in exchange_results if r is not None]
    if not valid:
        return None

    votes = {"up": 0, "down": 0, "neutral": 0}
    for r in valid:
        votes[r["direction"]] += 1

    min_confirm = ANALYSIS["min_exchanges_confirm"]

    if votes["up"] >= min_confirm:
        final_direction = "up"
        confirmed_by = votes["up"]
    elif votes["down"] >= min_confirm:
        final_direction = "down"
        confirmed_by = votes["down"]
    else:
        return None

    if confirmed_by >= 3:
        level = "strong"
    elif confirmed_by == 2:
        level = "medium"
    else:
        level = "weak"

    avg_price = sum(r["price"] for r in valid) / len(valid)

    all_big_bids = []
    all_big_asks = []
    for r in valid:
        all_big_bids.extend(r["big_bids"])
        all_big_asks.extend(r["big_asks"])

    all_big_bids.sort(key=lambda x: x["volume_usdt"], reverse=True)
    all_big_asks.sort(key=lambda x: x["volume_usdt"], reverse=True)

    target_level = None
    if final_direction == "down" and all_big_bids:
        target_level = all_big_bids[0]
    elif final_direction == "up" and all_big_asks:
        target_level = all_big_asks[0]

    return {
        "symbol":           symbol,
        "direction":        final_direction,
        "level":            level,
        "level_label":      SIGNAL_LEVELS[level],
        "confirmed_by":     confirmed_by,
        "total_exchanges":  len(valid),
        "avg_price":        round(avg_price, 4),
        "target_level":     target_level,
        "big_bids":         all_big_bids[:3],
        "big_asks":         all_big_asks[:3],
        "exchange_results": valid,
        "votes":            votes,
        "timestamp":        datetime.now(),
    }


def run_analysis(orderbooks: dict) -> list:
    signals = []

    for symbol in SYMBOLS:
        exchange_results = []

        for exchange, ob in orderbooks.get(symbol, {}).items():
            result = analyze_exchange(symbol, exchange, ob)
            exchange_results.append(result)

        signal = aggregate_signal(symbol, exchange_results)

        if signal:
            log.info(
                f"СИГНАЛ {signal['level_label']} | {symbol} | "
                f"{'ВВЕРХ ↑' if signal['direction'] == 'up' else 'ВНИЗ ↓'} | "
                f"подтверждено {signal['confirmed_by']}/{signal['total_exchanges']} бирж"
            )
            signals.append(signal)
        else:
            log.debug(f"{symbol}: сигнала нет")

    return signals
