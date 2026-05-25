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
    big_bids     = signal["big_bids"]
    big_asks     = signal["big_asks"]
    ts           = signal["timestamp"].strftime("%H:%M:%S")

    if direction == "up":
        dir_icon = "🟢"
        dir_text = "ВВЕРХ ↑"
        dir_emoji = "📈"
    else:
        dir_icon = "🔴"
        dir_text = "ВНИЗ ↓"
        dir_emoji = "📉"

    lines = []
    lines.append(f"{dir_icon} {level} СИГНАЛ {dir_emoji}")
    lines.append(f"{'─' * 28}")
    lines.append(f"💎 Монета:  <b>{symbol}</b>")
    lines.append(f"📍 Цена:    <b>{format_price(price, symbol)}</b>")
    lines.append(f"🎯 Сигнал: <b>{dir_text}</b>")
    lines.append("")

    # Подтверждения бирж
    lines.append(f"🏦 <b>Подтверждение бирж:</b>")
    for r in signal["exchange_results"]:
        dv = r["direction"]
        icon = "🟢" if dv == "up" else "🔴" if dv == "down" else "⚪"
        arrow = "↑" if dv == "up" else "↓" if dv == "down" else "—"
        lines.append(f"  {icon} {r['exchange'].capitalize()}: {arrow}")
    lines.append(f"  ✅ Согласны: {confirmed}/{total} бирж")
    lines.append("")

    # Кластеры покупок
    if bid_clusters:
        lines.append(f"🟢 <b>Кластеры покупок (зоны поддержки):</b>")
        for c in bid_clusters[:3]:
            lines.append(
                f"  🔵 {format_price(c['price'], symbol)} "
                f"— {format_number(c['volume_usdt'])} USDT "
                f"({c['distance_pct']}% от цены)"
            )
        lines.append("")
    elif big_bids:
        lines.append(f"🟢 <b>Крупные покупки:</b>")
        for b in big_bids[:3]:
            lines.append(
                f"  📦 {format_price(b['price'], symbol)} "
                f"— {format_number(b['volume_usdt'])} USDT "
                f"({b['distance_pct']}% от цены)"
            )
        lines.append("")

    # Кластеры продаж
    if ask_clusters:
        lines.append(f"🔴 <b>Кластеры продаж (зоны сопротивления):</b>")
        for c in ask_clusters[:3]:
            lines.append(
                f"  🔵 {format_price(c['price'], symbol)} "
                f"— {format_number(c['volume_usdt'])} USDT "
                f"({c['distance_pct']}% от цены)"
            )
        lines.append("")
    elif big_asks:
        lines.append(f"🔴 <b>Крупные продажи:</b>")
        for a in big_asks[:3]:
            lines.append(
                f"  📦 {format_price(a['price'], symbol)} "
                f"— {format_number(a['volume_usdt'])} USDT "
                f"({a['distance_pct']}% от цены)"
            )
        lines.append("")

    # Цель
    if target:
        lines.append(f"🎯 <b>Цель движения:</b>")
        lines.append(
            f"  {format_price(target['price'], symbol)} "
            f"({format_number(target['volume_usdt'])} USDT, "
            f"{target['distance_pct']}% от цены)"
        )
        lines.append("")

    # Дисбаланс
    imb_list = [r["imbalance"] for r in signal["exchange_results"]]
    if imb_list:
        avg_bid = sum(i["bid_pct"] for i in imb_list) / len(imb_list)
        avg_ask = sum(i["ask_pct"] for i in imb_list) / len(imb_list)
        filled  = int(avg_bid / 10)
        bar     = "🟩" * filled + "🟥" * (10 - filled)
        lines.append(f"⚖️ <b>Дисбаланс стакана:</b>")
        lines.append(f"  {bar}")
        lines.append(f"  🟢 Покупки: {avg_bid:.1f}%  🔴 Продажи: {avg_ask:.1f}%")
        lines.append("")

    lines.append(f"{'─' * 28}")
    lines.append(f"🕐 {ts}  |  ⚠️ <i>Не является финансовым советом</i>")

    return "\n".join(lines)


async def send_message(text: str) -> bool:
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
        "📊 Мониторю монеты:\n"
        "  • BTC/USDT\n"
        "  • ETH/USDT\n"
        "  • SOL/USDT\n"
        "  • BNB/USDT\n"
        "  • XRP/USDT\n\n"
        "🏦 Биржи: Binance, Bybit, OKX\n"
        f"⏱ Анализ каждые {ANALYSIS['analyze_interval']} секунд\n"
        f"🔍 Радиус поиска: {ANALYSIS.get('max_distance_pct', 5)}% от цены\n"
        "─────────────────────────\n"
        "Ищу кластеры ликвидности... 👀"
    )
    await send_message(text)


async def send_error_message(error: str):
    await send_message(f"⚠️ <b>Ошибка:</b>\n<code>{error}</code>")


async def process_signal(signal: dict) -> bool:
    symbol   = signal["symbol"]
    cooldown = timedelta(minutes=ANALYSIS["signal_cooldown_minutes"])
    now      = datetime.now()

    if symbol in last_signal_time:
        if now - last_signal_time[symbol] < cooldown:
            return False

    message = build_signal_message(signal)
    success = await send_message(message)

    if success:
        last_signal_time[symbol] = now
        log.info(f"Сигнал отправлен: {symbol} {signal['direction']}")

    return success


async def process_signals(signals: list):
    for signal in signals:
        await process_signal(signal)
        await asyncio.sleep(0.5)
