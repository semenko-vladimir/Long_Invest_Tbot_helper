from dataclasses import dataclass, field
from typing import Any, Optional


SUPPORTED_STRATEGY_OPERATIONS = {"buy", "sell"}
STRATEGY_TYPE_CONFIRMATION_REQUIRED = "confirmation_required"
STRATEGY_TYPE_OBSERVATION = "observation"
STRATEGY_TYPE_AUTO_EXECUTE = "auto_execute"
SUPPORTED_STRATEGY_TYPES = {
    STRATEGY_TYPE_CONFIRMATION_REQUIRED,
    STRATEGY_TYPE_OBSERVATION,
    STRATEGY_TYPE_AUTO_EXECUTE,
}
STRATEGY_STATUS_LOADED = "loaded"
STRATEGY_STATUS_SKIPPED = "skipped"
STRATEGY_STATUS_BLOCKED = "blocked"
STRATEGY_STATUS_POLICY_BLOCKED = "policy_blocked"
STRATEGY_STATUS_SENT_FOR_CONFIRMATION = "sent_for_confirmation"
STRATEGY_STATUS_CONFIRMED = "confirmed"
STRATEGY_STATUS_NO_ACTION = "no_action"
STRATEGY_STATUS_DEDUPED = "deduped"
STRATEGY_STATUS_PREVIEWED = "previewed"
STRATEGY_STATUS_EXECUTION_STARTED = "execution_started"
STRATEGY_STATUS_EXECUTED = "executed"
STRATEGY_STATUS_FAILED = "failed"
STRATEGY_STATUS_EXPIRED = "expired"
STRATEGY_STATUS_OBSERVED = "observed"
STRATEGY_STATUSES = {
    STRATEGY_STATUS_LOADED,
    STRATEGY_STATUS_SKIPPED,
    STRATEGY_STATUS_BLOCKED,
    STRATEGY_STATUS_POLICY_BLOCKED,
    STRATEGY_STATUS_SENT_FOR_CONFIRMATION,
    STRATEGY_STATUS_CONFIRMED,
    STRATEGY_STATUS_NO_ACTION,
    STRATEGY_STATUS_DEDUPED,
    STRATEGY_STATUS_PREVIEWED,
    STRATEGY_STATUS_EXECUTION_STARTED,
    STRATEGY_STATUS_EXECUTED,
    STRATEGY_STATUS_FAILED,
    STRATEGY_STATUS_EXPIRED,
    STRATEGY_STATUS_OBSERVED,
}


class StrategyModelError(ValueError):
    pass


@dataclass(frozen=True)
class StrategyMetadata:
    strategy_id: str
    name: str
    description: str
    enabled: bool = True
    schedule: dict[str, Any] = field(default_factory=dict)
    strategy_type: str = STRATEGY_TYPE_CONFIRMATION_REQUIRED
    confirmation_required: bool = True

    @classmethod
    def from_mapping(
        cls,
        payload: dict[str, Any],
        *,
        default_strategy_type: str = STRATEGY_TYPE_CONFIRMATION_REQUIRED,
    ) -> "StrategyMetadata":
        if not isinstance(payload, dict):
            raise StrategyModelError("Strategy metadata must be a mapping.")

        strategy_id = _normalize_id(payload.get("id"))
        name = _clean_text(payload.get("name"))
        description = _clean_text(payload.get("description"))
        schedule = payload.get("schedule") or {}
        strategy_type = _normalize_strategy_type(payload.get("strategy_type") or default_strategy_type)

        if not strategy_id:
            raise StrategyModelError("Strategy metadata must include a valid id.")
        if not name:
            raise StrategyModelError("Strategy metadata must include a name.")
        if not description:
            raise StrategyModelError("Strategy metadata must include a description.")
        if not isinstance(schedule, dict):
            raise StrategyModelError("Strategy schedule must be a mapping.")

        return cls(
            strategy_id=strategy_id,
            name=name,
            description=description,
            enabled=_optional_bool(payload.get("enabled", True), "enabled"),
            schedule=dict(schedule),
            strategy_type=strategy_type,
            confirmation_required=_metadata_confirmation_required(payload, strategy_type),
        )


@dataclass(frozen=True)
class StrategyProposal:
    operation: str
    ticker: str
    lots: int
    reason: str
    dedupe_key: Optional[str] = None
    expires_in_seconds: Optional[int] = None
    max_estimated_value_rub: Optional[float] = None
    recheck_required: bool = True

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "StrategyProposal":
        if not isinstance(payload, dict):
            raise StrategyModelError("Strategy proposal must be a mapping.")

        operation = _clean_text(payload.get("operation")).lower()
        ticker = _normalize_ticker(payload.get("ticker"))
        reason = _clean_text(payload.get("reason"))
        lots = _positive_int(payload.get("lots"), "lots")
        expires_in_seconds = _optional_positive_int(payload.get("expires_in_seconds"), "expires_in_seconds")
        max_value = _optional_positive_float(payload.get("max_estimated_value_rub"), "max_estimated_value_rub")

        if operation not in SUPPORTED_STRATEGY_OPERATIONS:
            raise StrategyModelError("Strategy proposal operation must be buy or sell.")
        if not ticker:
            raise StrategyModelError("Strategy proposal ticker must use letters and numbers.")
        if not reason:
            raise StrategyModelError("Strategy proposal must include a reason.")

        dedupe_key = payload.get("dedupe_key")
        if dedupe_key is not None:
            dedupe_key = _clean_text(dedupe_key) or None

        return cls(
            operation=operation,
            ticker=ticker,
            lots=lots,
            reason=reason,
            dedupe_key=dedupe_key,
            expires_in_seconds=expires_in_seconds,
            max_estimated_value_rub=max_value,
            recheck_required=_optional_bool(payload.get("recheck_required", True), "recheck_required"),
        )


