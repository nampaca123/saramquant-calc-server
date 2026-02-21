import logging

from app.schema.dto.pipeline_metadata import PipelineMetadata
from app.db.repositories.audit_log import insert_audit_log

logger = logging.getLogger(__name__)


def log_api(method: str, path: str, status_code: int, duration_ms: int) -> None:
    insert_audit_log(
        server="calc",
        action="API",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
    )


def log_pipeline(meta: PipelineMetadata) -> None:
    insert_audit_log(
        server="calc",
        action="PIPELINE",
        method=meta.command,
        path=f"pipeline/{meta.command}",
        duration_ms=meta.total_duration_ms,
        metadata=meta.to_dict(),
    )
