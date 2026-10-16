import sqlite3
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_BESTAND = "pokertafel.db"

# De volgorde van handtypes, van zwakst naar sterkst.
# Dit gebruiken we om te bepalen of een nieuwe hand "beter" is dan de vorige beste hand.
HANDTYPE_VOLGORDE = [
    "Hoge kaart", "Paar", "Twee paar", "Drilling", "Straat",
    "Flush", "Full house", "Vierling", "Straight flush",
]


def verbind():
    conn = sqlite3.connect(DATABASE_BESTAND)
    conn.row_factory = sqlite3.Row
    return conn


def maak_tabellen():
    conn = verbind()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spelers (
            gebruikersnaam TEXT PRIMARY KEY,
            wachtwoord_hash TEXT NOT NULL,
            chips INTEGER NOT NULL DEFAULT 1000,
            hoogste_chips INTEGER NOT NULL DEFAULT 1000,
            beste_hand TEXT NOT NULL DEFAULT '',
            grootste_pot_winst INTEGER NOT NULL DEFAULT 0,
            aangemaakt_op TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def account_bestaat(gebruikersnaam):
    conn = verbind()
    rij = conn.execute(
        "SELECT 1 FROM spelers WHERE gebruikersnaam = ?", (gebruikersnaam,)
    ).fetchone()
    conn.close()
    return rij is not None


def account_aanmaken(gebruikersnaam, code):
    if account_bestaat(gebruikersnaam):
        return False, "Deze gebruikersnaam bestaat al."
    if not gebruikersnaam or len(gebruikersnaam.strip()) == 0:
        return False, "Vul een gebruikersnaam in."
    if not (code.isdigit() and len(code) == 4):
        return False, "De code moet uit precies 4 cijfers bestaan."

    hash_van_code = generate_password_hash(code)
    conn = verbind()
    conn.execute(
        "INSERT INTO spelers (gebruikersnaam, wachtwoord_hash, chips, hoogste_chips, aangemaakt_op) "
        "VALUES (?, ?, 1000, 1000, ?)",
        (gebruikersnaam, hash_van_code, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return True, ""


def inloggen(gebruikersnaam, code):
    conn = verbind()
    rij = conn.execute(
        "SELECT wachtwoord_hash FROM spelers WHERE gebruikersnaam = ?", (gebruikersnaam,)
    ).fetchone()
    conn.close()

    if rij is None:
        return False, "Deze gebruikersnaam bestaat niet."
    if not check_password_hash(rij["wachtwoord_hash"], code):
        return False, "Foute code."
    return True, ""


def chips_ophalen(gebruikersnaam):
    conn = verbind()
    rij = conn.execute(
        "SELECT chips FROM spelers WHERE gebruikersnaam = ?", (gebruikersnaam,)
    ).fetchone()
    conn.close()
    return rij["chips"] if rij else None


def chips_opslaan(gebruikersnaam, nieuwe_chips):
    conn = verbind()
    conn.execute(
        "UPDATE spelers SET chips = ?, "
        "hoogste_chips = MAX(hoogste_chips, ?) "
        "WHERE gebruikersnaam = ?",
        (nieuwe_chips, nieuwe_chips, gebruikersnaam),
    )
    conn.commit()
    conn.close()


def update_beste_hand(gebruikersnaam, nieuw_handtype):
    if nieuw_handtype not in HANDTYPE_VOLGORDE:
        return
    conn = verbind()
    rij = conn.execute(
        "SELECT beste_hand FROM spelers WHERE gebruikersnaam = ?", (gebruikersnaam,)
    ).fetchone()

    huidige_beste = rij["beste_hand"] if rij else ""
    is_beter = (
        huidige_beste == ""
        or HANDTYPE_VOLGORDE.index(nieuw_handtype) > HANDTYPE_VOLGORDE.index(huidige_beste)
    )
    if is_beter:
        conn.execute(
            "UPDATE spelers SET beste_hand = ? WHERE gebruikersnaam = ?",
            (nieuw_handtype, gebruikersnaam),
        )
        conn.commit()
    conn.close()


def update_grootste_pot(gebruikersnaam, potgrootte):
    conn = verbind()
    conn.execute(
        "UPDATE spelers SET grootste_pot_winst = MAX(grootste_pot_winst, ?) "
        "WHERE gebruikersnaam = ?",
        (potgrootte, gebruikersnaam),
    )
    conn.commit()
    conn.close()


def leaderboard_ophalen(limiet=10):
    conn = verbind()
    rijen = conn.execute(
        "SELECT gebruikersnaam, chips, hoogste_chips, beste_hand, grootste_pot_winst "
        "FROM spelers ORDER BY hoogste_chips DESC LIMIT ?",
        (limiet,),
    ).fetchall()
    conn.close()
    return [dict(rij) for rij in rijen]