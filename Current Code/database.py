import datetime
import os
import re
import sqlite3
from contextlib import closing

from werkzeug.security import check_password_hash, generate_password_hash

BASISPAD = os.path.dirname(os.path.abspath(__file__))
DATABASE_BESTAND = os.environ.get("POKER_DB") or os.path.join(BASISPAD, "pokertafel.db")
STARTCHIPS = 1000

HANDTYPE_VOLGORDE = [
    "Hoge kaart", "Paar", "Twee paar", "Drilling", "Straat",
    "Flush", "Full house", "Vierling", "Straight flush",
]

NAAM_PATROON = re.compile(r"^[A-Za-z0-9_\- ]{2,16}$")
CODE_PATROON = re.compile(r"^[0-9]{4}$")


def verbind():
    conn = sqlite3.connect(DATABASE_BESTAND, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def maak_tabellen():
    with closing(verbind()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spelers (
                gebruikersnaam TEXT PRIMARY KEY COLLATE NOCASE,
                wachtwoord_hash TEXT NOT NULL,
                chips INTEGER NOT NULL DEFAULT 1000,
                hoogste_chips INTEGER NOT NULL DEFAULT 1000,
                beste_hand TEXT NOT NULL DEFAULT '',
                grootste_pot_winst INTEGER NOT NULL DEFAULT 0,
                aangemaakt_op TEXT NOT NULL
            )
            """
        )


def schoon_naam(naam):
    return re.sub(r"\s+", " ", str(naam or "")).strip()


def account_aanmaken(naam, code):
    naam = schoon_naam(naam)
    code = str(code or "").strip()
    if not NAAM_PATROON.match(naam):
        return False, "Kies een naam van 2 tot 16 tekens (letters, cijfers, spatie, _ of -)."
    if not CODE_PATROON.match(code):
        return False, "De code moet uit precies 4 cijfers bestaan."
    try:
        with closing(verbind()) as conn, conn:
            conn.execute(
                "INSERT INTO spelers (gebruikersnaam, wachtwoord_hash, chips, hoogste_chips, aangemaakt_op) "
                "VALUES (?, ?, ?, ?, ?)",
                (naam, generate_password_hash(code), STARTCHIPS, STARTCHIPS,
                 datetime.datetime.now().isoformat()),
            )
    except sqlite3.IntegrityError:
        return False, "Deze gebruikersnaam bestaat al."
    return True, ""


def inloggen(naam, code):
    naam = schoon_naam(naam)
    with closing(verbind()) as conn:
        rij = conn.execute("SELECT * FROM spelers WHERE gebruikersnaam = ?", (naam,)).fetchone()
    if rij is None:
        return False, "Deze gebruikersnaam bestaat niet.", None
    if not check_password_hash(rij["wachtwoord_hash"], str(code or "").strip()):
        return False, "Foute code.", None
    return True, "", dict(rij)


def speler_ophalen(naam):
    with closing(verbind()) as conn:
        rij = conn.execute("SELECT * FROM spelers WHERE gebruikersnaam = ?", (naam,)).fetchone()
    return dict(rij) if rij else None


def chips_ophalen(naam):
    speler = speler_ophalen(naam)
    return speler["chips"] if speler else None


def chips_opslaan(naam, chips):
    chips = max(0, int(chips))
    with closing(verbind()) as conn, conn:
        conn.execute(
            "UPDATE spelers SET chips = ?, hoogste_chips = MAX(hoogste_chips, ?) "
            "WHERE gebruikersnaam = ?",
            (chips, chips, naam),
        )


def update_beste_hand(naam, handtype):
    if handtype not in HANDTYPE_VOLGORDE:
        return
    speler = speler_ophalen(naam)
    if speler is None:
        return
    huidige = speler["beste_hand"]
    if huidige == "" or HANDTYPE_VOLGORDE.index(handtype) > HANDTYPE_VOLGORDE.index(huidige):
        with closing(verbind()) as conn, conn:
            conn.execute("UPDATE spelers SET beste_hand = ? WHERE gebruikersnaam = ?", (handtype, naam))


def update_grootste_pot(naam, pot):
    with closing(verbind()) as conn, conn:
        conn.execute(
            "UPDATE spelers SET grootste_pot_winst = MAX(grootste_pot_winst, ?) WHERE gebruikersnaam = ?",
            (int(pot), naam),
        )


def leaderboard_ophalen(limiet=10):
    with closing(verbind()) as conn:
        rijen = conn.execute(
            "SELECT gebruikersnaam, chips, hoogste_chips, beste_hand, grootste_pot_winst "
            "FROM spelers ORDER BY hoogste_chips DESC, chips DESC, gebruikersnaam ASC LIMIT ?",
            (int(limiet),),
        ).fetchall()
    return [dict(rij) for rij in rijen]
