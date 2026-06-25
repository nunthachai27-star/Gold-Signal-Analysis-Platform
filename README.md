# Gold Signal Analysis Platform (MVP)

วิเคราะห์ XAUUSD หลาย timeframe ด้วยข้อมูลจาก **OANDA v20** + วิเคราะห์ด้วย **OpenAI** แล้วส่งสัญญาณเข้า **Telegram** อัตโนมัติ รันเป็นรอบด้วย scheduler

## สถาปัตยกรรม

```
[Scheduler] → OANDA (OHLC หลาย TF) → คำนวณ indicator (EMA/RSI/MACD/ATR)
   → สร้าง snapshot → OpenAI วิเคราะห์ (JSON) → validate + threshold
   → dedup/cooldown → Telegram + บันทึก DB
```

ทุก external boundary เป็น interface: `PriceProvider` (OANDA), `Analyzer` (OpenAI),
`Notifier` (Telegram) — สลับ implementation ได้โดยไม่แตะ engine

## Setup

```bash
py -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env           # แล้วเติม token (OANDA / OpenAI / Telegram)
```

> ใช้ Python 3.11+ (พัฒนา/ทดสอบบน 3.14). คำนวณ indicator เองด้วย pandas/numpy
> จึงไม่ผูกกับ pandas-ta

## รันเทสต์

```bash
python -m pytest -v
```

## รัน service

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

## Config (.env)

| Key | คำอธิบาย | ค่าเริ่มต้น |
|-----|----------|------------|
| `OANDA_TOKEN` | API token (จาก practice account) | (จำเป็น) |
| `OANDA_ENV` | practice / live | practice |
| `OPENAI_API_KEY` | คีย์ OpenAI | (จำเป็น) |
| `OPENAI_MODEL` | model id | gpt-4o-mini |
| `TELEGRAM_BOT_TOKEN` | bot token | (จำเป็น) |
| `SYMBOL` | สัญลักษณ์ | XAU_USD |
| `TIMEFRAMES` | ชุด TF | D1,H4,H1,M15,M5 |
| `SCHEDULER_INTERVAL_MIN` | ความถี่รอบ (นาที) | 5 |
| `SIGNAL_THRESHOLD` | prob ขั้นต่ำที่จะส่ง | 55 |
| `COOLDOWN_MIN` | กันส่งซ้ำ (นาที) | 30 |
| `DB_URL` | SQLAlchemy URL | sqlite:///./gold_signal.db |

## สถานะ

MVP (Phase 1): core engine + Telegram. ยังไม่รวม Dashboard, TradingView webhook,
result tracking, LINE — อยู่ใน phase ถัดไป (ดู `docs/superpowers/specs/`)
