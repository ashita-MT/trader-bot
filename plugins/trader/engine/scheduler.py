from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .market import refresh_prices, refresh_virtual_prices
from ..handlers.number_lottery import draw_number_lottery
from ..handlers.pool_lottery import draw_pool_lottery


class MarketScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start_real(self, interval=300):
        self.scheduler.add_job(refresh_prices, "interval", seconds=interval, id="refresh_prices", replace_existing=True)
        print(f"[Scheduler] real stocks refresh every {interval}s", flush=True)

    def start_virtual(self, interval=300):
        self.scheduler.add_job(refresh_virtual_prices, "interval", seconds=interval, id="refresh_virtual", replace_existing=True)
        print(f"[Scheduler] virtual stocks refresh every {interval}s", flush=True)

    def start_number_lottery(self, interval=86400):
        def do_draw():
            result = draw_number_lottery()
            print(f"[NumberLottery] round {result['round']} winning: {result['winning_number']} winners: {result['winners']}", flush=True)
        self.scheduler.add_job(do_draw, "interval", seconds=interval, id="number_lottery_draw", replace_existing=True)
        print(f"[Scheduler] number lottery draw every {interval}s", flush=True)

    def start_pool_lottery(self, interval=86400):
        def do_draw():
            result = draw_pool_lottery()
            print(f"[PoolLottery] round {result['round']} pool: {result['total_pool']} winners: {result['winners']}", flush=True)
        self.scheduler.add_job(do_draw, "interval", seconds=interval, id="pool_lottery_draw", replace_existing=True)
        print(f"[Scheduler] pool lottery draw every {interval}s", flush=True)

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
