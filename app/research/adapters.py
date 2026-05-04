from typing import Protocol

from app.research.schemas import AdapterResult


class DataSourceAdapter(Protocol):
    """Read-only source adapter for research data; never exposes broker order methods."""

    @property
    def source_name(self) -> str:
        ...

    def fetch(self, ticker: str) -> AdapterResult:
        ...
