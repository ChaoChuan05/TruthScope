import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.exceptions import UnsafeUrlError

BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal"}


def validatePublicUrl(url: str) -> str:
    """Reject unsupported schemes and obvious private-network targets."""

    parsedUrl = urlsplit(url)
    if parsedUrl.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are allowed.")
    if not parsedUrl.hostname or parsedUrl.username or parsedUrl.password:
        raise UnsafeUrlError("URL must contain a public hostname and no embedded credentials.")

    hostname = parsedUrl.hostname.rstrip(".").lower()
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith((".localhost", ".local")):
        raise UnsafeUrlError("Local network URLs are not allowed.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return url

    if not address.is_global:
        raise UnsafeUrlError("Private, loopback, link-local, and reserved URLs are not allowed.")
    return url


async def validatePublicHostResolution(url: str) -> str:
    """Resolve a hostname and reject any non-public address before retrieval."""

    validatePublicUrl(url)
    parsedUrl = urlsplit(url)
    hostname = parsedUrl.hostname
    if hostname is None:
        raise UnsafeUrlError("URL must contain a hostname.")

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            parsedUrl.port or (443 if parsedUrl.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise UnsafeUrlError("URL hostname could not be resolved.") from error

    if not addresses:
        raise UnsafeUrlError("URL hostname did not resolve to an address.")
    for addressInfo in addresses:
        address = ipaddress.ip_address(addressInfo[4][0])
        if not address.is_global:
            raise UnsafeUrlError("URL resolves to a non-public network address.")
    return url
