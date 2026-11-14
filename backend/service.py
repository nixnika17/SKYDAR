"""Core: frame stack -> epochs -> same-wavelength matching (or co-add) -> difference -> candidates -> JPEG/GIF/spectrum."""
import io, os, time, base64, threading, datetime as dt
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, maximum_filter
from . import demo
from .grid import pix_to_radec, SCALE

EPOCH_GAP_DAYS = 45   # gap between frames > N days => new epoch (a new pass of the all-sky survey)
WAVE_TOL = 0.05       # frames are compared only if |dlambda|/lambda <= 5%
OUT_PX = 480
_cache, _lock = {}, threading.Lock()


def is_demo():
    return os.getenv("DEMO", "1") == "1"


def mjd_date(m):
    return (dt.date(1858, 11, 17) + dt.timedelta(days=float(m))).isoformat()


def real_status():
    """Real-data mode needs astropy + pyvo + reproject. Returns (ok, missing_packages)."""
    import importlib.util as iu
    missing = [m for m in ("astropy", "pyvo", "reproject") if iu.find_spec(m) is None]
    return (not missing, missing)


def clear_cache():
    with _lock:
        _cache.clear()


# ---------- stack and epochs ----------
def get_stack(ra, dec, fov, det="D4", demo_mode=None):
    demo_mode = is_demo() if demo_mode is None else demo_mode
    key = (round(ra, 5), round(dec, 5), round(fov, 4), det, demo_mode)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < 1800:
            return hit[1]
    if demo_mode:
        frames, n = demo.stack(ra, dec, fov, det)
    else:
        from . import irsa
        frames, n = irsa.stack(ra, dec, fov, det)
    if not frames:
        raise LookupError("No SPHEREx frames for this position / detector")
    frames.sort(key=lambda f: f["mjd"])
    ep, last = -1, None
    for f in frames:
        if last is None or f["mjd"] - last > EPOCH_GAP_DAYS:
            ep += 1
        f["epoch"], last = ep, f["mjd"]
    epochs = []
    for e in range(ep + 1):
        ms = [f["mjd"] for f in frames if f["epoch"] == e]
        epochs.append(dict(i=e, mjd=float(np.mean(ms)), date=mjd_date(np.mean(ms)), n=len(ms)))
    st = dict(frames=frames, n=n, epochs=epochs, ra=ra, dec=dec, fov=fov, det=det, demo=demo_mode, coadds={})
    with _lock:
        _cache[key] = (time.time(), st)
    return st


def _coadd(st, e):
    """Average of ALL frames of one epoch (background-subtracted): the 'add everything the detector saw' mode."""
    if e not in st["coadds"]:
        fs = [f for f in st["frames"] if f["epoch"] == e]
        st["coadds"][e] = dict(
            mjd=float(np.mean([f["mjd"] for f in fs])), wave=float(np.mean([f["wave"] for f in fs])),
            img=np.mean([f["img"] - np.median(f["img"]) for f in fs], axis=0),
            flag_pct=round(float(np.mean([f.get("flag_pct", 0) for f in fs])), 1), n=len(fs), uri=None)
    return st["coadds"][e]


def match(st, wave, coadd=False):
    """For every epoch: the frame with the closest wavelength (None if outside tolerance), or the epoch co-add."""
    out = []
    for e in st["epochs"]:
        fs = [f for f in st["frames"] if f["epoch"] == e["i"]]
        if not fs:
            out.append(None)
        elif coadd:
            out.append(_coadd(st, e["i"]))
        else:
            f = min(fs, key=lambda f: abs(f["wave"] - wave))
            out.append(f if abs(f["wave"] - wave) / wave <= WAVE_TOL else None)
    return out


def wave_options(st):
    """Wavelengths covered by at least two epochs (otherwise there is nothing to compare)."""
    waves = sorted({round(f["wave"], 3) for f in st["frames"]})
    scored = [(w, sum(m is not None for m in match(st, w))) for w in waves]
    good = [(w, c) for w, c in scored if c >= 2] or scored
    kept = []
    for w, c in good:
        if not kept or w / kept[-1]["w"] > 1.01:
            kept.append(dict(w=w, n_epochs=c))
    return kept


def best_wave(st):
    opts = wave_options(st)
    return max(opts, key=lambda o: (o["n_epochs"], -abs(o["w"] - 2.5)))["w"]


