import base64
import hashlib
import hmac
from decimal import Decimal
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import simplejson as json

from nuonuo import Nuonuo, SANDBOX_URL, AuthenticationError, ProtocolError, TransportError
from nuonuo.signing import sign


@pytest.fixture
def client():
    with Nuonuo('app', 'secret', access_token='token', tax_number='tax', base_url=SANDBOX_URL) as c:
        c._session.post = Mock()
        c._session.post.return_value = response({'code': 'E0000', 'result': {}})
        yield c


def response(data, status=200):
    r = requests.Response()
    r.status_code = status
    r._content = json.dumps(data).encode()
    r._content_consumed = True
    return r


def test_signature_official_vector():
    # Frozen against official NNOpenSDK.py get_sign; synthetic credentials only.
    assert sign('secret', 'app', 'a' * 32, '12345678', '{"name":"中文"}', '1700000000') == '4BzcKzrcoqxPis0W/W3X2ae0uIo='


def test_wire_bytes_and_precision(client, monkeypatch):
    monkeypatch.setattr('nuonuo.client.time.time', lambda: 1700000000)
    monkeypatch.setattr('nuonuo.client.secrets.randbelow', lambda n: 2345678)
    client.call('nuonuo.example', {'name': '中文', 'amount': Decimal('123456789.123456789')}, senid='a' * 32)
    args, kw = client._session.post.call_args
    assert args == (SANDBOX_URL,)
    assert kw['params'] == {'appkey': 'app', 'senid': 'a' * 32, 'nonce': '12345678', 'timestamp': '1700000000'}
    assert kw['data'] == '{"name":"中文","amount":123456789.123456789}'.encode()
    source = b'a=services&l=v1&p=open&k=app&i=' + b'a' * 32 + b'&n=12345678&t=1700000000&f=' + kw['data']
    expected = base64.b64encode(hmac.new(b'secret', source, hashlib.sha1).digest()).decode()
    assert kw['headers']['X-Nuonuo-Sign'] == expected
    assert kw['headers']['accessToken'] == 'token'
    assert kw['headers']['userTax'] == 'tax'
    assert kw['allow_redirects'] is False
    assert kw['timeout'] == (5, 30)


@pytest.mark.parametrize('code', ['E0000', 'S0000', '200', 'S0101', 'E9500', 'invalid_token'])
def test_business_envelope_not_interpreted_or_retried(client, code):
    expected = {'code': code, 'describe': '说明', 'result': [1, 2]}
    client._session.post.return_value = response(expected)
    assert client.invoice.pending() == expected
    assert client._session.post.call_count == 1


@pytest.mark.parametrize('status', [301, 302, 400, 401, 429, 500])
def test_http_failure_no_retry(client, status):
    client._session.post.return_value = response({'secret': 'sensitive'}, status)
    with pytest.raises(TransportError) as exc:
        client.invoice.pending()
    assert 'sensitive' not in str(exc.value)
    assert client._session.post.call_count == 1


def test_timeout_no_retry_or_leaked_credentials(client):
    client._session.post.side_effect = requests.Timeout('https://secret.example/?accessToken=private')
    with pytest.raises(TransportError) as exc:
        client.invoice.pending()
    assert 'private' not in str(exc.value)
    assert exc.value.__suppress_context__
    assert client._session.post.call_count == 1


@pytest.mark.parametrize('content', [b'<html>error</html>', b'[]', b'null', b'{}', b'{"code":null}', b'\xff'])
def test_malformed_response(client, content):
    client._session.post.return_value._content = content
    with pytest.raises(ProtocolError):
        client.invoice.pending()


def test_token_contracts(client):
    client._session.post.return_value = response({'access_token': 'new', 'expires_in': '86400', 'refresh_token': 'r', 'userId': 'u'})
    assert client.get_merchant_token()['access_token'] == 'new'
    assert client._session.post.call_args.kwargs['data'] == {
        'client_id': 'app', 'client_secret': 'secret', 'grant_type': 'client_credentials'}
    client.exchange_code('code', 'merchant', 'https://example.com/callback')
    fields = client._session.post.call_args.kwargs['data']
    assert fields['taxNum'] == 'merchant'
    assert fields['grant_type'] == 'authorization_code'
    assert client.tax_number == 'merchant'
    client.refresh_isv_token('r', 'u')
    assert client._session.post.call_args.kwargs['data'] == {
        'client_id': 'u', 'client_secret': 'secret', 'grant_type': 'refresh_token', 'refresh_token': 'r'}


def test_token_rejection_does_not_replace_token(client):
    client._session.post.return_value = response({'error': 'invalid_client', 'error_description': 'sensitive'})
    with pytest.raises(AuthenticationError) as exc:
        client.get_merchant_token()
    assert 'sensitive' not in str(exc.value)
    assert client._access_token == 'token'


def test_authorization_url(client):
    query = parse_qs(urlsplit(client.authorization_url('https://example.com/cb?a=1&b=2', 'a+b')).query)
    assert query == {'appKey': ['app'], 'response_type': ['code'], 'redirect_uri': ['https://example.com/cb?a=1&b=2'], 'state': ['a+b']}


def test_no_implicit_auth_and_instance_isolation(client):
    with Nuonuo('other', 'other-secret') as other:
        other._session.post = Mock()
        with pytest.raises(AuthenticationError):
            other.invoice.pending()
        other._session.post.assert_not_called()
        other.set_access_token('other-token')
        assert client._access_token == 'token'


