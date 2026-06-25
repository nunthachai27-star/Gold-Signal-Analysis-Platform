# Gold Signal Analysis Platform — MVP Design Spec

วันที่: 2026-06-25
สถานะ: อนุมัติการออกแบบแล้ว (รอ review เอกสาร)

## 1. ขอบเขต MVP (Phase 1)

MVP รอบนี้ทำเฉพาะ **Core engine + Telegram** เท่านั้น:

ดึงข้อมูล XAUUSD → คำนวณ indicator → ส่งให้ LLM วิเคราะห์ → สร้าง signal → ส่ง Telegram → บันทึก DB

**เลื่อนไป Phase ถัดไป (ไม่อยู่ใน MVP นี้):**
- Web Dashboard
- TradingView webhook ingestion
- Signal result tracking (วัด win/loss อัตโนมัติ)
- LINE integration
- ระบบสมาชิก / multi-user setting

## 2. การตัดสินใจหลักด้านสถาปัตยกรรม

| ประเด็น | การตัดสินใจ |
|--------|-------------|
| จุดวิเคราะห์ | Server วิเคราะห์เอง (ดึงข้อมูลเอง) — webhook ไม่ใช้ใน MVP |
| Trigger | Scheduler รันเป็นรอบ (default ทุก 5 นาที) |
| แหล่งข้อมูลราคา | **OANDA v20 REST API** (instrument `XAU_USD`) — ตรงกับ chart `OANDA:XAUUSD` |
| ตัววิเคราะห์ | **LLM วิเคราะห์เต็มตัว** (OpenAI / ChatGPT API) ผ่าน Structured Output |
| Indicator | คำนวณฝั่ง server ด้วย pandas-ta แล้วส่งเป็น feature ให้ LLM |
| Tech stack | Python ล้วน (FastAPI) |
| Database | SQLite (ผ่าน SQLAlchemy) — ออกแบบให้ย้าย PostgreSQL ภายหลังได้ |

## 3. ภาพรวม Flow

```
[Scheduler ทุก N นาที]
   → [OANDA v20] ดึง OHLC: D1, H4, H1, M15, M5 → cache ลง DB (ดึงเฉพาะแท่งใหม่)
   → [Indicator Layer] pandas-ta: EMA(fast/slow), RSI, MACD, ATR + swing high/low ต่อ TF
   → [Snapshot Builder] สรุปย่อหลาย TF เป็น JSON กระชับ
   → [OpenAI Analyzer] ส่ง snapshot + system prompt → LLM ตอบ JSON (Structured Output)
        { direction, entry, sl, tp1, tp2, buy_prob, sell_prob, type, reasoning }
   → [Validator] ตรวจตัวเลขสมเหตุผล + กรอง threshold
   → [Dedup/Cooldown] ส่งเฉพาะสัญญาณใหม่จริง
   → [Telegram Notifier] ส่งข้อความ
   → [Repository] บันทึก signal_history (เก็บ reasoning + snapshot ที่ใช้)
```

## 4. หน่วยย่อยและ Interface

ทุกขอบเขตที่อาจเปลี่ยน provider ออกแบบเป็น interface เพื่อสลับ implementation ได้โดยไม่กระทบ engine

### 4.1 `PriceProvider` (interface)
- หน้าที่: ดึง OHLC ของ symbol + timeframe ที่ระบุ คืนเป็น list ของแท่งเทียน (มาตรฐานกลาง)
- Implementation MVP: `OandaProvider`
  - Endpoint: `GET /v3/instruments/XAU_USD/candles?granularity={G}&count={N}&price=M`
  - Granularity mapping: `D1→D, H4→H4, H1→H1, M15→M15, M5→M5` (รองรับ `W, M30, M1` ในอนาคต)
  - Auth: `Authorization: Bearer {OANDA_TOKEN}`
  - Host: practice = `api-fxpractice.oanda.com`, live = `api-fxtrade.oanda.com` (เลือกผ่าน config)
  - ใช้ราคา mid (`price=M`) เป็นค่าตั้งต้น

