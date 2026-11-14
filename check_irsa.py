# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Quick check of the real IRSA channel (run BEFORE the hackathon): python check_irsa.py"""
import time
from backend import irsa, catalogs
ra, dec = 133.7951, -7.2452
t = time.time(); rows = irsa.find_frames(ra, dec, "D4")
print(f"TAP: {len(rows)} D4 frames in {time.time()-t:.1f}s")
if rows:
    st, n, notes = irsa.stack(ra, dec, 0.05, "D4", limit=6)
    for note in notes:
        print("NOTE:", note)
    print(f"cutouts: {len(st)} ok, lambda =", [round(f['wave'], 3) for f in st], "MJD =", [round(f['mjd'], 1) for f in st],
          "flag% =", [f['flag_pct'] for f in st])
for name in ("gaia", "wise"):
    try:
        r = catalogs.fetch(name, ra, dec, 0.1, False)
        print(f"{name}: {len(r['sources'])} sources")
    except Exception as e:
        print(f"{name}: FAILED ({type(e).__name__}: {e})")
