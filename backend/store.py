import sqlite3, threading
from pathlib import Path

_dir = Path(__file__).resolve().parent.parent / "data"
_dir.mkdir(parents=True, exist_ok=True)  # the folder may not exist on a fresh checkout
_db = sqlite3.connect(_dir / "skydar.db", check_same_thread=False)
_lock = threading.Lock()
_db.execute("CREATE TABLE IF NOT EXISTS watch(id INTEGER PRIMARY KEY, chat INT, name TEXT, ra REAL, dec REAL, seen INT DEFAULT 0)")
try:
    _db.execute("ALTER TABLE watch ADD COLUMN fov REAL DEFAULT 0.15")
except sqlite3.OperationalError:
    pass  # column already there
_db.execute("CREATE TABLE IF NOT EXISTS users(chat INT PRIMARY KEY, lat REAL, lon REAL, tz REAL)")
_db.execute("CREATE TABLE IF NOT EXISTS sent(chat INT, key TEXT, PRIMARY KEY(chat, key))")
_db.commit()


def add(chat, name, ra, dec, fov=0.15):
    with _lock:
        c = _db.execute("INSERT INTO watch(chat,name,ra,dec,fov) VALUES(?,?,?,?,?)", (chat, name, ra, dec, fov)); _db.commit()
        return c.lastrowid


def mine(chat):
    with _lock:
        return _db.execute("SELECT id,name,ra,dec,fov FROM watch WHERE chat=?", (chat,)).fetchall()


def delete(chat, wid):
    with _lock:
        _db.execute("DELETE FROM watch WHERE chat=? AND id=?", (chat, wid)); _db.commit()


def everything():
    with _lock:
        return _db.execute("SELECT id,chat,name,ra,dec,fov FROM watch").fetchall()


def set_user(chat, lat, lon, tz):
    with _lock:
        _db.execute("INSERT OR REPLACE INTO users(chat,lat,lon,tz) VALUES(?,?,?,?)", (chat, lat, lon, tz)); _db.commit()


def get_user(chat):
    with _lock:
        return _db.execute("SELECT lat,lon,tz FROM users WHERE chat=?", (chat,)).fetchone()


def was_sent(chat, key):
    with _lock:
        return _db.execute("SELECT 1 FROM sent WHERE chat=? AND key=?", (chat, key)).fetchone() is not None


def mark_sent(chat, key):
    with _lock:
        _db.execute("INSERT OR IGNORE INTO sent(chat,key) VALUES(?,?)", (chat, key)); _db.commit()
