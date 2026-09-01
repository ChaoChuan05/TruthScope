import pytest

from app.core.exceptions import UnsafeUrlError
from app.core.security import validatePublicUrl
from app.schemas.verification import VerificationRequest


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/",
        "http://[::1]/",
        "file:///etc/passwd",
        "https://localhost/private",
        "https://user:secret@example.com/",
    ],
)
def test_privateOrUnsafeUrl_isRejected(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validatePublicUrl(url)


def test_publicUrl_isAccepted() -> None:
    assert validatePublicUrl("https://data.gov.my/") == "https://data.gov.my/"


def test_urlVerificationRequest_rejectsLocalhost() -> None:
    with pytest.raises(ValueError):
        VerificationRequest(input="http://localhost/private", inputType="url")
