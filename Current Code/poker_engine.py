import time
from treys import Card, Deck, Evaluator

evaluator = Evaluator()

KLEINE_BLIND = 10
GROTE_BLIND = 20
BEDENKTIJD = 20  # seconden per beurt
HUIS_DONATIE = 1000  # chips die je krijgt wanneer je volledig blut bent

SUIT_SYMBOLEN = {"s": "\u2660", "h": "\u2665", "d": "\u2666", "c": "\u2663"}

VERTALING_HANDTYPE = {
    "High Card": "Hoge kaart",
    "Pair": "Paar",
    "Two Pair": "Twee paar",
    "Three of a Kind": "Drilling",
    "Straight": "Straat",
    "Flush": "Flush",
    "Full House": "Full house",
    "Four of a Kind": "Vierling",
    "Straight Flush": "Straight flush",
}


def kaart_naar_tekst(kaart):
    ruw = Card.int_to_str(kaart)
    return ruw[0] + SUIT_SYMBOLEN.get(ruw[1], ruw[1])


def zichtbare_hand(kaarten):
    return [kaart_naar_tekst(k) for k in kaarten]


def eigen_handtype(hand, community):
    """Geeft het huidige handtype terug ('Paar', 'Flush', ...) of None als er nog geen
    3 community cards liggen (treys heeft minstens 5 kaarten in totaal nodig)."""
    if len(community) < 3 or len(hand) < 2:
        return None
    score = evaluator.evaluate(community, hand)
    engelse_naam = evaluator.class_to_string(evaluator.get_rank_class(score))
    return VERTALING_HANDTYPE.get(engelse_naam, engelse_naam)


def andere_speler(pid):
    return 2 if pid == 1 else 1


def nieuw_spel():
    return {
        "spelers": {
            1: {
                "naam": "Speler 1", "chips": 1000, "hand": [], "street_bet": 0,
                "totale_inzet": 0, "gefold": False, "all_in": False, "acted": False,
                "token": None, "verbonden": False, "gebruikersnaam": None, "donatie": False,
            },
            2: {
                "naam": "Speler 2", "chips": 1000, "hand": [], "street_bet": 0,
                "totale_inzet": 0, "gefold": False, "all_in": False, "acted": False,
                "token": None, "verbonden": False, "gebruikersnaam": None, "donatie": False,
            },
        },
        "community": [],
        "pot": 0,
        "laatste_pot": 0,
        "fase": "wachten",
        "beurt": None,
        "dealer": 1,
        "huidige_inzet": 0,
        "laatste_actie": {1: "-", 2: "-"},
        "winnaar": None,
        "wintekst": "",
        "deadline": None,
        "_deck": None,
        "hand_nummer": 0,
    }


def herstel_blut_spelers(state):
    """Als een speler op 0 chips staat, krijgt hij een donatie van het huis.
    Geeft de lijst van pid's terug die net een donatie kregen, zodat de server
    dat eenmalig als pop-up kan tonen."""
    gedoneerd_aan = []
    for pid, speler in state["spelers"].items():
        if speler["chips"] <= 0:
            speler["chips"] = HUIS_DONATIE
            speler["donatie"] = True
            gedoneerd_aan.append(pid)
    return gedoneerd_aan


def start_nieuwe_hand(state):
    for pid, s in state["spelers"].items():
        s["hand"] = []
        s["street_bet"] = 0
        s["totale_inzet"] = 0
        s["gefold"] = False
        s["all_in"] = False
        s["acted"] = False

    state["community"] = []
    state["pot"] = 0
    state["winnaar"] = None
    state["wintekst"] = ""
    state["hand_nummer"] += 1

    deck = Deck()
    state["_deck"] = deck
    for pid in (1, 2):
        state["spelers"][pid]["hand"] = deck.draw(2)

    dealer = state["dealer"]
    andere = andere_speler(dealer)

    inzet_klein = min(KLEINE_BLIND, state["spelers"][dealer]["chips"])
    inzet_groot = min(GROTE_BLIND, state["spelers"][andere]["chips"])

    state["spelers"][dealer]["chips"] -= inzet_klein
    state["spelers"][dealer]["street_bet"] = inzet_klein
    state["spelers"][dealer]["totale_inzet"] = inzet_klein

    state["spelers"][andere]["chips"] -= inzet_groot
    state["spelers"][andere]["street_bet"] = inzet_groot
    state["spelers"][andere]["totale_inzet"] = inzet_groot

    state["pot"] = inzet_klein + inzet_groot
    state["huidige_inzet"] = inzet_groot
    state["fase"] = "preflop"
    state["beurt"] = dealer
    state["laatste_actie"] = {1: "-", 2: "-"}
    nieuwe_beurt_timer(state)


def start_volgende_hand(state):
    if state["spelers"][1]["chips"] <= 0 or state["spelers"][2]["chips"] <= 0:
        herstel_blut_spelers(state)
    state["dealer"] = andere_speler(state["dealer"])
    start_nieuwe_hand(state)


def nieuwe_beurt_timer(state):
    state["deadline"] = time.time() + BEDENKTIJD


def ronde_klaar(state):
    s1, s2 = state["spelers"][1], state["spelers"][2]
    if s1["gefold"] or s2["gefold"]:
        return True
    if s1["all_in"] and s2["all_in"]:
        return True
    gelijk = s1["street_bet"] == s2["street_bet"]
    beiden_gehad = s1["acted"] and s2["acted"]
    return gelijk and beiden_gehad


