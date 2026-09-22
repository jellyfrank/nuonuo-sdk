"""Thin business wrappers preserve official field spelling and business responses."""
from collections.abc import Mapping


class Invoice:
    def __init__(self, client):
        self._client = client

    def pending(self, extension_num=None, *, senid=None):
        """100075: speed-billing requests within the platform's 72-hour window."""
        data = {} if extension_num is None else {'extensionNum': str(extension_num)}
        return self._client.call('nuonuo.speedBilling.querySpeedBilling', data, senid=senid)

    def query(self, *, serial_nos=None, order_nos=None, include_details=False, senid=None):
        """100188: query up to 50 existing order numbers OR invoice serials."""
        if bool(serial_nos) == bool(order_nos):
            raise ValueError('Provide either serial_nos or order_nos')
        values = serial_nos if serial_nos else order_nos
        if (not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 50
                or any(not isinstance(v, str) or not v.strip() for v in values)):
            raise ValueError('Provide 1 to 50 non-empty string identifiers')
        data = {'serialNos' if serial_nos else 'orderNos': list(values),
                'isOfferInvoiceDetail': '1' if include_details else '0'}
        return self._client.call('nuonuo.ElectronInvoice.queryInvoiceResult', data, senid=senid)

    def pdf_url(self, data, *, senid=None):
        """100185: return the PDF URL envelope; does not download the file."""
        return self._client.call('nuonuo.ElectronInvoice.getPDF', data, senid=senid)

    def inspect(self, data, *, senid=None):
        """100136: invoice authenticity inspection; may consume paid quota."""
        return self._client.call('nuonuo.electronInvoice.invoiceInspection', data, senid=senid)

    def cancel(self, data, *, senid=None):
        """100166: cancel an eligible issued invoice."""
        return self._client.call('nuonuo.electronInvoice.invoiceCancellation', data, senid=senid)

    def redeliver(self, data, *, senid=None):
        """100249: explicitly send an existing invoice via provider email/SMS."""
        return self._client.call('nuonuo.ElectronInvoice.deliveryInvoice', data, senid=senid)

    def issue_red(self, data, *, senid=None):
        """101018: full red reversal, only for supported WeChat/Alipay linked blue invoices."""
        return self._client.call('nuonuo.ElectronInvoice.unifiedfastInvoiceRed', data, senid=senid)


class Nst:
    """Separate Nuoshuitong SaaS product; requires corresponding entitlement."""

    def __init__(self, client):
        self._client = client

    def issue(self, order, *, senid=None):
        """100607: submit official order fields; persist order identity BEFORE calling."""
        if not isinstance(order, Mapping):
            raise TypeError('order must be a mapping of official order fields')
        order_no = order.get('orderNo')
        if not isinstance(order_no, str) or not order_no.strip() or len(order_no) > 64:
            raise ValueError('Persist a non-empty orderNo of at most 64 characters before submission')
        return self._client.call('nuonuo.OpeMplatform.requestBillingNew', {'order': order}, senid=senid)

    def list_invoices(self, data, *, senid=None):
        """100595: paginated invoice list; caller supplies official filter fields."""
        return self._client.call('nuonuo.OpeMplatform.queryInvoiceList', data, senid=senid)

    def query(self, *, serial_nos=None, order_nos=None, include_details=False, senid=None):
        """NST result lookup verified against the authorized test account.

        The payload matches the invoice result query, but the product namespace differs.
        """
        if bool(serial_nos) == bool(order_nos):
            raise ValueError('Provide either serial_nos or order_nos')
        values = serial_nos if serial_nos else order_nos
        if (not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 50
                or any(not isinstance(v, str) or not v.strip() for v in values)):
            raise ValueError('Provide 1 to 50 non-empty string identifiers')
        data = {'serialNos' if serial_nos else 'orderNos': list(values),
                'isOfferInvoiceDetail': '1' if include_details else '0'}
        return self._client.call('nuonuo.OpeMplatform.queryInvoiceResult', data, senid=senid)
