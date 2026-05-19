import logging
from dataclasses import asdict, dataclass
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.backend.api.dependencies import get_default_web_db
from app.backend.web.context import get_web_services
from app.research.services import ResearchReportService, TickerResearchService
from app.research.snapshots import ResearchSnapshotService, snapshot_to_dict


logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass(frozen=True)
class ResearchServices:
    ticker_research: TickerResearchService
    report_builder: ResearchReportService


def get_research_services() -> ResearchServices:
    web_services = get_web_services()
    return ResearchServices(
        ticker_research=web_services.ticker_research,
        report_builder=web_services.report_builder,
    )


@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def research_page():
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Read-Only Ticker Research - Investor Terminal</title>
  <style>
    body { margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #171a1c; background: #f6f7f8; }
    main { width: min(900px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0; }
    h1 { margin: 0 0 10px; font-size: 32px; }
    p { color: #5d666d; line-height: 1.5; }
    form { display: flex; gap: 12px; margin: 22px 0; }
    label { flex: 1; display: grid; gap: 8px; color: #5d666d; font-weight: 700; }
    input { min-height: 42px; padding: 10px 12px; border: 1px solid #d9dedb; border-radius: 8px; font: inherit; }
    button { min-height: 42px; padding: 10px 14px; border: 1px solid #1f7a4d; border-radius: 8px; color: white; background: #1f7a4d; font: inherit; font-weight: 700; }
    pre { overflow-x: auto; min-height: 180px; padding: 16px; border: 1px solid #d9dedb; border-radius: 8px; background: #fff; }
    .notice { padding: 16px; border: 1px solid #f0cc74; border-radius: 8px; background: #fff4d6; }
    @media (max-width: 640px) { form { flex-direction: column; } }
  </style>
</head>
<body>
  <main>
    <p><a href="/portfolio">Investor Terminal</a></p>
    <h1>Read-only ticker research</h1>
    <p>Enter a ticker to fetch an educational long-term research report from the local API.</p>
    <div class="notice">
      Reports may be partial. Review the returned data_gaps and errors fields before relying on the data.
      This page only reads research data and does not submit broker orders.
    </div>
    <form id="research-form">
      <label for="research-ticker">
        Ticker
        <input id="research-ticker" name="ticker" autocomplete="off" placeholder="SBER" required>
      </label>
      <button type="submit">Open report</button>
    </form>
    <pre id="research-output" aria-live="polite">Enter a ticker to load a report.</pre>
  </main>
  <script>
    document.getElementById("research-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      const input = document.getElementById("research-ticker");
      const output = document.getElementById("research-output");
      const ticker = input.value.trim().toUpperCase();
      if (!ticker) {
        output.textContent = "Ticker is required.";
        return;
      }

      output.textContent = "Loading...";
      try {
        const response = await fetch("/api/research/" + encodeURIComponent(ticker));
        const payload = await response.json();
        output.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        output.textContent = "Research report could not be loaded: " + error;
      }
    });
  </script>
</body>
</html>"""


@router.get("/snapshots")
def list_research_snapshots(
    ticker: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_default_web_db),
):
    snapshots = ResearchSnapshotService(db).list_recent(ticker=ticker, limit=limit)
    return jsonable_encoder([snapshot_to_dict(snapshot) for snapshot in snapshots])


@router.get("/snapshots/{snapshot_id}")
def read_research_snapshot(
    snapshot_id: int,
    db: Session = Depends(get_default_web_db),
):
    snapshot = ResearchSnapshotService(db).get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Research snapshot not found.")
    return jsonable_encoder(snapshot_to_dict(snapshot))


@router.get("/{ticker}")
def read_ticker_research(
    ticker: str,
    services: ResearchServices = Depends(get_research_services),
    db: Session = Depends(get_default_web_db),
):
    adapter_results = services.ticker_research.collect(ticker)
    report = services.report_builder.build_report(ticker, adapter_results)
    _try_save_report_snapshot(report, db)
    return jsonable_encoder(asdict(report))


def _try_save_report_snapshot(report, db: Session) -> None:
    try:
        ResearchSnapshotService(db).save_report(report)
    except Exception:
        logger.exception("Failed to save research snapshot; rolling back session.")
        try:
            db.rollback()
        except Exception:
            logger.exception("Research snapshot rollback failed.")
