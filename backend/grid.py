"""Shared north-up pixel grid onto which every frame is projected (so blinking does not jump and markers line up)."""
import math

SCALE = 3.075  # arcsec/px (SPHEREx native 6.15"/px, oversampled x2)


def grid_size(fov_deg):
    return max(48, int(round(fov_deg * 3600 / SCALE)))


def target_wcs(ra, dec, n):
    from astropy.wcs import WCS  # only needed for real data
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-SCALE / 3600, SCALE / 3600]
    return w


def pix_to_radec(x, y, ra, dec, n):
    """Pixel (0-based, y grows north) -> RA/Dec (small-field TAN approximation)."""
    c = (n - 1) / 2
    return (ra - (x - c) * SCALE / 3600 / math.cos(math.radians(dec)), dec + (y - c) * SCALE / 3600)


def radec_to_pix(r, d, ra, dec, n):
    """Inverse of pix_to_radec."""
    c = (n - 1) / 2
    dra = ((r - ra + 180) % 360) - 180
    return (c - dra * math.cos(math.radians(dec)) * 3600 / SCALE, c + (d - dec) * 3600 / SCALE)
