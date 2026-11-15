# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Real SPHEREx data from IRSA: TAP search (spherex.artifact + spherex.plane) and cutouts.
Query and cutout URL follow the official IRSA tutorial 'spherex_cutouts' (Caltech-IPAC/irsa-tutorials)."""
import hashlib, json, logging, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, requests
from .grid import grid_size, target_wcs
from . import errors as E

log = logging.getLogger("skydar.irsa")
TAP_URL = "https://irsa.ipac.caltech.edu/TAP"
BASE = "https://irsa.ipac.caltech.edu/"
CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
_SESS = E.session()  # retries 429/5xx with a pause
SERVICE = "NASA/IPAC IRSA"


def _tap():
    import pyvo
    try:
        return pyvo.dal.TAPService(TAP_URL, session=_SESS)
    except TypeError:  # older pyvo without the session argument
        return pyvo.dal.TAPService(TAP_URL)


def find_frames_ex(ra, dec, detector="D4"):
    """-> (rows, stale). stale = None for a live answer, or dict(error, when) when the archive failed and the last saved list is used."""
    q = f"""
    SELECT a.uri AS uri, p.time_bounds_lower AS t0
    FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid
    WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
      AND p.energy_bandpassname = 'SPHEREx-{detector}'
    ORDER BY p.time_bounds_lower"""
    f = CACHE / ("tap_" + hashlib.sha1(f"{ra:.4f},{dec:.4f},{detector}".encode()).hexdigest() + ".json")
    try:
        tab = _tap().search(q).to_table()
        rows = [dict(uri=str(r["uri"]), mjd=float(r["t0"])) for r in tab]
        f.write_text(json.dumps(dict(t=time.time(), rows=rows)))
        return rows, None
    except Exception as e:
        if f.exists():  # archive down: fall back to the last list we saw
            d = json.loads(f.read_text())
            log.warning("IRSA TAP failed (%s); using saved frame list", e)
            return d["rows"], dict(error=e, when=d["t"])
        raise


def find_frames(ra, dec, detector="D4"):
    """All SPHEREx spectral images covering the point. New releases are picked up automatically (queried live)."""
    return find_frames_ex(ra, dec, detector)[0]


def latest_obs():
    """MJD of the most recent SPHEREx exposure in the archive (used to announce new data)."""
    tab = _tap().search("SELECT MAX(time_bounds_upper) AS t FROM spherex.plane").to_table()
    return float(tab["t"][0])


def _download(url):
    p = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".fits")
    if not p.exists():
        r = _SESS.get(url, timeout=(10, 120))
        r.raise_for_status()
        p.write_bytes(r.content)
    return p


def _one(row, ra, dec, fov, n, tw, errs=None):
    from astropy.io import fits
    from astropy.wcs import WCS
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    from reproject import reproject_interp
    try:
        # IRSA cutout format: centre in degrees ('d' suffix), size in degrees (0.01..0.5)
        url = f"{BASE}{row['uri']}?center={ra:.6f},{dec:.6f}d&size={fov}"
        with fits.open(_download(url)) as h:
            hdu = h["IMAGE"] if "IMAGE" in h else h[1]
            w = WCS(hdu.header)
            x, y = w.world_to_pixel(SkyCoord(ra * u.deg, dec * u.deg))
            sp = WCS(hdu.header, fobj=h, key="W"); sp.sip = None
            wl, _ = sp.pixel_to_world(x, y)
            wave = float(wl.to(u.micrometer).value)
            img = reproject_interp((np.nan_to_num(hdu.data.astype(float)), w), tw, shape_out=(n, n), return_footprint=False)
            flag_pct = None  # contamination / quality metadata: fraction of pixels with any FLAGS bit set
            try:
                if "FLAGS" in h:
                    flag_pct = round(float(np.mean(np.asarray(h["FLAGS"].data) > 0) * 100), 1)
            except Exception:
                pass
        img = np.nan_to_num(img)
        if not np.any(img):
            return None
        return dict(mjd=row["mjd"], wave=wave, img=img, flag_pct=flag_pct if flag_pct is not None else 0.0, uri=row["uri"])
    except Exception as e:  # single frames may be broken / at the edge - skip them
        log.warning("frame skipped: %s", e)
        if errs is not None:
            errs.append(e)
        return None


def stack(ra, dec, fov, detector="D4", limit=80, workers=6):
    """-> (frames, n, notes). notes = honest messages about anything that was degraded (saved list, skipped frames)."""
    rows, stale = find_frames_ex(ra, dec, detector)
    notes = []
    if stale:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(stale["when"]))
        notes.append(f"{E.explain(stale['error'], SERVICE)['title']}. Using the frame list saved on {when}.")
    if len(rows) > limit:  # thin out evenly in time
        rows = [rows[i] for i in np.linspace(0, len(rows) - 1, limit).astype(int)]
    n = grid_size(fov)
    tw = target_wcs(ra, dec, n)
    errs = []
    with ThreadPoolExecutor(workers) as ex:
        out = [f for f in ex.map(lambda r: _one(r, ra, dec, fov, n, tw, errs), rows) if f]
    if not out and errs:
        raise errs[0]  # every download failed: report the real cause instead of "no frames"
    if errs:
        notes.append(f"{len(errs)} of {len(rows)} frames could not be downloaded ({E.explain(errs[0], SERVICE)['title']}); the rest are shown.")
    return out, n, notes