def volgende_fase(state):
    for pid in (1, 2):
        state["spelers"][pid]["street_bet"] = 0
        state["spelers"][pid]["acted"] = False
    state["huidige_inzet"] = 0
    state["laatste_actie"] = {1: "-", 2: "-"}

    if state["fase"] == "preflop":
        state["community"] += state["_deck"].draw(3)
        state["fase"] = "flop"
    elif state["fase"] == "flop":
        state["community"] += state["_deck"].draw(1)
        state["fase"] = "turn"
    elif state["fase"] == "turn":
        state["community"] += state["_deck"].draw(1)
        state["fase"] = "river"
    elif state["fase"] == "river":
        bepaal_winnaar(state)
        return

    if state["spelers"][1]["all_in"] or state["spelers"][2]["all_in"]:
        volgende_fase(state)
        return

    state["beurt"] = andere_speler(state["dealer"])
    nieuwe_beurt_timer(state)


def bepaal_winnaar(state):
    s1, s2 = state["spelers"][1], state["spelers"][2]
    score1 = evaluator.evaluate(state["community"], s1["hand"])
    score2 = evaluator.evaluate(state["community"], s2["hand"])

    pot = state["pot"]
    state["laatste_pot"] = pot
    if score1 < score2:
        winnaar = 1
    elif score2 < score1:
        winnaar = 2
    else:
        winnaar = 0

    if winnaar == 0:
        s1["chips"] += pot // 2
        s2["chips"] += pot // 2
        state["wintekst"] = f"Gelijkspel, de pot van {pot} wordt gedeeld."
    else:
        state["spelers"][winnaar]["chips"] += pot
        beste_score = score1 if winnaar == 1 else score2
        klasse = evaluator.class_to_string(evaluator.get_rank_class(beste_score))
        klasse_nl = VERTALING_HANDTYPE.get(klasse, klasse)
        state["wintekst"] = f"Speler {winnaar} wint de pot van {pot} met {klasse_nl}."

    state["pot"] = 0
    state["fase"] = "showdown"
    state["winnaar"] = winnaar
    state["beurt"] = None
    state["deadline"] = None


def eindig_hand_door_fold(state, winnaar):
    pot = state["pot"]
    state["laatste_pot"] = pot
    state["spelers"][winnaar]["chips"] += pot
    state["wintekst"] = f"Speler {winnaar} wint de pot van {pot} doordat de tegenstander foldde."
    state["pot"] = 0
    state["fase"] = "showdown"
    state["winnaar"] = winnaar
    state["beurt"] = None
    state["deadline"] = None


def verwerk_actie(state, pid, actie, bedrag=0):
    if state["fase"] in ("wachten", "showdown", "einde"):
        return False, "Er is geen actieve ronde bezig."
    if state["beurt"] != pid:
        return False, "Het is niet jouw beurt."

    speler = state["spelers"][pid]
    tegenstander = state["spelers"][andere_speler(pid)]

    if actie == "fold":
        speler["gefold"] = True
        state["laatste_actie"][pid] = "fold"
        eindig_hand_door_fold(state, winnaar=andere_speler(pid))
        return True, ""

    elif actie == "check":
        verschil = state["huidige_inzet"] - speler["street_bet"]
        if verschil > 0:
            werkelijk = min(verschil, speler["chips"])
            speler["chips"] -= werkelijk
            speler["street_bet"] += werkelijk
            speler["totale_inzet"] += werkelijk
            state["pot"] += werkelijk
            if speler["chips"] == 0:
                speler["all_in"] = True
            state["laatste_actie"][pid] = "call"
        else:
            state["laatste_actie"][pid] = "check"
        speler["acted"] = True

    elif actie == "raise":
        try:
            bedrag = int(bedrag)
        except (TypeError, ValueError):
            return False, "Ongeldig bedrag."

        max_bereikbaar = speler["chips"] + speler["street_bet"]
        minimum = state["huidige_inzet"] + GROTE_BLIND if state["huidige_inzet"] > 0 else GROTE_BLIND
        minimum = min(minimum, max_bereikbaar)

        if bedrag < minimum:
            return False, f"Minimum raise is {minimum}."
        if bedrag > max_bereikbaar:
            bedrag = max_bereikbaar

        nodig = bedrag - speler["street_bet"]
        nodig = min(nodig, speler["chips"])
        speler["chips"] -= nodig
        speler["street_bet"] += nodig
        speler["totale_inzet"] += nodig
        state["pot"] += nodig
        state["huidige_inzet"] = speler["street_bet"]
        if speler["chips"] == 0:
            speler["all_in"] = True
        state["laatste_actie"][pid] = f"raise naar {speler['street_bet']}"
        speler["acted"] = True
        tegenstander["acted"] = False

    else:
        return False, "Onbekende actie."

    if ronde_klaar(state):
        volgende_fase(state)
    else:
        state["beurt"] = andere_speler(pid)
        nieuwe_beurt_timer(state)

    return True, ""


def check_timeout(state):
    if state["fase"] in ("wachten", "showdown", "einde"):
        return
    if state["deadline"] is None:
        return
    if time.time() >= state["deadline"]:
        pid = state["beurt"]
        if pid is not None:
            verwerk_actie(state, pid, "fold")
