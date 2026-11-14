"""Synthetic SPHEREx-like frame stack (no network needed).
Shows the main SPHEREx trap: wavelength varies across a frame (linear variable filter), so only frames with the
same wavelength may be compared. The field has stars of different colour, a variable star (brightens between
epochs) and a moving object (shifts between epochs)."""
import numpy as np

from .grid import grid_size
from .reference import DETECTORS

EPOCH_MJD = [60795.0, 60975.0, 61155.0, 61300.0]  # ~every 6 months


def scene(ra, dec, fov):
    """Deterministic fake sky for a position: (n, stars[(x, y, flux, colour)], variable (x, y), mover start (x, y))."""
    n = grid_size(fov)
    rng = np.random.default_rng(int(abs(ra * 1000 + dec * 10)) % 2**31)
    stars = [(rng.uniform(6, n - 6), rng.uniform(6, n - 6), rng.uniform(60, 400), rng.uniform(-1, 1)) for _ in range(14)]
    return n, stars, (n * 0.30, n * 0.68), np.array([n * 0.22, n * 0.35])


def _blob(img, x, y, f, fwhm=4.0):
    s = fwhm / 2.355
    r = int(4 * s) + 1
    x0, x1 = max(0, int(x) - r), min(img.shape[1], int(x) + r + 1)
    y0, y1 = max(0, int(y) - r), min(img.shape[0], int(y) + r + 1)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    img[y0:y1, x0:x1] += f * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * s * s))


def stack(ra, dec, fov, detector="D4"):
    n, stars, var, mov0 = scene(ra, dec, fov)
    rng = np.random.default_rng(int(abs(ra * 1000 + dec * 10)) % 2**31 + 7)
    d = DETECTORS[detector]
    pad = 0.12 * (d["hi"] - d["lo"])
    waves = np.linspace(d["lo"] + pad, d["hi"] - pad, 5)
    frames = []
    for e, mjd in enumerate(EPOCH_MJD):
        for k, lam in enumerate(waves):
            img = rng.normal(0, 2.0, (n, n)) + 20 * (1 + 0.1 * e)  # background + noise
            for x, y, f, color in stars:  # colour: flux depends on wavelength, not on epoch
                _blob(img, x, y, f * np.exp(0.3 * color * (lam - 2.5)))
            _blob(img, *var, 120 * (1 + 0.9 * e) * (1 + 0.1 * (lam - 2.5)))
            p = mov0 + np.array([e * n * 0.12, e * n * 0.07])
            _blob(img, p[0], p[1], 170)
            frames.append(dict(mjd=mjd + 0.4 * k, wave=float(lam), img=img, epoch=e,
                               flag_pct=round(float(rng.uniform(0, 3)), 1), uri="demo"))
    return frames, n
