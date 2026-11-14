# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""When and where to look: altitude/azimuth of a sky position for an observer over the next 24 h (Sun-aware)."""
import datetime as dt, math

R = math.pi / 180
DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _jd(t):
    return t.timestamp() / 86400 + 2440587.5


def _lst(jd, lon):
    return (280.46061837 + 360.98564736629 * (jd - 2451545.0) + lon) % 360


def sun_radec(jd):
    """Low-precision solar position (about 0.01 deg) - plenty for 'is it dark yet?'."""
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    return (math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360,
            math.degrees(math.asin(math.sin(eps) * math.sin(lam))))


def altaz(ra, dec, jd, lat, lon):
    H, d, p = (_lst(jd, lon) - ra) * R, dec * R, lat * R
    x = math.sin(d) * math.cos(p) - math.cos(d) * math.cos(H) * math.sin(p)
    y = -math.cos(d) * math.sin(H)
    z = math.sin(d) * math.sin(p) + math.cos(d) * math.cos(H) * math.cos(p)
    return math.degrees(math.asin(max(-1, min(1, z)))), math.degrees(math.atan2(y, x)) % 360


def tonight(ra, dec, lat, lon, now=None, min_alt=10, dark=-12):
    """status: visible (dark sky, above min_alt) | daylight (up only in twilight/day) | never (below horizon for 24 h)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    pts = []
    for i in range(24 * 6 + 1):
        t = now + dt.timedelta(minutes=10 * i)
        jd = _jd(t)
        alt, az = altaz(ra, dec, jd, lat, lon)
        sra, sdec = sun_radec(jd)
        pts.append((t, alt, az, altaz(sra, sdec, jd, lat, lon)[0]))
    up = [p for p in pts if p[1] >= min_alt]
    good = [p for p in up if p[3] <= dark]
    iso = lambda t: t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    top = max(pts, key=lambda p: p[1])
    if good:
        b, status = max(good, key=lambda p: p[1]), "visible"
    elif up:
        b, status = max(up, key=lambda p: p[1]), "daylight"
    else:
        b, status = top, "never"
    out = dict(status=status, best=iso(b[0]), alt=round(b[1]), az=round(b[2]), dir=DIRS[round(b[2] / 45) % 8], max_alt=round(top[1]))
    if good:
        out.update({"from": iso(good[0][0]), "to": iso(good[-1][0])})
    return out
