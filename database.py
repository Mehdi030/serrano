"""
SQLite-Datenbank für Serrano-Bot
Speichert: Bewerbungen, Mitglieder, Verwarnungen, Notizen, Rang-Historie
"""
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "serrano.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                user_id        TEXT PRIMARY KEY,
                charakter_name TEXT,
                rang           INTEGER DEFAULT 1,
                eintritt       TEXT,
                recruiter_id   TEXT,
                last_active    TEXT,
                status         TEXT DEFAULT 'aktiv'
            );

            CREATE TABLE IF NOT EXISTS bewerbungen (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         TEXT NOT NULL,
                maestro_id      TEXT NOT NULL,
                welle1_data     TEXT,
                welle2_data     TEXT,
                status          TEXT DEFAULT 'welle1_offen',
                message_id      TEXT,
                channel_id      TEXT,
                erstellt        TEXT,
                aktualisiert    TEXT
            );

            CREATE TABLE IF NOT EXISTS warnings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT NOT NULL,
                grund        TEXT,
                moderator_id TEXT,
                timestamp    TEXT
            );

            CREATE TABLE IF NOT EXISTS notes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT NOT NULL,
                text      TEXT,
                author_id TEXT,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS rang_historie (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT NOT NULL,
                alter_rang   INTEGER,
                neuer_rang   INTEGER,
                grund        TEXT,
                moderator_id TEXT,
                timestamp    TEXT
            );

            CREATE TABLE IF NOT EXISTS abmeldungen (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT NOT NULL,
                bis       TEXT,
                grund     TEXT,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS routen (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                start_ort    TEXT,
                ziel         TEXT,
                ware         TEXT,
                status       TEXT DEFAULT 'aktiv',
                erstellt_von TEXT,
                erstellt     TEXT,
                aktualisiert TEXT,
                notizen      TEXT
            );
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def now() -> str:
    return datetime.utcnow().isoformat()


# ---------- Members ----------
def member_exists(user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM members WHERE user_id = ?", (str(user_id),)).fetchone()
        return row is not None


def member_create(user_id: int, charakter_name: str, rang: int, recruiter_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO members (user_id, charakter_name, rang, eintritt, recruiter_id, last_active, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'aktiv')",
            (str(user_id), charakter_name, rang, now(), str(recruiter_id), now()),
        )
        conn.commit()


def member_get(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM members WHERE user_id = ?", (str(user_id),)).fetchone()


def member_update_rang(user_id: int, neuer_rang: int):
    with get_conn() as conn:
        conn.execute("UPDATE members SET rang = ? WHERE user_id = ?", (neuer_rang, str(user_id)))
        conn.commit()


def member_update_active(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE members SET last_active = ? WHERE user_id = ?", (now(), str(user_id)))
        conn.commit()


def member_set_status(user_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE members SET status = ? WHERE user_id = ?", (status, str(user_id)))
        conn.commit()


def member_list_by_rang(rang: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM members WHERE rang = ? AND status = 'aktiv' ORDER BY eintritt", (rang,)
        ).fetchall()


def member_list_inactive(tage: int):
    cutoff = (datetime.utcnow().timestamp() - tage * 86400)
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM members WHERE status = 'aktiv'").fetchall()
        result = []
        for r in rows:
            if not r["last_active"]:
                continue
            try:
                ts = datetime.fromisoformat(r["last_active"]).timestamp()
                if ts < cutoff:
                    result.append(r)
            except Exception:
                pass
        return result


# ---------- Bewerbungen ----------
def bewerbung_create(user_id: int, maestro_id: int, welle1_json: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO bewerbungen (user_id, maestro_id, welle1_data, status, erstellt, aktualisiert) "
            "VALUES (?, ?, ?, 'welle1_offen', ?, ?)",
            (str(user_id), str(maestro_id), welle1_json, now(), now()),
        )
        conn.commit()
        return cur.lastrowid


def bewerbung_set_welle2(bewerbung_id: int, welle2_json: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bewerbungen SET welle2_data = ?, status = 'welle2_offen', aktualisiert = ? WHERE id = ?",
            (welle2_json, now(), bewerbung_id),
        )
        conn.commit()


def bewerbung_set_status(bewerbung_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bewerbungen SET status = ?, aktualisiert = ? WHERE id = ?",
            (status, now(), bewerbung_id),
        )
        conn.commit()


def bewerbung_set_message(bewerbung_id: int, message_id: int, channel_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bewerbungen SET message_id = ?, channel_id = ? WHERE id = ?",
            (str(message_id), str(channel_id), bewerbung_id),
        )
        conn.commit()


def bewerbung_get(bewerbung_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM bewerbungen WHERE id = ?", (bewerbung_id,)).fetchone()


def bewerbung_get_active_by_user(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM bewerbungen WHERE user_id = ? AND status NOT IN ('angenommen','abgelehnt') "
            "ORDER BY id DESC LIMIT 1",
            (str(user_id),),
        ).fetchone()


def bewerbung_list(status_filter: str = None):
    with get_conn() as conn:
        if status_filter:
            return conn.execute(
                "SELECT * FROM bewerbungen WHERE status = ? ORDER BY erstellt DESC", (status_filter,)
            ).fetchall()
        return conn.execute("SELECT * FROM bewerbungen ORDER BY erstellt DESC LIMIT 50").fetchall()


# ---------- Warnings ----------
def warn_add(user_id: int, grund: str, moderator_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO warnings (user_id, grund, moderator_id, timestamp) VALUES (?, ?, ?, ?)",
            (str(user_id), grund, str(moderator_id), now()),
        )
        conn.commit()


def warn_count(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM warnings WHERE user_id = ?", (str(user_id),)
        ).fetchone()
        return row["n"] if row else 0


def warn_list(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM warnings WHERE user_id = ? ORDER BY timestamp DESC", (str(user_id),)
        ).fetchall()


# ---------- Notes ----------
def note_add(user_id: int, text: str, author_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notes (user_id, text, author_id, timestamp) VALUES (?, ?, ?, ?)",
            (str(user_id), text, str(author_id), now()),
        )
        conn.commit()


def note_list(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY timestamp DESC", (str(user_id),)
        ).fetchall()


# ---------- Rang-Historie ----------
def rang_log(user_id: int, alter_rang: int, neuer_rang: int, grund: str, moderator_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rang_historie (user_id, alter_rang, neuer_rang, grund, moderator_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(user_id), alter_rang, neuer_rang, grund, str(moderator_id), now()),
        )
        conn.commit()


def rang_history(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM rang_historie WHERE user_id = ? ORDER BY timestamp DESC", (str(user_id),)
        ).fetchall()


# ---------- Abmeldungen ----------
def abmeldung_add(user_id: int, bis: str, grund: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO abmeldungen (user_id, bis, grund, timestamp) VALUES (?, ?, ?, ?)",
            (str(user_id), bis, grund, now()),
        )
        conn.commit()


def abmeldung_active(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM abmeldungen WHERE user_id = ? ORDER BY id DESC LIMIT 1", (str(user_id),)
        ).fetchone()


# ---------- Routen ----------
def route_create(name: str, start_ort: str, ziel: str, ware: str, erstellt_von: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO routen (name, start_ort, ziel, ware, status, erstellt_von, erstellt, aktualisiert) "
            "VALUES (?, ?, ?, ?, 'aktiv', ?, ?, ?)",
            (name, start_ort, ziel, ware, str(erstellt_von), now(), now()),
        )
        conn.commit()
        return cur.lastrowid


def route_get(route_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM routen WHERE id = ?", (route_id,)).fetchone()


def route_list(status_filter: str = None):
    with get_conn() as conn:
        if status_filter:
            return conn.execute(
                "SELECT * FROM routen WHERE status = ? ORDER BY erstellt DESC", (status_filter,)
            ).fetchall()
        return conn.execute("SELECT * FROM routen ORDER BY erstellt DESC").fetchall()


def route_set_status(route_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE routen SET status = ?, aktualisiert = ? WHERE id = ?",
            (status, now(), route_id),
        )
        conn.commit()


def route_delete(route_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM routen WHERE id = ?", (route_id,))
        conn.commit()


def route_add_notiz(route_id: int, notiz: str):
    with get_conn() as conn:
        existing = conn.execute("SELECT notizen FROM routen WHERE id = ?", (route_id,)).fetchone()
        if not existing:
            return
        new_notes = (existing["notizen"] or "") + f"\n[{now()[:16]}] {notiz}"
        conn.execute(
            "UPDATE routen SET notizen = ?, aktualisiert = ? WHERE id = ?",
            (new_notes, now(), route_id),
        )
        conn.commit()
