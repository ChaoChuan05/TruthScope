from collections import defaultdict
from collections.abc import Sequence

from app.schemas.agentOutput import AgentAnalysis, BiasAuditResult, ContextAnalysis
from app.schemas.common import BiasAuditStatus, EvidenceStance, Verdict
from app.schemas.evidence import EvidenceRecord
from app.schemas.verification import Claim, VerificationScore

FORMULA_VERSION = "truthscope-evidence-v2"


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
    if not analyses:
        return 0.0
    analysesByClaim: defaultdict[str, list[AgentAnalysis]] = defaultdict(list)
    for analysis in analyses:
        analysesByClaim[analysis.claimId].append(analysis)

    pairScores: list[float] = []
    for claimAnalyses in analysesByClaim.values():
        valuesByModel: defaultdict[str, list[float]] = defaultdict(list)
        for analysis in claimAnalyses:
            valuesByModel[analysis.modelName].append(
                _signedStance(analysis.stance, analysis.supportStrength)
            )
        values = [sum(items) / len(items) for items in valuesByModel.values()]
        for index, leftValue in enumerate(values):
            for rightValue in values[index + 1 :]:
                pairScores.append(1 - abs(leftValue - rightValue) / 2)
    return sum(pairScores) / len(pairScores) if pairScores else 0.5


def _hasIndependentVerifierCoverage(
    claims: Sequence[Claim],
    analyses: Sequence[AgentAnalysis],
) -> bool:
    modelsByClaim: defaultdict[str, set[str]] = defaultdict(set)
    for analysis in analyses:
        modelsByClaim[analysis.claimId].add(analysis.modelName)
    return bool(claims) and all(len(modelsByClaim[claim.claimId]) >= 2 for claim in claims)


def calculateVerificationScore(
    *,
    claims: Sequence[Claim],
    evidence: Sequence[EvidenceRecord],
    analyses: Sequence[AgentAnalysis],
    biasAudit: BiasAuditResult | None,
    contextAnalysis: ContextAnalysis | None,
) -> VerificationScore | None:
    """Calculate evidence support and confidence without political identity inputs."""

    if not evidence or not claims:
        return None

    assessmentValues: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    for analysis in analyses:
        for assessment in analysis.evidenceAssessments:
            assessmentValues[(analysis.claimId, assessment.evidenceId)].append(
                _signedStance(assessment.stance, assessment.strength)
            )

    claimTruthScores: list[float] = []
    claimAverageQualities: list[float] = []
    claimConsistencies: list[float] = []
    claimEvidenceSufficiencies: list[float] = []
    directionalWeight = 0.0
    coveredClaimIds: set[str] = set()
    for claim in claims:
        claimEvidence = [record for record in evidence if claim.claimId in record.claimIds]
        if claimEvidence:
            coveredClaimIds.add(claim.claimId)

        weightedSupport = 0.0
        totalQuality = 0.0
        directionalValues: list[tuple[float, float]] = []
        for record in claimEvidence:
            qualityWeight = record.quality.normalizedWeight()
            totalQuality += qualityWeight
            values = assessmentValues.get((claim.claimId, record.evidenceId))
            stanceValue = (
                sum(values) / len(values)
                if values
                else _signedStance(record.stance, record.stanceStrength)
            )
            if stanceValue:
                weightedSupport += qualityWeight * stanceValue
                directionalWeight += qualityWeight * abs(stanceValue)
                directionalValues.append((stanceValue, qualityWeight))

        supportValue = (
            weightedSupport / sum(weight for _, weight in directionalValues)
            if directionalValues
            else 0
        )
        supportValue = max(-1.0, min(1.0, supportValue))
        claimTruthScores.append(50 + 50 * supportValue)
        claimAverageQualities.append(totalQuality / len(claimEvidence) if claimEvidence else 0.0)
        absoluteWeighted = sum(abs(value) * weight for value, weight in directionalValues)
        claimConsistencies.append(
            abs(weightedSupport) / absoluteWeighted if absoluteWeighted else 0.0
        )
        claimEvidenceSufficiencies.append(min(len(directionalValues) / 2, 1.0))

    truthScore = round(sum(claimTruthScores) / len(claimTruthScores), 2)
    averageQuality = sum(claimAverageQualities) / len(claimAverageQualities)
    coverage = len(coveredClaimIds) / len(claims)
    consistency = sum(claimConsistencies) / len(claimConsistencies)
    modelAgreement = calculateModelAgreement(analyses)
    hasIndependentVerifierCoverage = _hasIndependentVerifierCoverage(claims, analyses)
    evidenceSufficiency = sum(claimEvidenceSufficiencies) / len(claimEvidenceSufficiencies)
    confidence = (
        0.35 * averageQuality + 0.25 * coverage + 0.20 * consistency + 0.20 * modelAgreement
    ) * evidenceSufficiency
    if analyses and not hasIndependentVerifierCoverage:
        confidence *= 0.75
    if biasAudit is None or biasAudit.status != BiasAuditStatus.PASSED:
        confidence *= biasAudit.confidencePenalty if biasAudit else 0.7
    if contextAnalysis and (
        contextAnalysis.staleEvidenceIds or contextAnalysis.suspectedTruncationEvidenceIds
    ):
        confidence *= 0.85
    confidenceScore = round(max(0.0, min(100.0, confidence * 100)), 2)
    verdict = _verdictForScores(truthScore, confidenceScore)
    if not hasIndependentVerifierCoverage or (
        biasAudit is None or biasAudit.status != BiasAuditStatus.PASSED
    ):
        verdict = Verdict.MIXED_OR_INCONCLUSIVE

    return VerificationScore(
        truthScore=truthScore,
        confidenceScore=confidenceScore,
        verdict=verdict,
        evidenceWeight=round(directionalWeight, 4),
        evidenceCoverage=round(coverage, 4),
        modelAgreement=round(modelAgreement, 4),
        formulaVersion=FORMULA_VERSION,
    )
