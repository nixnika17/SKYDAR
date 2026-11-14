# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Known asteroids / comets predicted inside a field (IMCCE SkyBoT cone search). EXPERIMENTAL, best effort:
if the service is unreachable or answers in an unexpected format we simply return nothing."""
import logging
import requests

log = logging.getLogger("skydar.skybot")
URL = "https://ssp.imcce.fr/webservices/skybot/api/conesearch.php"


def solar_system(ra, dec, fov, mjd, limit=3):
    r = requests.get(URL, params={"-ep": mjd + 2400000.5, "-ra": ra, "-dec": dec, "-rs": min(fov * 3600 * 0.75, 1800),
                                  "-mime": "json", "-output": "basic", "-loc": "500"}, timeout=20)
    r.raise_for_status()
    j = r.json()
    rows = j.get("data", []) if isinstance(j, dict) else j
    cols = j.get("columns") if isinstance(j, dict) else None
    out = []
    for row in rows or []:
        d = row if isinstance(row, dict) else dict(zip(cols or [], row))
        low = {str(k).lower(): v for k, v in d.items()}
        name = low.get("name") or low.get("number")
        if not name:
            continue
        cls = str(low.get("class") or low.get("type") or "")
        try:
            mag = float(low.get("v") or low.get("mv"))
        except (TypeError, ValueError):
            mag = None
        out.append(dict(name=str(name), comet="comet" in cls.lower(), cls=cls, mag=mag))
    out.sort(key=lambda o: (o["mag"] is None, o["mag"] or 99))
    return out[:limit]
