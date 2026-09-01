import logging


def configureLogging(logLevel: str) -> None:
    """Configure concise application logging without request content or secrets."""

    logging.basicConfig(
        level=getattr(logging, logLevel.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
