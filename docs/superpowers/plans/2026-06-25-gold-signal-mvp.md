# Gold Signal Analysis Platform MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้าง Python service ที่ดึงราคา XAUUSD จาก OANDA หลาย timeframe, คำนวณ indicator, ให้ OpenAI วิเคราะห์เป็นสัญญาณเทรด, ส่ง Telegram และบันทึกลงฐานข้อมูล — รันเป็นรอบด้วย scheduler

**Architecture:** Pipeline ฉีดผ่าน dependency injection: `OandaProvider` → `compute_indicators` → `build_snapshot` → `OpenAiAnalyzer` → `validate_and_filter` → `should_send` → `TelegramNotifier` + `Repository`. ทุก external boundary (OANDA, OpenAI, Telegram) เป็น interface ที่ inject http client/LLM client ได้ จึงทดสอบโดยไม่ยิง API จริง

**Tech Stack:** Python 3.11+, FastAPI, APScheduler, SQLAlchemy 2.x (SQLite), pandas + pandas-ta, requests, openai SDK, pydantic-settings, pytest

## Global Constraints

- Python 3.11+
- `numpy<2.0` — บังคับ เพราะ `pandas-ta==0.3.14b0` ใช้ `from numpy import NaN` ที่พังบน numpy 2.x
- `pandas-ta==0.3.14b0`
- Symbol มาตรฐานภายในระบบ = `XAU_USD` (รูปแบบ OANDA)
- Timeframe codes ภายในระบบ = `D1, H4, H1, M15, M5` (map ไป OANDA granularity ใน provider)
- ห้าม commit `.env` หรือไฟล์ `*.db` (มีใน `.gitignore` แล้ว)
- ทุก external API (OANDA, OpenAI, Telegram) ต้อง inject client ได้ และต้องถูก mock ในเทสต์ — ห้ามยิง network จริงในเทสต์
- เวลาในระบบเก็บเป็น UTC (`datetime` แบบ timezone-aware)

---

## File Structure

| ไฟล์ | ความรับผิดชอบ |
|------|----------------|
| `requirements.txt` | dependency list |
| `.env.example` | template config |
| `app/__init__.py` | package marker |
| `app/config.py` | โหลด settings จาก env (pydantic-settings) |
| `app/domain.py` | dataclass กลาง: `Candle`, `TimeframeIndicators`, `SignalDecision` |
| `app/db/models.py` | SQLAlchemy models |
| `app/db/session.py` | engine / session factory / init_db |
| `app/repository.py` | persistence helpers |
| `app/providers/base.py` | `PriceProvider` interface |
| `app/providers/oanda.py` | `OandaProvider` |
| `app/analysis/indicators.py` | `compute_indicators` |
| `app/analysis/snapshot.py` | `build_snapshot` |
| `app/analysis/base.py` | `Analyzer` interface |
| `app/analysis/openai_analyzer.py` | `OpenAiAnalyzer` + prompt/schema |
| `app/analysis/validator.py` | `validate_and_filter` |
| `app/analysis/dedup.py` | `should_send` |
| `app/notify/base.py` | `Notifier` interface |
| `app/notify/telegram.py` | `TelegramNotifier` + `format_signal` |
| `app/pipeline.py` | `run_cycle` orchestration |
| `app/main.py` | FastAPI app + scheduler wiring |
| `tests/...` | unit + integration tests |

---

### Task 1: Project scaffold + config

**Files:**
- Create: `requirements.txt`, `.env.example`, `app/__init__.py`, `app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic-settings) กับ property `timeframe_list -> list[str]`, และ `get_settings() -> Settings`

- [ ] **Step 1: Write requirements.txt**

```
fastapi==0.115.*
uvicorn==0.32.*
pydantic-settings==2.*
SQLAlchemy==2.*
APScheduler==3.*
pandas==2.*
numpy==1.26.*
pandas-ta==0.3.14b0
requests==2.*
openai==1.*
pytest==8.*
```

- [ ] **Step 2: Write .env.example**

```
OANDA_TOKEN=
OANDA_ENV=practice
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
TELEGRAM_BOT_TOKEN=
SYMBOL=XAU_USD
TIMEFRAMES=D1,H4,H1,M15,M5
SCHEDULER_INTERVAL_MIN=5
SIGNAL_THRESHOLD=55
COOLDOWN_MIN=30
DB_URL=sqlite:///./gold_signal.db
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_config.py
from app.config import Settings

def test_timeframe_list_parses_csv():
    s = Settings(timeframes="D1, H4 , M5")
    assert s.timeframe_list == ["D1", "H4", "M5"]

def test_defaults_present():
    s = Settings()
    assert s.symbol == "XAU_USD"
    assert s.signal_threshold == 55
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError: app.config)

- [ ] **Step 5: Create app/__init__.py (empty) and app/config.py**

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    oanda_token: str = ""
    oanda_env: str = "practice"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    telegram_bot_token: str = ""
    symbol: str = "XAU_USD"
    timeframes: str = "D1,H4,H1,M15,M5"
    scheduler_interval_min: int = 5
    signal_threshold: int = 55
    cooldown_min: int = 30
    db_url: str = "sqlite:///./gold_signal.db"

    @property
    def timeframe_list(self) -> list[str]:
        return [t.strip() for t in self.timeframes.split(",") if t.strip()]


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example app/__init__.py app/config.py tests/test_config.py
git commit -m "feat: project scaffold and settings"
```

---

### Task 2: Domain models

**Files:**
- Create: `app/domain.py`
- Test: `tests/test_domain.py`

**Interfaces:**
- Produces:
  - `Candle(symbol:str, timeframe:str, time:datetime, open:float, high:float, low:float, close:float, volume:float=0.0)`
  - `TimeframeIndicators(timeframe:str, close:float, ema_fast:float, ema_slow:float, rsi:float, macd:float, macd_signal:float, atr:float, swing_high:float, swing_low:float, trend:str)`
  - `SignalDecision(direction:str, entry:float, sl:float, tp1:float, tp2:float, buy_prob:float, sell_prob:float, type:str, reasoning:str)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_domain.py
