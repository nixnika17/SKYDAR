# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""Quick check of the real data channels (run BEFORE the hackathon):  python check_irsa.py
It prints every step as it happens and never waits silently for more than about 2 minutes."""
import socket, time
socket.setdefaulttimeout(60)


def say(*a):
    print(*a, flush=True)


say("SKYDAR data check - each step prints as it runs.\n")
say("Step 0/4: loading the program ...")
from backend import irsa, catalogs, errors  # noqa: E402

RA, DEC = 133.7951, -7.2452  # WISE 0855
SVC = "NASA/IPAC IRSA"
res = {}


def fail(step, e, svc):
    i = errors.explain(e, svc)
    say(f"   [FAIL] {i['title']}" + (f" - {i['detail']}" if i["detail"] else ""))
    say(f"   technical: {type(e).__name__}: {str(e)[:220]}")
    res[step] = False


say("\nStep 1/4: which SPHEREx tables does the IRSA archive offer? (this shows whether data release 1 changed the table names)")
try:
    t = time.time()
    tab = irsa._tap().search("SELECT table_name FROM TAP_SCHEMA.tables WHERE table_name LIKE 'spherex%'").to_table()
    names = sorted(str(r["table_name"]) for r in tab)
    say(f"   [OK] {len(names)} tables in {time.time() - t:.1f}s: {', '.join(names)}")
    res["tables"] = True
except Exception as e:
    fail("tables", e, SVC)

say("\nStep 2/4: searching SPHEREx frames at the position of WISE 0855 (can take up to a minute) ...")
rows = []
try:
    t = time.time()
    rows, stale = irsa.find_frames_ex(RA, DEC, "D4")
    if stale:
        say(f"   [WARN] the archive failed ({errors.explain(stale['error'], SVC)['title']}); using the frame list saved earlier: {len(rows)} frames")
    else:
        say(f"   [OK] {len(rows)} frames found in {time.time() - t:.1f}s")
    res["search"] = bool(rows)
    if not rows:
        say("   [FAIL] the search worked but returned no frames (table names or the position may differ after the new data release)")
except Exception as e:
    fail("search", e, SVC)

say("\nStep 3/4: downloading a few image cutouts ...")
if rows:
    try:
        t = time.time()
        frames, n, notes = irsa.stack(RA, DEC, 0.05, "D4", limit=6)
        say(f"   [OK] {len(frames)} cutouts in {time.time() - t:.1f}s | wavelengths (um): {[round(f['wave'], 3) for f in frames]}")
        say(f"        MJD: {[round(f['mjd'], 1) for f in frames]} | flagged pixels %: {[f['flag_pct'] for f in frames]}")
        for note in notes:
            say("   NOTE:", note)
        res["cutouts"] = bool(frames)
    except Exception as e:
        fail("cutouts", e, SVC)
else:
    say("   skipped (no frame list)")

say("\nStep 4/4: overlay catalogues (Gaia and AllWISE) ...")
for name, svc in (("gaia", "ESA Gaia archive"), ("wise", "NASA/IPAC IRSA (AllWISE)")):
    try:
        t = time.time()
        r = catalogs.fetch(name, RA, DEC, 0.1, False)
        say(f"   [OK] {name}: {len(r['sources'])} sources in {time.time() - t:.1f}s")
        res[name] = True
    except Exception as e:
        say(f"   {name}:")
        fail(name, e, svc)

say("\n=== SUMMARY ===")
for k in ("tables", "search", "cutouts", "gaia", "wise"):
    say(f"  {k:8} {'OK' if res.get(k) else 'FAILED / skipped'}")
say("Send this whole output to the developer assistant if anything FAILED.")