@dataclass(frozen=True)
class StrategyObservation:
    message: str
    ticker: str = ""
    severity: str = "info"

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "StrategyObservation":
        if not isinstance(payload, dict):
            raise StrategyModelError("Strategy observation must be a mapping.")

        message = _clean_text(payload.get("message") or payload.get("reason"))
        ticker = _optional_ticker(payload.get("ticker"))
        severity = _normalize_observation_severity(payload.get("severity") or "info")

        if not message:
            raise StrategyModelError("Strategy observation must include a message.")

        return cls(message=message, ticker=ticker, severity=severity)


@dataclass(frozen=True)
class StrategyValidationResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def message(self) -> str:
        return " ".join(self.reasons)


@dataclass(frozen=True)
class StrategyRunResult:
    strategy_id: str
    strategy_name: str
    status: str
    reason: str = ""
    strategy_type: str = STRATEGY_TYPE_CONFIRMATION_REQUIRED
    proposal: Optional[StrategyProposal] = None
    observation: Optional[StrategyObservation] = None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StrategyHistoryRowView:
    id: int
    strategy_id: str
    strategy_name: str
    strategy_type: str
    ticker: str
    operation: str
    lots: int
    status: str
    reason: str
    run_id: str = ""
    dedupe_key: str = ""
    dedupe_scope: str = ""
    order_id: Optional[str] = None
    estimated_value_display: str = ""
    created_at_display: str = ""


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_id(value: Any) -> str:
    normalized = _clean_text(value)
    if not normalized or not normalized.replace("_", "").replace("-", "").isalnum():
        return ""
    return normalized


def _normalize_ticker(value: Any) -> str:
    normalized = _clean_text(value).upper()
    if not normalized or not normalized.replace("-", "").isalnum():
        return ""
    return normalized


def _optional_ticker(value: Any) -> str:
    if value in (None, ""):
        return ""
    ticker = _normalize_ticker(value)
    if not ticker:
        raise StrategyModelError("Strategy observation ticker must use letters and numbers.")
    return ticker


def _normalize_strategy_type(value: Any) -> str:
    normalized = _clean_text(value).lower()
    if normalized in {"proposal", "proposals", "confirmation", "confirmation_required"}:
        return STRATEGY_TYPE_CONFIRMATION_REQUIRED
    if normalized in {"observation", "observations", "no_confirmation", "no-confirmation"}:
        return STRATEGY_TYPE_OBSERVATION
    if normalized in {"auto_execute", "auto-execute", "auto_execution", "auto-execution"}:
        return STRATEGY_TYPE_AUTO_EXECUTE
    raise StrategyModelError("Strategy type must be confirmation_required, observation, or auto_execute.")


def _metadata_confirmation_required(payload: dict[str, Any], strategy_type: str) -> bool:
    if "confirmation_required" in payload:
        confirmation_required = _optional_bool(payload.get("confirmation_required"), "confirmation_required")
    else:
        if strategy_type == STRATEGY_TYPE_AUTO_EXECUTE:
            raise StrategyModelError("Auto-execute strategies must set confirmation_required=false.")
        confirmation_required = strategy_type == STRATEGY_TYPE_CONFIRMATION_REQUIRED

    if strategy_type == STRATEGY_TYPE_CONFIRMATION_REQUIRED and not confirmation_required:
        raise StrategyModelError("Confirmation-required strategies must set confirmation_required=true.")
    if strategy_type == STRATEGY_TYPE_OBSERVATION and confirmation_required:
        raise StrategyModelError("Observation strategies must set confirmation_required=false.")
    if strategy_type == STRATEGY_TYPE_AUTO_EXECUTE and confirmation_required:
        raise StrategyModelError("Auto-execute strategies must set confirmation_required=false.")
    return confirmation_required


def _normalize_observation_severity(value: Any) -> str:
    severity = _clean_text(value).lower()
    if severity in {"info", "warning", "error"}:
        return severity
    raise StrategyModelError("Strategy observation severity must be info, warning, or error.")


def _positive_int(value: Any, field_name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise StrategyModelError(f"Strategy proposal {field_name} must be a positive integer.") from exc
    if result < 1:
        raise StrategyModelError(f"Strategy proposal {field_name} must be a positive integer.")
    return result


def _optional_positive_int(value: Any, field_name: str) -> Optional[int]:
    if value in (None, ""):
        return None
    return _positive_int(value, field_name)


def _optional_positive_float(value: Any, field_name: str) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise StrategyModelError(f"Strategy proposal {field_name} must be a positive number.") from exc
    if result <= 0:
        raise StrategyModelError(f"Strategy proposal {field_name} must be a positive number.")
    return result


def _optional_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _clean_text(value).lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise StrategyModelError(f"Strategy {field_name} must be a boolean.")