from datetime import datetime, timezone
from app.domain import Candle, TimeframeIndicators, SignalDecision

def test_candle_fields():
    c = Candle("XAU_USD", "M5", datetime(2024, 1, 1, tzinfo=timezone.utc),
               1.0, 2.0, 0.5, 1.5)
    assert c.close == 1.5 and c.volume == 0.0

def test_signal_decision_fields():
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 60, 40, "Normal", "because")
    assert d.direction == "BUY" and d.tp2 == 2020
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_domain.py -v`
Expected: FAIL (ModuleNotFoundError: app.domain)

- [ ] **Step 3: Write app/domain.py**

```python
# app/domain.py
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    symbol: str
    timeframe: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class TimeframeIndicators:
    timeframe: str
    close: float
    ema_fast: float
    ema_slow: float
    rsi: float
    macd: float
    macd_signal: float
    atr: float
    swing_high: float
    swing_low: float
    trend: str  # "up" | "down" | "side"


@dataclass
class SignalDecision:
    direction: str  # "BUY" | "SELL" | "NONE"
    entry: float
    sl: float
    tp1: float
    tp2: float
    buy_prob: float
    sell_prob: float
    type: str  # "Scalp" | "Normal"
    reasoning: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_domain.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/domain.py tests/test_domain.py
git commit -m "feat: shared domain dataclasses"
```

---

### Task 3: Database models, session, repository

**Files:**
- Create: `app/db/__init__.py`, `app/db/models.py`, `app/db/session.py`, `app/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Consumes: `app.domain.Candle`, `app.domain.SignalDecision`
- Produces:
  - `app.db.session.make_engine(db_url:str)`, `init_db(engine)`, `make_session_factory(engine)`
  - `app.db.models.Base`, `PriceCandle`, `SignalHistory`, `Recipient`
  - `Repository(session_factory)` with:
    - `save_candles(candles: list[Candle]) -> int` (จำนวน row ใหม่ที่เพิ่ม, ข้าม duplicate)
    - `get_active_recipients() -> list[str]` (คืน list ของ telegram_chat_id)
    - `add_recipient(chat_id:str, name:str="") -> None`
    - `get_last_signal(symbol:str) -> SignalHistory | None`
    - `save_signal(symbol:str, decision:SignalDecision, summary:str, snapshot_json:str, generated_at:datetime) -> SignalHistory`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repository.py
from datetime import datetime, timezone
from app.db.session import make_engine, init_db, make_session_factory
from app.domain import Candle, SignalDecision
from app.repository import Repository

def make_repo():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return Repository(make_session_factory(engine))

def test_save_candles_dedupes():
    repo = make_repo()
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    c = Candle("XAU_USD", "M5", t, 1, 2, 0.5, 1.5)
    assert repo.save_candles([c]) == 1
    assert repo.save_candles([c]) == 0  # duplicate ignored

def test_recipients_roundtrip():
    repo = make_repo()
    repo.add_recipient("123", "me")
    assert repo.get_active_recipients() == ["123"]

def test_signal_save_and_last():
    repo = make_repo()
    assert repo.get_last_signal("XAU_USD") is None
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 60, 40, "Normal", "r")
    repo.save_signal("XAU_USD", d, "summary", "{}", datetime(2024, 1, 1, tzinfo=timezone.utc))
    last = repo.get_last_signal("XAU_USD")
    assert last.direction == "BUY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL (ModuleNotFoundError: app.db.session)

- [ ] **Step 3: Write app/db/__init__.py (empty) and app/db/models.py**

```python
# app/db/models.py
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PriceCandle(Base):
    __tablename__ = "price_candles"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(8))
    candle_time: Mapped[datetime] = mapped_column(DateTime)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "candle_time", name="uq_candle"),
    )


class SignalHistory(Base):
    __tablename__ = "signal_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20))
    signal_type: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(8))
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit_1: Mapped[float] = mapped_column(Float)
    take_profit_2: Mapped[float] = mapped_column(Float)
    buy_probability: Mapped[float] = mapped_column(Float)
    sell_probability: Mapped[float] = mapped_column(Float)
    timeframe_summary: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    snapshot_json: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="sent")


class Recipient(Base):
    __tablename__ = "recipients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
```

- [ ] **Step 4: Write app/db/session.py**

```python
# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base


def make_engine(db_url: str):
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, connect_args=connect_args, future=True)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
```

- [ ] **Step 5: Write app/repository.py**

```python
# app/repository.py
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db.models import PriceCandle, SignalHistory, Recipient
from app.domain import Candle, SignalDecision


class Repository:
    def __init__(self, session_factory):
        self._sf = session_factory

    def save_candles(self, candles: list[Candle]) -> int:
        added = 0
        with self._sf() as s:
            for c in candles:
                row = PriceCandle(
                    symbol=c.symbol, timeframe=c.timeframe, candle_time=c.time,
                    open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume,
                )
                s.add(row)
                try:
                    s.commit()
                    added += 1
                except IntegrityError:
                    s.rollback()
        return added

    def add_recipient(self, chat_id: str, name: str = "") -> None:
        with self._sf() as s:
            s.add(Recipient(telegram_chat_id=chat_id, name=name, is_active=True,
                            created_at=datetime.now(timezone.utc)))
            s.commit()

    def get_active_recipients(self) -> list[str]:
        with self._sf() as s:
            rows = s.execute(
                select(Recipient).where(Recipient.is_active.is_(True))
            ).scalars().all()
            return [r.telegram_chat_id for r in rows]

    def get_last_signal(self, symbol: str) -> SignalHistory | None:
        with self._sf() as s:
            return s.execute(
                select(SignalHistory)
                .where(SignalHistory.symbol == symbol)
                .order_by(SignalHistory.generated_at.desc())
            ).scalars().first()

    def save_signal(self, symbol: str, decision: SignalDecision, summary: str,
                    snapshot_json: str, generated_at: datetime) -> SignalHistory:
        with self._sf() as s:
            row = SignalHistory(
                symbol=symbol, signal_type=decision.type, direction=decision.direction,
                entry_price=decision.entry, stop_loss=decision.sl,
                take_profit_1=decision.tp1, take_profit_2=decision.tp2,
                buy_probability=decision.buy_prob, sell_probability=decision.sell_prob,
                timeframe_summary=summary, reasoning=decision.reasoning,
                snapshot_json=snapshot_json, generated_at=generated_at, status="sent",
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            return row
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_repository.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add app/db tests/test_repository.py app/repository.py
git commit -m "feat: db models, session, repository"
```

