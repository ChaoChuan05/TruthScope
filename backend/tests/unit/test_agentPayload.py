from app.agents.nodes.common import evidenceForModel


def test_evidencePayload_capsModelExcerptWithoutMutatingStoredEvidence(sampleEvidence) -> None:
    originalExcerpt = "x" * 5_000
    evidence = sampleEvidence.model_copy(update={"excerpt": originalExcerpt})

    payload = evidenceForModel([evidence], maxExcerptChars=1_500)

    assert payload[0]["excerpt"] == "x" * 1_500
    assert "Model input excerpt capped at 1500 characters." in payload[0]["limitations"]
    assert evidence.excerpt == originalExcerpt
