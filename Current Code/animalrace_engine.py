import random
import time

DIEREN = [
    {"naam": "Dumbo de Turbo", "emoji": "🐘", "soort": "Olifant", "zin": "Vergeet nooit te remmen"},
    {"naam": "Koning Kater", "emoji": "🦁", "soort": "Leeuw", "zin": "Brult luid, rent harder"},
    {"naam": "Flitsvalk", "emoji": "🦅", "soort": "Valk", "zin": "Ziet alles, behalve de finish"},
    {"naam": "Koe-l Bloed", "emoji": "🐄", "soort": "Koe", "zin": "Heeft schrik van het gras"},
    {"naam": "Pinguïn op Slippers", "emoji": "🐧", "soort": "Pinguïn", "zin": "Glijdt naar de overwinning"}
]

BAAN_LENGTE = 20         
MAX_STAP = 3               
TICK_DUUR = 1.0            
STARTVERTRAGING = 2.0      
UITBETALING_MULTIPLIER = 4  
HUIS_DONATIE = 1000

def nieuw_spel():
    return {
        "spelers": {
            1: {"naam": "Speler 1", "chips": 1000, "inzet": 0, "dier": None, "status": "wacht"},
            2: {"naam": "Speler 2", "chips": 1000, "inzet": 0, "dier": None, "status": "wacht"},
        },
        "fase": "inzetten",   
        "verloop": [],        
        "winnaar_dier": None,
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
    n = len(DIEREN)
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
    for pid, (dier, bedrag) in keuzes.items():
        speler = state["spelers"][pid]
        bedrag = max(1, min(int(bedrag), speler["chips"]))
        speler["chips"] -= bedrag
        speler["inzet"] = bedrag
        speler["dier"] = int(dier)
        speler["status"] = "ingezet"
        speler.pop("resultaat", None)

    state["verloop"], state["winnaar_dier"] = simuleer_race()
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
        return [0] * len(DIEREN)
    return state["verloop"][huidige_tick(state)]

def check_race(state):
    if state["fase"] != "racen":
        return False
    if huidige_tick(state) < len(state["verloop"]) - 1:
        return False
    verwerk_uitbetaling(state)
    state["fase"] = "afgelopen"
    return True

def verwerk_uitbetaling(state):
    winnaar = state["winnaar_dier"]
    winnaar_naam = DIEREN[winnaar]["naam"]
    for speler in state["spelers"].values():
        if speler["dier"] == winnaar:
            winst = speler["inzet"] * UITBETALING_MULTIPLIER
            speler["chips"] += winst
            speler["status"] = "gewonnen"
            speler["resultaat"] = f"{winnaar_naam} wint, je krijgt {winst} chips!"
        else:
            speler["status"] = "verloren"
            gekozen_naam = DIEREN[speler['dier']]['naam'] if speler['dier'] is not None else "niets"
            speler["resultaat"] = f"{winnaar_naam} wint! {gekozen_naam} verliest {speler['inzet']} chips."

def klaar_voor_nieuwe_ronde(state):
    herstel_blut_spelers(state)
    state["fase"] = "inzetten"
    state["verloop"] = []
    state["winnaar_dier"] = None
    state["start_tijd"] = None
    for speler in state["spelers"].values():
        speler["inzet"] = 0
        speler["dier"] = None
        speler["status"] = "wacht"
        speler.pop("resultaat", None)