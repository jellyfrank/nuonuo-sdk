"""Bounded downloads; allow-list is administrator configuration, never vendor input."""
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

from .exceptions import ProtocolError, TransportError

MAX_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Document:
    name: str
    mimetype: str
    data: bytes


def download_document(url, *, allowed_hosts, kind='pdf'):
    """Download one PDF/OFD/XML without credentials or redirects (10 MB limit)."""
    kinds = {'pdf': 'application/pdf', 'ofd': 'application/ofd', 'xml': 'application/xml'}
    if kind not in kinds:
        raise ValueError('Unsupported document kind')
    parsed = urlsplit(url)
    hosts = {host.strip().lower() for host in allowed_hosts if host.strip()}
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.hostname.lower() not in hosts
            or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError('Document URL is not allowed')
    try:
        with requests.Session() as session:
            session.trust_env = False  # Never inherit netrc credentials or proxy settings.
            with session.get(url, timeout=(5, 30), stream=True, allow_redirects=False) as response:
                if response.status_code != 200:
                    raise TransportError('Document download failed')
                chunks, size = [], 0
                for chunk in response.iter_content(64 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ProtocolError('Document exceeds 10 MB')
                    chunks.append(chunk)
    except requests.RequestException:
        raise TransportError('Document download failed') from None
    content = b''.join(chunks)
    if not content:
        raise ProtocolError('Empty document')
    if kind == 'pdf' and not content.startswith(b'%PDF-'):
        raise ProtocolError('Response is not PDF')
    if kind == 'ofd' and not content.startswith(b'PK'):
        raise ProtocolError('Response is not an OFD container')
    if kind == 'xml' and not content.lstrip(b'\xef\xbb\xbf \r\n\t').startswith(b'<'):
        raise ProtocolError('Response is not XML')
    return Document('invoice.' + kind, kinds[kind], content)
