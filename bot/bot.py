"""Telegram bot: turns SPHEREx changes into alerts ("what happened, where, and WHEN/WHERE to look") with a time-lapse GIF."""
import asyncio, datetime as dt, logging, os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend import service as S, store, events as EV, visibility as VIS
from backend.reference import TARGETS

log = logging.getLogger("skydar.bot")
PRESETS = {t["id"]: t for t in TARGETS}
COMMANDS = [
    BotCommand(command="start", description="🔭 Start SKYDAR & show info"),
    BotCommand(command="app", description="🌌 Open the sky map"),
    BotCommand(command="watch", description="Watch target: <preset> or RA DEC [name]"),
    BotCommand(command="events", description="What is happening now"),
    BotCommand(command="list", description="List watched targets"),
    BotCommand(command="unwatch", description="Stop watching target by ID"),
    BotCommand(command="location", description="Set LAT LON [UTC_OFFSET]"),
    BotCommand(command="demo", description="Show sample alert"),
    BotCommand(command="about", description="ℹ️ About the project"),
]


async def set_bot_commands(bot):
    """Fills the blue 'Menu' button next to the message box with the command list."""
    await bot.set_my_commands(COMMANDS)                                              # default scope
    await bot.set_my_commands(COMMANDS, scope=BotCommandScopeAllPrivateChats())      # wins over older lists set in BotFather


def about_text():
    name = os.getenv("DEVELOPER_NAME", "").strip() or "(set DEVELOPER_NAME in .env)"
    link = os.getenv("DEVELOPER_LINK", "").strip()
    return ("ℹ️ SKYDAR - made for the NASA Space Apps Challenge 2026 «Planet X and SPHEREx».\n"
            "It turns changes in SPHEREx telescope images into sky events and tells you when and where to look.\n\n"
            f"🧑‍💻 Developer: {name}" + (f"\n🔗 {link}" if link else "") +
            "\n🤖 Built with Claude (Anthropic AI assistant)\n📡 Data: NASA/IPAC IRSA, ESA Gaia, WISE")


ICON = {"moving": "🏃", "variable": "💥", "transient": "✨", "asteroid": "☄️", "release": "📡"}


