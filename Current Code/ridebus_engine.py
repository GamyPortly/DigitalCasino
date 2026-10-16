"""Ride the Bus - engine voor het Digital Casino.

Regels (2 spelers, beiden spelen tegelijk hun eigen 'bus'):
  Inzetten -> elke speler zet in.
  Vraag 1: Rood of zwart?                      (kaart 1)
  Vraag 2: Hoger of lager dan kaart 1?         (kaart 2)  gelijk = fout
  Vraag 3: Binnen of buiten kaart 1 en 2?      (kaart 3)  gelijk aan een rand = fout
  Vraag 4: Welk symbool?                       (kaart 4)
Na elke juiste vraag mag je uitbetalen (cash out) of doorgaan.
Een foute gok = inzet kwijt. Alle 4 goed = maximale uitbetaling.
"""
import random

SUIT_SYMBOLEN = {"s": "\u2660", "h": "\u2665", "d": "\u2666", "c": "\u2663"}
RANG_TEKST = {11: "J", 12: "Q", 13: "K", 14: "A"}

# Uitbetaling (vermenigvuldiger van de inzet) na 1, 2, 3 of 4 juiste antwoorden
MULTIPLIERS = [2, 3, 5, 10]

VRAGEN = [
    {"titel": "Rood of zwart?", "opties": ["rood", "zwart"]},
    {"titel": "Hoger of lager dan je eerste kaart?", "opties": ["hoger", "lager"]},
    {"titel": "Binnen of buiten je eerste twee kaarten?", "opties": ["binnen", "buiten"]},
    {"titel": "Welk symbool?", "opties": ["harten", "ruiten", "schoppen", "klaveren"]},
]

SYMBOOL_NAAR_KEUZE = {"h": "harten", "d": "ruiten", "s": "schoppen", "c": "klaveren"}


def kaart_tekst(kaart):
    rang, suit = kaart
    return RANG_TEKST.get(rang, str(rang)) + SUIT_SYMBOLEN[suit]


def nieuw_deck():
    deck = [(r, s) for r in range(2, 15) for s in "shdc"]
    random.shuffle(deck)
    return deck


def nieuwe_speler(naam):
    return {
        "naam": naam, "chips": 1000, "inzet": 0, "kaarten": [], "stap": 0,
        "status": "wacht",  # wacht, ingezet, spelen, verloren, uitbetaald, gewonnen
        "resultaat": "",
    }


def nieuw_spel():
    return {
        "fase": "inzetten",  # inzetten, spelen, afgelopen
        "spelers": {1: nieuwe_speler("Speler 1"), 2: nieuwe_speler("Speler 2")},
        "_deck": [],
    }


def is_rood(kaart):
    return kaart[1] in ("h", "d")


def huidige_waarde(speler):
    """Hoeveel chips je krijgt als je nu uitbetaalt (0 als je nog niets goed hebt)."""
    if speler["stap"] <= 0:
        return 0
    return speler["inzet"] * MULTIPLIERS[min(speler["stap"], len(MULTIPLIERS)) - 1]


def plaats_inzet(state, pid, bedrag):
    if state["fase"] != "inzetten":
        return False, "Er kan nu niet ingezet worden."
    speler = state["spelers"][pid]
    if speler["status"] != "wacht":
        return False, "Je hebt al ingezet."
    try:
        bedrag = int(bedrag)
    except (TypeError, ValueError):
        return False, "Ongeldig bedrag."
    if bedrag <= 0:
        return False, "Inzet moet groter dan 0 zijn."
    if bedrag > speler["chips"]:
        return False, "Je hebt niet genoeg chips."

    speler["chips"] -= bedrag
    speler["inzet"] = bedrag
    speler["status"] = "ingezet"

    if all(s["status"] == "ingezet" for s in state["spelers"].values()):
        state["_deck"] = nieuw_deck()
        state["fase"] = "spelen"
        for s in state["spelers"].values():
            s["status"] = "spelen"
            s["stap"] = 0
            s["kaarten"] = []
    return True, ""


def _controleer_einde(state):
    if all(s["status"] in ("verloren", "uitbetaald", "gewonnen") for s in state["spelers"].values()):
        state["fase"] = "afgelopen"


def _is_juist(stap, keuze, kaarten, nieuwe):
    if stap == 0:
        return (keuze == "rood") == is_rood(nieuwe)
    if stap == 1:
        eerste = kaarten[0][0]
        if nieuwe[0] == eerste:
            return False
        return (keuze == "hoger") == (nieuwe[0] > eerste)
    if stap == 2:
        laag, hoog = sorted((kaarten[0][0], kaarten[1][0]))
        if nieuwe[0] in (laag, hoog):
            return False
        binnen = laag < nieuwe[0] < hoog
        return (keuze == "binnen") == binnen
    if stap == 3:
        return SYMBOOL_NAAR_KEUZE[nieuwe[1]] == keuze
    return False


def gok(state, pid, keuze):
    if state["fase"] != "spelen":
        return False, "Er is geen ronde bezig."
    speler = state["spelers"][pid]
    if speler["status"] != "spelen":
        return False, "Jouw ronde is al afgelopen."
    stap = speler["stap"]
    if keuze not in VRAGEN[stap]["opties"]:
        return False, "Ongeldige keuze."

    nieuwe = state["_deck"].pop()
    juist = _is_juist(stap, keuze, speler["kaarten"], nieuwe)
    speler["kaarten"].append(nieuwe)

    if not juist:
        speler["status"] = "verloren"
        speler["resultaat"] = f"Fout! Je verliest je inzet van {speler['inzet']} chips."
    else:
        speler["stap"] += 1
        if speler["stap"] >= len(VRAGEN):
            winst = huidige_waarde(speler)
            speler["chips"] += winst
            speler["status"] = "gewonnen"
            speler["resultaat"] = f"Je hebt de bus gereden! Je wint {winst} chips ({MULTIPLIERS[-1]}x)."
    _controleer_einde(state)
    return True, ""


def uitbetalen(state, pid):
    if state["fase"] != "spelen":
        return False, "Er is geen ronde bezig."
    speler = state["spelers"][pid]
    if speler["status"] != "spelen":
        return False, "Jouw ronde is al afgelopen."
    if speler["stap"] < 1:
        return False, "Je moet eerst minstens 1 vraag goed hebben."
    winst = huidige_waarde(speler)
    speler["chips"] += winst
    speler["status"] = "uitbetaald"
    speler["resultaat"] = f"Uitbetaald: {winst} chips ({MULTIPLIERS[speler['stap'] - 1]}x)."
    _controleer_einde(state)
    return True, ""


def klaar_voor_nieuwe_ronde(state):
    for s in state["spelers"].values():
        s["inzet"] = 0
        s["kaarten"] = []
        s["stap"] = 0
        s["status"] = "wacht"
        s["resultaat"] = ""
    state["_deck"] = []
    state["fase"] = "inzetten"
