# ============================================
#   TELEGRAM БОТ
# ============================================

import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ANALYSIS

log = logging.getLogger(__name__)
last_signal_time = {}


def format_number(num: float) -> str:
    if num >= 1_000_000:
        return f"{num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return f"{num:.2f}"


def format_price(price: float, symbol: str) -> str:
    if "BTC" in symbol:
        return f"${price:,.2f}"
    elif price >= 100:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:,.4f}"
    else:
        return f"${price:,.5f}"


def build_signal_message(signal: dict) -> str:
    symbol       = signal["symbol"]
    direction    = signal["direction"]
    level        = signal["level_label"]
    price        = signal["avg_price"]
    confirmed    = signal["confirmed_by"]
    total        = signal["total_exchanges"]
    target       = signal["target_level"]
    bid_clusters = signal.get("bid_clusters", [])
    ask_clusters = signal.get("ask_clusters", [])
    ts           = signal["timestamp"].strftime("%H:%M:%S")

    dir_icon  = "🟢" if direction == "up" else "🔴"
    dir_text  = "ВВЕРХ ↑" if direction == "up" else "ВНИЗ ↓"
    dir_emoji = "📈" if direction == "up" else "📉"

    lines = []
    lines.append(f"{dir_icon} {level} СИГНАЛ {dir_emoji}")
    lines.append(f"{'─' * 24}")
    lines.append(f"💎 <b>{symbol}</b> | {format_price(price, symbol)}")
    lines.append(f"🎯 <b>{dir_text}</b> | {confirmed}/{total} бирж")
    lines.append("")

    # Кластеры покупок — максимум 2
    if bid_clusters:
        lines.append(f"🟢 <b>Зоны покупок:</b>")
        for c in bid_clusters[:2]:
            lines.append(f"  {format_price(c['price'], symbol)} — {format_number(c['volume_usdt'])} USDT ({c['distance_pct']}%)")
    lines.append("")

    # Кластеры продаж — максимум 2
    if ask_clusters:
        lines.append(f"🔴 <b>Зоны продаж:</b>")
        for c in ask_clusters[:2]:
            lines.append(f"  {format_price(c['price'], symbol)} — {format_number(c['volume_usdt'])} USDT ({c['distance_pct']}%)")
    lines.append("")

    # Цель
    if target:
        lines.append(f"🎯 Цель: <b>{format_price(target['price'], symbol)}</b> ({format_number(target['volume_usdt'])} USDT)")
        lines.append("")

    # Дисбаланс
    imb_list = [r["imbalance"] for r in signal["exchange_results"]]
    if imb_list:
        avg_bid = sum(i["bid_pct"] for i in imb_list) / len(imb_list)
        avg_ask = sum(i["ask_pct"] for i in imb_list) / len(imb_list)
        filled  = int(avg_bid / 10)
        bar     = "🟩" * filled + "🟥" * (10 - filled)
        lines.append(f"⚖️ {bar}")
        lines.append(f"🟢 {avg_bid:.1f}%  🔴 {avg_ask:.1f}%")
        lines.append("")

    lines.append(f"🕐 {ts} | ⚠️ <i>Не фин. совет</i>")

    return "\n".join(lines)


async def send_message(text: str) -> bool:
    # Обрезаем если слишком длинное
    if len(text) > 4000:
        text = text[:4000] + "\n..."

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                log.error(f"Telegram ошибка {resp.status}: {body}")
                return False
    except Exception as e:
        log.error(f"Ошибка отправки в Telegram: {e}")
        return False


async def send_startup_message():
    text = (
        "🤖 <b>Трейдинг-бот запущен!</b>\n"
        "─────────────────────────\n"
        "📊 BTC | ETH | SOL | BNB | XRP\n"
        "🏦 Binance | Bybit | OKX\n"
        f"⏱ Анализ каждые {ANALYSIS['analyze_interval']}с\n"
        f"🔍 Радиус: {ANALYSIS.get('max_distance_pct', 5)}% от цены\n"
        "─────────────────────────\n"
        "Ищу кластеры ликвидности... 👀"
    )
    await send_message(text)


async def send_error_message(error: str):
    await send_message(f"⚠️ <b>Ошибка:</b>\n<code>{error[:200]}</code>")


async def process_signal(signal: dict) -> bool:
    symbol    = signal["symbol"]
    direction = signal["direction"]
    cooldown  = timedelta(minutes=ANALYSIS["signal_cooldown_minutes"])
    now       = datetime.now()

    # Кулдаун по символу И направлению
    key = f"{symbol}_{direction}"
    if key in last_signal_time:
        if now - last_signal_time[key] < cooldown:
            remaining = int((cooldown - (now - last_signal_time[key])).total_seconds() / 60)
            log.debug(f"{symbol}: кулдаун {remaining} мин.")
            return False

    message = build_signal_message(signal)
    success = await send_message(message)

    if success:
        last_signal_time[key] = now
        log.info(f"Сигнал отправлен: {symbol} {direction}")

    return success


async def process_signals(signals: list):
    for signal in signals:
        await process_signal(signal)
        await asyncio.sleep(0.5)
