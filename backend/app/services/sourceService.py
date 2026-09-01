from app.core.security import validatePublicUrl
from app.schemas.evidence import EvidenceRecord


def validateEvidenceTraceability(evidence: list[EvidenceRecord]) -> None:
    """Reject duplicate evidence IDs and records without traceable source URLs."""

    evidenceIds: set[str] = set()
    for record in evidence:
        if record.evidenceId in evidenceIds:
            raise ValueError(f"Duplicate evidence ID: {record.evidenceId}")
        if not str(record.source.url):
            raise ValueError(f"Evidence has no source URL: {record.evidenceId}")
        validatePublicUrl(str(record.source.url))
        evidenceIds.add(record.evidenceId)