---

### Task 4: PriceProvider interface + OandaProvider

**Files:**
- Create: `app/providers/__init__.py`, `app/providers/base.py`, `app/providers/oanda.py`
- Test: `tests/test_oanda.py`

**Interfaces:**
- Consumes: `app.domain.Candle`
- Produces:
  - `app.providers.base.PriceProvider` (abstract) with `get_candles(symbol:str, timeframe:str, count:int=250) -> list[Candle]`
  - `app.providers.oanda.OandaProvider(token:str, env:str="practice", session=None)` implementing it
  - `OandaProvider._parse(symbol, timeframe, data:dict) -> list[Candle]` (staticmethod, parses OANDA response)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_oanda.py
from app.providers.oanda import OandaProvider

SAMPLE = {
    "candles": [
        {"complete": True, "time": "2024-01-02T00:00:00.000000000Z",
         "volume": 10, "mid": {"o": "2050.1", "h": "2060.2", "l": "2045.0", "c": "2055.5"}},
        {"complete": False, "time": "2024-01-03T00:00:00.000000000Z",
         "volume": 3, "mid": {"o": "2055.5", "h": "2058.0", "l": "2054.0", "c": "2057.0"}},
    ]
}

def test_parse_skips_incomplete_and_maps_fields():
    candles = OandaProvider._parse("XAU_USD", "D1", SAMPLE)
    assert len(candles) == 1
    c = candles[0]
    assert c.close == 2055.5 and c.high == 2060.2
    assert c.timeframe == "D1" and c.symbol == "XAU_USD"
    assert c.time.year == 2024 and c.time.hour == 0

class _FakeResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

class _FakeSession:
    def __init__(self, payload): self.payload = payload; self.calls = []
    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        return _FakeResp(self.payload)

def test_get_candles_calls_correct_endpoint():
    sess = _FakeSession(SAMPLE)
    p = OandaProvider("tok", env="practice", session=sess)
    candles = p.get_candles("XAU_USD", "H4", count=100)
    assert len(candles) == 1
    url, params, headers = sess.calls[0]
    assert "instruments/XAU_USD/candles" in url
    assert params["granularity"] == "H4" and params["count"] == 100
    assert headers["Authorization"] == "Bearer tok"
    assert "api-fxpractice.oanda.com" in url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_oanda.py -v`
Expected: FAIL (ModuleNotFoundError: app.providers.oanda)

- [ ] **Step 3: Write app/providers/__init__.py (empty) and app/providers/base.py**

```python
# app/providers/base.py
from abc import ABC, abstractmethod
from app.domain import Candle


class PriceProvider(ABC):
    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, count: int = 250) -> list[Candle]:
        ...
```

- [ ] **Step 4: Write app/providers/oanda.py**

```python
# app/providers/oanda.py
from datetime import datetime, timezone
import requests
from app.domain import Candle
from app.providers.base import PriceProvider

