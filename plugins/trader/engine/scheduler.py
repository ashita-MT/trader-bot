from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .market import refresh_prices, refresh_virtual_prices
from ..handlers.lottery import draw_lottery


class MarketScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start_real(self, interval=300):
        self.scheduler.add_job(refresh_prices, "interval", seconds=interval, id="refresh_prices", replace_existing=True)
        print(f"[Scheduler] real stocks refresh every {interval}s", flush=True)

    def start_virtual(self, interval=300):
        self.scheduler.add_job(refresh_virtual_prices, "interval", seconds=interval, id="refresh_virtual", replace_existing=True)
        print(f"[Scheduler] virtual stocks refresh every {interval}s", flush=True)

    def start_lottery(self, interval=86400):
        def do_draw():
            result = draw_lottery()
            print(f"[Lottery] round {result['round']} winning: {result['winning_number']} winners: {result['winners']}", flush=True)

        self.scheduler.add_job(do_draw, "interval", seconds=interval, id="lottery_draw", replace_existing=True)
        print(f"[Scheduler] lottery draw every {interval}s", flush=True)

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
