"""Dedicated scheduler entry point — run outside gunicorn workers."""
import logging
import os
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_shutdown = False


def _handle_signal(signum, _frame) -> None:
    global _shutdown
    logger.info("Received signal %s, shutting down scheduler", signum)
    _shutdown = True


def main() -> None:
    # Never auto-start a second scheduler via create_app()'s ENABLE_SCHEDULER flag.
    os.environ["ENABLE_SCHEDULER"] = "0"

    from app import create_app
    from app.services.scheduler import start_scheduler

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    app = create_app()
    with app.app_context():
        scheduler = start_scheduler(app)
        logger.info("Scheduler process running (Ctrl+C / SIGTERM to stop)")
        try:
            while not _shutdown:
                time.sleep(1)
        finally:
            sched = app.extensions.get("apscheduler")
            if sched is not None and getattr(sched, "running", False):
                sched.shutdown(wait=False)
                logger.info("Scheduler stopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