def build(token, public_url):
    bot, dp = Bot(token), Dispatcher()

    def kb(ev=None, ra=None, dec=None, fov=0.15):
        if ev and ev.get("field"):
            ra, dec, fov = ev["field"]
        url = f"{public_url}/app/" + (f"?ra={ra}&dec={dec}&fov={fov}&demo={'1' if S.is_demo() else '0'}" if ra is not None else "")
        rows = [[InlineKeyboardButton(text="🗺 Open in the web app", web_app=WebAppInfo(url=url))]]
        if public_url.startswith("https://"):  # a plain URL button opens the default browser: full screen on a PC
            rows.append([InlineKeyboardButton(text="🌐 Open in browser", url=url)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def main_kb():
        """Always-visible button under the message box that opens the mini app (the Menu button shows commands instead)."""
        if not public_url.startswith("https://"):
            return None
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🌌 Open SKYDAR", web_app=WebAppInfo(url=f"{public_url}/app/"))]],
                                   resize_keyboard=True, is_persistent=True)

    async def say(m, text, **kw):
        kw.setdefault("reply_markup", main_kb())
        return await m.answer(text, **kw)

    def when_text(chat, ev):
        """'When and where to look' for this user, or a hint to share a location."""
        if ev.get("ra") is None:
            return ""
        u = store.get_user(chat)
        if not u:
            return "📍 Send /location LAT LON (e.g. /location 50.4 30.5) and I will tell you when and where to look."
        lat, lon, tz = u
        v = VIS.tonight(ev["ra"], ev["dec"], lat, lon)
        T = lambda s: (dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ") + dt.timedelta(hours=tz)).strftime("%H:%M")
        z = f"UTC{tz:+g}"
        if v["status"] == "visible":
            return f"👀 Look tonight: best around {T(v['best'])} ({z}), {v['alt']}° high toward {v['dir']}."
        if v["status"] == "daylight":
            return "🌤 It is above your horizon only in daylight/twilight in the next 24 h - try another night."
        return f"🌍 It stays below your horizon from your location for the next 24 h (max {v['max_alt']}°)."

    def caption(chat, ev):
        tag = "🧪 DEMO · " if ev.get("demo") else ""
        parts = [f"{tag}{ICON.get(ev['kind'], '🔭')} {ev['title']}", ev["text"], when_text(chat, ev), ev.get("vis", "")]
        return "\n\n".join(p for p in parts if p)[:1000]

    def _gif(ev):
        ra, dec, fov = ev["field"]
        return S.blink_gif(S.build_view(S.get_stack(ra, dec, fov, "D4", ev["demo"])))

    async def send_event(chat, ev):
        cap = caption(chat, ev)
        if ev.get("field"):
            try:
                gif = await asyncio.to_thread(_gif, ev)
                return await bot.send_animation(chat, BufferedInputFile(gif, "timelapse.gif"), caption=cap, reply_markup=kb(ev))
            except Exception as e:
                log.warning("gif failed: %s", e)
        await bot.send_message(chat, cap, reply_markup=kb(ev) if ev.get("field") else None)

    async def deliver(chat, evs):
        """Send every event this chat has not received yet."""
        n = 0
        for ev in evs:
            if not store.was_sent(chat, ev["id"]):
                store.mark_sent(chat, ev["id"])
                await send_event(chat, ev)
                n += 1
        return n

    async def subscribe(chat, tg):
        store.add(chat, tg["name"], tg["ra"], tg["dec"], tg["fov"])
        evs = await asyncio.to_thread(EV.scan_point, tg, S.is_demo())
        sent = await deliver(chat, evs)
        if not sent:
            await bot.send_message(chat, f"✅ Watching «{tg['name']}». Nothing has changed there yet - I'll message you when something does.",
                                   reply_markup=kb(ra=tg["ra"], dec=tg["dec"], fov=tg["fov"]))

    @dp.message(CommandStart())
    async def start(m: types.Message):
        arg = (m.text or "").split(maxsplit=1)[1] if len((m.text or "").split()) > 1 else ""
        if arg.startswith("watch_") and arg[6:] in PRESETS:
            await subscribe(m.chat.id, PRESETS[arg[6:]])
            if main_kb():
                await m.answer("👇 The “🌌 Open SKYDAR” button under the message box opens the sky map at any time.", reply_markup=main_kb())
            return
        names = ", ".join(PRESETS)
        await say(m, "🔭 SKYDAR turns telescope data into sky events: something moved, a star flared, new data arrived.\n\n"
                       f"/watch <preset> or /watch RA DEC [name] (degrees)\nPresets: {names}\n"
                       "/events - what is happening now\n/list, /unwatch ID\n"
                       "/location LAT LON [UTC_OFFSET] - so I can tell you WHEN and WHERE to look\n/app - open the sky map\n/demo - sample alert\n/about - about the project",
                       reply_markup=kb())
        if main_kb():
            await m.answer("👇 The “🌌 Open SKYDAR” button under the message box opens the sky map at any time.", reply_markup=main_kb())

    @dp.message(Command("app"))
    async def app_cmd(m: types.Message):
        await say(m, "🌌 Open the SKYDAR sky map:", reply_markup=kb())

    @dp.message(Command("about"))
    async def about(m: types.Message):
        await say(m, about_text(), disable_web_page_preview=True)

    @dp.message(Command("events"))
    async def events_cmd(m: types.Message):
        r = EV.get_events(S.is_demo())
        if r["scanning"] and not r["events"]:
            return await say(m, "Scanning the sky… try again in a minute.")
        evs = [e for e in r["events"] if e["kind"] != "release"][:5] or r["events"][:1]
        if not evs:
            return await say(m, "The sky is quiet right now.")
        for e in evs:
            await say(m, caption(m.chat.id, e), reply_markup=kb(e) if e.get("field") else None)

    @dp.message(Command("demo"))
    async def demo(m: types.Message):
        evs = await asyncio.to_thread(EV.scan_point, PRESETS["wise0855"], True)
        for e in evs[:1] or []:
            await send_event(m.chat.id, e)

    @dp.message(Command("watch"))
    async def watch(m: types.Message):
        args = (m.text or "").split()[1:]
        try:
            if args and args[0].lower() in PRESETS:
                tg = PRESETS[args[0].lower()]
            else:
                ra, dec = float(args[0]), float(args[1])
                assert 0 <= ra < 360 and -90 <= dec <= 90
                tg = dict(id=f"pt{abs(int(ra * 100))}_{abs(int(dec * 100))}", name=" ".join(args[2:]) or "My point", ra=ra, dec=dec, fov=0.15)
        except (ValueError, IndexError, AssertionError):
            return await say(m, "Usage: /watch <preset> or /watch RA DEC [name] in degrees, e.g. /watch 133.79 -7.245 WISE0855")
        await say(m, "Scanning… (real data can take 1-2 min)")
        try:
            await subscribe(m.chat.id, tg)
        except Exception as e:
            await say(m, f"Failed: {e}")

    @dp.message(Command("location"))
    async def location(m: types.Message):
        a = (m.text or "").replace(",", " ").split()[1:]
        try:
            lat, lon = float(a[0]), float(a[1])
            assert -90 <= lat <= 90 and -180 <= lon <= 180
            tz = float(a[2]) if len(a) > 2 else round(lon / 15)
        except (ValueError, IndexError, AssertionError):
            return await say(m, "Usage: /location LAT LON [UTC_OFFSET], e.g. /location 50.4 30.5 2")
        store.set_user(m.chat.id, lat, lon, tz)
        await say(m, f"📍 Saved: {lat:.2f}, {lon:.2f}, times in UTC{tz:+g}. I'll add 'when and where to look' to alerts.")

    @dp.message(Command("list"))
    async def lst(m: types.Message):
        await say(m, "\n".join(f"{i}. {n} ({r:.3f}, {d:.3f})" for i, n, r, d, f in store.mine(m.chat.id)) or "No subscriptions.")

    @dp.message(Command("unwatch"))
    async def unwatch(m: types.Message):
        try:
            store.delete(m.chat.id, int(m.text.split()[1]))
            await say(m, "Removed.")
        except (ValueError, IndexError):
            await say(m, "Usage: /unwatch ID")

    async def check_all():
        """Scheduler job: new events for every subscription + 'new SPHEREx data' for everyone who subscribed."""
        demo_mode = S.is_demo()
        rows = store.everything()
        S.clear_cache()  # force a fresh IRSA query so newly released frames are discovered
        for wid, chat, name, ra, dec, fov in rows:
            try:
                tg = next((t for t in TARGETS if abs(t["ra"] - ra) < 1e-6 and abs(t["dec"] - dec) < 1e-6), None) or dict(id=f"w{wid}", name=name, ra=ra, dec=dec, fov=fov)
                await deliver(chat, await asyncio.to_thread(EV.scan_point, tg, demo_mode))
            except Exception as e:
                log.warning("check %s: %s", name, e)
        try:
            rel = await asyncio.to_thread(EV.release_event, demo_mode)
            if rel["new"]:
                for chat in {r[1] for r in rows}:
                    await deliver(chat, [rel])
        except Exception as e:
            log.warning("release check: %s", e)

    return bot, dp, check_all


async def run_bot(token, public_url, every_min=360):
    bot, dp, check_all = build(token, public_url)
    try:
        me = await bot.get_me()
        os.environ["BOT_USERNAME"] = me.username or ""  # lets the web app show "Alert me in Telegram" buttons
    except Exception as e:
        log.warning("get_me: %s", e)
    try:
        await set_bot_commands(bot)
        n = len(await bot.get_my_commands(scope=BotCommandScopeAllPrivateChats()))
        print(f"✅ Telegram command menu set: {n} commands")
    except Exception as e:
        log.warning("set commands: %s", e)
        print("! Could not set the command menu:", e)
    try:
        # The button next to the message box shows the COMMAND LIST ("Menu"). A web-app menu button would hide it;
        # the sky map is opened with /app and the buttons under bot messages instead.
        await bot.set_chat_menu_button(menu_button=types.MenuButtonCommands())
    except Exception as e:
        log.warning("menu button: %s", e)
    sch = AsyncIOScheduler(); sch.add_job(check_all, "interval", minutes=every_min); sch.start()
    await dp.start_polling(bot, handle_signals=False)
