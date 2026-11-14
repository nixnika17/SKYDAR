"""Server-side sky background (CDS hips2fits). Fetched by the backend so the browser never has to reach CDS directly
(blocked CDN / ad-blocker / ISP issues were the reason the Sky tab stayed black). Several mirrors are tried."""
import logging, threading, time
import requests

log = logging.getLogger("skydar.sky")
HIPS = {"dss": "CDS/P/DSS2/color", "2mass": "CDS/P/2MASS/color", "wise": "CDS/P/allWISE/color"}  # whitelist
HOSTS = ["https://alasky.cds.unistra.fr", "https://alaskybis.cds.unistra.fr", "https://alasky.u-strasbg.fr"]
_cache, _lock = {}, threading.Lock()


def fetch(ra, dec, fov, survey="dss", size=700):
    """Returns (jpeg_bytes, source_label) or (None, reason)."""
    if survey not in HIPS:
        survey = "dss"
    key = (round(ra, 4), round(dec, 4), round(fov, 3), survey)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < 3600:
            return hit[1], hit[2]
    params = dict(hips=HIPS[survey], width=size, height=size, fov=fov, projection="TAN", coordsys="icrs",
                  ra=ra, dec=dec, format="jpg")
    last = "no host reachable"
    for h in HOSTS:
        try:
            r = requests.get(f"{h}/hips-image-services/hips2fits", params=params, timeout=7)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                label = f"{HIPS[survey]} via {h.split('//')[1]}"
                with _lock:
                    _cache[key] = (time.time(), r.content, label)
                return r.content, label
            last = f"{h}: HTTP {r.status_code}"
        except Exception as e:
            last = f"{h}: {type(e).__name__}"
            log.warning("hips2fits %s failed: %s", h, e)
    return None, last