def meta(st):
    return dict(n=st["n"], demo=st["demo"], det=st["det"], fov=st["fov"], scale=SCALE, n_frames=len(st["frames"]),
                epochs=st["epochs"], waves=wave_options(st), best_wave=best_wave(st))


# ---------- detection ----------
def detect(d, nsigma=5.0, fwhm=4.0):
    n = d.shape[0]
    sm = gaussian_filter(d, fwhm / 2.355)
    sd = 1.4826 * np.median(np.abs(sm - np.median(sm))) + 1e-9
    out = []
    for sign in (1, -1):
        s = sign * sm
        peaks = (s == maximum_filter(s, size=int(fwhm * 1.5) | 1)) & (s > nsigma * sd)
        for y, x in zip(*np.nonzero(peaks)):
            if min(x, y, n - 1 - x, n - 1 - y) >= 3:
                out.append(dict(x=int(x), y=int(y), snr=float(s[y, x] / sd), sign=sign))
    return out


def classify(per_epoch, st):
    """Group detections by position. variable = changes at one place; mover = vanishes here / appears elsewhere."""
    groups = []
    for e, dets in per_epoch.items():
        for d in dets:
            g = next((g for g in groups if np.hypot(g["x"] - d["x"], g["y"] - d["y"]) < 3.5), None)
            if g is None:
                g = dict(x=d["x"], y=d["y"], pat={}, snr=0.0)
                groups.append(g)
            g["pat"][e] = d["sign"]; g["snr"] = max(g["snr"], d["snr"])
    for g in groups:
        g["kind"] = "variable" if len(g["pat"]) >= 2 else "transient"
    # movers: mirrored groups (+/- at different places) or single "+" in different epochs with similar brightness
    for a in groups:
        for b in groups:
            if a is not b and len(a["pat"]) >= 2 and a["pat"] == {e: -s for e, s in b["pat"].items()} \
                    and 0.5 < a["snr"] / b["snr"] < 2:
                a["kind"] = b["kind"] = "mover"
    singles = [g for g in groups if g["kind"] == "transient" and list(g["pat"].values())[0] == 1]
    if len({list(g["pat"])[0] for g in singles}) >= 2:
        for g in singles:
            g["kind"] = "mover"
    n = st["n"]
    cands = []
    for g in sorted(groups, key=lambda g: -g["snr"])[:12]:
        ra, dec = pix_to_radec(g["x"], g["y"], st["ra"], st["dec"], n)
        cands.append(dict(kind=g["kind"], nx=(g["x"] + .5) / n, ny=1 - (g["y"] + .5) / n, ra=round(ra, 5),
                          dec=round(dec, 5), snr=round(g["snr"], 1), epochs=sorted(g["pat"]),
                          x=int(g["x"]), y=int(g["y"]), plus=sorted(e for e, s in g["pat"].items() if s == 1)))
    return cands


# ---------- rendering ----------
def _jpeg(arr_u8):
    im = Image.fromarray(np.flipud(arr_u8))  # y grows north -> flip for the screen (north up)
    im = im.resize((OUT_PX, OUT_PX), Image.BICUBIC)
    buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=88)
    return buf.getvalue()


def build_view(st, wave=None, coadd=False):
    wave = best_wave(st) if wave is None else wave
    sel = match(st, wave, coadd)
    avail = [i for i, f in enumerate(sel) if f]
    if not avail:
        raise LookupError("No frames at this wavelength")
    imgs = {i: sel[i]["img"] - np.median(sel[i]["img"]) for i in avail}  # remove background
    allv = np.concatenate([imgs[i].ravel() for i in avail])
    lo, hi = np.percentile(allv, [5, 99.7])  # SAME stretch for all epochs - honest brightness comparison
    raw, diffs = {}, {}
    for i in avail:
        raw[i] = _jpeg((np.clip((imgs[i] - lo) / max(hi - lo, 1e-9), 0, 1) ** 0.5 * 255).astype("uint8"))
        others = [imgs[j] for j in avail if j != i]
        if others:
            diffs[i] = imgs[i] - np.median(others, axis=0)
    diff_jpg = {}
    if diffs:
        scale = 6 * 1.4826 * np.median(np.abs(np.concatenate([d.ravel() for d in diffs.values()]))) + 1e-9
        for i, d in diffs.items():
            v = np.clip(d / scale, -1, 1); p, m = np.clip(v, 0, 1), np.clip(-v, 0, 1)
            rgb = np.stack([p * 255 + m * 80, p * 170 + m * 200, p * 60 + m * 255], -1).astype("uint8")
            diff_jpg[i] = _jpeg(rgb)
    cands = classify({i: detect(d) for i, d in diffs.items()}, st) if diffs else []
    eps = []
    for i, e in enumerate(st["epochs"]):
        f = sel[i]
        eps.append(dict(i=i, date=e["date"], mjd=e["mjd"], wave=round(f["wave"], 3) if f else None,
                        n_frames=f.get("n", 1) if f else 0, flag_pct=f.get("flag_pct") if f else None,
                        raw=raw.get(i), diff=diff_jpg.get(i)))
    shown = wave if not coadd else float(np.mean([f["wave"] for f in sel if f]))
    return dict(wave=round(shown, 3), coadd=coadd, epochs=eps, candidates=cands, n=st["n"], demo=st["demo"])


