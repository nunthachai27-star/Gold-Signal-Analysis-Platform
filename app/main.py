import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from openai import OpenAI
from app.config import get_settings
from app.db.session import make_engine, init_db, make_session_factory
from app.repository import Repository
from app.providers.oanda import OandaProvider
from app.analysis.openai_analyzer import OpenAiAnalyzer
from app.notify.telegram import TelegramNotifier
from app.pipeline import run_cycle

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

settings = get_settings()
engine = make_engine(settings.db_url)
init_db(engine)
repo = Repository(make_session_factory(engine))
provider = OandaProvider(settings.oanda_token, env=settings.oanda_env)
analyzer = OpenAiAnalyzer(OpenAI(api_key=settings.openai_api_key or "missing"),
                          settings.openai_model)
notifier = TelegramNotifier(settings.telegram_bot_token)
scheduler = BackgroundScheduler()


def _cycle():
    try:
        result = run_cycle(provider, analyzer, notifier, repo, settings,
                           datetime.now(timezone.utc))
        log.info("cycle result: %s", result)
    except Exception as exc:  # noqa: BLE001
        log.error("cycle failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(_cycle, "interval",
                      minutes=settings.scheduler_interval_min, id="cycle")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Gold Signal Analysis Platform", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analysis/run")
def analysis_run():
    return run_cycle(provider, analyzer, notifier, repo, settings,
                     datetime.now(timezone.utc))
