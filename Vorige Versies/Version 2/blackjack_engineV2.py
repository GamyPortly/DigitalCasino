import random

RANGEN = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "B", "V", "H", "A"]
KLEUREN = ["\u2660", "\u2665", "\u2666", "\u2663"]

DEALER_STOPT_VANAF = 17
BLACKJACK_UITBETALING = 1.5  # 3 tegen 2


def nieuw_deck():
    deck = [(rang, kleur) for rang in RANGEN for kleur in KLEUREN]
    random.shuffle(deck)
    return deck


def kaart_waarde(kaart):
    rang = kaart[0]
    if rang in ("B", "V", "H"):
        return 10
    if rang == "A":
        return 11
    return int(rang)


def bereken_waarde(hand):
    totaal = sum(kaart_waarde(k) for k in hand)
    aantal_azen = sum(1 for k in hand if k[0] == "A")
    while totaal > 21 and aantal_azen > 0:
        totaal -= 10
        aantal_azen -= 1
    return totaal


def is_blackjack(hand):
    return len(hand) == 2 and bereken_waarde(hand) == 21


def is_bust(hand):
    return bereken_waarde(hand) > 21


def nieuw_spel():
    return {
        "deck": [],
        "dealer_hand": [],
        "dealer_verborgen": True,
        "spelers": {
            1: {"naam": "Speler 1", "chips": 1000, "hand": [], "inzet": 0, "status": "wacht"},
            2: {"naam": "Speler 2", "chips": 1000, "hand": [], "inzet": 0, "status": "wacht"},
        },
        "fase": "inzetten",
        "beurt": None,
    }


def start_ronde(state, inzetten):
    state["deck"] = nieuw_deck()
    state["dealer_hand"] = []
    state["dealer_verborgen"] = True

    for pid, bedrag in inzetten.items():
        speler = state["spelers"][pid]
        bedrag = min(bedrag, speler["chips"])
        speler["chips"] -= bedrag
        speler["inzet"] = bedrag
        speler["hand"] = []
        speler["status"] = "aan_de_beurt"

    for _ in range(2):
        for pid in state["spelers"]:
            state["spelers"][pid]["hand"].append(state["deck"].pop())
        state["dealer_hand"].append(state["deck"].pop())

    for pid, speler in state["spelers"].items():
        if is_blackjack(speler["hand"]):
            speler["status"] = "blackjack"

    state["fase"] = "spelen"
    state["beurt"] = eerste_actieve_speler(state)
    if state["beurt"] is None:
        dealer_beurt(state)


def eerste_actieve_speler(state):
    for pid in (1, 2):
        if state["spelers"][pid]["status"] == "aan_de_beurt":
            return pid
    return None


def volgende_speler(state, huidige_pid):
    volgorde = [1, 2]
    idx = volgorde.index(huidige_pid)
    for volgende in volgorde[idx + 1:]:
        if state["spelers"][volgende]["status"] == "aan_de_beurt":
            return volgende
    return None


def hit(state, pid):
    speler = state["spelers"][pid]
    if state["beurt"] != pid or speler["status"] != "aan_de_beurt":
        return False, "Jij bent niet aan de beurt."

    speler["hand"].append(state["deck"].pop())

    if is_bust(speler["hand"]):
        speler["status"] = "bust"
        ga_naar_volgende(state, pid)
    return True, ""


def stand(state, pid):
    speler = state["spelers"][pid]
    if state["beurt"] != pid or speler["status"] != "aan_de_beurt":
        return False, "Jij bent niet aan de beurt."

    speler["status"] = "gestopt"
    ga_naar_volgende(state, pid)
    return True, ""


def ga_naar_volgende(state, huidige_pid):
    volgende_pid = volgende_speler(state, huidige_pid)
    state["beurt"] = volgende_pid
    if volgende_pid is None:
        dealer_beurt(state)


def dealer_beurt(state):
    state["dealer_verborgen"] = False

    iedereen_klaar = all(
        state["spelers"][pid]["status"] in ("bust", "blackjack")
        for pid in state["spelers"]
    )

    if not iedereen_klaar:
        while bereken_waarde(state["dealer_hand"]) < DEALER_STOPT_VANAF:
            state["dealer_hand"].append(state["deck"].pop())

    verwerk_uitbetaling(state)
    state["fase"] = "afgelopen"
    state["beurt"] = None


def verwerk_uitbetaling(state):
    dealer_waarde = bereken_waarde(state["dealer_hand"])
    dealer_bust = is_bust(state["dealer_hand"])

    for pid, speler in state["spelers"].items():
        if speler["status"] == "blackjack":
            winst = speler["inzet"] + round(speler["inzet"] * BLACKJACK_UITBETALING)
            speler["chips"] += winst
            speler["resultaat"] = "blackjack, wint " + str(winst)
        elif speler["status"] == "bust":
            speler["resultaat"] = "bust, verliest " + str(speler["inzet"])
        else:
            eigen_waarde = bereken_waarde(speler["hand"])
            if dealer_bust or eigen_waarde > dealer_waarde:
                winst = speler["inzet"] * 2
                speler["chips"] += winst
                speler["resultaat"] = "wint " + str(winst)
            elif eigen_waarde == dealer_waarde:
                speler["chips"] += speler["inzet"]
                speler["resultaat"] = "gelijkspel, inzet terug"
            else:
                speler["resultaat"] = "verliest " + str(speler["inzet"])


def klaar_voor_nieuwe_ronde(state):
    state["fase"] = "inzetten"
    state["dealer_hand"] = []
    state["dealer_verborgen"] = True
    state["beurt"] = None
    for speler in state["spelers"].values():
        speler["hand"] = []
        speler["inzet"] = 0
        speler["status"] = "wacht"
        speler.pop("resultaat", None)