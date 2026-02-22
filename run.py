import os

from app import create_app
from app.scheduler import init_scheduler

app = create_app()

if __name__ == "__main__":
    init_scheduler()
    app.run(port=int(os.environ.get("PORT", 5000)))
