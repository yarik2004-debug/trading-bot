# ============================================
#   TELEGRAM БОТ — ОТПРАВКА СИГНАЛОВ
# ============================================

import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ANALYSIS

log = logging.getLogger(__name__)

# Защита от спама — запоминаем когда последний раз слали сигнал по монете
last_signal_time = {}


# ============================================
#   ФОРМАТИРОВАНИЕ СООБЩЕНИЙ
# ============================================

def format_number(num: float) -> str:
    """Красивый формат числа: 1234567 → 1,234,567"""
    if num >= 1_000_000:
        return f"{num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return f"{num:.2f}"


def format_price(price: float, symbol: str) -> str:
    """Форматируем цену в зависимости от монеты"""
    if "BTC" in symbol:
        return f"${price:,.2f}"
    elif price >= 100:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:,.4f}"
    else:
        return f"${price:,.6f}"


def build_signal_message(signal: dict) -> str:
    """
    Строим красивое сообщение для Telegram.
    """
    symbol    = signal["symbol"]
    direction = signal["direction"]
    level     = signal["level_label"]
    price     = signal["avg_price"]
    confirmed = signal["confirmed_by"]
    total     = signal["total_exchanges"]
    target    = signal["target_level"]
    big_bids  = signal["big_bids"]
    big_asks  = signal["big_asks"]
    votes     = signal["votes"]
    ts        = signal["timestamp"].strftime("%H:%M:%S")

    # Иконки направления
    if direction == "up":
        dir_icon  = "🟢"
        dir_text  = "ВВЕРХ ↑"
        dir_emoji = "📈"
    else:
        dir_icon  = "🔴"
        dir_text  = "ВНИЗ ↓"
        dir_emoji = "📉"

    lines = []

    # --- Заголовок ---
    lines.append(f"{dir_icon} {level} СИГНАЛ {dir_emoji}")
    lines.append(f"{'─' * 28}")
    lines.append(f"💎 Монета:  <b>{symbol}</b>")
    lines.append(f"📍 Цена:    <b>{format_price(price, symbol)}</b>")
    lines.append(f"🎯 Сигнал: <b>{dir_text}</b>")
    lines.append(f"")

    # --- Подтверждения бирж ---
    lines.append(f"🏦 <b>Подтверждение бирж:</b>")
    exchange_names = {
        r["exchange"]: r["direction"]
        for r in signal["exchange_results"]
    }
    for exch, direction_vote in exchange_names.items():
        if direction_vote == "up":
            icon = "🟢"
        elif direction_vote == "down":
            icon = "🔴"
        else:
            icon = "⚪"
        lines.append(f"  {icon} {exch.capitalize()}: {'↑' if direction_vote == 'up' else '↓' if direction_vote == 'down' else '—'}")
    lines.append(f"  ✅ Согласны: {confirmed}/{total} бирж")
    lines.append(f"")

    # --- Крупные блоки покупок ---
    if big_bids:
        lines.append(f"🟢 <b>Крупные покупки (поддержка):</b>")
        for b in big_bids[:3]:
            lines.append(
                f"  📦 {format_price(b['price'], symbol)} "
                f"— {format_number(b['volume_usdt'])} USDT "
                f"({b['distance_pct']}% от цены)"
            )
        lines.append(f"")

    # --- Крупные блоки продаж ---
    if big_asks:
        lines.append(f"🔴 <b>Крупные продажи (сопротивление):</b>")
        for a in big_asks[:3]:
            lines.append(
                f"  📦 {format_price(a['price'], symbol)} "
                f"— {format_number(a['volume_usdt'])} USDT "
                f"({a['distance_pct']}% от цены)"
            )
        lines.append(f"")

    # --- Целевой уровень ---
    if target:
        lines.append(f"🎯 <b>Цель движения:</b>")
        lines.append(
            f"  {format_price(target['price'], symbol)} "
            f"({format_number(target['volume_usdt'])} USDT)"
        )
        lines.append(f"")

    # --- Дисбаланс стакана ---
    imb_list = [r["imbalance"] for r in signal["exchange_results"]]
    if imb_list:
        avg_bid_pct = sum(i["bid_pct"] for i in imb_list) / len(imb_list)
        avg_ask_pct = sum(i["ask_pct"] for i in imb_list) / len(imb_list)
        bar_filled  = int(avg_bid_pct / 10)
        bar_empty   = 10 - bar_filled
        bar         = "🟩" * bar_filled + "🟥" * bar_empty
        lines.append(f"⚖️ <b>Дисбаланс стакана:</b>")
        lines.append(f"  {bar}")
        lines.append(f"  🟢 Покупки: {avg_bid_pct:.1f}%  🔴 Продажи: {avg_ask_pct:.1f}%")
        lines.append(f"")

    # --- Подвал ---
    lines.append(f"{'─' * 28}")
    lines.append(f"🕐 {ts}  |  ⚠️ <i>Не является финансовым советом</i>")

    return "\n".join(lines)


# ============================================
#   ОТПРАВКА В TELEGRAM
# ============================================

async def send_message(text: str) -> bool:
    """Отправляет сообщение в Telegram через HTTP API"""
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
                else:
                    body = await resp.text()
                    log.error(f"Telegram ошибка {resp.status}: {body}")
                    return False
    except Exception as e:
        log.error(f"Ошибка отправки в Telegram: {e}")
        return False


async def send_startup_message():
    """Сообщение при запуске бота"""
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
        f"✅ Минимум подтверждений: {ANALYSIS['min_exchanges_confirm']} биржи\n"
        "─────────────────────────\n"
        "Жду крупных блоков ликвидности... 👀"
    )
    await send_message(text)


async def send_error_message(error: str):
    """Сообщение об ошибке"""
    text = f"⚠️ <b>Ошибка бота:</b>\n<code>{error}</code>"
    await send_message(text)


# ============================================
#   ПРОВЕРКА КУЛДАУНА И ОТПРАВКА СИГНАЛА
# ============================================

async def process_signal(signal: dict) -> bool:
    """
    Проверяет кулдаун и отправляет сигнал если прошло достаточно времени.
    Возвращает True если сигнал был отправлен.
    """
    symbol   = signal["symbol"]
    cooldown = timedelta(minutes=ANALYSIS["signal_cooldown_minutes"])
    now      = datetime.now()

    # Проверяем кулдаун
    if symbol in last_signal_time:
        elapsed = now - last_signal_time[symbol]
        if elapsed < cooldown:
            remaining = (cooldown - elapsed).seconds // 60
            log.debug(f"{symbol}: кулдаун, ещё {remaining} мин.")
            return False

    # Формируем и отправляем сообщение
    message = build_signal_message(signal)
    success = await send_message(message)

    if success:
        last_signal_time[symbol] = now
        log.info(f"Сигнал отправлен: {symbol} {signal['direction']}")

    return success


async def process_signals(signals: list):
    """Обрабатывает список сигналов"""
    for signal in signals:
        await process_signal(signal)
        await asyncio.sleep(0.5)  # небольшая пауза между сообщениями
