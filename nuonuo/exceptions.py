"""Errors deliberately omit URLs, credentials and remote response bodies."""


class NuonuoError(Exception):
    """Base SDK error."""


class TransportError(NuonuoError):
    """Outcome may be unknown; never blindly repeat an invoice submission."""


class ProtocolError(NuonuoError):
    """The remote response did not follow the expected JSON contract."""


class AuthenticationError(NuonuoError):
    """Token endpoint rejected the request or returned no token."""
