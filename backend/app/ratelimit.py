"""Per-IP rate limit (slowapi). In memory: fine for one API instance, see README limits.

The key must be an address the client can't choose. X-Forwarded-For is never used: its
leftmost entry is whatever the client sent, so trusting it let anyone reset their limit
with a fake header (found on the live deploy). Behind Cloudflare (Render's edge), the
CF-Connecting-IP header is set by Cloudflare to the real client address, so we use it
only when TRUST_CF_CONNECTING_IP says we're behind Cloudflare. Otherwise (local, CI) the
socket address is the client.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def client_ip(request: Request) -> str:
    if get_settings().trust_cf_connecting_ip:
        if cf_ip := request.headers.get("cf-connecting-ip", "").strip():
            return cf_ip
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
