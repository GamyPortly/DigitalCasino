import random
import time

PAARDEN = ["Thunderbolt", "Shadowfax", "Blaze", "Spirit", "Comet"]
BAAN_LENGTE = 20           # aantal stappen tot de finish
MAX_STAP = 3               # elk paard zet per tick 0 t/m MAX_STAP stappen
TICK_DUUR = 1.0            # seconden per tick (gelijk aan de poll-interval van de schermen)
STARTVERTRAGING = 2.0      # seconden tussen "alle inzetten binnen" en de start
UITBETALING_MULTIPLIER = 4  # winnaar krijgt inzet x 4 terug (net als in het oorspronkelijke spel)
HUIS_DONATIE = 1000


def nieuw_spel():
    return {
        "spelers": {
            1: {"naam": "Speler 1", "chips": 1000, "inzet": 0, "paard": None, "status": "wacht"},
            2: {"naam": "Speler 2", "chips": 1000, "inzet": 0, "paard": None, "status": "wacht"},
        },
        "fase": "inzetten",   # inzetten -> racen -> afgelopen
        "verloop": [],        # lijst van posities per tick (index = tick)
        "winnaar_paard": None,
        "start_tijd": None,
    }


def herstel_blut_spelers(state):
    gedoneerd_aan = []
    for pid, speler in state["spelers"].items():
        if speler["chips"] <= 0:
            speler["chips"] = HUIS_DONATIE
            gedoneerd_aan.append(pid)
    return gedoneerd_aan


def simuleer_race():
    """Berekent de hele race vooraf. Geeft (verloop, winnaar_index) terug.
    De server geeft per tick enkel de huidige posities vrij, dus niemand kan vooruit kijken."""
    n = len(PAARDEN)
    ruw = [0] * n
    verloop = [[0] * n]
    while True:
        for i in range(n):
            ruw[i] += random.randint(0, MAX_STAP)
        verloop.append([min(p, BAAN_LENGTE) for p in ruw])
        if max(ruw) >= BAAN_LENGTE:
            beste = max(ruw)
            winnaars = [i for i, p in enumerate(ruw) if p == beste]
            return verloop, random.choice(winnaars)


def start_ronde(state, keuzes):
    """keuzes = {pid: (paard_index, bedrag)}"""
    for pid, (paard, bedrag) in keuzes.items():
        speler = state["spelers"][pid]
        bedrag = max(1, min(int(bedrag), speler["chips"]))
        speler["chips"] -= bedrag
        speler["inzet"] = bedrag
        speler["paard"] = int(paard)
        speler["status"] = "ingezet"
        speler.pop("resultaat", None)

    state["verloop"], state["winnaar_paard"] = simuleer_race()
    state["start_tijd"] = time.time() + STARTVERTRAGING
    state["fase"] = "racen"


def huidige_tick(state):
    if not state["verloop"] or state["start_tijd"] is None:
        return 0
    verstreken = time.time() - state["start_tijd"]
    if verstreken < 0:
        return 0
    return min(int(verstreken / TICK_DUUR), len(state["verloop"]) - 1)


def huidige_posities(state):
    if not state["verloop"]:
        return [0] * len(PAARDEN)
    return state["verloop"][huidige_tick(state)]


def check_race(state):
    """Rondt de race af zodra de laatste tick bereikt is. Geeft True terug als de race
    net afgelopen is, zodat de server de chips kan opslaan."""
    if state["fase"] != "racen":
        return False
    if huidige_tick(state) < len(state["verloop"]) - 1:
        return False
    verwerk_uitbetaling(state)
    state["fase"] = "afgelopen"
    return True


def verwerk_uitbetaling(state):
    winnaar = state["winnaar_paard"]
    for speler in state["spelers"].values():
        if speler["paard"] == winnaar:
            winst = speler["inzet"] * UITBETALING_MULTIPLIER
            speler["chips"] += winst
            speler["status"] = "gewonnen"
            speler["resultaat"] = f"{PAARDEN[winnaar]} wint, je krijgt {winst} chips"
        else:
            speler["status"] = "verloren"
            speler["resultaat"] = (
                f"{PAARDEN[winnaar]} wint, {PAARDEN[speler['paard']]} verliest, "
                f"je verliest {speler['inzet']}"
            )


def klaar_voor_nieuwe_ronde(state):
    herstel_blut_spelers(state)
    state["fase"] = "inzetten"
    state["verloop"] = []
    state["winnaar_paard"] = None
    state["start_tijd"] = None
    for speler in state["spelers"].values():
        speler["inzet"] = 0
        speler["paard"] = None
        speler["status"] = "wacht"
        speler.pop("resultaat", None)
