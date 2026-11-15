# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Naked-eye star catalogue (~5000 stars to magnitude 6) for the sky map.
Downloaded once by the SERVER (so the browser never needs the CDN) from the open d3-celestial data set and cached in data/.
You can also place the file yourself as data/stars.6.json. The format is verified against Sirius before it is trusted."""
import json, logging, math
from pathlib import Path
import requests

log = logging.getLogger("skydar.stars")
DATA = Path(__file__).resolve().parent.parent / "data"
RAW, CACHE = DATA / "stars.6.json", DATA / "stars_compact.json"
URLS = ["https://cdn.jsdelivr.net/gh/ofrohn/d3-celestial@master/data/stars.6.json",
        "https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/stars.6.json"]
SIRIUS = (101.287, -16.716)


def _parse(obj):
    out = []
    if isinstance(obj, dict) and "features" in obj:        # GeoJSON: coordinates = [RA deg, Dec deg], properties.mag
        for f in obj["features"]:
            try:
                lon, lat = f["geometry"]["coordinates"][:2]
                out.append([float(lon) % 360, float(lat), float(f["properties"]["mag"])])
            except Exception:
                continue
    elif isinstance(obj, list):                              # plain [[ra, dec, mag], ...]
        for r in obj:
            try:
                out.append([float(r[0]) % 360, float(r[1]), float(r[2])])
            except Exception:
                continue
    return out


def _verified(stars):
    """Sirius (mag -1.46) must sit at its known place; tries a 180-degree RA shift some data sets use."""
    for shift in (0, 180):
        ok = any(m < -1 and abs(((ra + shift) % 360) - SIRIUS[0]) < 0.6 and abs(d - SIRIUS[1]) < 0.6 for ra, d, m in stars)
        if ok:
            return [[(ra + shift) % 360, d, m] for ra, d, m in stars]
    raise ValueError("catalogue format not recognised (Sirius not found at its known position)")


def _compact(stars):
    stars = sorted(_verified(stars), key=lambda s: s[2])
    return [[round(ra, 3), round(d, 3), round(m, 2)] for ra, d, m in stars if m <= 6.5]


def get_catalog():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    DATA.mkdir(parents=True, exist_ok=True)
    raw = None
    if RAW.exists():
        raw = json.loads(RAW.read_text())
    else:
        last = None
        for u in URLS:
            try:
                r = requests.get(u, timeout=25)
                r.raise_for_status()
                raw = r.json()
                RAW.write_text(r.text)
                break
            except Exception as e:
                last = e
                log.warning("star catalogue %s: %s", u, e)
        if raw is None:
            raise RuntimeError(f"could not download the star catalogue ({type(last).__name__}). "
                               f"Download {URLS[1]} and save it as {RAW}")
    stars = _compact(_parse(raw))
    CACHE.write_text(json.dumps(stars, separators=(",", ":")))
    log.info("star catalogue ready: %d stars", len(stars))
    return stars
