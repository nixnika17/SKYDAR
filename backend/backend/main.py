# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
import logging, os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import time
from concurrent.futures import ThreadPoolExecutor
import requests
from . import service as S, sky, catalogs, stars as STARS, events as EV, visibility as VIS, errors as ERR
from .reference import DETECTORS, TARGETS

log = logging.getLogger("skydar.api")
ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "webapp"
if not (WEB / "index.html").exists():
    raise RuntimeError(f"webapp/index.html not found in {WEB} - check the project layout")
app = FastAPI(title="SKYDAR - SPHEREx time-lapse viewer")


def _mode(demo):
    """demo=None -> server default (DEMO env); otherwise the caller's choice. Real mode needs extra packages."""
    d = S.is_demo() if demo is None else demo
    if not d:
        ok, missing = S.real_status()
        if not ok:
            raise HTTPException(503, dict(title="Real-data mode needs extra Python packages", detail="Missing: " + ", ".join(missing),
                                          hint=f"Run: pip install {' '.join(missing)} - then restart. Demo data keeps working.", upstream=False, code=None, service="SKYDAR"))
    return d


def _check(ra, dec, detector):
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        raise HTTPException(422, "RA must be in [0, 360) deg and Dec in [-90, 90] deg")
    if detector not in DETECTORS:
        raise HTTPException(422, "detector must be one of D1..D6")


def _stack(ra, dec, fov, detector, demo):
    _check(ra, dec, detector)
    d = _mode(demo)
    fov = min(max(fov, 0.01), 0.5)  # IRSA cutout service limits
    try:
        return S.get_stack(ra, dec, fov, detector, d)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        log.exception("stack failed")
        info = ERR.explain(e, "NASA/IPAC IRSA")
        raise HTTPException(503 if info["upstream"] else 500, info)


@app.get("/api/health")
def health():
    ok, missing = S.real_status()
    return dict(ok=True, demo=S.is_demo(), real_ok=ok, real_missing=missing)


@app.get("/api/config")
def config():
    return dict(bot=os.getenv("BOT_USERNAME", ""), developer=os.getenv("DEVELOPER_NAME", ""), link=os.getenv("DEVELOPER_LINK", ""))


@app.get("/api/targets")
def targets():
    return dict(targets=TARGETS, detectors=DETECTORS)


@app.get("/api/stack")
def stack(ra: float, dec: float, fov: float = 0.1, detector: str = "D4", demo: bool | None = None):
    return S.meta(_stack(ra, dec, fov, detector, demo))


@app.get("/api/view")
def view(ra: float, dec: float, fov: float = 0.1, detector: str = "D4", wave: float | None = None, coadd: bool = False, demo: bool | None = None):
    st = _stack(ra, dec, fov, detector, demo)
    try:
        return S.view_json(S.build_view(st, wave, coadd))
    except LookupError as e:
        raise HTTPException(404, str(e))


@app.get("/api/blink.gif")
def blink(ra: float, dec: float, fov: float = 0.1, detector: str = "D4", wave: float | None = None, coadd: bool = False, demo: bool | None = None):
    st = _stack(ra, dec, fov, detector, demo)
    try:
        gif = S.blink_gif(S.build_view(st, wave, coadd))
    except LookupError as e:
        raise HTTPException(404, str(e))
    return Response(gif, media_type="image/gif", headers={"Content-Disposition": 'inline; filename="skydar_blink.gif"'})


@app.get("/api/spectrum")
def spectrum(ra: float, dec: float, fov: float = 0.1, detector: str = "D4", nx: float = 0.5, ny: float = 0.5, r: float = 3.0, demo: bool | None = None):
    st = _stack(ra, dec, fov, detector, demo)
    return S.spectrum(st, min(max(nx, 0), 1), min(max(ny, 0), 1), min(max(r, 1), 8))


@app.get("/api/catalog")
def catalog(ra: float, dec: float, fov: float = 0.1, name: str = "gaia", demo: bool | None = None):
    _check(ra, dec, "D4")
    d = _mode(demo)
    try:
        return catalogs.fetch(name, ra, dec, min(max(fov, 0.01), 0.5), d)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        log.warning("catalogue %s failed: %s", name, e)
        raise HTTPException(503, ERR.explain(e, "ESA Gaia archive" if name == "gaia" else "NASA/IPAC IRSA (AllWISE)"))


@app.get("/api/status")
def status():
    """Live health of the outside services we depend on (VOSI 'availability' endpoints), so the UI can say who is down."""
    checks = [("NASA/IPAC IRSA", "https://irsa.ipac.caltech.edu/TAP/availability"), ("ESA Gaia", "https://gea.esac.esa.int/tap-server/tap/availability")]

    def ping(c):
        name, url = c
        t = time.time()
        try:
            r = requests.get(url, timeout=6)
            ok = r.status_code < 400
            return dict(name=name, ok=ok, code=r.status_code, ms=int((time.time() - t) * 1000), note="" if ok else f"error {r.status_code}")
        except Exception as e:
            return dict(name=name, ok=False, code=None, ms=None, note=ERR.explain(e, name)["title"].replace(name + " ", ""))
    with ThreadPoolExecutor(len(checks)) as ex:
        return dict(services=list(ex.map(ping, checks)))


@app.get("/api/events")
def events(demo: bool | None = None, refresh: bool = False):
    """Plain-language sky events. Scanning runs in the background; poll until scanning is false."""
    return EV.get_events(_mode(demo), force=refresh)


@app.get("/api/visibility")
def visibility(ra: float, dec: float, lat: float, lon: float):
    _check(ra, dec, "D4")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, "lat/lon out of range")
    return VIS.tonight(ra, dec, lat, lon)


@app.get("/api/stars")
def stars_catalog():
    """Naked-eye stars [[ra, dec, mag], ...] for the sky map (downloaded once, then cached in data/)."""
    try:
        return STARS.get_catalog()
    except Exception as e:
        raise HTTPException(503, str(e))


@app.get("/api/sky.jpg")
def sky_image(ra: float, dec: float, fov: float = 0.25, survey: str = "dss", detector: str = "D4", demo: bool | None = None):
    _check(ra, dec, detector)
    fov = min(max(fov, 0.02), 5.0)
    data, src = sky.fetch(ra, dec, fov, survey)
    if data is None:  # CDS unreachable -> fall back to our own SPHEREx co-add so the picture is never empty
        try:
            data = S.coadd_jpeg(_stack(ra, dec, min(fov, 0.5), detector, demo))
        except HTTPException:
            raise HTTPException(502, f"Sky survey unreachable ({src}) and no SPHEREx data for fallback")
        src = f"SPHEREx co-add (fallback; survey server unreachable: {src})"
    return Response(data, media_type="image/jpeg", headers={"X-Sky-Source": src.encode("ascii", "replace").decode(),
                                                            "Cache-Control": "max-age=600"})


@app.get("/api/refresh")
def refresh():
    """Drop in-memory caches so the next request re-queries IRSA (picks up newly released frames)."""
    S.clear_cache()
    return dict(ok=True)


@app.get("/")
def root():
    return RedirectResponse("/app/")


app.mount("/app", StaticFiles(directory=WEB, html=True), name="app")
