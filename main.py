# ============================================
#   ГЛАВНЫЙ ФАЙЛ — ЗАПУСК БОТА
# ============================================

import asyncio
import logging
from collector import start_collector, get_orderbook
from analyzer import run_analysis
from telegram_bot import process_signals, send_startup_message, send_error_message
from config import SYMBOLS, ANALYSIS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


async def analysis_loop():
    """
    Цикл анализа — каждые N секунд собирает данные
    со всех бирж и отправляет сигналы.
    """
    interval = ANALYSIS["analyze_interval"]

    # Ждём пока сборщик наберёт первые данные
    log.info("Ждём первые данные с бирж (15 секунд)...")
    await asyncio.sleep(15)

    while True:
        try:
            # Собираем стаканы по всем монетам
            orderbooks = {symbol: get_orderbook(symbol) for symbol in SYMBOLS}

            # Запускаем анализ
            signals = run_analysis(orderbooks)

            # Отправляем сигналы в Telegram
            if signals:
                await process_signals(signals)
            else:
                log.info("Сигналов нет — ждём следующего цикла...")

        except Exception as e:
            log.error(f"Ошибка в цикле анализа: {e}")
            await send_error_message(str(e))

        await asyncio.sleep(interval)


async def main():
    log.info("=" * 40)
    log.info("  ТРЕЙДИНГ-БОТ ЗАПУСКАЕТСЯ")
    log.info("=" * 40)

    # Сообщение о запуске в Telegram
    await send_startup_message()

    # Запускаем сборщик и анализатор параллельно
    await asyncio.gather(
        start_collector(),
        analysis_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
