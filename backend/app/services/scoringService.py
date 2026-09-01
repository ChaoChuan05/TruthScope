from collections import defaultdict
from collections.abc import Sequence

from app.schemas.agentOutput import AgentAnalysis, BiasAuditResult, ContextAnalysis
from app.schemas.common import BiasAuditStatus, EvidenceStance, Verdict
from app.schemas.evidence import EvidenceRecord
from app.schemas.verification import Claim, VerificationScore

FORMULA_VERSION = "truthscope-evidence-v1"


def _signedStance(stance: EvidenceStance, strength: float) -> float:
    if stance == EvidenceStance.SUPPORTS:
        return strength
    if stance == EvidenceStance.CONTRADICTS:
        return -strength
    return 0.0


def _verdictForScores(truthScore: float, confidenceScore: float) -> Verdict:
    if confidenceScore < 40:
        return Verdict.MIXED_OR_INCONCLUSIVE
    if truthScore <= 19:
        return Verdict.STRONGLY_CONTRADICTED
    if truthScore <= 39:
        return Verdict.MOSTLY_CONTRADICTED
    if truthScore <= 60:
        return Verdict.MIXED_OR_INCONCLUSIVE
    if truthScore <= 80:
        return Verdict.MOSTLY_SUPPORTED
    return Verdict.STRONGLY_SUPPORTED


def calculateModelAgreement(analyses: Sequence[AgentAnalysis]) -> float:
    if len(analyses) < 2:
        return 0.5 if analyses else 0.0
    values = [_signedStance(item.stance, item.supportStrength) for item in analyses]
    pairScores: list[float] = []
    for index, leftValue in enumerate(values):
        for rightValue in values[index + 1 :]:
            pairScores.append(1 - abs(leftValue - rightValue) / 2)
    return sum(pairScores) / len(pairScores)


def calculateVerificationScore(
    *,
    claims: Sequence[Claim],
    evidence: Sequence[EvidenceRecord],
    analyses: Sequence[AgentAnalysis],
    biasAudit: BiasAuditResult | None,
    contextAnalysis: ContextAnalysis | None,
) -> VerificationScore | None:
    """Calculate evidence support and confidence without political identity inputs."""

    if not evidence:
        return None

    assessmentValues: defaultdict[str, list[float]] = defaultdict(list)
    for analysis in analyses:
        for assessment in analysis.evidenceAssessments:
            assessmentValues[assessment.evidenceId].append(
                _signedStance(assessment.stance, assessment.strength)
            )

    weightedSupport = 0.0
    directionalWeight = 0.0
    totalQuality = 0.0
    directionalValues: list[tuple[float, float]] = []
    coveredClaimIds: set[str] = set()
    for record in evidence:
        qualityWeight = record.quality.normalizedWeight()
        totalQuality += qualityWeight
        coveredClaimIds.update(record.claimIds)
        values = assessmentValues.get(record.evidenceId)
        stanceValue = (
            sum(values) / len(values)
            if values
            else _signedStance(record.stance, record.stanceStrength)
        )
        if stanceValue:
            effectiveWeight = qualityWeight * abs(stanceValue)
            weightedSupport += qualityWeight * stanceValue
            directionalWeight += effectiveWeight
            directionalValues.append((stanceValue, qualityWeight))

    supportValue = (
        weightedSupport / sum(weight for _, weight in directionalValues) if directionalValues else 0
    )
    supportValue = max(-1.0, min(1.0, supportValue))
    truthScore = round(50 + 50 * supportValue, 2)

    averageQuality = totalQuality / len(evidence)
    coverage = len(coveredClaimIds) / len(claims) if claims else 0.0
    absoluteWeighted = sum(abs(value) * weight for value, weight in directionalValues)
    consistency = abs(weightedSupport) / absoluteWeighted if absoluteWeighted else 0.0
    modelAgreement = calculateModelAgreement(analyses)
    evidenceSufficiency = min(len(directionalValues) / 2, 1.0)
    confidence = (
        0.35 * averageQuality + 0.25 * coverage + 0.20 * consistency + 0.20 * modelAgreement
    ) * evidenceSufficiency
    if 0 < len(analyses) < 2:
        confidence *= 0.75
    if biasAudit is None or biasAudit.status != BiasAuditStatus.PASSED:
        confidence *= biasAudit.confidencePenalty if biasAudit else 0.7
    if contextAnalysis and (
        contextAnalysis.staleEvidenceIds or contextAnalysis.suspectedTruncationEvidenceIds
    ):
        confidence *= 0.85
    confidenceScore = round(max(0.0, min(100.0, confidence * 100)), 2)

    return VerificationScore(
        truthScore=truthScore,
        confidenceScore=confidenceScore,
        verdict=_verdictForScores(truthScore, confidenceScore),
        evidenceWeight=round(directionalWeight, 4),
        evidenceCoverage=round(coverage, 4),
        modelAgreement=round(modelAgreement, 4),
        formulaVersion=FORMULA_VERSION,
    )
