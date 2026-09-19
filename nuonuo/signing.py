"""Nuonuo /open/v1/services signature, matching the official Python sample."""
import base64
import hashlib
import hmac


def sign(secret, app_key, senid, nonce, content, timestamp):
    """Sign the exact Unicode JSON text subsequently sent as UTF-8 bytes."""
    message = (
        f"a=services&l=v1&p=open&k={app_key}&i={senid}"
        f"&n={nonce}&t={timestamp}&f={content}"
    )
    digest = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha1).digest()
    return base64.b64encode(digest).decode('ascii')