### 4.2 Indicator Layer
- หน้าที่: รับแท่งเทียนของแต่ละ TF → คำนวณ EMA(fast/slow), RSI, MACD, ATR และหา swing high/low ล่าสุด ด้วย pandas-ta
- คืน object indicator ต่อ TF แบบ deterministic (ทดสอบได้)

### 4.3 Snapshot Builder
- หน้าที่: รวม indicator ทุก TF เป็น JSON ย่อสำหรับป้อน LLM เพื่อคุมต้นทุน token
- ต่อ TF บรรจุ: trend (เทียบราคา/EMA), RSI value, MACD state, ราคาปัจจุบัน, swing high/low, ATR
- ไม่ส่งแท่งเทียนดิบทั้งหมด

### 4.4 `Analyzer` (interface)
- หน้าที่: รับ snapshot → คืน signal ที่มีโครงสร้างชัดเจน
- Implementation MVP: `OpenAiAnalyzer`
  - ใช้ OpenAI Chat Completions / Responses API พร้อม **Structured Outputs** (JSON Schema บังคับ)
  - System prompt กำหนดบทบาท "นักวิเคราะห์ XAUUSD แบบ multi-timeframe" พร้อมกฎการให้ Entry/SL/TP/probability
  - Model ตั้งใน config (ค่าเริ่มต้นเลือกตัวคุ้มค่า เช่น `gpt-4o-mini` / `gpt-4.1-mini`)
  - Output schema: `direction (BUY|SELL|NONE)`, `entry`, `sl`, `tp1`, `tp2`, `buy_prob`, `sell_prob`, `type (Scalp|Normal)`, `reasoning`
- ออกแบบให้สลับเป็น rule-based หรือ LLM provider อื่นได้ภายหลัง

### 4.5 Validator
- หน้าที่: ตรวจผลจาก LLM ก่อนใช้งานจริง
- กฎตรวจ:
  - ถ้า BUY: `sl < entry < tp1 < tp2`; ถ้า SELL: `sl > entry > tp1 > tp2`
  - `buy_prob + sell_prob` ใกล้เคียง 100
  - ราคาอยู่ในช่วงสมเหตุผลเทียบราคาปัจจุบัน (กัน LLM หลอน)
  - กรอง threshold: ออกสัญญาณเฉพาะเมื่อ prob ฝั่งที่ชนะ ≥ ค่าที่ตั้ง (default 55%) มิฉะนั้นถือว่า NONE
- ผลที่ไม่ผาน validate: log แล้วข้ามรอบ (ไม่ส่ง)

### 4.6 Dedup / Cooldown
- หน้าที่: กันสแปม
- ส่งใหม่เฉพาะเมื่อ: ทิศทางเปลี่ยนจากสัญญาณล่าสุด หรือผ่าน cooldown (default ไม่ส่งซ้ำภายใน X นาที)
- อ้างอิงสัญญาณล่าสุดจาก `signal_history`

### 4.7 `Notifier` (interface)
- หน้าที่: ส่งข้อความสัญญาณ
- Implementation MVP: `TelegramNotifier` (Telegram Bot API)
  - ส่งถึง chat_id หลายรายจาก `recipients`
  - retry เมื่อส่งล้มเหลว (backoff สั้นๆ)
  - รูปแบบข้อความตามสเปคข้อ 9 (Symbol, Direction, Entry, SL, TP1, TP2, probability, timeframe bias, time)

### 4.8 Repository
- หน้าที่: persistence layer ครอบ SQLAlchemy session — อ่าน/เขียน candles, signal_history, recipients

## 5. Data Model (SQLite ผ่าน SQLAlchemy)

### `price_candles`
`id, symbol, timeframe, candle_time, open, high, low, close, volume` — unique (symbol, timeframe, candle_time)

### `signal_history`
`id, symbol, signal_type, direction, entry_price, stop_loss, take_profit_1, take_profit_2, buy_probability, sell_probability, timeframe_summary, score, reasoning, snapshot_json, generated_at, status`

### `recipients`
`id, name, telegram_chat_id, is_active, created_at`

## 6. โครงไฟล์โปรเจกต์

