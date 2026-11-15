# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Honest, human-readable explanations for failures (what broke, why, and what we do about it) + a retrying HTTP session.
Observatory servers are often overloaded during busy periods (e.g. hackathons): we retry, fall back to saved data, and always say so."""
import re, socket
import requests
from requests.adapters import HTTPAdapter

RETRY_CODES = (429, 500, 502, 503, 504)
HINT = "We show saved data when we have it. Otherwise try again in a minute - or switch to Demo data."


class _TimeoutAdapter(HTTPAdapter):
    """Gives every request a default timeout (requests has none, so a silent server could hang the app forever)."""
    def __init__(self, *a, timeout=(10, 60), **k):
        self._to = timeout
        super().__init__(*a, **k)

    def send(self, request, **kw):
        if kw.get("timeout") is None:
            kw["timeout"] = self._to
        return super().send(request, **kw)


def session(timeout=(10, 60)):
    """requests session with default timeouts that retries transient server errors with a growing pause (1.5 s, 3 s, 6 s)."""
    from urllib3.util.retry import Retry
    s = requests.Session()
    ad = _TimeoutAdapter(timeout=timeout, max_retries=Retry(total=3, connect=2, read=1, status=3, backoff_factor=1.5,
                                                            status_forcelist=RETRY_CODES, allowed_methods=None, respect_retry_after_header=True))
    s.mount("https://", ad); s.mount("http://", ad)
    return s


def code_of(e):
    r = getattr(e, "response", None)
    if r is not None and getattr(r, "status_code", None):
        return int(r.status_code)
    for a in ("code", "status_code", "status"):
        v = getattr(e, a, None)
        if isinstance(v, int) and 100 <= v < 600:
            return v
    m = re.search(r"(?:http(?: error)?|status(?: code)?|error)\D{0,3}\b([45]\d\d)\b", str(e), re.I)
    return int(m.group(1)) if m else None


def explain(e, service="the data service"):
    """-> dict(title, detail, hint, code, service, upstream, retry). 'upstream' = the fault is outside our app."""
    code, text = code_of(e), str(e).lower()
    up, retry = True, True
    if isinstance(e, ImportError):
        return dict(title="Real-data mode needs extra Python packages", detail=str(e)[:160], hint="Run: pip install astropy pyvo reproject - then restart. Demo data still works.",
                    code=None, service=service, upstream=False, retry=False)
    if isinstance(e, (requests.exceptions.Timeout, socket.timeout, TimeoutError)) or "timed out" in text:
        title, detail = f"{service} did not answer in time", "The server is slow or overloaded right now."
    elif isinstance(e, (requests.exceptions.ConnectionError, socket.gaierror, ConnectionError)) and not code:
        title, detail = f"Cannot reach {service}", "No connection to the server - your internet, a VPN or a firewall may be blocking it."
    elif code == 429:
        title, detail = f"{service} says: too many requests (error 429)", "The archive asks us to slow down."
    elif code and code >= 500:
        title, detail = f"{service} is temporarily unavailable (error {code})", "The servers are overloaded or under maintenance."
    elif code in (401, 403):
        title, detail = f"{service} refused the request (error {code})", "Access is blocked or needs a login."
        retry = False
    elif code == 404:
        title, detail = f"{service} has no data for this request (error 404)", "That position or file is not in the archive."
        retry = False
    elif code or isinstance(e, (requests.exceptions.RequestException, OSError)) or type(e).__module__.startswith(("pyvo", "astroquery", "urllib3")):
        title, detail = f"{service} returned an unexpected answer" + (f" (error {code})" if code else ""), f"{type(e).__name__}: {str(e)[:140]}"
    else:
        up = False
        title, detail, retry = "Something went wrong while processing the images", f"{type(e).__name__}: {str(e)[:160]}", False
    return dict(title=title, detail=detail, hint=HINT if up else "Reload the page; if it keeps happening, tell the developer.",
                code=code, service=service, upstream=up, retry=retry)


def line(e, service):
    """One short line for logs / event feed."""
    i = explain(e, service)
    return i["title"] + (f" - {i['detail']}" if i["detail"] else "")
