# ============================================
#   АНАЛИЗАТОР ORDER BOOK
# ============================================

import logging
from datetime import datetime
from config import SYMBOLS, ANALYSIS, SIGNAL_LEVELS

log = logging.getLogger(__name__)


def get_top_levels(orders: dict, side: str, depth: int = 20) -> list:
    reverse = (side == "bids")
    sorted_levels = sorted(orders.items(), key=lambda x: x[0], reverse=reverse)
    return sorted_levels[:depth]


def calc_volume_usdt(price: float, qty: float) -> float:
    return price * qty


def find_big_blocks(orders: dict, side: str, symbol: str, current_price: float) -> list:
    """
    Ищет крупные блоки по ВСЕМУ стакану без ограничения дистанции.
    Группирует близкие уровни в кластеры.
    """
    min_vol = ANALYSIS["min_big_volume"][symbol]
    max_dist = ANALYSIS.get("max_distance_pct", 5.0)
    big_blocks = []

    for price, qty in orders.items():
        volume_usdt = calc_volume_usdt(price, qty)
        distance_pct = abs(price - current_price) / current_price * 100

        # Ищем блоки в радиусе max_distance_pct от цены
        if distance_pct > max_dist:
            continue

        if volume_usdt >= min_vol:
            big_blocks.append({
                "price":        price,
                "qty":          qty,
                "volume_usdt":  volume_usdt,
                "side":         side,
                "distance_pct": round(distance_pct, 2),
            })

    big_blocks.sort(key=lambda x: x["volume_usdt"], reverse=True)
    return big_blocks


def find_clusters(orders: dict, side: str, symbol: str, current_price: float) -> list:
    """
    Группирует уровни в кластеры — зоны где скопилось много объёма.
    Кластер = группа уровней в радиусе 0.3% друг от друга.
    """
    min_vol   = ANALYSIS["min_big_volume"][symbol]
    max_dist  = ANALYSIS.get("max_distance_pct", 5.0)
    cluster_r = 0.003  # 0.3% — радиус кластера

    # Фильтруем уровни по дистанции
    levels = []
    for price, qty in orders.items():
        dist = abs(price - current_price) / current_price * 100
        if dist <= max_dist:
            levels.append((price, qty, price * qty))

    if not levels:
        return []

    # Сортируем по цене
    reverse = (side == "bids")
    levels.sort(key=lambda x: x[0], reverse=reverse)

    # Группируем в кластеры
    clusters = []
    used = set()

    for i, (price, qty, vol) in enumerate(levels):
        if i in used:
            continue

        cluster_vol   = vol
        cluster_prices = [price]
        used.add(i)

        for j, (price2, qty2, vol2) in enumerate(levels):
            if j in used:
                continue
            if abs(price - price2) / price <= cluster_r:
                cluster_vol += vol2
                cluster_prices.append(price2)
                used.add(j)

        if cluster_vol >= min_vol:
            avg_price = sum(cluster_prices) / len(cluster_prices)
            dist = abs(avg_price - current_price) / current_price * 100
            clusters.append({
                "price":        round(avg_price, 6),
                "volume_usdt":  cluster_vol,
                "side":         side,
                "distance_pct": round(dist, 2),
                "levels_count": len(cluster_prices),
            })

    clusters.sort(key=lambda x: x["volume_usdt"], reverse=True)
    return clusters


def calc_imbalance(bids: dict, asks: dict, depth: int = 50) -> dict:
    top_bids = sorted(bids.items(), key=lambda x: x[0], reverse=True)[:depth]
    top_asks = sorted(asks.items(), key=lambda x: x[0])[:depth]

    bid_volume = sum(p * q for p, q in top_bids)
    ask_volume = sum(p * q for p, q in top_asks)
    total = bid_volume + ask_volume

    if total == 0:
        return {"bid_pct": 50, "ask_pct": 50, "ratio": 1.0, "dominant": "neutral"}

    bid_pct = bid_volume / total * 100
    ask_pct = ask_volume / total * 100

    if bid_volume > ask_volume:
        ratio    = bid_volume / ask_volume if ask_volume > 0 else 999
        dominant = "bids"
    else:
        ratio    = ask_volume / bid_volume if bid_volume > 0 else 999
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
    bids    = ob.get("bids", {})
    asks    = ob.get("asks", {})
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

    # Отдельные блоки
    big_bids = find_big_blocks(bids, "bids", symbol, current_price)
    big_asks = find_big_blocks(asks, "asks", symbol, current_price)

    # Кластеры ликвидности
    bid_clusters = find_clusters(bids, "bids", symbol, current_price)
    ask_clusters = find_clusters(asks, "asks", symbol, current_price)

    imbalance = calc_imbalance(bids, asks)

    ratio     = ANALYSIS["imbalance_ratio"]
    direction = "neutral"

    if imbalance["dominant"] == "bids" and imbalance["ratio"] >= ratio:
        direction = "up"
    elif imbalance["dominant"] == "asks" and imbalance["ratio"] >= ratio:
        direction = "down"

    return {
        "exchange":     exchange,
        "symbol":       symbol,
        "price":        current_price,
        "big_bids":     big_bids[:5],
        "big_asks":     big_asks[:5],
        "bid_clusters": bid_clusters[:3],
        "ask_clusters": ask_clusters[:3],
        "imbalance":    imbalance,
        "direction":    direction,
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
        confirmed_by    = votes["up"]
    elif votes["down"] >= min_confirm:
        final_direction = "down"
        confirmed_by    = votes["down"]
    else:
        return None

    level = "strong" if confirmed_by >= 3 else "medium" if confirmed_by == 2 else "weak"

    avg_price = sum(r["price"] for r in valid) / len(valid)

    all_big_bids     = []
    all_big_asks     = []
    all_bid_clusters = []
    all_ask_clusters = []

    for r in valid:
        all_big_bids.extend(r["big_bids"])
        all_big_asks.extend(r["big_asks"])
        all_bid_clusters.extend(r["bid_clusters"])
        all_ask_clusters.extend(r["ask_clusters"])

    all_big_bids.sort(key=lambda x: x["volume_usdt"], reverse=True)
    all_big_asks.sort(key=lambda x: x["volume_usdt"], reverse=True)
    all_bid_clusters.sort(key=lambda x: x["volume_usdt"], reverse=True)
    all_ask_clusters.sort(key=lambda x: x["volume_usdt"], reverse=True)

    # Цель — ближайший крупный кластер в направлении движения
    target_level = None
    if final_direction == "down":
        target_level = all_bid_clusters[0] if all_bid_clusters else (all_big_bids[0] if all_big_bids else None)
    elif final_direction == "up":
        target_level = all_ask_clusters[0] if all_ask_clusters else (all_big_asks[0] if all_big_asks else None)

    return {
        "symbol":           symbol,
        "direction":        final_direction,
        "level":            level,
        "level_label":      SIGNAL_LEVELS[level],
        "confirmed_by":     confirmed_by,
        "total_exchanges":  len(valid),
        "avg_price":        round(avg_price, 6),
        "target_level":     target_level,
        "big_bids":         all_big_bids[:3],
        "big_asks":         all_big_asks[:3],
        "bid_clusters":     all_bid_clusters[:3],
        "ask_clusters":     all_ask_clusters[:3],
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
                f"{signal['confirmed_by']}/{signal['total_exchanges']} бирж"
            )
            signals.append(signal)
        else:
            log.debug(f"{symbol}: сигнала нет")

    return signals