@pytest.mark.parametrize('kwargs', [{}, {'order_nos': 'abc'}, {'order_nos': ['']}, {'order_nos': ['a'] * 51}, {'order_nos': ['a'], 'serial_nos': ['b']}])
def test_query_validation(client, kwargs):
    with pytest.raises(ValueError):
        client.invoice.query(**kwargs)
    client._session.post.assert_not_called()


def test_query_shape(client):
    client.invoice.query(order_nos=['order'], include_details=True)
    assert json.loads(client._session.post.call_args.kwargs['data']) == {'orderNos': ['order'], 'isOfferInvoiceDetail': '1'}


@pytest.mark.parametrize('group,name,method', [
    ('invoice', 'pdf_url', 'nuonuo.ElectronInvoice.getPDF'),
    ('invoice', 'inspect', 'nuonuo.electronInvoice.invoiceInspection'),
    ('invoice', 'cancel', 'nuonuo.electronInvoice.invoiceCancellation'),
    ('invoice', 'redeliver', 'nuonuo.ElectronInvoice.deliveryInvoice'),
    ('invoice', 'issue_red', 'nuonuo.ElectronInvoice.unifiedfastInvoiceRed'),
    ('nst', 'issue', 'nuonuo.OpeMplatform.requestBillingNew'),
    ('nst', 'list_invoices', 'nuonuo.OpeMplatform.queryInvoiceList'),
])
def test_documented_method_mapping(client, group, name, method):
    getattr(getattr(client, group), name)({'orderNo': 'existing'}, senid='b' * 32)
    kw = client._session.post.call_args.kwargs
    assert kw['headers']['method'] == method
    assert json.loads(kw['data']) == ({'order': {'orderNo': 'existing'}} if name == 'issue' else {'orderNo': 'existing'})


@pytest.mark.parametrize('value', [float('nan'), float('inf'), Decimal('NaN'), Decimal('Infinity')])
def test_reject_nonfinite_money(client, value):
    with pytest.raises(ValueError):
        client.call('nuonuo.test', {'amount': value})
    client._session.post.assert_not_called()


@pytest.mark.parametrize('url', ['http://example.com/open/v1/services', 'https://user:pass@example.com/open/v1/services', 'https://example.com/wrong', SANDBOX_URL + '?x=1'])
def test_endpoint_validation(url):
    with pytest.raises(ValueError):
        Nuonuo('a', 'b', base_url=url)


@pytest.mark.parametrize('senid', ['', 'a', '中' * 32, '-' * 32])
def test_senid_validation(client, senid):
    with pytest.raises(ValueError):
        client.invoice.pending(senid=senid)
    client._session.post.assert_not_called()


@pytest.mark.parametrize('order', [{}, {'orderNo': ''}, {'orderNo': 'x' * 65}, None])
def test_issue_requires_persistable_identity(client, order):
    with pytest.raises((ValueError, TypeError)):
        client.nst.issue(order)
    client._session.post.assert_not_called()


def test_response_decimal_preserved(client):
    client._session.post.return_value._content = b'{"code":"E0000","result":{"amount":123.4567890123456789}}'
    assert client.invoice.pending()['result']['amount'] == Decimal('123.4567890123456789')


def test_nst_query_namespace(client):
    client.nst.query(order_nos=['persisted'], include_details=True)
    kw = client._session.post.call_args.kwargs
    assert kw['headers']['method'] == 'nuonuo.OpeMplatform.queryInvoiceResult'
    assert json.loads(kw['data']) == {'orderNos': ['persisted'], 'isOfferInvoiceDetail': '1'}


@pytest.mark.parametrize('kwargs', [{}, {'order_nos': 'a'}, {'order_nos': ['a'] * 51}, {'serial_nos': ['a'], 'order_nos': ['a']}])
def test_nst_query_validation(client, kwargs):
    with pytest.raises(ValueError):
        client.nst.query(**kwargs)
    client._session.post.assert_not_called()


@pytest.mark.parametrize('url', ['http://files.example/a', 'https://evil.example/a', 'https://u:p@files.example/a', 'https://files.example:8443/a'])
def test_document_host_guard(url):
    from nuonuo.documents import download_document
    with pytest.raises(ValueError):
        download_document(url, allowed_hosts=['files.example'])


def test_download_bounded_and_no_redirect(monkeypatch):
    from nuonuo.documents import download_document
    from unittest.mock import MagicMock
    session = MagicMock()
    monkeypatch.setattr('nuonuo.documents.requests.Session', lambda: session)
    r = session.__enter__.return_value.get.return_value.__enter__.return_value
    r.status_code = 200
    r.iter_content.return_value = [b'%PDF-synthetic']
    doc = download_document('https://files.example/a', allowed_hosts=['files.example'])
    assert doc.data == b'%PDF-synthetic'
    assert session.__enter__.return_value.trust_env is False
    assert session.__enter__.return_value.get.call_args.kwargs['allow_redirects'] is False
    r.status_code = 302
    with pytest.raises(TransportError):
        download_document('https://files.example/a', allowed_hosts=['files.example'])
    r.status_code = 200
    r.iter_content.return_value = [b'x' * (10 * 1024 * 1024 + 1)]
    with pytest.raises(ProtocolError):
        download_document('https://files.example/a', allowed_hosts=['files.example'])
