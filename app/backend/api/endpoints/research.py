from dataclasses import asdict, dataclass

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder

from app.research.services import ResearchReportService, TickerResearchService
from app.research.tinvest_adapter import TInvestDataAdapter


router = APIRouter()


@dataclass(frozen=True)
class ResearchServices:
    ticker_research: TickerResearchService
    report_builder: ResearchReportService


def get_research_services() -> ResearchServices:
    return ResearchServices(
        ticker_research=TickerResearchService([TInvestDataAdapter()]),
        report_builder=ResearchReportService(),
    )


@router.get("/{ticker}")
def read_ticker_research(
    ticker: str,
    services: ResearchServices = Depends(get_research_services),
):
    adapter_results = services.ticker_research.collect(ticker)
    report = services.report_builder.build_report(ticker, adapter_results)
    return jsonable_encoder(asdict(report))