```
app/
  config.py            # pydantic-settings อ่าน .env
  scheduler.py         # APScheduler รันทุก N นาที, orchestrate flow
  providers/
    base.py            # PriceProvider interface
    oanda.py           # OandaProvider
  analysis/
    indicators.py      # คำนวณ indicator + swing
    snapshot.py        # Snapshot Builder
    base.py            # Analyzer interface
    openai_analyzer.py # OpenAiAnalyzer
    validator.py       # Validator + threshold
    dedup.py           # Dedup/Cooldown
  notify/
    base.py            # Notifier interface
    telegram.py        # TelegramNotifier + message format
  db/
    models.py          # SQLAlchemy models
    session.py         # engine/session setup
  repository.py        # persistence helpers
  main.py              # FastAPI app: GET /health, POST /analysis/run (manual trigger)
tests/
  fixtures/            # candle fixtures, canned LLM responses
  test_indicators.py
  test_snapshot.py
  test_validator.py
  test_dedup.py
  test_telegram_format.py
  test_flow.py         # integration ด้วย mock provider + mock analyzer
.env.example
requirements.txt
README.md
```

## 7. Config (.env + settings)

| Key | คำอธิบาย | ค่าเริ่มต้น |
|-----|----------|------------|
| `OANDA_TOKEN` | API token | (จำเป็น) |
| `OANDA_ENV` | practice / live | practice |
| `OPENAI_API_KEY` | คีย์ OpenAI | (จำเป็น) |
| `OPENAI_MODEL` | model id | gpt-4o-mini |
| `TELEGRAM_BOT_TOKEN` | bot token | (จำเป็น) |
| `SYMBOL` | สัญลักษณ์ | XAU_USD |
| `TIMEFRAMES` | ชุด TF | D1,H4,H1,M15,M5 |
| `SCHEDULER_INTERVAL_MIN` | ความถี่รอบ | 5 |
| `SIGNAL_THRESHOLD` | prob ขั้นต่ำที่จะส่ง | 55 |
| `COOLDOWN_MIN` | กันส่งซ้ำ | 30 |
| `DB_URL` | SQLAlchemy URL | sqlite:///./gold_signal.db |

## 8. การทดสอบ (TDD)

- `test_indicators` — ป้อนแท่งเทียนที่รู้ผล ตรวจค่า EMA/RSI/MACD/ATR
- `test_snapshot` — snapshot สร้างถูกต้องจาก indicator
- `test_validator` — ตรวจ logic SL/TP ถูกฝั่ง, prob รวม 100, threshold, กรองค่า LLM หลอน
- `test_dedup` — ส่ง/ไม่ส่งตามทิศทางเปลี่ยน + cooldown
- `test_telegram_format` — รูปแบบข้อความตรงสเปค
- `test_flow` — integration end-to-end ด้วย mock `PriceProvider` (fixture candles) + mock `Analyzer` (canned JSON) → ตรวจว่าบันทึก DB + เรียก notifier ถูกต้อง
- OANDA และ OpenAI ถูก mock ในเทสต์ทั้งหมด (ไม่ยิง API จริง)

## 9. Error Handling

- OANDA ล่ม / timeout → retry + backoff, ถ้ายังล้มเหลวข้ามรอบนั้น (log)
- Rate limit → เคารพ limit, cache แท่งเก่าใน DB ดึงเฉพาะแท่งใหม่
- OpenAI ล้มเหลว / ตอบผิด schema → retry จำกัดครั้ง, ถ้าไม่ได้ข้ามรอบ
- ผล LLM ไม่ผ่าน Validator → ไม่ส่ง, log ไว้ตรวจสอบ
- Telegram ส่งล้มเหลว → retry + บันทึก error
- ทุก error เขียน log ตรวจย้อนหลังได้

## 10. Non-Functional (สำหรับ MVP)

- รันได้ 24x7 บน VM/Docker (deploy รายละเอียดทำใน phase ถัดไป)
- เก็บ secret ใน .env (ไม่ commit) — `.env.example` เป็น template
- log แยก info/error

## 11. นอกขอบเขต (ยืนยันอีกครั้ง)

Dashboard, webhook ingestion, result tracking, LINE, multi-user, backtest, AI explanation layer — **ทั้งหมดอยู่ Phase ถัดไป** จะ brainstorm + spec แยกเป็นรอบของตัวเอง
