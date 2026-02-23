import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 4
preload_app = False


def on_starting(server):
    from app.scheduler import init_scheduler
    init_scheduler()