GRANULARITY = {
    "W1": "W", "D1": "D", "H4": "H4", "H1": "H1",
    "M30": "M30", "M15": "M15", "M5": "M5", "M1": "M1",
}
HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaProvider(PriceProvider):
    def __init__(self, token: str, env: str = "practice", session=None):
        self.token = token
        self.host = HOSTS[env]
        self.session = session or requests.Session()

    def get_candles(self, symbol: str, timeframe: str, count: int = 250) -> list[Candle]:
        url = f"{self.host}/v3/instruments/{symbol}/candles"
        params = {"granularity": GRANULARITY[timeframe], "count": count, "price": "M"}
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.session.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        return self._parse(symbol, timeframe, resp.json())

    @staticmethod
    def _parse(symbol: str, timeframe: str, data: dict) -> list[Candle]:
        out = []
        for c in data.get("candles", []):
            if not c.get("complete", True):
                continue
            mid = c["mid"]
            ts = datetime.strptime(c["time"][:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc)
            out.append(Candle(
                symbol=symbol, timeframe=timeframe, time=ts,
                open=float(mid["o"]), high=float(mid["h"]),
                low=float(mid["l"]), close=float(mid["c"]),
                volume=float(c.get("volume", 0)),
            ))
        return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_oanda.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add app/providers tests/test_oanda.py
git commit -m "feat: PriceProvider interface and OANDA implementation"
```

---

### Task 5: Indicator computation

**Files:**
- Create: `app/analysis/__init__.py`, `app/analysis/indicators.py`
- Test: `tests/test_indicators.py`

**Interfaces:**
- Consumes: `app.domain.Candle`, `app.domain.TimeframeIndicators`
- Produces: `compute_indicators(candles: list[Candle], ema_fast:int=50, ema_slow:int=200, rsi_len:int=14, atr_len:int=14, swing_lookback:int=20) -> TimeframeIndicators`
  - `trend` = `"up"` ถ้า `close > ema_fast > ema_slow`, `"down"` ถ้า `close < ema_fast < ema_slow`, ไม่งั้น `"side"`
  - ฟิลด์ NaN ใดๆ fallback เป็นค่า `close` ล่าสุด (ema/macd) หรือ `50.0` (rsi) หรือ `0.0` (atr)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_indicators.py
from datetime import datetime, timezone, timedelta
from app.domain import Candle
from app.analysis.indicators import compute_indicators

def _series(prices):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    out = []
    for i, p in enumerate(prices):
        out.append(Candle("XAU_USD", "H1", base + timedelta(hours=i),
                           open=p, high=p + 1, low=p - 1, close=p, volume=1))
    return out

def test_uptrend_detected():
    candles = _series([2000 + i for i in range(120)])  # steadily rising
    ind = compute_indicators(candles, ema_fast=10, ema_slow=30, swing_lookback=10)
    assert ind.trend == "up"
    assert ind.ema_fast > ind.ema_slow
    assert ind.swing_high >= ind.swing_low
    assert ind.timeframe == "H1"

def test_downtrend_detected():
    candles = _series([2200 - i for i in range(120)])  # steadily falling
    ind = compute_indicators(candles, ema_fast=10, ema_slow=30, swing_lookback=10)
    assert ind.trend == "down"
    assert ind.ema_fast < ind.ema_slow

def test_fields_never_nan():
    candles = _series([2000 + (i % 5) for i in range(60)])
    ind = compute_indicators(candles, ema_fast=10, ema_slow=30)
    for v in [ind.ema_fast, ind.ema_slow, ind.rsi, ind.macd,
              ind.macd_signal, ind.atr]:
        assert v == v  # not NaN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_indicators.py -v`
Expected: FAIL (ModuleNotFoundError: app.analysis.indicators)

- [ ] **Step 3: Write app/analysis/__init__.py (empty) and app/analysis/indicators.py**

```python
# app/analysis/indicators.py
import pandas as pd
import pandas_ta as ta
from app.domain import Candle, TimeframeIndicators


def _last(series, fallback: float) -> float:
    if series is None or len(series) == 0:
        return fallback
    val = series.iloc[-1]
    return float(val) if val == val else fallback  # NaN check


def compute_indicators(candles: list[Candle], ema_fast: int = 50,
                       ema_slow: int = 200, rsi_len: int = 14,
                       atr_len: int = 14, swing_lookback: int = 20) -> TimeframeIndicators:
    df = pd.DataFrame([{
        "open": c.open, "high": c.high, "low": c.low,
        "close": c.close, "volume": c.volume,
    } for c in candles])

    close = df["close"]
    last_close = float(close.iloc[-1])

    ef = _last(ta.ema(close, length=min(ema_fast, len(df))), last_close)
    es = _last(ta.ema(close, length=min(ema_slow, len(df))), last_close)
    rsi = _last(ta.rsi(close, length=rsi_len), 50.0)
    atr = _last(ta.atr(df["high"], df["low"], close, length=atr_len), 0.0)

    macd_df = ta.macd(close)
    if macd_df is not None and not macd_df.empty:
        macd = _last(macd_df.iloc[:, 0], 0.0)         # MACD line
        macd_signal = _last(macd_df.iloc[:, 2], 0.0)  # signal line
    else:
        macd = macd_signal = 0.0

    window = df.tail(swing_lookback)
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())

    if last_close > ef > es:
        trend = "up"
    elif last_close < ef < es:
        trend = "down"
    else:
        trend = "side"

    return TimeframeIndicators(
        timeframe=candles[-1].timeframe, close=last_close,
        ema_fast=ef, ema_slow=es, rsi=rsi, macd=macd,
        macd_signal=macd_signal, atr=atr,
        swing_high=swing_high, swing_low=swing_low, trend=trend,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_indicators.py -v`
Expected: PASS (3 passed)

> หากเกิด `ImportError: cannot import name 'NaN' from 'numpy'` แปลว่า numpy เป็น 2.x — รัน `pip install "numpy<2.0"` ตาม Global Constraints

- [ ] **Step 5: Commit**

```bash
git add app/analysis/__init__.py app/analysis/indicators.py tests/test_indicators.py
git commit -m "feat: multi-indicator computation per timeframe"
```

---

### Task 6: Snapshot builder

**Files:**
- Create: `app/analysis/snapshot.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `app.domain.TimeframeIndicators`
- Produces:
  - `build_snapshot(symbol:str, indicators_by_tf: dict[str, TimeframeIndicators], current_price: float) -> dict`
    - คืน dict: `{"symbol", "current_price", "timeframes": {tf: {trend, close, rsi, macd_state, ema_fast, ema_slow, atr, swing_high, swing_low}}}`
    - `macd_state` = `"bullish"` ถ้า `macd > macd_signal` ไม่งั้น `"bearish"`
  - `summarize(indicators_by_tf: dict[str, TimeframeIndicators]) -> str` คืนข้อความเช่น `"D1 up / H4 up / M5 side"`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_snapshot.py
from app.domain import TimeframeIndicators
from app.analysis.snapshot import build_snapshot, summarize

def _ind(tf, trend, macd, sig):
    return TimeframeIndicators(tf, 2000, 2001, 1999, 55, macd, sig, 5,
                               2010, 1990, trend)

def test_snapshot_structure():
    ind = {"D1": _ind("D1", "up", 1.0, 0.5), "M5": _ind("M5", "side", -1.0, 0.0)}
    snap = build_snapshot("XAU_USD", ind, 2000.0)
    assert snap["symbol"] == "XAU_USD"
    assert snap["current_price"] == 2000.0
    assert snap["timeframes"]["D1"]["macd_state"] == "bullish"
    assert snap["timeframes"]["M5"]["macd_state"] == "bearish"
    assert snap["timeframes"]["D1"]["trend"] == "up"

def test_summarize_format():
    ind = {"D1": _ind("D1", "up", 1, 0), "M5": _ind("M5", "side", 1, 0)}
    assert summarize(ind) == "D1 up / M5 side"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: FAIL (ModuleNotFoundError: app.analysis.snapshot)

- [ ] **Step 3: Write app/analysis/snapshot.py**

```python
# app/analysis/snapshot.py
from app.domain import TimeframeIndicators


def build_snapshot(symbol: str, indicators_by_tf: dict[str, TimeframeIndicators],
                   current_price: float) -> dict:
    tfs = {}
    for tf, ind in indicators_by_tf.items():
        tfs[tf] = {
            "trend": ind.trend,
            "close": round(ind.close, 3),
            "rsi": round(ind.rsi, 2),
            "macd_state": "bullish" if ind.macd > ind.macd_signal else "bearish",
            "ema_fast": round(ind.ema_fast, 3),
            "ema_slow": round(ind.ema_slow, 3),
            "atr": round(ind.atr, 3),
            "swing_high": round(ind.swing_high, 3),
            "swing_low": round(ind.swing_low, 3),
        }
    return {"symbol": symbol, "current_price": round(current_price, 3), "timeframes": tfs}


def summarize(indicators_by_tf: dict[str, TimeframeIndicators]) -> str:
    return " / ".join(f"{tf} {ind.trend}" for tf, ind in indicators_by_tf.items())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/analysis/snapshot.py tests/test_snapshot.py
git commit -m "feat: compact multi-timeframe snapshot builder"
```

---

### Task 7: Analyzer interface + OpenAI analyzer

**Files:**
- Create: `app/analysis/base.py`, `app/analysis/openai_analyzer.py`
- Test: `tests/test_openai_analyzer.py`

**Interfaces:**
- Consumes: `app.domain.SignalDecision`
- Produces:
  - `app.analysis.base.Analyzer` (abstract) with `analyze(snapshot:dict) -> SignalDecision`
  - `app.analysis.openai_analyzer.OpenAiAnalyzer(client, model:str)` implementing it; `client` ต้องมี `client.chat.completions.create(...)` ที่คืน object ซึ่ง `.choices[0].message.content` เป็น JSON string ตรงกับฟิลด์ของ `SignalDecision`
  - module-level `SYSTEM_PROMPT: str` และ `SIGNAL_SCHEMA: dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_openai_analyzer.py
import json
from app.analysis.openai_analyzer import OpenAiAnalyzer

class _Msg:
    def __init__(self, content): self.content = content
class _Choice:
    def __init__(self, content): self.message = _Msg(content)
class _Resp:
    def __init__(self, content): self.choices = [_Choice(content)]

class _FakeCompletions:
    def __init__(self, payload): self.payload = payload; self.kwargs = None
    def create(self, **kwargs):
        self.kwargs = kwargs
        return _Resp(json.dumps(self.payload))

class _FakeChat:
    def __init__(self, payload): self.completions = _FakeCompletions(payload)
class _FakeClient:
    def __init__(self, payload): self.chat = _FakeChat(payload)

PAYLOAD = {
    "direction": "BUY", "entry": 2000.0, "sl": 1990.0, "tp1": 2010.0,
    "tp2": 2020.0, "buy_prob": 62.0, "sell_prob": 38.0,
    "type": "Normal", "reasoning": "higher TFs aligned up",
}

def test_analyze_returns_signal_decision():
    client = _FakeClient(PAYLOAD)
    analyzer = OpenAiAnalyzer(client, "gpt-4o-mini")
    snap = {"symbol": "XAU_USD", "current_price": 2000.0, "timeframes": {}}
    decision = analyzer.analyze(snap)
    assert decision.direction == "BUY"
    assert decision.buy_prob == 62.0
    assert decision.type == "Normal"
    # passes correct model + uses structured output
    assert client.chat.completions.kwargs["model"] == "gpt-4o-mini"
    assert client.chat.completions.kwargs["response_format"]["type"] == "json_schema"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_openai_analyzer.py -v`
Expected: FAIL (ModuleNotFoundError: app.analysis.openai_analyzer)

- [ ] **Step 3: Write app/analysis/base.py**

```python
# app/analysis/base.py
from abc import ABC, abstractmethod
from app.domain import SignalDecision


class Analyzer(ABC):
    @abstractmethod
    def analyze(self, snapshot: dict) -> SignalDecision:
        ...
```

- [ ] **Step 4: Write app/analysis/openai_analyzer.py**

```python
# app/analysis/openai_analyzer.py
import json
from app.analysis.base import Analyzer
from app.domain import SignalDecision

SYSTEM_PROMPT = (
    "You are an expert XAUUSD (gold) multi-timeframe technical analyst. "
    "You receive a JSON snapshot of indicators across timeframes "
    "(D1, H4, H1, M15, M5). Decide a single actionable trade.\n"
    "Rules:\n"
    "- Use higher timeframes (D1/H4/H1) for directional bias and lower "
    "timeframes (M15/M5) for entry timing.\n"
    "- If timeframes conflict and there is no clear edge, return direction "
    "\"NONE\".\n"
    "- For BUY: sl < entry < tp1 < tp2. For SELL: sl > entry > tp1 > tp2.\n"
    "- entry must be near current_price.\n"
    "- buy_prob + sell_prob must equal 100.\n"
    "- type is \"Scalp\" when driven mainly by M15/M5, otherwise \"Normal\".\n"
    "- Base sl/tp distances on the provided atr and swing levels.\n"
    "Return ONLY the structured JSON object."
)

SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "direction": {"type": "string", "enum": ["BUY", "SELL", "NONE"]},
        "entry": {"type": "number"},
        "sl": {"type": "number"},
        "tp1": {"type": "number"},
        "tp2": {"type": "number"},
        "buy_prob": {"type": "number"},
        "sell_prob": {"type": "number"},
        "type": {"type": "string", "enum": ["Scalp", "Normal"]},
        "reasoning": {"type": "string"},
    },
    "required": ["direction", "entry", "sl", "tp1", "tp2", "buy_prob",
                 "sell_prob", "type", "reasoning"],
    "additionalProperties": False,
}


