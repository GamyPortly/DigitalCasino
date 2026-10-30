import random
import time

NUMMERS = list(range(0, 37))
RODE_NUMMERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BEDENKTIJD = 30
HUIS_DONATIE = 1000


def nieuw_spel():
    return {
        "spelers": {
            1: {"naam": "Speler 1", "chips": 1000, "inzetten": [], "status": "wacht"},
            2: {"naam": "Speler 2", "chips": 1000, "inzetten": [], "status": "wacht"},
        },
        "fase": "inzetten",  # inzetten -> draaien -> afgelopen
        "winnend_nummer": None,
        "draai_start_tijd": None,
        "wachttijd_draaien": 6.0,  # duur van de draaianimatie in seconden
        "wachtende_inzetten": {},
    }


def herstel_blut_spelers(state):
    gedoneerd_aan = []
    for pid, speler in state["spelers"].items():
        if speler["chips"] <= 0:
            speler["chips"] = HUIS_DONATIE
            gedoneerd_aan.append(pid)
    return gedoneerd_aan


def plaats_inzet(state, pid, type_inzet, waarde, bedrag):
    if state["fase"] != "inzetten":
        return False, "Het rad draait al of de ronde is afgelopen."
        
    speler = state["spelers"][pid]
    bedrag = int(bedrag)
    if bedrag <= 0 or bedrag > speler["chips"]:
        return False, "Ongeldig inzetbedrag."

    if type_inzet == "kleur" and waarde not in ("rood", "zwart"):
        return False, "Ongeldige kleur."
    if type_inzet == "pariteit" and waarde not in ("even", "oneven"):
        return False, "Ongeldige keuze."

    # Je mag maar op één kant inzetten: rood OF zwart, even OF oneven.
    if type_inzet in ("kleur", "pariteit"):
        for eerder in speler["inzetten"]:
            if eerder["type"] == type_inzet and eerder["waarde"] != waarde:
                return False, f"Je hebt al op {eerder['waarde']} ingezet, je kunt niet ook op {waarde} inzetten."

    speler["inzetten"].append({"type": type_inzet, "waarde": waarde, "bedrag": bedrag})
    speler["chips"] -= bedrag
    speler["status"] = "ingezet"
    return True, ""


def bevestig_inzet_klaar(state, pid):
    state["wachtende_inzetten"][pid] = True
    if len(state["wachtende_inzetten"]) == 2:
        start_draai(state)


def start_draai(state):
    state["winnend_nummer"] = random.choice(NUMMERS)
    state["draai_start_tijd"] = time.time()
    state["fase"] = "draaien"


def check_draai_klaar(state):
    if state["fase"] != "draaien" or state["draai_start_tijd"] is None:
        return False
    if time.time() - state["draai_start_tijd"] >= state["wachttijd_draaien"]:
        verwerk_uitbetaling(state)
        state["fase"] = "afgelopen"
        return True
    return False


def verwerk_uitbetaling(state):
    win_nr = state["winnend_nummer"]
    is_rood = win_nr in RODE_NUMMERS
    is_zwart = win_nr != 0 and not is_rood
    is_even = win_nr != 0 and win_nr % 2 == 0
    is_oneven = win_nr % 2 != 0

    for pid, speler in state["spelers"].items():
        totale_winst = 0
        for inzet in speler["inzetten"]:
            t = inzet["type"]
            w = inzet["waarde"]
            b = inzet["bedrag"]

            if t == "getal" and int(w) == win_nr:
                totale_winst += b * 36
            elif t == "kleur" and w == "rood" and is_rood:
                totale_winst += b * 2
            elif t == "kleur" and w == "zwart" and is_zwart:
                totale_winst += b * 2
            elif t == "pariteit" and w == "even" and is_even:
                totale_winst += b * 2
            elif t == "pariteit" and w == "oneven" and is_oneven:
                totale_winst += b * 2

        speler["chips"] += totale_winst
        kleur_tekst = "Rood" if is_rood else ("Zwart" if is_zwart else "Groen")
        speler["resultaat"] = f"Nummer is {win_nr} ({kleur_tekst}). Winst: {totale_winst} chips."


def klaar_voor_nieuwe_ronde(state):
    herstel_blut_spelers(state)
    state["fase"] = "inzetten"
    state["winnend_nummer"] = None
    state["draai_start_tijd"] = None
    state["wachtende_inzetten"] = {}
    for speler in state["spelers"].values():
        speler["inzetten"] = []
        speler["status"] = "wacht"
        speler.pop("resultaat", None)