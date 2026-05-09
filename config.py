"""
Serrano-Bot Konfiguration
Hier alle IDs eintragen — Anleitung in der README.
"""

EMBED_COLOR = 0x8B0000  # Blutrot — kann jederzeit geändert werden

KARTELL_NAME = "Serrano Kartell"
SERVER_NAME = "Azzlack City"

# Rang-Hierarchie: Rang-Nummer -> (Anzeigename, Discord-Rollen-ID)
# Rollen-IDs musst du eintragen (siehe README "IDs herausfinden")
RANGS = {
    1:  ("Candidato",   1439018133712142352),
    2:  ("Lavatore",    1439018133712142353),
    3:  ("Fratelli",    1439018133712142354),
    4:  ("Soldato",     1439018133712142355),
    5:  ("Reclutatore", 1439018133728792726),
    6:  ("Supervisore", 1439018133728792727),
    7:  ("Capo",        1439018133728792728),
    8:  ("Contabile",   1439018133728792729),
    9:  ("Maestro",     1439018133728792730),
    10: ("Consigliere", 1439018133728792731),
    11: ("Vice Don",    1439018133728792732),
    12: ("Don",         1439018133728792733),
}

# --- Berechtigungs-Listen ---
# Genau diese Ränge dürfen den jeweiligen Bereich nutzen.
# Hierarchie-Schutz: Aktionen gegen MITGLIEDER sind nur gegen niedrigere Ränge möglich.

# Recruiting (Bewerbungen, Welle 1+2, Annehmen/Ablehnen)
RECRUITING_RANKS = [9, 11, 12]

# Personal-Aktionen mit Hierarchie-Check (befoerdern, degradieren, verwarnen, notiz)
PERSONAL_AKTION_RANKS = [5, 9, 11, 12]

# Rauswurf (immer mit Hierarchie-Check)
RAUSWURF_RANKS = [11, 12]

# Routenverwaltung
ROUTE_RANKS = [6, 7, 11, 12]

# Inventar / Kasse / Abgaben (Contabile = Buchhalter)
INVENTORY_RANKS = [8, 9, 11, 12]

# Rang der bei Annahme automatisch vergeben wird
RANG_NACH_ANNAHME = 1  # Candidato

# Channel-IDs (in der README erklärt wie man sie kopiert)
CHANNEL_VORSTELLUNGSGESPRAECH = 1439018134739750998  # Bewerbungsdokumente landen hier
CHANNEL_LOGS = 1439018134962044994                   # alle Bot-Aktionen werden hier geloggt
CHANNEL_BENVENUTO = 1439018134089633810              # Welcome-Nachricht bei Annahme
CHANNEL_SANKTIONEN = 1439018134278508686             # bei Auto-Eskalation Verwarnungen

# Optionale Auto-Post-Channels für Inventar (0 = aus). IDs aus #Bestand, #Geldverlauf etc. eintragen.
CHANNEL_BESTAND = 0          # Auto-Post bei /inventar bestand updates
CHANNEL_LAGERVERLAUF = 0     # Auto-Post bei /inventar ein/aus
CHANNEL_GELDVERLAUF = 0      # Auto-Post bei /kasse ein/aus
CHANNEL_ABGABEN = 0          # Auto-Post bei /abgabe verbuchen

# Verwarnungs-Eskalation
WARN_LIMIT_BIS_SANKTION = 2  # ab dieser Anzahl Warns -> Auto-Post in Sanktion

# Probezeit in Tagen (Candidato -> automatischer Hinweis für Promote)
PROBEZEIT_TAGE = 14

# Inaktivitäts-Warnung in Tagen
INAKTIV_WARNUNG_TAGE = 7
