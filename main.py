# ============================================
#   ГЛАВНЫЙ ФАЙЛ
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
    lines = ["🔍 <b>ОТЧЁТ</b>\n"]
    for symbol in SYMBOLS:
        lines.append(f"<b>{symbol}</b>")
        for exchange, ob in orderbooks.get(symbol, {}).items():
            bids    = ob.get("bids", {})
            asks    = ob.get("asks", {})
            updated = ob.get("updated")
            if not bids or not asks:
                lines.append(f"  ❌ {exchange}: нет данных")
                continue
            price     = get_current_price(bids, asks)
            imbalance = calc_imbalance(bids, asks)
            big_bids  = find_big_blocks(bids, "bids", symbol, price)
            big_asks  = find_big_blocks(asks, "asks", symbol, price)
            lines.append(f"  ✅ {exchange}: {len(bids)} уровней | {imbalance['bid_pct']}% vs {imbalance['ask_pct']}% | блоков: 🟢{len(big_bids)} 🔴{len(big_asks)}")
    await send_message("\n".join(lines))


async def analysis_loop():
    interval = ANALYSIS["analyze_interval"]

    log.info("Ждём первые данные (15с)...")
    await asyncio.sleep(15)

    # Отладочный отчёт при старте
    orderbooks = {symbol: get_orderbook(symbol) for symbol in SYMBOLS}
    await debug_report(orderbooks)

    cycle = 0
    while True:
        try:
            orderbooks = {symbol: get_orderbook(symbol) for symbol in SYMBOLS}
            signals    = run_analysis(orderbooks)

            if signals:
                await process_signals(signals)
            else:
                log.info("Сигналов нет...")

            # Отчёт каждые 20 циклов (~10 минут)
            cycle += 1
            if cycle % 20 == 0:
                await debug_report(orderbooks)

        except Exception as e:
            log.error(f"Ошибка: {e}")
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
