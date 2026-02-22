import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)

FS_SCHEDULE = [
    ("4", "7"),   # Q4/Annual  (KR 3/31 deadline, US ~3/1)
    ("5", "22"),  # Q1         (KR 5/15 deadline, US ~5/10)
    ("8", "21"),  # Q2/Semi    (KR 8/14 deadline, US ~8/9)
    ("11", "21"), # Q3         (KR 11/14 deadline, US ~11/9)
]

_JOB_MAP = {
    "kr":    "run_daily_kr",
    "us":    "run_daily_us",
    "kr-fs": "run_collect_fs_kr",
    "us-fs": "run_collect_fs_us",
}


def _run_job(command: str) -> None:
    pipe = PipelineOrchestrator()
    method = getattr(pipe, _JOB_MAP[command])
    try:
        method()
    except Exception:
        logger.exception(f"[Scheduler] Pipeline '{command}' failed")


def init_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="Asia/Seoul")

    sched.add_job(
        _run_job, CronTrigger(hour=18, minute=0, day_of_week="mon-fri"),
        args=["kr"], id="daily_kr", misfire_grace_time=3600,
    )
    sched.add_job(
        _run_job, CronTrigger(hour=9, minute=0, day_of_week="tue-sat"),
        args=["us"], id="daily_us", misfire_grace_time=3600,
    )

    for month, day in FS_SCHEDULE:
        for cmd in ("kr-fs", "us-fs"):
            sched.add_job(
                _run_job,
                CronTrigger(month=month, day=day, hour=3, minute=0),
                args=[cmd], id=f"fs_{cmd}_m{month}", misfire_grace_time=86400,
            )

    sched.start()
    logger.info("Scheduler started — %d jobs registered", len(sched.get_jobs()))
    return sched
