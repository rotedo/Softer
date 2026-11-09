"""Background loop: refresh tiers, suggestions, news every few hours (cheap, read-only on orderflow.db)."""
import asyncio, logging, os
import aggregator as a, news, scanner, store

CACHE = {}


def refresh():
    CACHE["tiers"] = a.tiers()
    CACHE["suggestions"] = scanner.suggestions(["BTCUSDT", "ETHUSDT"] + [t["sym"] for t in CACHE["tiers"] if t["tier"] == 2][:5])
    news.calendar()
    news.headlines()


async def loop(*_):
    every = float(os.environ.get("JOBS_EVERY_H", "3")) * 3600
    while True:
        try:
            await asyncio.get_running_loop().run_in_executor(None, refresh)
        except Exception:
            logging.exception("jobs.refresh failed")
        await asyncio.sleep(every)
