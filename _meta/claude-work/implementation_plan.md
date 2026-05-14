# Implementation Plan — Tbot v1 Structural Improvements

Date: 2026-05-14

## What I Found

### Repository state
- Working tree clean (only `docs/` untracked before this session).
- 148 tests — all pass (`.\venv312\Scripts\python.exe -m unittest discover -q`).
- Python 3.12, venv312.

### Existing strengths
- `PROJECT_INSTRUCTIONS.md` — comprehensive v1 product framing and safety rules.
- `V1_SCOPE.md` — clear enabled / disabled / postponed scope.
- `AGENT_BEHAVIOR.md` — architecture rules.
- `app/research/schemas.py` — `SourceFreshness`, `DataGap`, `AdapterResult`, `InstrumentIdentity`, `MarketSnapshot`, `ResearchReport` (with `disclaimer`, `educational_rating`, `confidence`).
- `app/research/adapters.py` — `DataSourceAdapter` Protocol.
- `app/research/services.py` — `TickerResearchService` with `RESEARCH_DISCLAIMER`.
- `app/research/local_fundamentals_adapter.py` — read-only local data adapter.
- Tests already contain inline stub adapters (`SuccessfulAdapter`, `PartialAdapter`, `FailingAdapter`).

### Gaps identified
1. No typed `RiskFactor` dataclass — `ResearchReport.risks` is untyped `list[str]`.
2. No typed `AnalysisSignal` dataclass — `educational_rating` is bare `Optional[str]`.
3. No legacy module inventory document.
4. No `_meta/claude-work/` meta infrastructure.

## Candidate Tasks

| ID | Task | Risk | Value |
|----|------|------|-------|
| A  | Meta files (plan, log, questions) | None | Required by prompt |
| B  | Add `RiskFactor` + `AnalysisSignal` types to `schemas.py` + tests | Low | Extends existing patterns cleanly |
| C  | ~~StubDataAdapter~~ | Skipped | Inline stubs already exist in tests |
| D  | Legacy inventory document | None | Audit value |
| E  | Safety documentation update | Low | Clarity |

## Chosen Tasks (this session)

1. **Task A** — Meta infrastructure (`_meta/claude-work/` files) ← in progress
2. **Task B** — Typed `RiskFactor` + `AnalysisSignal` dataclasses in `app/research/schemas.py`
3. **Task D** — Legacy inventory document

## Allowed Files

- `_meta/claude-work/*.md` (new files)
- `app/research/schemas.py` (additive only — new dataclasses + optional fields)
- `tests/test_research_schemas.py` (new test file)

## Forbidden Files

- `.env`, `*.db`, `alembic/`, migration files
- `app/services/orders.py`, `app/services/trading_policy.py`
- `app/integrations/tinvest.py`
- Any file that controls real order execution
- `app/services/mode.py` (ModeService safety gate)
- Existing tests (only add new tests)

## Tests to Run

```powershell
.\venv312\Scripts\python.exe -m unittest discover -q
```

## Rollback Plan

All changes are either:
- New files under `_meta/` (deleteable with no impact)
- Additive dataclasses in `schemas.py` with no migration or consumer changes
- New test file (deleteable)

To roll back: `git checkout app/research/schemas.py` and delete new files.
