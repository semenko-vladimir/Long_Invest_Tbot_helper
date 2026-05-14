# Legacy Module Inventory — Tbot v1

Date: 2026-05-14
Agent: claude-sonnet-4-6

This inventory documents modules that are **not active in the v1 runtime** per `PROJECT_INSTRUCTIONS.md` and `V1_SCOPE.md`. None are deleted. Recommendations are advisory only — owner must approve any removal.

---

## 1. Signal Modules (`app/client/signals/`)

| File | Type | Dependencies | Status | Recommendation |
|------|------|-------------|--------|----------------|
| `alligator_signal.py` | Technical indicator | `sma_signal` (internal) | Not wired into v1 | Isolate |
| `bollinger_signal.py` | Technical indicator | `sma_signal`, `rsi_signal` (internal) | Not wired into v1 | Isolate |
| `ema_signal.py` | Technical indicator | stdlib only | Not wired into v1 | Isolate |
| `macd_signal.py` | Technical indicator | stdlib only | Not wired into v1 | Isolate |
| `rsi_signal.py` | Technical indicator | stdlib only | Not wired into v1 | Isolate |
| `sma_signal.py` | Technical indicator | stdlib only | Not wired into v1 | Isolate |
| `gpt_signal.py` | LLM signal | `g4f` (not in base requirements) | Not wired, hard dep on `g4f` | Remove/isolate |
| `lstm_signal.py` | ML signal | `numpy`, `pandas`, `sklearn`, `keras` (optional deps) | Not wired, hard dep on optional ML stack | Remove/isolate |

**Active import check:** No active v1 code (outside the signal module directory itself) imports from `app.client.signals`. Safe to isolate.

**Notes:**
- `gpt_signal.py` requires `g4f` (third-party GPT library) — not in `requirements-base.txt`, only `requirements-optional.txt`. Will fail to import on a clean v1 install.
- `lstm_signal.py` requires `keras`/`sklearn`/`numpy` — same situation.

---

## 2. Chart/Graphics Modules (`app/client/graphics/`)

| File | Type | Dependencies | Status | Recommendation |
|------|------|-------------|--------|----------------|
| `alligator_graph.py` | Signal chart | matplotlib (optional) | Not wired into v1 | Isolate |
| `bollinger_graph.py` | Signal chart | matplotlib (optional) | Not wired into v1 | Isolate |
| `ema_graph.py` | Signal chart | matplotlib (optional) | Not wired into v1 | Isolate |
| `macd_graph.py` | Signal chart | matplotlib (optional) | Not wired into v1 | Isolate |
| `rsi_graph.py` | Signal chart | matplotlib (optional) | Not wired into v1 | Isolate |
| `sma_graph.py` | Signal chart | matplotlib (optional) | Not wired into v1 | Isolate |
| `statistics_graph.py` | Stats chart (262 lines) | matplotlib (optional) | Not wired into v1 runtime | Review — may contain reusable stats logic |

**Active import check:** No active v1 code imports from `app.client.graphics`. Safe to isolate.

---

## 3. Client-Side API Clients with Legacy Scope

| File | Notes |
|------|-------|
| `app/client/api/signals_client.py` | Signal API client — no active signal router in v1 |
| `app/client/api/trading_client.py` | Review needed — confirm whether this is used by active Telegram handlers |

---

## 4. Other Potentially Legacy Files (needs owner review)

| File | Notes |
|------|-------|
| `app/client/handlers/bot/bot_handler.py` | Contains references to signals/strategy — verify which handlers are active |
| `app/client/handlers/help/help_handler.py` | May reference disabled features |

---

## 5. Requirements Files — Orphaned Dependencies

| File | Contents | Status |
|------|----------|--------|
| `requirements.txt` | Alias to `requirements-base.txt` | OK |
| `requirements-v1.txt` | Alias to `requirements-base.txt` | OK |
| `requirements-optional.txt` | `g4f`, `keras`, `sklearn`, `matplotlib`, charting deps | Optional — **not imported by v1 runtime** |
| `requirements-dev.txt` | `pytest`, `httpx` | OK |

---

## Recommended Isolation Strategy

**When ready (owner to approve):**

1. Create `app/client/legacy/signals/` and `app/client/legacy/graphics/` subdirectories.
2. Move the 15 files listed above (excluding `statistics_graph.py` pending review).
3. Add `_LEGACY_NOTE.md` to each legacy subdirectory explaining status.
4. Verify tests still pass.

**Do NOT delete** until at least one full release cycle has passed without any reference to the legacy code.

---

## What Is Active in v1 (for reference)

The following are confirmed active per `V1_SCOPE.md`:
- `app/services/` — all services (portfolio, orders, dividends, watchlist, etc.)
- `app/research/` — research schemas, adapters, services
- `app/backend/` — FastAPI routes (research, portfolio, settings, etc.)
- `app/client/handlers/` — Telegram handlers for portfolio, orders, research, investment plans
- `app/integrations/tinvest.py` — T-Invest broker integration
