"""Synchronous, instance-scoped Nuonuo client. No implicit retries or token requests."""
import secrets
import time
import uuid
from collections.abc import Mapping
from urllib.parse import urlencode, urlsplit

import requests
import simplejson as json

from .exceptions import AuthenticationError, ProtocolError, TransportError
from .invoice import Invoice, Nst
from .signing import sign

PRODUCTION_URL = 'https://sdk.nuonuo.com/open/v1/services'
SANDBOX_URL = 'https://sandbox.nuonuocs.cn/open/v1/services'
TOKEN_URL = 'https://open.nuonuo.com/accessToken'
AUTHORIZE_URL = 'https://open.nuonuo.com/authorize'


def _https_url(value, path=None):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or (path and parsed.path != path)):
        raise ValueError('Expected an HTTPS endpoint with no credentials, query or fragment')
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or '\r' in value or '\n' in value:
        raise ValueError(f'{name} must be a non-empty, single-line string')
    return value


class Nuonuo:
    """One instance per application, environment and authorized merchant.

    Tokens are acquired explicitly because the platform limits token requests.
    Persist token responses in the caller's secret store; reuse across workers.
    """

    def __init__(self, app_key, app_secret, *, access_token=None, tax_number='',
                 base_url=PRODUCTION_URL, token_url=TOKEN_URL, timeout=(5, 30)):
        self.app_key = _text(app_key, 'app_key')
        self._app_secret = _text(app_secret, 'app_secret')
        self.base_url = _https_url(base_url, '/open/v1/services')
        self.token_url = _https_url(token_url)
        self.tax_number = _text(tax_number, 'tax_number') if tax_number else ''
        values = timeout if isinstance(timeout, tuple) else (timeout,)
        if len(values) not in (1, 2) or any(not isinstance(v, (int, float)) or not 0 < v < float('inf') for v in values):
            raise ValueError('timeout must contain positive finite seconds')
        self.timeout = timeout
        self._session = requests.Session()
        self._access_token = None
        if access_token is not None:
            self.set_access_token(access_token)
        self.invoice = Invoice(self)
        self.nst = Nst(self)

    def _post(self, url, **kwargs):
        try:
            response = self._session.post(
                url, timeout=self.timeout, allow_redirects=False, **kwargs,
            )
        except requests.RequestException:
            raise TransportError('Network request failed; remote outcome may be unknown') from None
        try:
            if not 200 <= response.status_code < 300:
                raise TransportError(f'Unexpected HTTP status {response.status_code}; no retry performed')
            try:
                data = json.loads(response.content, use_decimal=True)
            except (ValueError, UnicodeError):
                raise ProtocolError('Response is not valid JSON') from None
            if not isinstance(data, dict):
                raise ProtocolError('Expected a JSON object')
            return data
        finally:
            response.close()

    def _token_request(self, fields):
        data = self._post(self.token_url, data=fields)
        token = data.get('access_token')
        if not isinstance(token, str) or not token.strip() or '\r' in token or '\n' in token:
            raise AuthenticationError('Token endpoint returned no valid access token')
        self.set_access_token(token)
        return data

    def set_access_token(self, token):
        """Install a persisted or freshly obtained token without an HTTP request."""
        self._access_token = _text(token, 'access_token')

    def get_merchant_token(self):
        """Self-use application token. Caller manages expiry and shared persistence."""
        return self._token_request({
            'client_id': self.app_key, 'client_secret': self._app_secret,
            'grant_type': 'client_credentials',
        })

    def authorization_url(self, redirect_uri, state):
        """Caller must verify returned state before exchanging the authorization code."""
        return AUTHORIZE_URL + '?' + urlencode({
            'appKey': self.app_key, 'response_type': 'code',
            'redirect_uri': _text(redirect_uri, 'redirect_uri'),
            'state': _text(state, 'state'),
        })

    def exchange_code(self, code, tax_number, redirect_uri):
        """Exchange a one-use ISV authorization code and bind this merchant."""
        tax_number = _text(tax_number, 'tax_number')
        data = self._token_request({
            'client_id': self.app_key, 'client_secret': self._app_secret,
            'grant_type': 'authorization_code', 'code': _text(code, 'code'),
            'taxNum': tax_number, 'redirect_uri': _text(redirect_uri, 'redirect_uri'),
        })
        self.tax_number = tax_number
        return data

    def refresh_isv_token(self, refresh_token, user_id):
        """client_id is the authorized user's userId, NOT appKey, for refresh."""
        return self._token_request({
            'client_id': _text(user_id, 'user_id'), 'client_secret': self._app_secret,
            'grant_type': 'refresh_token',
            'refresh_token': _text(refresh_token, 'refresh_token'),
        })

    def call(self, method, data, *, senid=None):
        """Return the full business envelope, including error codes, unchanged.

        senid identifies transport requests, not a substitute for order identity.
        There is deliberately no auto-refresh, retry, or success-code guessing.
        """
        _text(method, 'method')
        if not isinstance(data, Mapping):
            raise TypeError('data must be a mapping of official API fields')
        if not self._access_token:
            raise AuthenticationError('Set or explicitly acquire an access token first')
        if senid is None:
            senid = uuid.uuid4().hex
        if not isinstance(senid, str) or len(senid) != 32 or not senid.isascii() or not senid.isalnum():
            raise ValueError('senid must contain 32 ASCII letters or digits')
        content = json.dumps(dict(data), ensure_ascii=False, separators=(',', ':'),
                             use_decimal=True, allow_nan=False)
        # simplejson permits non-finite Decimal values; strict parse catches them too.
        json.loads(content, allow_nan=False)
        timestamp = str(int(time.time()))
        nonce = str(10_000_000 + secrets.randbelow(90_000_000))
        result = self._post(
            self.base_url,
            params={'senid': senid, 'nonce': nonce, 'timestamp': timestamp, 'appkey': self.app_key},
            headers={
                'Content-Type': 'application/json; charset=UTF-8',
                'X-Nuonuo-Sign': sign(self._app_secret, self.app_key, senid, nonce, content, timestamp),
                'accessToken': self._access_token, 'userTax': self.tax_number, 'method': method,
            },
            data=content.encode('utf-8'),
        )
        if not isinstance(result.get('code'), (str, int)):
            raise ProtocolError('Response has no business code')
        return result

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
