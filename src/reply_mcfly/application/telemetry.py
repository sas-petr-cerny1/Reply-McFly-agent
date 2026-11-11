import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger("reply_mcfly.workflow")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def emit(
    event: str,
    *,
    job_id: str | None = None,
    status: str | None = None,
    error_code: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "event": event,
                "job_id": job_id,
                "correlation_id": job_id,
                "status": status,
                "error_code": error_code,
                "duration_seconds": duration_seconds,
            }
        )
    )
