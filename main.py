# ============================================
#   ГЛАВНЫЙ ФАЙЛ — ЗАПУСК БОТА
# ============================================

import asyncio
import logging
from collector import start_collector, get_orderbook
from analyzer import run_analysis, calc_imbalance, get_current_price, find_big_blocks
from telegram_bot import process_signals, send_startup_message, send_error_message, send_message
from config import SYMBOLS, ANALYSIS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


async def debug_report(orderbooks: dict):
    """Отправляет детальный отчёт в Telegram что реально видит бот"""
    lines = ["🔍 <b>ОТЛАДОЧНЫЙ ОТЧЁТ</b>\n"]

    for symbol in SYMBOLS:
        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"💎 <b>{symbol}</b>")

        for exchange, ob in orderbooks.get(symbol, {}).items():
            bids = ob.get("bids", {})
            asks = ob.get("asks", {})
            updated = ob.get("updated")

            if not bids or not asks:
                lines.append(f"  ❌ {exchange}: нет данных")
                continue

            price = get_current_price(bids, asks)
            imbalance = calc_imbalance(bids, asks)
            big_bids = find_big_blocks(bids, "bids", symbol, price)
            big_asks = find_big_blocks(asks, "asks", symbol, price)

            lines.append(f"\n  🏦 <b>{exchange.capitalize()}</b>")
            lines.append(f"  📍 Цена: {price:.4f}")
            lines.append(f"  📊 Уровней bids: {len(bids)} | asks: {len(asks)}")
            lines.append(f"  ⚖️ Покупки: {imbalance['bid_pct']}% | Продажи: {imbalance['ask_pct']}%")
            lines.append(f"  📈 Дисбаланс: {imbalance['ratio']}x ({imbalance['dominant']})")
            lines.append(f"  🟢 Крупных блоков покупок: {len(big_bids)}")
            lines.append(f"  🔴 Крупных блоков продаж: {len(big_asks)}")

            # Показываем топ-3 уровня по объёму
            top_bids = sorted(bids.items(), key=lambda x: x[0]*x[1], reverse=True)[:3]
            lines.append(f"  💰 Топ bid объёмы:")
            for p, q in top_bids:
                lines.append(f"     {p:.4f} → {p*q:,.0f} USDT")

            top_asks = sorted(asks.items(), key=lambda x: x[0]*x[1], reverse=True)[:3]
            lines.append(f"  💰 Топ ask объёмы:")
            for p, q in top_asks:
                lines.append(f"     {p:.4f} → {p*q:,.0f} USDT")

        lines.append("")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⚙️ Порог объёма BTC: {ANALYSIS['min_big_volume']['BTC/USDT']:,} USDT")
    lines.append(f"⚙️ Порог объёма ETH: {ANALYSIS['min_big_volume']['ETH/USDT']:,} USDT")
    lines.append(f"⚙️ Порог объёма XRP: {ANALYSIS['min_big_volume']['XRP/USDT']:,} USDT")
    lines.append(f"⚙️ Дисбаланс ratio: {ANALYSIS['imbalance_ratio']}")
    lines.append(f"⚙️ Мин. подтверждений: {ANALYSIS['min_exchanges_confirm']}")

    await send_message("\n".join(lines))


async def analysis_loop():
    interval = ANALYSIS["analyze_interval"]

    log.info("Ждём первые данные с бирж (15 секунд)...")
    await asyncio.sleep(15)

    # Сразу шлём отладочный отчёт
    log.info("Отправляем отладочный отчёт...")
    orderbooks = {symbol: get_orderbook(symbol) for symbol in SYMBOLS}
    await debug_report(orderbooks)

    cycle = 0
    while True:
        try:
            orderbooks = {symbol: get_orderbook(symbol) for symbol in SYMBOLS}
            signals = run_analysis(orderbooks)

            if signals:
                await process_signals(signals)
            else:
                log.info("Сигналов нет — ждём следующего цикла...")

            # Каждые 10 циклов шлём отладочный отчёт
            cycle += 1
            if cycle % 10 == 0:
                await debug_report(orderbooks)

        except Exception as e:
            log.error(f"Ошибка в цикле анализа: {e}")
            await send_error_message(str(e))

        await asyncio.sleep(interval)


async def main():
    log.info("=" * 40)
    log.info("  ТРЕЙДИНГ-БОТ ЗАПУСКАЕТСЯ")
    log.info("=" * 40)

    await send_startup_message()

    await asyncio.gather(
        start_collector(),
        analysis_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
