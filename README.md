---
title: SkyDar
emoji: 🔭
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# SKYDAR — Planet X & SPHEREx (NASA Space Apps 2026)

A public web tool that shows SPHEREx images of any patch of sky as a short time-lapse, so moving objects
(brown dwarfs, asteroids, nearby stars) and variable stars are easy to spot. Optional Telegram bot for push alerts.

## Why it is different
Most tools only show dry changes in telescope images. SKYDAR turns them into **events** people can act on:
a spot moved, a variable star changed brightness, new SPHEREx data arrived, a known asteroid crosses the field - shown as glowing dots on a first-person
sky map, in an event feed, and pushed by a Telegram bot with a time-lapse GIF and **when and where to look from your location**
(Sun-aware: it must be dark and the object above 10°; the Moon is not considered).

## Stars on the sky map
Built in: 115 brightest named stars (`webapp/stars.js`, constellation lines, facts). Full naked-eye catalogue (~5000 stars to magnitude 6): downloaded once by the
server from the open d3-celestial data set (`python get_stars.py`, or automatically on the first start) and cached in `data/`. If the download is blocked, save
`https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/stars.6.json` as `data/stars.6.json` and run `python get_stars.py` again.
The file is verified against Sirius before use. The 🌃 menu (city / suburb / countryside / very dark sky) sets the faintest star shown, so the map matches what your eyes could see.
Full screen: ⛶ button (F11 in a browser; inside Telegram it uses Telegram's fullscreen when the client supports it, otherwise "Open in browser").

## Demo / Real switch
Top-right switch in the app (or `?demo=1` / `?demo=0` in the URL). **Demo** = synthetic data (works offline, instant). **Real** = live SPHEREx cutouts from IRSA;
needs `pip install astropy pyvo reproject` (the app tells you if they are missing) and a network path to IRSA; the first load of each patch takes 30-60 s.
The `DEMO` value in `.env` is only the default. Your choice is remembered in the browser.

## What you see
* **Sky tab** - a first-person planetarium: you stand outside and look up (drag to look around, pinch/scroll to zoom, ⏱ slider to turn the sky).
  Tap any star or any empty spot -> "See what changes here" opens the SPHEREx time-lapse for that position. Five 🎯 missions (the challenge's test targets) give it a game feel (⭐ score is kept in the browser).
  Drawn locally from ~115 bright stars (`webapp/stars.js`) - **no external servers**, works even when CDS/Aladin are blocked. No planets/Moon yet; positions are approximate.
* **Time-lapse tab** - the SPHEREx viewer (coordinates, FOV, detectors, blink/swipe/subtract, overlays, spectrum under "Advanced tools").

## Challenge checklist
| Challenge item | Where |
|---|---|
| Enter RA/Dec, show images "like a little video" | Viewer tab: coordinate form (degrees or sexagesimal), ▶ time-lapse, blink, swipe |
| Test targets: WISE 0855, Barnard's Star, ε Indi B, RW Aur, R Dra | one-tap presets (`backend/reference.py`) |
| Choose the field of view | FOV selector 0.05°–0.5° (IRSA cutout limit) |
| Add / subtract images from different times | "A − B", "A + B" modes + automatic Difference layer |
| Co-add each of the six detectors | Detector selector D1–D6 + "Co-add all bands" switch |
| Spectra on the fly | click the image → spectrum of that position from every frame |
| Overlay Gaia / WISE | Overlays panel (Gaia DR3 propagated with proper motion; AllWISE) |
| Query by URL / embedding | `?ra=…&dec=…&fov=…&det=D4&coadd=1&embed=1` |
| Metadata such as contamination flags | Frame metadata table (share of flagged pixels per frame) |
| Easy to update with new data | frames are discovered live via IRSA TAP; the bot re-checks on a schedule and announces new releases (`irsa.latest_obs`); `GET /api/refresh` clears the cache |
| Events / alerts | `backend/events.py` -> `/api/events`, Events tab, sky-map beacons, Telegram bot |


## Real data
1. `python check_irsa.py` — checks IRSA TAP, cutouts, Gaia and AllWISE.
2. In `.env` set `DEMO=0`, restart. The first request for a new position takes tens of seconds (TAP ≈ 15 s + cutouts); then it is cached in `data/cache/`.

## How it works
1. IRSA TAP (`spherex.artifact` ⨝ `spherex.plane`, `CONTAINS(POINT, poly)`, `energy_bandpassname='SPHEREx-Dn'`) → frame list with MJD.
2. Cutout per frame: `URL?center=RA,DECd&size=fov`; wavelength from the spectral WCS (WAVE) at the target pixel; `FLAGS` extension → flagged-pixel share.
3. All frames are reprojected onto one north-up grid (3.075″/px) and background-subtracted.
4. Frames are grouped into epochs (gap > 45 days = new survey pass).
5. **Key SPHEREx trap:** wavelength depends on position on the detector (linear variable filter), so for a chosen λ each epoch contributes the frame with the closest λ (±5 %). Or co-add all frames of an epoch.
6. Difference = epoch − median of the other epochs → smoothing → peaks > 5σ (positive and negative).
7. Classification: variable (changes in place), mover (mirrored +/− or traces at different places), transient.
8. Spectrum = aperture photometry (r = 3 grid px) minus local background in every frame, plotted vs wavelength.


## Event types
| kind | meaning | how it is detected |
|---|---|---|
| moving | a bright spot shifts between survey passes | mirrored +/- pairs in epoch differences; displacement and speed from first vs last pass |
| variable | brightness change | same-place +/- changes; % change from aperture photometry per epoch |
| transient | a spot in one pass only | single detection > 8 sigma (may be an artefact) |
| asteroid | known asteroid/comet predicted in the field | IMCCE SkyBoT cone search (**experimental**, best effort) |
| release | new SPHEREx observations in the archive | latest exposure time from IRSA TAP vs last seen |

## API
`/api/events` · `/api/visibility` · `/api/config` · `/api/targets` · `/api/stack` · `/api/view` · `/api/spectrum` · `/api/catalog?name=gaia|wise` · `/api/blink.gif` · `/api/sky.jpg` · `/api/refresh` · `/api/health`

## Limitations 
* Real-data paths (IRSA cutouts, Gaia/AllWISE overlays, SkyBoT, release detection) and the Telegram bot were written against the public service docs but could not be run in the authoring sandbox - run `python check_irsa.py` first.
* Demo events are synthetic by design (marked DEMO). In real mode an "event" is only a candidate detection plus context, not a confirmed discovery.
* Visibility ignores the Moon and weather; "needs a telescope" notes for presets are approximate magnitudes.
* Candidates, not discoveries: no SIMBAD/SkyBoT cross-match, no artefact mask (flags are shown, not applied).
* A SPHEREx pixel ≈ 6″: slow motions (a few ″/yr) shift ~1 px; visible mainly over a long baseline.
* At least 2 epochs at the same wavelength are needed; fresh sky regions may have only one.
* Demo mode uses synthetic data (marked DEMO in the UI). Spectrum units are relative (MJy/sr × pixels), not calibrated flux.
* Preset coordinates of fast movers are approximate positions for 2026.0 — verify with the Gaia overlay.


## Credits
NASA/IPAC Infrared Science Archive (IRSA) — SPHEREx Spectral Images (TAP + Cutout service), AllWISE; ESA Gaia DR3; CDS (Aladin Lite, hips2fits, DSS2, 2MASS).
