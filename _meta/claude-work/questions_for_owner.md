# Questions for Owner — Tbot v1

Date: 2026-05-14
Agent: claude-sonnet-4-6 (via Claude Code)

Low-risk changes proceed without blocking; questions here require owner decision before implementation.

---

## Product Direction

1. **Web terminal auth** — `PROJECT_INSTRUCTIONS.md` says "local/no-auth for phase 1." Is that still correct, or is there a timeline to add simple login (e.g., single shared password) before inviting a second user?

2. **Multi-user phase boundary** — Phase 1 allows multiple configured users via `users.json`. What is the trigger to advance to Phase 2 (e.g., remote access, proper auth)?

3. **Research terminal vs Telegram** — Long-term: is the web terminal meant to replace Telegram, or will both be maintained indefinitely? This affects how much effort to put into Telegram UX improvements.

---

## Safety

4. **Auto-schedule blocks** — The recent commits (`feat: implement auto-schedule blocks 3 & 4`, `Add auto schedule price conditions`) suggest some scheduling/automation. How do these interact with `ENABLE_BACKGROUND_SCHEDULERS="false"` default? Is there a confirmation/audit trail for any scheduled actions?

5. **`ALLOW_PROD_TRADING` path** — Is production trading ever tested against a real broker account? If yes, how often, and should there be a second confirmation layer (e.g., PIN, TOTP)?

---

## Investment Analytics

6. **Educational rating timing** — `PROJECT_INSTRUCTIONS.md` defers `BUY/HOLD/SELL/WATCH/AVOID` labels to a future task. Is this in scope for the next 2 weeks, or still postponed?

7. **Valuation snapshots** — Should `ResearchReport` eventually include P/E, EV/EBITDA, P/B fields, or is that out of v1 scope?

8. **Macro context** — `macro_context` field exists on `ResearchReport` but has no adapter. Is there a preferred free data source (e.g., FRED, World Bank API) or will this remain local JSON only?

---

## Data Sources

9. **`local_fundamentals.json`** — This is the only non-broker data source. How often is it manually updated? Should there be a staleness threshold warning (e.g., > 30 days)?

10. **T-Invest market data** — `TInvestBroker` is the only live price source. Is there an acceptable fallback if the T-Invest API is unavailable (e.g., cached last price, "price unavailable" banner)?

11. **Future fundamentals provider** — Any preference for fundamentals data: Tinkoff Pulse, FinancialModelingPrep, Simfin, or local CSV files?

---

## Telegram UX

12. **Inline buttons vs commands** — Some handlers use inline keyboards, others use text commands. Is there a preference to standardize?

13. **Notification verbosity** — Should the bot send daily summary notifications, or only on explicit user request?

---

## Web UX

14. **Current web terminal status** — Is the web terminal running and usable today? If not, what is the primary blocker?

15. **Mobile friendliness** — Is mobile browser access needed, or is this desktop-only?

---

## Testing

16. **Integration test policy** — All current tests are offline unit tests. Is there appetite for a separate test suite that runs against sandbox broker API (skipped by default, enabled via env flag)?

17. **Test database** — Tests currently create temporary SQLite DBs. Should these use `:memory:` databases instead to avoid leaving files?

---

## Legacy Cleanup

18. **Signal/LSTM/GPT modules** — `app/client/signals/` has 7 modules (alligator, bollinger, ema, gpt, lstm, macd, rsi, sma). None are active in v1. Recommended disposition: isolate to `legacy/` subdirectory now, or leave in place until a cleanup sprint? See `_meta/claude-work/legacy_inventory.md`.

19. **`app/client/graphics/`** — 7 chart modules, none active in v1 runtime. Same question: isolate or leave?

20. **`requirements-optional.txt`** — Is anyone importing these dependencies? Should a CI check enforce that base requirements don't import optional deps?

---

## Next 2-Week Priorities

21. **Suggested priority order** (owner to confirm):
    - [ ] A — Typed analytics schema (RiskFactor, AnalysisSignal) — done this session
    - [ ] B — `local_fundamentals.json` coverage for 5-10 key tickers
    - [ ] C — Web terminal smoke test (can it start and show portfolio?)
    - [ ] D — Staleness warnings for research data
    - [ ] E — Educational rating prototype (non-binding BUY/HOLD/SELL/WATCH/AVOID)

    Is this ordering acceptable, or should a different area be prioritized?