def view_json(v):
    b64 = lambda b: ("data:image/jpeg;base64," + base64.b64encode(b).decode()) if b else None
    return dict(wave=v["wave"], coadd=v["coadd"], n=v["n"], demo=v["demo"], candidates=v["candidates"],
                epochs=[dict(e, raw=b64(e["raw"]), diff=b64(e["diff"])) for e in v["epochs"]])


def blink_gif(v, size=360, ms=800):
    frames = []
    for e in v["epochs"]:
        if not e["raw"]:
            continue
        im = Image.open(io.BytesIO(e["raw"])).convert("RGB").resize((size, size))
        d = ImageDraw.Draw(im)
        for c in v["candidates"]:
            x, y = c["nx"] * size, c["ny"] * size
            col = {"mover": (255, 90, 90), "variable": (255, 179, 71)}.get(c["kind"], (120, 220, 255))
            d.ellipse([x - 14, y - 14, x + 14, y + 14], outline=col, width=2)
        d.rectangle([0, size - 22, size, size], fill=(0, 0, 0))
        d.text((6, size - 17), f"{e['date']}   {e['wave']} um" + ("   [DEMO]" if v["demo"] else ""), fill=(255, 255, 255))
        frames.append(im)
    if not frames:
        raise LookupError("Nothing to animate")
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=ms, loop=0)
    return buf.getvalue()


def coadd_jpeg(st):
    """Offline fallback for the sky tab: mean of every frame in the stack."""
    img = np.mean([f["img"] - np.median(f["img"]) for f in st["frames"]], axis=0)
    lo, hi = np.percentile(img, [5, 99.7])
    return _jpeg((np.clip((img - lo) / max(hi - lo, 1e-9), 0, 1) ** 0.5 * 255).astype("uint8"))


# ---------- spectrum on the fly ----------
def spectrum(st, nx, ny, r=3.0):
    """Aperture photometry at (nx, ny) in every frame -> flux vs wavelength (relative units: MJy/sr x pixels)."""
    n = st["n"]
    x, y = nx * n - .5, (1 - ny) * n - .5
    yy, xx = np.ogrid[:n, :n]
    d = np.hypot(xx - x, yy - y)
    ap, bg = d <= r, (d > r + 3) & (d <= r + 8)
    pts = []
    for f in st["frames"]:
        b = np.median(f["img"][bg]) if bg.any() else np.median(f["img"])
        pts.append(dict(wave=round(f["wave"], 3), flux=round(float((f["img"][ap] - b).sum()), 2),
                        epoch=f["epoch"], date=mjd_date(f["mjd"])))
    pts.sort(key=lambda p: p["wave"])
    ra, dec = pix_to_radec(x, y, st["ra"], st["dec"], n)
    return dict(ra=round(ra, 5), dec=round(dec, 5), r_arcsec=round(r * SCALE, 1), points=pts, demo=st["demo"])


def analyze(ra, dec, fov=0.1, det="D4", demo_mode=None, coadd=False):
    st = get_stack(ra, dec, fov, det, demo_mode)
    v = build_view(st, coadd=coadd)
    return dict(n_frames=len(st["frames"]), n_epochs=len(st["epochs"]), wave=v["wave"],
                candidates=v["candidates"], view=v, demo=st["demo"])
