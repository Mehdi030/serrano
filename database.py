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

            CREATE TABLE IF NOT EXISTS inventar_items (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT UNIQUE NOT NULL,
                kategorie TEXT,
                einheit   TEXT DEFAULT 'Stück',
                bestand   INTEGER DEFAULT 0,
                erstellt  TEXT
            );

            CREATE TABLE IF NOT EXISTS inventar_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id    INTEGER,
                aktion     TEXT,
                menge      INTEGER,
                grund      TEXT,
                member_id  TEXT,
                timestamp  TEXT,
                FOREIGN KEY(item_id) REFERENCES inventar_items(id)
            );

            CREATE TABLE IF NOT EXISTS kasse (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                aktion     TEXT,
                betrag     INTEGER,
                grund      TEXT,
                member_id  TEXT,
                timestamp  TEXT
            );

            CREATE TABLE IF NOT EXISTS abgaben (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                betrag     INTEGER,
                notiz      TEXT,
                erfasst_von TEXT,
                timestamp  TEXT
            );

            CREATE TABLE IF NOT EXISTS bot_state (
                key   TEXT PRIMARY KEY,
                value TEXT
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


# ---------- Inventar ----------
def inv_item_create(name: str, kategorie: str, einheit: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO inventar_items (name, kategorie, einheit, bestand, erstellt) VALUES (?, ?, ?, 0, ?)",
            (name, kategorie, einheit, now()),
        )
        conn.commit()
        return cur.lastrowid


def inv_item_get(name: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM inventar_items WHERE name = ? COLLATE NOCASE", (name,)).fetchone()


def inv_item_get_by_id(item_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM inventar_items WHERE id = ?", (item_id,)).fetchone()


def inv_item_list():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM inventar_items ORDER BY kategorie, name").fetchall()


def inv_item_delete(item_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM inventar_log WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM inventar_items WHERE id = ?", (item_id,))
        conn.commit()


def inv_buchen(item_id: int, aktion: str, menge: int, grund: str, member_id: int):
    """aktion: 'ein' oder 'aus'. Menge immer positiv."""
    delta = menge if aktion == "ein" else -menge
    with get_conn() as conn:
        conn.execute("UPDATE inventar_items SET bestand = bestand + ? WHERE id = ?", (delta, item_id))
        conn.execute(
            "INSERT INTO inventar_log (item_id, aktion, menge, grund, member_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, aktion, menge, grund, str(member_id), now()),
        )
        conn.commit()


def inv_log(item_id: int = None, limit: int = 20):
    with get_conn() as conn:
        if item_id:
            return conn.execute(
                "SELECT l.*, i.name AS item_name FROM inventar_log l JOIN inventar_items i ON l.item_id = i.id "
                "WHERE l.item_id = ? ORDER BY l.timestamp DESC LIMIT ?",
                (item_id, limit),
            ).fetchall()
        return conn.execute(
            "SELECT l.*, i.name AS item_name FROM inventar_log l JOIN inventar_items i ON l.item_id = i.id "
            "ORDER BY l.timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()


# ---------- Kasse ----------
def kasse_buchen(aktion: str, betrag: int, grund: str, member_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO kasse (aktion, betrag, grund, member_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (aktion, betrag, grund, str(member_id), now()),
        )
        conn.commit()


def kasse_stand() -> int:
    with get_conn() as conn:
        rows = conn.execute("SELECT aktion, betrag FROM kasse").fetchall()
        return sum(r["betrag"] if r["aktion"] == "ein" else -r["betrag"] for r in rows)


def kasse_log(limit: int = 20):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM kasse ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()


# ---------- Abgaben ----------
def abgabe_add(user_id: int, betrag: int, notiz: str, erfasst_von: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO abgaben (user_id, betrag, notiz, erfasst_von, timestamp) VALUES (?, ?, ?, ?, ?)",
            (str(user_id), betrag, notiz, str(erfasst_von), now()),
        )
        conn.commit()


def abgabe_list(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM abgaben WHERE user_id = ? ORDER BY timestamp DESC", (str(user_id),)
        ).fetchall()


def abgabe_total(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(betrag), 0) AS total FROM abgaben WHERE user_id = ?", (str(user_id),)
        ).fetchone()
        return row["total"] if row else 0


def abgabe_top(limit: int = 10):
    with get_conn() as conn:
        return conn.execute(
            "SELECT user_id, SUM(betrag) AS total, COUNT(*) AS anzahl FROM abgaben "
            "GROUP BY user_id ORDER BY total DESC LIMIT ?",
            (limit,),
        ).fetchall()


# ---------- Stats fuer Dashboard ----------
def member_count_all() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM members WHERE status = 'aktiv'").fetchone()
        return row["n"] if row else 0


def member_count_per_rang() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT rang, COUNT(*) AS n FROM members WHERE status = 'aktiv' GROUP BY rang"
        ).fetchall()
        return {r["rang"]: r["n"] for r in rows}


def top_recruiter(limit: int = 5):
    with get_conn() as conn:
        return conn.execute(
            "SELECT recruiter_id, COUNT(*) AS n FROM members WHERE recruiter_id IS NOT NULL "
            "AND status = 'aktiv' GROUP BY recruiter_id ORDER BY n DESC LIMIT ?",
            (limit,),
        ).fetchall()


def total_warns() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM warnings").fetchone()
        return row["n"] if row else 0


def total_bewerbungen_open() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM bewerbungen WHERE status NOT IN ('angenommen','abgelehnt')"
        ).fetchone()
        return row["n"] if row else 0


def total_routen_aktiv() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM routen WHERE status = 'aktiv'").fetchone()
        return row["n"] if row else 0


# ---------- Generischer Key-Value-Store (Bot-State) ----------
def state_set(key: str, value):
    val = str(value) if value is not None else None
    with get_conn() as conn:
        if val is None:
            conn.execute("DELETE FROM bot_state WHERE key = ?", (key,))
        else:
            conn.execute(
                "INSERT INTO bot_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, val),
            )
        conn.commit()


def state_get(key: str, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def inv_last_log():
    """Letzter Eintrag im Inventar-Log (für Dashboard 'Letzte Bewegung')."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT l.*, i.name AS item_name, i.einheit AS einheit FROM inventar_log l "
            "JOIN inventar_items i ON l.item_id = i.id ORDER BY l.timestamp DESC LIMIT 1"
        ).fetchone()
