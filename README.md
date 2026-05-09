# Serrano-Bot

Discord-Bot fuer das **Serrano Kartell** (FiveM Roleplay, Server: Azzlack City).

Was er kann:
- **Bewerbungs-System (Colloquio)** — 2-Wellen IC-Interview, Maestro fuellt Dokument aus, alles archiviert
- **Personal-Verwaltung** — Akten, Promote/Demote, Verwarnungen, Notizen, Inaktiv-Tracking, Abmeldungen
- **Auto-Logging** — alle Aktionen in einem Log-Channel

---

## TEIL 1 — Bot bei Discord erstellen

1. Geh auf https://discord.com/developers/applications
2. **New Application** → Name: `Serrano-Bot`
3. Links auf **Bot** klicken → **Reset Token** → Token KOPIEREN (nur 1× sichtbar!)
4. **Privileged Gateway Intents**: `SERVER MEMBERS INTENT` aktivieren
5. Links **OAuth2** → **URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions:
     - Manage Roles
     - Send Messages
     - Embed Links
     - Read Message History
     - View Channels
6. Generierte URL oeffnen → Bot zu deinem Server einladen
7. **WICHTIG:** Im Discord-Server die Bot-Rolle in der Hierarchie ueber alle Rang-Rollen schieben (sonst kann der Bot keine Rollen vergeben)

---

## TEIL 2 — IDs herausfinden

Aktiviere im Discord den Entwicklermodus: `Einstellungen → Erweitert → Entwicklermodus AN`

Dann auf alles was du brauchst rechtsklicken → "ID kopieren":

| Brauchst du fuer | Wo |
|---|---|
| `GUILD_ID` | Rechtsklick auf Server-Icon |
| Rollen-IDs (12 Stueck) | Server-Einstellungen → Rollen → ID kopieren |
| Channel-IDs | Rechtsklick auf Channel |

---

## TEIL 3 — Konfiguration

### 3a) `.env` erstellen

Kopier `.env.example` zu `.env` und trage ein:

```
DISCORD_TOKEN=DEIN_BOT_TOKEN_VON_OBEN
GUILD_ID=DEINE_SERVER_ID
```

### 3b) `config.py` ausfuellen

Oeffne `config.py` und ersetze alle `0` durch die echten IDs:

```python
RANGS = {
    1:  ("Candidato",   123456789012345678),  # <- Rollen-ID hier
    2:  ("Lavatore",    123456789012345678),
    ...
}

CHANNEL_VORSTELLUNGSGESPRAECH = 123456789012345678
CHANNEL_LOGS = 123456789012345678
CHANNEL_BENVENUTO = 123456789012345678
CHANNEL_SANKTIONEN = 123456789012345678
```

---

## TEIL 4 — Hosting auf Railway (kostenlos, 24/7)

1. Geh auf https://railway.app → mit GitHub einloggen
2. Lade diesen Ordner zu einem **GitHub-Repo** hoch (privat!)
   - Stell sicher dass `.env` NICHT mitgeladen wird (steht in `.gitignore`)
3. In Railway: **New Project** → **Deploy from GitHub repo** → Repo auswaehlen
4. Variables setzen (Variables-Tab):
   - `DISCORD_TOKEN` = dein Token
   - `GUILD_ID` = deine Server-ID
5. Settings → Generate Domain (nicht noetig, aber optional)
6. Bot startet automatisch. Logs siehst du im Railway-Dashboard.

**Free-Tier Limits:** 500 Stunden/Monat (~20 Tage). Fuer 24/7 musst du Hobby-Plan ($5/Monat).

### Alternative: lokal auf deinem PC testen

```
python -m venv venv
venv\Scripts\activate          (Windows)
pip install -r requirements.txt
python bot.py
```

---

## TEIL 5 — Commands im Discord nutzen

### Bewerbungs-System

| Command | Wer darf? | Was passiert? |
|---|---|---|
| `/colloquio start bewerber:@user` | Maestro+ | Modal Welle 1 oeffnet sich, Maestro tippt Antworten waehrend Befragung |
| `/colloquio welle2 bewerbung_id:42` | Maestro+ | Modal Welle 2 (Charakter-Tiefe) — 2 Teile |
| `/colloquio liste status:offen` | jeder | Uebersicht aller Bewerbungen |
| `/colloquio zeigen bewerbung_id:42` | jeder | Eine Bewerbung im Detail |

Nach Welle 2 erscheinen **[✅ Annehmen] [❌ Ablehnen] Buttons** unter dem Dokument.

### Personal-Verwaltung

| Command | Wer darf? | Was passiert? |
|---|---|---|
| `/akte user:@x` | jeder | Komplette Personal-Akte |
| `/promote user:@x grund:` | Maestro+ | Rang +1 |
| `/demote user:@x grund:` | Maestro+ | Rang -1 |
| `/warn user:@x grund:` | Capo+ | Verwarnung (Auto-Eskalation bei 2) |
| `/note user:@x text:` | Capo+ | Interne Notiz |
| `/liste rang:7` | jeder | alle Capos auflisten |
| `/inaktiv tage:7` | jeder | wer war 7+ Tage offline? |
| `/abmelden bis: grund:` | Mitglieder | Selbst-Abmeldung (Urlaub) |
| `/rauswurf user:@x grund:` | Vice Don+ | Komplett-Ausschluss |

---

## TEIL 6 — Berechtigungs-System aendern

In `config.py`:

```python
MIN_RANG_COLLOQUIO_STARTEN = 9   # Maestro
MIN_RANG_COLLOQUIO_ANNEHMEN = 9  # Maestro
MIN_RANG_PROMOTE = 9             # Maestro darf befoerdern
MIN_RANG_WARN = 7                # Capo darf verwarnen
MIN_RANG_KICK = 11               # Vice Don darf kicken
```

Aenderungen → Bot neu starten.

---

## Troubleshooting

**Bot reagiert nicht auf Slash-Commands:**
- Bot 1× komplett neu starten — beim ersten Start werden Commands gesynced (kann 1–2 Min dauern)
- Sicherstellen dass `GUILD_ID` korrekt ist

**Bot kann keine Rollen vergeben:**
- Bot-Rolle in der Hierarchie ueber alle Rang-Rollen schieben
- Berechtigung "Rollen verwalten" pruefen

**"DISCORD_TOKEN fehlt":**
- `.env` Datei pruefen, kein Leerzeichen vor/nach dem `=`
- Auf Railway: Variables-Tab pruefen

---

## Daten

Alle Daten in `data/serrano.db` (SQLite). Backup machen indem du diese Datei kopierst.

Bei Railway: Volumes einrichten damit die DB beim Re-Deploy nicht weg ist:
- Settings → Volumes → Add Volume → Mount Path: `/app/data`
