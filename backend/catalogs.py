# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Overlay catalogues: Gaia DR3 (ESA TAP) and AllWISE (IRSA TAP), returned as normalised image positions.
Gaia positions (epoch 2016.0) are propagated to EPOCH_NOW with proper motions - essential for Barnard's Star etc."""
import logging, math, threading, time
import numpy as np
from .grid import grid_size, radec_to_pix
from .reference import EPOCH_NOW

log = logging.getLogger("skydar.catalogs")
GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap"
IRSA_TAP = "https://irsa.ipac.caltech.edu/TAP"
_cache, _lock = {}, threading.Lock()


def _f(v):
    return float("nan") if np.ma.is_masked(v) else float(v)


_SESS = None


def _tap(url, q):
    global _SESS
    import pyvo
    from . import errors
    _SESS = _SESS or errors.session()  # retries 429/5xx with a pause
    try:
        svc = pyvo.dal.TAPService(url, session=_SESS)
    except TypeError:  # older pyvo without the session argument
        svc = pyvo.dal.TAPService(url)
    return svc.search(q, maxrec=1500).to_table()


def _gaia(ra, dec, r):
    q = (f"SELECT TOP 800 ra, dec, phot_g_mean_mag AS mag, pmra, pmdec FROM gaiadr3.gaia_source "
         f"WHERE 1=CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},{r})) AND phot_g_mean_mag < 19.5 "
         f"ORDER BY phot_g_mean_mag")
    out, dt = [], EPOCH_NOW - 2016.0
    for row in _tap(GAIA_TAP, q):
        a, d, m, pa, pd = (_f(row[k]) for k in ("ra", "dec", "mag", "pmra", "pmdec"))
        pa, pd = (0.0 if math.isnan(pa) else pa), (0.0 if math.isnan(pd) else pd)
        out.append((a + pa * dt / 3.6e6 / max(math.cos(math.radians(d)), 1e-3), d + pd * dt / 3.6e6, m))
    return out


def _wise(ra, dec, r):
    q = (f"SELECT TOP 800 ra, dec, w1mpro AS mag FROM allwise_p3as_psd "
         f"WHERE CONTAINS(POINT('ICRS',ra,dec),CIRCLE('ICRS',{ra},{dec},{r}))=1 ORDER BY w1mpro")
    return [(_f(row["ra"]), _f(row["dec"]), _f(row["mag"])) for row in _tap(IRSA_TAP, q)]


def _demo(ra, dec, fov):
    from . import demo
    n, stars, var, _ = demo.scene(ra, dec, fov)
    from .grid import pix_to_radec
    srcs = [(x, y, 16 - 2.5 * math.log10(f / 100)) for x, y, f, _c in stars] + [(var[0], var[1], 14.8)]
    return [(*pix_to_radec(x, y, ra, dec, n), m) for x, y, m in srcs]


def fetch(name, ra, dec, fov, demo_mode):
    if name not in ("gaia", "wise"):
        raise ValueError("catalogue must be 'gaia' or 'wise'")
    key = (name, round(ra, 5), round(dec, 5), round(fov, 4), demo_mode)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < 3600:
            return hit[1]
    r = fov * 0.75  # covers the corners of the square field
    raw = _demo(ra, dec, fov) if demo_mode else (_gaia(ra, dec, r) if name == "gaia" else _wise(ra, dec, r))
    n = grid_size(fov)
    srcs = []
    for a, d, m in raw:
        x, y = radec_to_pix(a, d, ra, dec, n)
        if 0 <= x < n and 0 <= y < n:
            srcs.append(dict(ra=round(a, 5), dec=round(d, 5), mag=None if math.isnan(m) else round(m, 2),
                             nx=(x + .5) / n, ny=1 - (y + .5) / n))
    res = dict(name=name, demo=demo_mode, sources=srcs,
               note="Gaia DR3, propagated to 2026.0 with proper motions" if name == "gaia" else "AllWISE W1 (epoch ~2010)")
    with _lock:
        _cache[key] = (time.time(), res)
    return res
