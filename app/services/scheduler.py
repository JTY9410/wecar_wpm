"""APScheduler: 자동 동기화 09/13/18 KST (PRD §5.4)."""
from config import Config


def start_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    def _job():
        with app.app_context():
            from app.services.sync_engine import sync_listings
            sync_listings(with_images=True)

    for hour in Config.SYNC_HOURS:
        scheduler.add_job(_job, CronTrigger(hour=hour, minute=0),
                          id=f"sync_{hour}", replace_existing=True)
    scheduler.start()
    app.extensions["apscheduler"] = scheduler
    return scheduler
