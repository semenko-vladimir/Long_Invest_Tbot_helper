# Questions for the Project Owner

Audit date: 2026-05-14
These are questions to resolve before the next development cycle.
Work was not stopped to ask these — they are recorded here for async review.

---

## Product vision

1. Is the primary interface Telegram or the web terminal? ROADMAP says web terminal, README says Telegram. Which should receive priority for UX investment in the next 2 weeks?

2. Is this project intended to be shared with other users (colleagues, friends), or strictly single-user local? The multi-user (P1) architecture supports multiple users, but there is no web authentication. Clarifying this determines whether auth is needed.

3. Educational ratings (BUY/HOLD/SELL/WATCH/AVOID) are deferred in PROJECT_INSTRUCTIONS.md. Do you want them in the next 3 months? If yes, what data sources would they be based on?

4. Is the project intended as a portfolio showcase for job applications in macro/investment analytics? If yes, which parts should be emphasized: safety gates, research module, analytics, or the overall architecture?

---

## Safety

5. `PlanConfirmationService._execute` is called while `self._lock` is held, and it makes a broker network call inside the lock. This can cause the confirmation service to freeze if the broker is slow or times out. Do you want this fixed before P2-T1 (APScheduler wiring) is implemented? **Strongly recommend yes.**

6. `configure_investor_reminders()` uses legacy `CHAT_ID` from `.env` instead of the multi-user `UserContextResolver`. If multiple users are configured in `users.json`, only the `.env` CHAT_ID user receives reminders. Is this acceptable for now, or should it be fixed to use per-user context?

7. `ALLOW_AUTO_INVESTING` defaults to `false`. If P2-T1 (APScheduler PlanRunner wiring) is implemented, do you want auto-execution to remain manually confirmed via Telegram ✅ for all users at all times, or are there scenarios where `confirmation_required=False` should be permitted?

---

## Investment logic

8. For `price_rule=pct_from_avg`, the implementation fetches closing prices via `broker.get_closing_prices()`. Does the T-Invest SDK actually support this call? If not, `pct_from_avg` will silently fail (returning `allowed=False` with "Не удалось получить историческую среднюю цену"). Has this been tested end-to-end?

9. The `investment_plans` feature lets users set `operation=sell`. Sell-side auto-planning for a long-term investor is unusual. Is sell-side planning intentional, or should it be restricted to buy-only for v1?

10. The `local_fundamentals.json` file is sparse. Do you want it expanded with real MOEX company data (manually curated)? Which 10–20 tickers are most relevant to your actual watchlist?

---

## UI/UX

11. Web terminal has no authentication. Is it accessed only from localhost (safe), or do you sometimes expose the port remotely (e.g., via ngrok, SSH tunnel, VPN)? If remotely accessible, basic auth should be added immediately.

12. P3-T1 (responsive layout, sidebar) is planned but not started. Is this important enough to prioritize over P2 (auto-schedule) or P4 (analytics/charts)?

13. The investor reminder currently sends a generic text message. Would you prefer a richer daily report (portfolio value, open plans, recent activity), or is the current minimal reminder sufficient?

---

## Architecture

14. There are two Python environments: `venv/` and `venv312/`. Can `venv/` be deleted? What is it currently used for?

15. `app/run.py` registers Telegram handlers inline (including the `/start` handler definition). Is it acceptable to refactor `run.py` to be purely startup orchestration, moving handler registration to a separate module?

16. `app/client/store/store.py` is imported by `schedulers_config.py` at startup. This makes the legacy store module active even when schedulers are disabled. Should this import be decoupled (lazy import inside the function)?

---

## Data

17. Are you open to manually maintaining `app/research/data/local_fundamentals.json` with company data for your watchlist tickers? Or should the research feature rely entirely on T-Invest API data?

18. What broker data does the T-Invest SDK actually return for `get_closing_prices()`? Has this been verified with a real or sandbox token?

19. The T-Invest SDK packages are pinned via direct PyPI URLs marked as "quarantined." Have these packages been manually reviewed for safety? If not, do you plan to replace them with an official SDK version?

---

## Tests

20. `P0-T3` (ROADMAP) planned WatchlistService tests. Were these completed or still pending? The test file was not found in the directory listing.

21. Is there any test that exercises the full flow: InvestmentPlan → PlanRunner → PlanConfirmationService → OrderService → broker? If not, adding this integration test should be a priority before P2-T1 wiring.

22. Do you run tests on every commit (CI/pre-commit hook), or only manually? If manually, a pre-commit hook for `python -m unittest discover -q` would prevent regressions.

---

## Legacy cleanup

23. Should legacy signal files (`app/client/signals/`) be moved to `_legacy/` (isolation), or is there a plan to eventually use them for educational purposes (e.g., showing historical signal backtest, not for live trading)?

24. `app/client/graphics/` contains chart generation files. Are these ever used, or can they be isolated immediately?

25. What is in `app/client/strategy/`? Contents were not directly inspected in this audit.

26. What is in `app/client/orders/`? This directory exists separately from `app/services/orders.py`. Is it legacy or active?

---

## Priorities for the next 2 weeks

27. In order of importance, which of these would you like completed first:
    - a) Fix PlanConfirmationService deadlock risk
    - b) Fix investor_reminders multi-user
    - c) Complete WatchlistService tests (P0-T3)
    - d) Implement PlanRunner APScheduler wiring (P2-T1)
    - e) Isolate legacy signal files to `_legacy/`
    - f) Expand local_fundamentals.json data
    - g) Portfolio snapshot storage (P4-T1)
    - h) Responsive web UI (P3-T1)