class OpenAiAnalyzer(Analyzer):
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def analyze(self, snapshot: dict) -> SignalDecision:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(snapshot)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "signal", "schema": SIGNAL_SCHEMA,
                                "strict": True},
            },
            temperature=0.2,
        )
        data = json.loads(resp.choices[0].message.content)
        return SignalDecision(**data)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_openai_analyzer.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add app/analysis/base.py app/analysis/openai_analyzer.py tests/test_openai_analyzer.py
git commit -m "feat: Analyzer interface and OpenAI structured-output analyzer"
```

---

### Task 8: Validator

**Files:**
- Create: `app/analysis/validator.py`
- Test: `tests/test_validator.py`

**Interfaces:**
- Consumes: `app.domain.SignalDecision`
- Produces: `validate_and_filter(decision: SignalDecision, current_price: float, threshold: float) -> tuple[bool, str]`
  - คืน `(True, "ok")` ถ้าผ่าน, ไม่งั้น `(False, reason)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validator.py
from app.domain import SignalDecision
from app.analysis.validator import validate_and_filter

def buy(buy_prob=62, entry=2000, sl=1990, tp1=2010, tp2=2020):
    return SignalDecision("BUY", entry, sl, tp1, tp2, buy_prob, 100 - buy_prob,
                          "Normal", "r")

