---
title: SKYDAR
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


## When outside servers fail (they do, especially during hackathons)
SKYDAR never hides a failure. Every upstream problem is explained in a banner: **what** failed (NASA/IPAC IRSA, ESA Gaia, our own server), **which error** (e.g. 503 overloaded, 429 too many requests, timeout, no connection) and **what to do**.
What the app does about it automatically:
* Transient errors (429, 500, 502, 503, 504) are retried 3 times with a growing pause (`backend/errors.py`).
* The last good frame list from IRSA is saved in `data/cache/`, downloaded cutouts are kept there too, and a stale in-memory copy is served if a refresh fails - the UI then shows a yellow
  "Showing saved or partial data" banner with the reason. If only some frames fail, the rest are shown and the number of skipped frames is stated.
* If nothing is saved, the banner offers **Try again** and **Use demo data**. The Events tab shows a live "Archives now" status line (`/api/status`).
* Our own server down / a sleeping free host is reported as such ("The SKYDAR server is not responding ... wait about a minute").
**Before presenting**: open every target once in Real mode so the cache is warm; keep Demo mode as the safe fallback.

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


## Phone / sensors
🧭 **Gyroscope** (Sky tab, off by default): hold the phone up like a window and move it around. Uses the browser motion sensors (needs https, i.e. the tunnel/hosted URL;
iOS asks for permission) or Telegram's own sensor API. If no data arrives within a few seconds it switches itself off and suggests "Open in browser".
The menu is collapsed behind ☰ on narrow screens. 🌐 in the header (inside Telegram) and a "🌐 Open in browser" button in bot messages open the normal browser.

## Use of Super Intelligence (SI) - disclosure
This project was developed with **Claude (Anthropic)**, an SI chatbot/LLM. It helped write the code (backend, web app, Telegram bot), the user interface texts, the documentation and the submission text.
The developer set the goals, ran and tested the app, and chose what to keep. Every source file carries a header comment stating this.
Data note: `webapp/stars.js` (115 stars, constellation figures, fun facts) was generated by the assistant from general knowledge - approximate and not verified against a catalogue;
the full star catalogue comes from d3-celestial. Other SI use: the Telegram bot avatar image and a 10-second part of the demo video were generated with SI tools, and the bot's command descriptions were drafted with one.
Both the image and the video part carry a visible "SI-generated" watermark, and the image file's metadata says so (see `watermark_si.py`).
Tools: image = Gemini , video = Gemini.
The web app itself contains no SI-generated pictures (text, CSS and system emoji only), audio.
SKYDAR is an independent project for the NASA Space Apps Challenge, not affiliated with or endorsed by NASA, and it uses no NASA logos or branding.


## Credits
NASA/IPAC Infrared Science Archive (IRSA) — SPHEREx Spectral Images (TAP + Cutout service), AllWISE; ESA Gaia DR3; CDS (Aladin Lite, hips2fits, DSS2, 2MASS).
