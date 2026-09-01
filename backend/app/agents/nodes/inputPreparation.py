import logging

from app.agents.nodes.common import AsyncNode, NodeUpdate, workflowError
from app.agents.state import VerificationGraphState
from app.integrations.retrieval.client import DocumentFetcherProtocol
from app.schemas.common import InputType

logger = logging.getLogger(__name__)


def createInputPreparationNode(documentFetcher: DocumentFetcherProtocol) -> AsyncNode:
    async def inputPreparation(state: VerificationGraphState) -> NodeUpdate:
        if state["inputType"] == InputType.TEXT:
            return {
                "analysisInput": state["originalInput"],
                "sourceDocument": None,
            }

        try:
            document = await documentFetcher.fetch(state["originalInput"])
            return {
                "analysisInput": document.text,
                "sourceDocument": document,
            }
        except Exception as error:
            logger.warning(
                "URL input preparation failed requestId=%s errorType=%s",
                state.get("requestId"),
                type(error).__name__,
            )
            return {
                "analysisInput": "",
                "sourceDocument": None,
                "errors": [
                    workflowError(
                        code="URL_INPUT_RETRIEVAL_FAILED",
                        stage="inputPreparation",
                        message="The public URL could not be retrieved safely.",
                        retryable=True,
                    )
                ],
                "warnings": ["Verification stopped before URL claim extraction."],
            }

    return inputPreparation