def test_valid_buy_passes():
    ok, reason = validate_and_filter(buy(), 2000.0, 55)
    assert ok is True and reason == "ok"

def test_none_direction_rejected():
    d = SignalDecision("NONE", 0, 0, 0, 0, 50, 50, "Normal", "")
    ok, _ = validate_and_filter(d, 2000.0, 55)
    assert ok is False

def test_below_threshold_rejected():
    ok, reason = validate_and_filter(buy(buy_prob=52), 2000.0, 55)
    assert ok is False and reason == "below threshold"

def test_bad_level_order_rejected():
    ok, reason = validate_and_filter(buy(sl=2005), 2000.0, 55)  # sl above entry
    assert ok is False and reason == "bad levels"

def test_prob_sum_invalid_rejected():
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 62, 30, "Normal", "r")
    ok, reason = validate_and_filter(d, 2000.0, 55)
    assert ok is False and reason == "prob sum invalid"

def test_entry_too_far_rejected():
    ok, reason = validate_and_filter(buy(entry=2000), 2500.0, 55)
    assert ok is False and reason == "entry too far from price"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validator.py -v`
Expected: FAIL (ModuleNotFoundError: app.analysis.validator)

- [ ] **Step 3: Write app/analysis/validator.py**

```python
# app/analysis/validator.py
from app.domain import SignalDecision


def validate_and_filter(decision: SignalDecision, current_price: float,
                        threshold: float) -> tuple[bool, str]:
    if decision.direction not in ("BUY", "SELL"):
        return False, "no direction"

    winning = decision.buy_prob if decision.direction == "BUY" else decision.sell_prob
    if winning < threshold:
        return False, "below threshold"

    if abs(decision.buy_prob + decision.sell_prob - 100) > 1:
        return False, "prob sum invalid"

    if decision.direction == "BUY":
        ordered = decision.sl < decision.entry < decision.tp1 < decision.tp2
    else:
        ordered = decision.sl > decision.entry > decision.tp1 > decision.tp2
    if not ordered:
        return False, "bad levels"

    if current_price > 0 and abs(decision.entry - current_price) / current_price > 0.02:
        return False, "entry too far from price"

    return True, "ok"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validator.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/analysis/validator.py tests/test_validator.py
git commit -m "feat: signal validator and threshold filter"
```

---

### Task 9: Dedup / cooldown

**Files:**
- Create: `app/analysis/dedup.py`
- Test: `tests/test_dedup.py`

**Interfaces:**
- Produces: `should_send(direction:str, last_direction:str|None, last_time, now, cooldown_min:int) -> bool`
  - `True` ถ้า `last_direction` เป็น None, หรือ direction ต่างจากเดิม, หรือเวลาผ่านไป ≥ cooldown

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dedup.py
from datetime import datetime, timezone, timedelta
from app.analysis.dedup import should_send

NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

def test_first_signal_sends():
    assert should_send("BUY", None, None, NOW, 30) is True

def test_direction_change_sends():
    last = NOW - timedelta(minutes=5)
    assert should_send("SELL", "BUY", last, NOW, 30) is True

def test_same_direction_within_cooldown_blocked():
    last = NOW - timedelta(minutes=10)
    assert should_send("BUY", "BUY", last, NOW, 30) is False

def test_same_direction_after_cooldown_sends():
    last = NOW - timedelta(minutes=31)
    assert should_send("BUY", "BUY", last, NOW, 30) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: FAIL (ModuleNotFoundError: app.analysis.dedup)

- [ ] **Step 3: Write app/analysis/dedup.py**

```python
# app/analysis/dedup.py
from datetime import datetime


