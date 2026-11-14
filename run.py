# SI-assisted: written with Claude (Anthropic's AI assistant); reviewed, tested and directed by the project developer.
"""One command: python run.py  -> API + web app + bot (+ https tunnel if cloudflared is installed)."""
import asyncio, atexit, os, re, shutil, socket, subprocess, threading, time, logging, webbrowser
from dotenv import load_dotenv
load_dotenv()
import uvicorn

logging.basicConfig(level=logging.INFO)


def free_port(start):
    """First free TCP port >= start (fixes 'WinError 10048: address already in use')."""
    for p in range(start, start + 30):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


def start_tunnel(port):
    exe = shutil.which("cloudflared")
    if not exe:
        print("! cloudflared not found: Telegram Mini Apps need https. Install cloudflared or set PUBLIC_URL in .env "
              "(the browser version works without it).")
        return f"http://localhost:{port}"
    p = subprocess.Popen([exe, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    atexit.register(p.terminate)
    end, url = time.time() + 40, None
    for line in p.stderr:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m:
            url = m.group(0); break
        if time.time() > end:
            break
    threading.Thread(target=lambda: [None for _ in p.stderr], daemon=True).start()  # keep the pipe drained
    return url or f"http://localhost:{port}"


async def main():
    want = int(os.getenv("PORT", "8000"))
    port = free_port(want)
    if port != want:
        print(f"! Port {want} is busy (an old run.py still open?) - using {port} instead")
    public = os.getenv("PUBLIC_URL", "").rstrip("/") or start_tunnel(port)
    local = f"http://localhost:{port}/app/"
    print(f"\n=== Web app: {local}   mode: {'DEMO (synthetic data)' if os.getenv('DEMO','1')=='1' else 'REAL SPHEREx DATA'} ===\n")
    tasks = [asyncio.create_task(uvicorn.Server(uvicorn.Config("backend.main:app", host="0.0.0.0", port=port)).serve())]
    token = os.getenv("BOT_TOKEN")
    if token:
        from bot.bot import run_bot
        tasks.append(asyncio.create_task(run_bot(token, public, int(os.getenv("CHECK_EVERY_MIN", "360")))))
    else:
        print("! BOT_TOKEN is empty - running the web app only")
    threading.Timer(2.0, lambda: webbrowser.open(local)).start()
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in done:
        if t.exception():
            print("! A component stopped:", repr(t.exception()))
    for t in pending:
        t.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
