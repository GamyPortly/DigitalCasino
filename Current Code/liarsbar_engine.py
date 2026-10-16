import random
import time

RANGEN = ["Heer", "Dame", "Boer"]
BEDENKTIJD = 20


def nieuw_deck():
    deck = []
    for rang in RANGEN:
        for _ in range(6):
            deck.append(rang)
    deck.append("Joker")
    deck.append("Joker")
    random.shuffle(deck)
    return deck


def nieuw_spel():
    return {
        "deck": [],
        "tafel_stapel": [],
        "laatste_gegooid": [],
        "doel_kaart": "Heer",
        "spelers": {
            1: {"naam": "Speler 1", "hand": [], "levens": 1, "is_levend": True, "status": "wacht"},
            2: {"naam": "Speler 2", "hand": [], "levens": 1, "is_levend": True, "status": "wacht"},
        },
        "fase": "spelen",
        "beurt": 1,
        "vorige_speler": None,
        "deadline": None,
        "winnaar": None,
        "melding": "",
        "reveal_info": None,
        "coinflip_info": None,
    }


def start_ronde(state):
    state["deck"] = nieuw_deck()
    state["tafel_stapel"] = []
    state["laatste_gegooid"] = []
    state["doel_kaart"] = random.choice(RANGEN)
    state["vorige_speler"] = None
    state["fase"] = "spelen"
    state["reveal_info"] = None
    state["coinflip_info"] = None
    state["melding"] = f"Nieuwe ronde! Doelkaart is: {state['doel_kaart']}"

    for pid, speler in state["spelers"].items():
        if speler["is_levend"]:
            speler["hand"] = [state["deck"].pop() for _ in range(5)]
            speler["status"] = "actief"

    for pid in (1, 2):
        if state["spelers"][pid]["is_levend"]:
            state["beurt"] = pid
            break

    nieuwe_beurt_timer(state)


def nieuwe_beurt_timer(state):
    state["deadline"] = time.time() + BEDENKTIJD


def volgende_speler(state):
    huidige = state["beurt"]
    volgende = 2 if huidige == 1 else 1
    if state["spelers"][volgende]["is_levend"]:
        state["beurt"] = volgende
    nieuwe_beurt_timer(state)


def speel_kaarten(state, pid, geselecteerde_indices):
    if state["fase"] != "spelen" or state["beurt"] != pid:
        return False, "Jij bent niet aan de beurt."

    speler = state["spelers"][pid]
    if not geselecteerde_indices:
        return False, "Selecteer minstens 1 kaart om te gooien."

    geselecteerde_indices = sorted(list(set(geselecteerde_indices)), reverse=True)
    gegooide_kaarten = []

    for idx in geselecteerde_indices:
        if 0 <= idx < len(speler["hand"]):
            gegooide_kaarten.append(speler["hand"].pop(idx))

    if not gegooide_kaarten:
        return False, "Ongeldige kaarten selectie."

    state["laatste_gegooid"] = gegooide_kaarten
    state["tafel_stapel"].extend(gegooide_kaarten)
    state["vorige_speler"] = pid
    state["melding"] = f"Speler {pid} heeft {len(gegooide_kaarten)} kaart(en) gegooid."

    volgende_speler(state)
    return True, ""


def call_bluff(state, pid):
    if state["fase"] != "spelen" or state["beurt"] != pid:
        return False, "Jij bent niet aan de beurt."
    if state["vorige_speler"] is None or not state["laatste_gegooid"]:
        return False, "Er zijn nog geen kaarten gegooid om te callen."

    beschuldigde_pid = state["vorige_speler"]
    gegooide_kaarten = state["laatste_gegooid"]
    doel = state["doel_kaart"]

    was_bluff = any(k != doel and k != "Joker" for k in gegooide_kaarten)
    verliezer_pid = beschuldigde_pid if was_bluff else pid

    state["fase"] = "coinflip"
    state["beurt"] = verliezer_pid
    state["reveal_info"] = {
        "caller": pid,
        "beschuldigde": beschuldigde_pid,
        "kaarten": gegooide_kaarten,
        "was_bluff": was_bluff,
        "verliezer": verliezer_pid,
    }
    state["coinflip_info"] = {"verliezer": verliezer_pid, "status": "wachten_op_keuze"}
    nieuwe_beurt_timer(state)
    return True, ""


def verwerk_coinflip(state, pid, keuze):
    if state["fase"] != "coinflip" or state["beurt"] != pid:
        return False, "Jij moet geen coinflip doen."

    keuze = str(keuze).lower()
    if keuze not in ("heads", "tails"):
        return False, "Kies 'heads' of 'tails'."

    uitkomst = random.choice(["heads", "tails"])
    juist = (keuze == uitkomst)
    speler = state["spelers"][pid]

    if not juist:
        speler["levens"] -= 1
        if speler["levens"] <= 0:
            speler["is_levend"] = False

    state["coinflip_info"] = {
        "verliezer": pid,
        "keuze": keuze,
        "uitkomst": uitkomst,
        "overleefd": juist,
    }

    levende_spelers = [p for p, s in state["spelers"].items() if s["is_levend"]]
    if len(levende_spelers) <= 1:
        state["fase"] = "afgelopen"
        state["winnaar"] = levende_spelers[0] if levende_spelers else None
    else:
        start_ronde(state)

    return True, ""


def check_timeout(state):
    if state["fase"] not in ("spelen", "coinflip") or state["deadline"] is None:
        return
    if time.time() >= state["deadline"]:
        pid = state["beurt"]
        if state["fase"] == "spelen":
            speler = state["spelers"][pid]
            if speler["hand"]:
                speel_kaarten(state, pid, [0])
        elif state["fase"] == "coinflip":
            verwerk_coinflip(state, pid, "heads")


def klaar_voor_nieuwe_ronde(state):
    for speler in state["spelers"].values():
        speler["levens"] = 1
        speler["is_levend"] = True
        speler["hand"] = []
        speler["status"] = "wacht"
    start_ronde(state)