def should_send(direction: str, last_direction: str | None,
                last_time: datetime | None, now: datetime,
                cooldown_min: int) -> bool:
    if last_direction is None or last_time is None:
        return True
    if direction != last_direction:
        return True
    elapsed_min = (now - last_time).total_seconds() / 60
    return elapsed_min >= cooldown_min
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/analysis/dedup.py tests/test_dedup.py
git commit -m "feat: dedup and cooldown gate"
```

---

### Task 10: Telegram notifier + message format

**Files:**
- Create: `app/notify/__init__.py`, `app/notify/base.py`, `app/notify/telegram.py`
- Test: `tests/test_telegram.py`

**Interfaces:**
- Consumes: `app.domain.SignalDecision`
- Produces:
  - `app.notify.base.Notifier` (abstract) with `send(chat_id:str, text:str) -> None`
  - `app.notify.telegram.TelegramNotifier(bot_token:str, session=None)` implementing it
  - `format_signal(decision: SignalDecision, symbol:str, summary:str, generated_at) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_telegram.py
from datetime import datetime, timezone
from app.domain import SignalDecision
from app.notify.telegram import TelegramNotifier, format_signal

def test_format_contains_key_lines():
    d = SignalDecision("BUY", 2000, 1990, 2010, 2020, 62, 38, "Normal", "r")
    text = format_signal(d, "XAU_USD", "D1 up / M5 side",
                         datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert "XAU_USD" in text
    assert "BUY" in text and "2000" in text
    assert "SL" in text and "1990" in text
    assert "TP1" in text and "TP2" in text
    assert "62" in text and "38" in text
    assert "D1 up / M5 side" in text

class _FakeResp:
    def raise_for_status(self): pass
    def json(self): return {"ok": True}
class _FakeSession:
    def __init__(self): self.calls = []
    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json)); return _FakeResp()

def test_send_posts_to_telegram_api():
    sess = _FakeSession()
    n = TelegramNotifier("BOTTOKEN", session=sess)
    n.send("123", "hello")
    url, payload = sess.calls[0]
    assert "botBOTTOKEN/sendMessage" in url
    assert payload == {"chat_id": "123", "text": "hello"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_telegram.py -v`
Expected: FAIL (ModuleNotFoundError: app.notify.telegram)

- [ ] **Step 3: Write app/notify/__init__.py (empty) and app/notify/base.py**

```python
# app/notify/base.py
from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, chat_id: str, text: str) -> None:
        ...
```

- [ ] **Step 4: Write app/notify/telegram.py**

```python
# app/notify/telegram.py
import requests
from app.domain import SignalDecision
from app.notify.base import Notifier


def format_signal(decision: SignalDecision, symbol: str, summary: str,
                  generated_at) -> str:
    return (
        f"\U0001F4C8 {symbol} Signal ({decision.type})\n"
        f"{decision.direction} {decision.entry:g}\n"
        f"SL {decision.sl:g}\n"
        f"TP1 {decision.tp1:g}\n"
        f"TP2 {decision.tp2:g}\n"
        f"BUY win probability: {decision.buy_prob:g}%\n"
        f"SELL win probability: {decision.sell_prob:g}%\n"
        f"Timeframe Bias: {summary}\n"
        f"Time: {generated_at:%Y-%m-%d %H:%M UTC}"
    )


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, session=None):
        self.bot_token = bot_token
        self.session = session or requests.Session()

    def send(self, chat_id: str, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        resp = self.session.post(url, json={"chat_id": chat_id, "text": text},
                                 timeout=10)
        resp.raise_for_status()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_telegram.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add app/notify tests/test_telegram.py
git commit -m "feat: Telegram notifier and signal message format"
```

---

### Task 11: Pipeline orchestration + FastAPI app + integration test

**Files:**
- Create: `app/pipeline.py`, `app/main.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: ทุก component ก่อนหน้า + `app.config.Settings`, `app.repository.Repository`
- Produces:
  - `run_cycle(provider, analyzer, notifier, repo, settings, now) -> dict` คืนสรุปผล: `{"status": "sent"|"skipped"|"rejected"|"no_data", "reason": str, "signal_id": int|None}`
  - ลำดับ: ดึง candles ทุก TF → save_candles → compute_indicators ต่อ TF → build_snapshot → analyzer.analyze → validate_and_filter → should_send → save_signal + notifier.send ให้ทุก recipient
  - `app/main.py`: FastAPI `app` + `GET /health` คืน `{"status":"ok"}` + `POST /analysis/run` รัน 1 cycle, และ APScheduler ตั้ง interval = `settings.scheduler_interval_min`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
from datetime import datetime, timezone, timedelta
from app.domain import Candle, SignalDecision
from app.config import Settings
from app.db.session import make_engine, init_db, make_session_factory
from app.repository import Repository
from app.pipeline import run_cycle

NOW = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

class FakeProvider:
    def get_candles(self, symbol, timeframe, count=250):
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [Candle(symbol, timeframe, base + timedelta(hours=i),
                       2000 + i, 2001 + i, 1999 + i, 2000 + i, 1)
                for i in range(120)]

class FakeAnalyzer:
    def __init__(self, decision): self.decision = decision
    def analyze(self, snapshot): return self.decision

class FakeNotifier:
    def __init__(self): self.sent = []
    def send(self, chat_id, text): self.sent.append((chat_id, text))

def make_repo():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    return Repository(make_session_factory(engine))

def settings():
    return Settings(timeframes="D1,M5", signal_threshold=55, cooldown_min=30)

def test_valid_signal_is_sent_and_saved():
    repo = make_repo()
    repo.add_recipient("123")
    decision = SignalDecision("BUY", 2119, 2110, 2130, 2140, 62, 38, "Normal", "r")
    notifier = FakeNotifier()
    result = run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier,
                       repo, settings(), NOW)
    assert result["status"] == "sent"
    assert len(notifier.sent) == 1
    assert repo.get_last_signal("XAU_USD").direction == "BUY"

