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

## Run (5 steps)
1. Python 3.10+: `pip install -r requirements.txt`
   (real-data mode needs `astropy`, `pyvo`, `reproject`; if they fail to install on Python 3.14 use a 3.12/3.13 virtualenv)
2. *(optional, Telegram)* @BotFather → `/newbot` → copy the token.
3. `copy .env.example .env` (Windows) / `cp .env.example .env`, set `BOT_TOKEN=` if you want the bot; keep `DEMO=1` for the first run.
4. *(optional)* install **cloudflared** for https (Telegram Mini App requires it): `winget install Cloudflare.cloudflared`.
5. `python run.py` — the browser opens automatically. If port 8000 is busy, the next free port is used.

Folder layout must be: `run.py`, `backend/`, `bot/`, `webapp/index.html`, `data/`.

## Real data
1. `python check_irsa.py` — checks IRSA TAP, cutouts, Gaia and AllWISE.
2. In `.env` set `DEMO=0`, restart. The first request for a new position takes tens of seconds (TAP ≈ 15 s + cutouts); then it is cached in `data/cache/`.

## Troubleshooting
* **Sky map** no longer needs CDS/Aladin at all (the old black-sky problem was CDS being unreachable from some networks).
* **"Failed to fetch"** in the Time-lapse tab = the Python server is not running; start `python run.py` and keep that terminal open.
* The browser asks for your location to set the sky correctly; if you refuse, tap 📍 to type latitude/longitude.
* **`WinError 10048` (port in use)** — an old `run.py` is still running; handled automatically now, or `netstat -ano | findstr :8000` + `taskkill /PID <pid> /F`.
* Check `http://localhost:8000/api/health` → `{"ok":true,"demo":true}`.

## How it works
1. IRSA TAP (`spherex.artifact` ⨝ `spherex.plane`, `CONTAINS(POINT, poly)`, `energy_bandpassname='SPHEREx-Dn'`) → frame list with MJD.
2. Cutout per frame: `URL?center=RA,DECd&size=fov`; wavelength from the spectral WCS (WAVE) at the target pixel; `FLAGS` extension → flagged-pixel share.
3. All frames are reprojected onto one north-up grid (3.075″/px) and background-subtracted.
4. Frames are grouped into epochs (gap > 45 days = new survey pass).
5. **Key SPHEREx trap:** wavelength depends on position on the detector (linear variable filter), so for a chosen λ each epoch contributes the frame with the closest λ (±5 %). Or co-add all frames of an epoch.
6. Difference = epoch − median of the other epochs → smoothing → peaks > 5σ (positive and negative).
7. Classification: variable (changes in place), mover (mirrored +/− or traces at different places), transient.
8. Spectrum = aperture photometry (r = 3 grid px) minus local background in every frame, plotted vs wavelength.

## Telegram bot
`/watch <preset>` or `/watch RA DEC [name]`, `/events`, `/list`, `/unwatch ID`, `/location LAT LON [UTC_OFFSET]` (enables "when and where to look"), `/demo`.
Deep link `https://t.me/<bot>?start=watch_barnard` subscribes to a preset (the web app shows this as an "Alert me in Telegram" button once the bot runs).
A scheduler job (every `CHECK_EVERY_MIN`, default 6 h, APScheduler - no Celery needed) re-scans subscriptions and sends only events the chat has not received yet
(table `sent` in `data/skydar.db`). Everyone with a subscription also gets "new SPHEREx data" notices.

The button left of the message box is the **command menu** ("Menu"); the bot fills it on every start (`set_bot_commands` in `bot/bot.py`).
The sky map is opened with `/app`, the buttons under bot messages, or a pinned message. (A web-app menu button would replace the command list, so it is not used.)

## Hosting + custom domain (stable URL, 24/7)
`python run.py` on a laptop gives a *temporary* https address (cloudflared quick tunnel) that changes on every start. For a stable public site and bot:
1. Push the repo to GitHub (without `.env` and `data/`). 2. Create a Web Service on a host (Render, Railway, Fly.io, a VPS).
3. Build command `pip install -r requirements-demo.txt` (light, demo data; use `requirements.txt` + more RAM for real data), start command `python run.py`.
4. Environment variables: `BOT_TOKEN`, `PUBLIC_URL` (the host's https URL or your domain, no trailing slash), `DEMO=1`, `DEVELOPER_NAME`, `DEVELOPER_LINK`. The host sets `PORT` itself.
5. Stop `python run.py` on your own computer while the hosted bot runs - two programs cannot poll the same bot token.
6. Add your domain in the host's "Custom domains" settings and create the DNS record it shows (TLS certificate is issued automatically), then set `PUBLIC_URL` to the domain.
7. @BotFather -> /mybots -> your bot -> Bot Settings -> Configure Mini App -> enable it with the same URL (`https://your-domain/app/`) to get a permanent "Open app" button on the bot's page.
Free hosting plans may sleep when idle (the bot sleeps too) and do not keep `data/` between restarts.

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

## Limitations (be honest with the judges)
* Real-data paths (IRSA cutouts, Gaia/AllWISE overlays, SkyBoT, release detection) and the Telegram bot were written against the public service docs but could not be run in the authoring sandbox - run `python check_irsa.py` first.
* Demo events are synthetic by design (marked DEMO). In real mode an "event" is only a candidate detection plus context, not a confirmed discovery.
* Visibility ignores the Moon and weather; "needs a telescope" notes for presets are approximate magnitudes.
* Candidates, not discoveries: no SIMBAD/SkyBoT cross-match, no artefact mask (flags are shown, not applied).
* A SPHEREx pixel ≈ 6″: slow motions (a few ″/yr) shift ~1 px; visible mainly over a long baseline.
* At least 2 epochs at the same wavelength are needed; fresh sky regions may have only one.
* Demo mode uses synthetic data (marked DEMO in the UI). Spectrum units are relative (MJy/sr × pixels), not calibrated flux.
* Preset coordinates of fast movers are approximate positions for 2026.0 — verify with the Gaia overlay.
* No Telegram `initData` validation on the backend.

## Developer / AI credit
Set `DEVELOPER_NAME` (and optionally `DEVELOPER_LINK`) in `.env` (or in your hosting's environment variables): it appears in the app (About tab) and in the bot (`/about`).
The "Built with Claude" statement is plain text in `webapp/index.html` (search for "Built with Claude") and in `bot/bot.py` (`about_text`).

## Phone / sensors
🧭 **Gyroscope** (Sky tab, off by default): hold the phone up like a window and move it around. Uses the browser motion sensors (needs https, i.e. the tunnel/hosted URL;
iOS asks for permission) or Telegram's own sensor API. If no data arrives within a few seconds it switches itself off and suggests "Open in browser".
The menu is collapsed behind ☰ on narrow screens. 🌐 in the header (inside Telegram) and a "🌐 Open in browser" button in bot messages open the normal browser.

## Credits
NASA/IPAC Infrared Science Archive (IRSA) — SPHEREx Spectral Images (TAP + Cutout service), AllWISE; ESA Gaia DR3; CDS (Aladin Lite, hips2fits, DSS2, 2MASS).
