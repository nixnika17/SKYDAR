# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Bridge between science and people: turn raw SPHEREx detections into plain-language sky EVENTS
(something moved / got brighter / new data arrived / a known asteroid passes) that can be shown on the sky map,
in the event feed and pushed by the Telegram bot."""
import datetime as dt, json, logging, math, threading, time
from pathlib import Path
import numpy as np
from . import service as S, errors as ERR
from .grid import SCALE
from .reference import TARGETS

log = logging.getLogger("skydar.events")
STATE = Path(__file__).resolve().parent.parent / "data" / "events_state.json"
_cache, _lock = {}, threading.Lock()
RANK = {"high": 0, "medium": 1, "low": 2}
# DEMO data is synthetic and contains every kind of change in every field; keep the demo story believable
DEMO_KINDS = {"barnard": {"moving"}, "wise0855": {"moving", "asteroid"}, "epsindib": {"moving"}, "rdra": {"variable"}, "rwaur": {"variable"}}


def conf(snr):
    return "high" if snr > 20 else "medium" if snr > 8 else "low"


def _state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _flux_by_epoch(st, c):
    """Median aperture flux of the source in each epoch (relative units)."""
    sp = S.spectrum(st, c["nx"], c["ny"])
    by = {}
    for p in sp["points"]:
        by.setdefault(p["epoch"], []).append(p["flux"])
    return {e: float(np.median(v)) for e, v in by.items()}


def scan_point(tg, demo_mode, det="D4"):
    """Events for one patch of sky. tg: dict(id, name, ra, dec, fov, [emoji, pm, vis])."""
    st = S.get_stack(tg["ra"], tg["dec"], tg["fov"], det, demo_mode)
    E = st["epochs"]
    if len(E) < 2:
        return []
    C = S.build_view(st)["candidates"]
    n, ctr = st["n"], (st["n"] - 1) / 2
    base = dict(target=tg["id"], target_name=tg["name"], emoji=tg.get("emoji", "🔭"), fov=tg["fov"], demo=bool(st["demo"]),
                vis=tg.get("vis", ""), field=[tg["ra"], tg["dec"], tg["fov"]])
    mk = lambda kind, key, title, text, c, **kw: dict(base, id=f"{tg['id']}:{kind}:{key}", kind=kind, title=title, text=text,
                                                     ra=c["ra"], dec=c["dec"], snr=c["snr"], conf=conf(c["snr"]), **kw)
    ev, last = [], len(E) - 1
    # 1) something moved: the brightest "+" spot of every epoch, first vs last
    plus = {}
    for c in C:
        if c["kind"] == "mover":
            for e in c["plus"]:
                if e not in plus or c["snr"] > plus[e]["snr"]:
                    plus[e] = c
    if len(plus) >= 2:
        es = sorted(plus)
        a, b = plus[es[0]], plus[es[-1]]
        arc = math.hypot(a["x"] - b["x"], a["y"] - b["y"]) * SCALE
        yrs = (E[es[-1]]["mjd"] - E[es[0]]["mjd"]) / 365.25
        if arc >= 1.5 * SCALE:
            d1, d2 = E[es[0]]["date"], E[es[-1]]["date"]
            txt = f"A bright spot shifted by about {arc:.0f}″ between {d1} and {d2}" + (f" (≈{arc / yrs:.1f}″ per year)" if yrs > .2 else "") + ". Stars stay put - something here is moving."
            if tg.get("pm"):
                txt += f" For reference, {tg['name']} is known to move ≈{tg['pm']}″ per year."
            ev.append(mk("moving", E[es[-1]]["date"], f"{tg['name']}: something is moving", txt, b, dates=[d1, d2]))
    # 2) brightness change
    vs = sorted((c for c in C if c["kind"] == "variable"), key=lambda c: -c["snr"])
    if vs:
        c = vs[0]
        fl = _flux_by_epoch(st, c)
        d1, d2 = E[0]["date"], E[last]["date"]
        f1, f2 = fl.get(0), fl.get(last)
        near = math.hypot(c["x"] - ctr, c["y"] - ctr) < 12 or (demo_mode and tg["id"] in ("rdra", "rwaur"))  # synthetic variable is not at the centre
        title = f"{tg['name']}: brightness changed" if near else f"A source near {tg['name']} changed brightness"
        if f1 and f2 and abs(f1) > 1e-6:
            pct = (f2 - f1) / abs(f1) * 100
            txt = f"It looks about {abs(pct):.0f}% {'brighter' if pct > 0 else 'fainter'} on {d2} than on {d1}."
        else:
            txt = f"It got brighter or fainter between {d1} and {d2}."
        ev.append(mk("variable", E[last]["date"], title, txt, c, dates=[d1, d2]))
    # 3) one-epoch spot (could be an artefact)
    tr = sorted((c for c in C if c["kind"] == "transient" and c["snr"] > 8), key=lambda c: -c["snr"])
    if tr:
        c = tr[0]
        ev.append(mk("transient", f"{E[last]['date']}:{c['x']}:{c['y']}", "A spot appeared or vanished",
                     "Seen in only one observation, so it could also be an instrument artefact.", c))
    # 4) known asteroids / comets
    try:
        if demo_mode and tg["id"] == "wise0855":
            c = dict(ra=tg["ra"] + 0.03, dec=tg["dec"] + 0.02, snr=0.0)
            ev.append(mk("asteroid", "demo", "☄️ A known asteroid crosses this field",
                         "(Sample event) A catalogued asteroid is predicted to cross this field around now.", c))
        elif not demo_mode:
            from . import skybot
            for o in skybot.solar_system(tg["ra"], tg["dec"], tg["fov"], E[last]["mjd"]):
                c = dict(ra=tg["ra"], dec=tg["dec"], snr=0.0)
                what = "comet" if o["comet"] else "asteroid"
                ev.append(mk("asteroid", o["name"].replace(" ", "_"), f"A known {what} crosses this field",
                             f"{o['name']}{f' (magnitude {o['mag']:.1f})' if o['mag'] else ''} is predicted to pass through this patch of sky around {E[last]['date']}. Source: IMCCE SkyBoT.", c))
    except Exception as e:
        log.warning("skybot: %s", e)
    if demo_mode and tg["id"] in DEMO_KINDS:
        ev = [e for e in ev if e["kind"] in DEMO_KINDS[tg["id"]]]
    return ev


def release_event(demo_mode):
    """'New SPHEREx data' notice. Real mode asks the archive for the latest exposure; demo shows a sample."""
    if demo_mode:
        from . import demo
        mjd, new = demo.EPOCH_MJD[-1], False
    else:
        from . import irsa
        mjd = irsa.latest_obs()
        stt = _state()
        new = int(mjd) > int(stt.get("last_mjd", 0))
        if new:
            stt["last_mjd"] = mjd
            try:
                STATE.write_text(json.dumps(stt))
            except Exception:
                pass
    date = S.mjd_date(mjd)
    return dict(id=f"release:{int(mjd)}", kind="release", title="New SPHEREx data" if new else "SPHEREx data status",
                text=f"The archive has SPHEREx observations up to {date}. Open a target to see whether anything changed in it.",
                target=None, target_name="SPHEREx", emoji="📡", ra=None, dec=None, snr=0.0, conf="high", demo=bool(demo_mode), new=new, vis="", field=None)


def scan_all(demo_mode, progress=None):
    events, errors = [], []
    try:
        events.append(release_event(demo_mode))
    except Exception as e:
        errors.append("data status: " + ERR.line(e, "NASA/IPAC IRSA"))
    for i, tg in enumerate(TARGETS):
        try:
            events += scan_point(tg, demo_mode)
        except Exception as e:
            log.warning("scan %s: %s", tg["id"], e)
            errors.append(f"{tg['name']}: {ERR.line(e, 'NASA/IPAC IRSA')}"[:200])
        if progress:
            progress(i + 1)
    events.sort(key=lambda e: (e["kind"] != "release", RANK.get(e["conf"], 3), -e["snr"]))
    return events, errors


def _summary(c, demo_mode):
    return dict(events=c["events"], scanning=c["scanning"], progress=c["progress"], total=len(TARGETS), errors=c["errors"],
                updated=c["t"] or None, demo=bool(demo_mode))


def get_events(demo_mode, force=False, ttl=1800):
    """Non-blocking: returns what is cached and (re)scans in a background thread when stale."""
    key = bool(demo_mode)
    with _lock:
        c = _cache.setdefault(key, dict(t=0, events=[], scanning=False, progress=0, errors=[]))
        stale = time.time() - c["t"] > ttl
        if (stale or force) and not c["scanning"]:
            c["scanning"], c["progress"] = True, 0
            threading.Thread(target=_run, args=(key,), daemon=True).start()
        return _summary(c, key)


def _run(key):
    c = _cache[key]
    try:
        def prog(i):
            c["progress"] = i
        ev, err = scan_all(key, prog)
        with _lock:
            c.update(events=ev, errors=err, t=time.time())
    except Exception as e:
        log.exception("scan failed")
        with _lock:
            c.update(errors=[f"{type(e).__name__}: {e}"], t=time.time())
    finally:
        with _lock:
            c["scanning"] = False