def test_rejected_signal_not_sent():
    repo = make_repo()
    repo.add_recipient("123")
    decision = SignalDecision("NONE", 0, 0, 0, 0, 50, 50, "Normal", "")
    notifier = FakeNotifier()
    result = run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier,
                       repo, settings(), NOW)
    assert result["status"] == "rejected"
    assert notifier.sent == []

def test_duplicate_within_cooldown_skipped():
    repo = make_repo()
    repo.add_recipient("123")
    decision = SignalDecision("BUY", 2119, 2110, 2130, 2140, 62, 38, "Normal", "r")
    notifier = FakeNotifier()
    run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier, repo, settings(), NOW)
    result = run_cycle(FakeProvider(), FakeAnalyzer(decision), notifier, repo,
                       settings(), NOW + timedelta(minutes=5))
    assert result["status"] == "skipped"
    assert len(notifier.sent) == 1  # only the first one
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL (ModuleNotFoundError: app.pipeline)

- [ ] **Step 3: Write app/pipeline.py**

```python
# app/pipeline.py
import json
import logging
from app.analysis.indicators import compute_indicators
from app.analysis.snapshot import build_snapshot, summarize
from app.analysis.validator import validate_and_filter
from app.analysis.dedup import should_send

log = logging.getLogger("pipeline")


def run_cycle(provider, analyzer, notifier, repo, settings, now) -> dict:
    symbol = settings.symbol
    indicators_by_tf = {}
    current_price = None

    for tf in settings.timeframe_list:
        candles = provider.get_candles(symbol, tf, count=250)
        if not candles:
            continue
        repo.save_candles(candles)
        indicators_by_tf[tf] = compute_indicators(candles)
        current_price = candles[-1].close

    if not indicators_by_tf or current_price is None:
        return {"status": "no_data", "reason": "no candles", "signal_id": None}

    snapshot = build_snapshot(symbol, indicators_by_tf, current_price)
    summary = summarize(indicators_by_tf)

    decision = analyzer.analyze(snapshot)

    ok, reason = validate_and_filter(decision, current_price, settings.signal_threshold)
    if not ok:
        log.info("signal rejected: %s", reason)
        return {"status": "rejected", "reason": reason, "signal_id": None}

    last = repo.get_last_signal(symbol)
    last_dir = last.direction if last else None
    last_time = last.generated_at if last else None
    # normalize naive datetime from sqlite to aware
    if last_time is not None and last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=now.tzinfo)

    if not should_send(decision.direction, last_dir, last_time, now,
                       settings.cooldown_min):
        return {"status": "skipped", "reason": "cooldown", "signal_id": None}

    row = repo.save_signal(symbol, decision, summary, json.dumps(snapshot), now)
    text = _format_for_send(decision, symbol, summary, now)
    for chat_id in repo.get_active_recipients():
        try:
            notifier.send(chat_id, text)
        except Exception as exc:  # noqa: BLE001
            log.error("telegram send failed for %s: %s", chat_id, exc)

    return {"status": "sent", "reason": "ok", "signal_id": row.id}


def _format_for_send(decision, symbol, summary, now):
    from app.notify.telegram import format_signal
    return format_signal(decision, symbol, summary, now)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write app/main.py**

```python
# app/main.py
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
analyzer = OpenAiAnalyzer(OpenAI(api_key=settings.openai_api_key), settings.openai_model)
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
```

- [ ] **Step 6: Verify app imports cleanly**

Run: `python -c "import app.main"`
Expected: ไม่มี error (import สำเร็จ; ไม่ต้องมี API key จริงเพราะยังไม่ยิง request)

- [ ] **Step 7: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS ทั้งหมด

- [ ] **Step 8: Commit**

```bash
git add app/pipeline.py app/main.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestration, FastAPI app, scheduler"
```

---

### Task 12: README + run instructions

**Files:**
- Create: `README.md`

**Interfaces:** none (documentation)

- [ ] **Step 1: Write README.md**

````markdown
# Gold Signal Analysis Platform (MVP)

วิเคราะห์ XAUUSD หลาย timeframe ด้วย OANDA data + OpenAI แล้วส่งสัญญาณเข้า Telegram

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env         # แล้วเติมค่า token
```

## Run tests

```bash
python -m pytest -v
```

## Run service

```bash
uvicorn app.main:app --reload
```

- `GET /health` — health check
- `POST /analysis/run` — รันวิเคราะห์ 1 รอบทันที
- Scheduler รันอัตโนมัติทุก `SCHEDULER_INTERVAL_MIN` นาที

## เพิ่มผู้รับ Telegram

```python
from app.config import get_settings
from app.db.session import make_engine, init_db, make_session_factory
from app.repository import Repository
s = get_settings()
e = make_engine(s.db_url); init_db(e)
Repository(make_session_factory(e)).add_recipient("<telegram_chat_id>", "me")
```
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup and run instructions"
```

---

## Self-Review Notes

**Spec coverage:**
- Data ingestion (server-pull) → Task 4 ✅
- Multi-timeframe analysis → Tasks 5–6 ✅
- LLM full analysis (Entry/SL/TP/probability/type) → Task 7 ✅
- Validation + threshold → Task 8 ✅
- Dedup/cooldown → Task 9 ✅
- Telegram notification → Task 10 ✅
- Persistence (candles/signals/recipients) → Task 3 ✅
- Scheduler trigger + manual run → Task 11 ✅
- Config-driven params → Task 1 ✅
- Error handling (provider/LLM/telegram failures) → run_cycle try/except + main `_cycle` ✅

**Out of scope (ตาม spec, ยืนยันไม่ทำใน MVP):** Dashboard, webhook ingestion, result tracking, LINE, multi-user, backtest, AI explanation layer

**Type consistency:** `SignalDecision` fields (direction/entry/sl/tp1/tp2/buy_prob/sell_prob/type/reasoning) ตรงกันทุก task (7→8→10→11) และตรงกับ OpenAI schema keys ✅
