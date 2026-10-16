"""Crash - engine voor het Digital Casino.

Beide spelers zetten in. Daarna begint een vermenigvuldiger te stijgen vanaf 1.00x.
Je moet uitbetalen (cash out) voordat de multiplier 'crasht'. Wie te laat is, verliest de inzet.
Het crashpunt wordt vooraf bepaald, maar blijft geheim tot het gebeurt.

Alles is tijdsgebaseerd: de multiplier is een functie van de verstreken tijd, dus
de server hoeft geen aparte timer te draaien. Optioneel kan een speler een
automatische cash-out instellen, die precies op het juiste moment wordt uitgevoerd.
"""
import math
import random
import time

GROEI = 0.10          # multiplier = e^(GROEI * seconden)
AFTELLEN = 3.0        # seconden tussen de laatste inzet en de start
MAX_CRASH = 50.0      # hoogst mogelijke crashpunt
HUIS_MARGE = 0.97     # 3% huisvoordeel


def nieuw_crashpunt():
    r = random.random()
    punt = math.floor(HUIS_MARGE * 100 / (1 - r)) / 100
    return max(0.50, min(MAX_CRASH, punt))


def tijd_voor_multiplier(m):
    """Na hoeveel seconden (sinds de start) bereikt de multiplier waarde m."""
    return math.log(m) / GROEI if m > 1 else 0.0


def multiplier_op(state, nu):
    t = nu - (state["start_tijd"] or nu)
    if t <= 0:
        return 1.00
    return math.floor(math.exp(GROEI * t) * 100) / 100


def nieuwe_speler(naam):
    return {
        "naam": naam, "chips": 1000, "inzet": 0, "auto": None,
        "status": "wacht",  # wacht, ingezet, spelen, uitbetaald, verloren
        "uitbetaald_bij": None, "winst": 0, "resultaat": "",
    }


def nieuw_spel():
    return {
        "fase": "inzetten",  # inzetten, lopend, afgelopen
        "spelers": {1: nieuwe_speler("Speler 1"), 2: nieuwe_speler("Speler 2")},
        "crash_punt": None,
        "start_tijd": None,
        "crash_tijd": None,
    }


def plaats_inzet(state, pid, bedrag, auto=None):
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

    auto_waarde = None
    if auto not in (None, "", 0):
        try:
            auto_waarde = round(float(auto), 2)
        except (TypeError, ValueError):
            return False, "Ongeldige automatische cash-out."
        if auto_waarde < 1.01:
            return False, "Automatische cash-out moet minstens 1.01x zijn."
        if auto_waarde > MAX_CRASH:
            auto_waarde = MAX_CRASH

    speler["chips"] -= bedrag
    speler["inzet"] = bedrag
    speler["auto"] = auto_waarde
    speler["status"] = "ingezet"

    if all(s["status"] == "ingezet" for s in state["spelers"].values()):
        nu = time.time()
        state["crash_punt"] = nieuw_crashpunt()
        state["start_tijd"] = nu + AFTELLEN
        state["crash_tijd"] = state["start_tijd"] + tijd_voor_multiplier(state["crash_punt"])
        state["fase"] = "lopend"
        for s in state["spelers"].values():
            s["status"] = "spelen"
    return True, ""


def _betaal_uit(speler, m):
    winst = int(speler["inzet"] * m)
    speler["chips"] += winst
    speler["winst"] = winst
    speler["uitbetaald_bij"] = m
    speler["status"] = "uitbetaald"
    speler["resultaat"] = f"Uitbetaald bij {m:.2f}x: {winst} chips (winst {winst - speler['inzet']:+d})."


def werk_bij(state, nu=None):
    """Voert automatische cash-outs uit en verwerkt een eventuele crash.
    Geeft de lijst terug van spelers waarvan de chips veranderd zijn."""
    gewijzigd = []
    if state["fase"] != "lopend":
        return gewijzigd
    nu = nu if nu is not None else time.time()

    for pid, s in state["spelers"].items():
        if s["status"] == "spelen" and s["auto"] is not None and s["auto"] < state["crash_punt"]:
            if nu >= state["start_tijd"] + tijd_voor_multiplier(s["auto"]):
                _betaal_uit(s, s["auto"])
                gewijzigd.append(pid)

    if nu >= state["crash_tijd"]:
        for s in state["spelers"].values():
            if s["status"] == "spelen":
                s["status"] = "verloren"
                s["resultaat"] = f"Gecrasht bij {state['crash_punt']:.2f}x! Je verliest {s['inzet']} chips."
        state["fase"] = "afgelopen"
    return gewijzigd


def cash_out(state, pid):
    nu = time.time()
    werk_bij(state, nu)  # eerst kijken of het spel al gecrasht is
    if state["fase"] != "lopend":
        speler = state["spelers"][pid]
        return False, "Te laat, het spel is al gecrasht." if speler["status"] == "verloren" else "Er is geen ronde bezig."
    speler = state["spelers"][pid]
    if speler["status"] != "spelen":
        return False, "Je hebt al uitbetaald."
    if nu < state["start_tijd"]:
        return False, "Het spel is nog niet gestart."
    _betaal_uit(speler, multiplier_op(state, nu))
    return True, ""


def klaar_voor_nieuwe_ronde(state):
    for s in state["spelers"].values():
        s["inzet"] = 0
        s["auto"] = None
        s["status"] = "wacht"
        s["uitbetaald_bij"] = None
        s["winst"] = 0
        s["resultaat"] = ""
    state["crash_punt"] = None
    state["start_tijd"] = None
    state["crash_tijd"] = None
    state["fase"] = "inzetten"
