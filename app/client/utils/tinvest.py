from typing import Optional

from t_tech.invest import Client
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX

from app.client.config import is_sandbox_mode


def get_tinvest_target(sandbox: Optional[bool] = None) -> str:
    """Return the current SDK endpoint for the explicit or configured mode."""
    use_sandbox = is_sandbox_mode() if sandbox is None else sandbox
    return INVEST_GRPC_API_SANDBOX if use_sandbox else INVEST_GRPC_API


def create_tinvest_client(token: str, *, sandbox: Optional[bool] = None) -> Client:
    """Create a verified T-Invest client for the requested application mode."""
    return Client(token, target=get_tinvest_target(sandbox))
