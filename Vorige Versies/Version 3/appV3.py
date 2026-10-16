import os
import secrets
import socket
import time

import qrcode
from flask import Flask, jsonify, render_template, request, session

import poker_engine as pe
import blackjack_engine as bj
import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("POKER_SECRET") or secrets.token_hex(16)
BASISPAD = os.path.dirname(os.path.abspath(__file__))

db.maak_tabellen()

state = pe.nieuw_spel()
blackjack_state = bj.nieuw_spel()

BESCHIKBARE_SPELLEN = {
    "poker": {"naam": "Poker (Texas Hold'em)", "beschikbaar": True},
    "blackjack": {"naam": "Blackjack", "beschikbaar": True},
    "paardenrace": {"naam": "Paardenrennen", "beschikbaar": False},
}
state["spel_keuze"] = None

# Elke speler-plek krijgt bij het opstarten van de server een eigen, willekeurig token.
# Dat token verandert NIET meer terwijl de server draait, dus de QR-link blijft de hele
# sessie lang bruikbaar, ook als spelers meermaals scannen, wisselen van spel, of afsluiten.
for _pid in (1, 2):
    state["spelers"][_pid]["token"] = secrets.token_urlsafe(8)

_laatst_gebruikte_basis_url = {"url": None}


def eigen_ip():
    """Reservemethode om het eigen lan-ip te raden, enkel gebruikt als het verzoek
    zelf geen bruikbaar adres teruggeeft (bijvoorbeeld bij het allereerste opstarten)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def bepaal_basis_url():
    """Bepaalt het adres dat in de QR-code moet komen. We gebruiken bij voorkeur het
    adres waarmee de browser van de dealer het centrale scherm zelf heeft geopend
    (request.host), want dat is gegarandeerd een adres dat op dit netwerk bereikbaar is.
    Enkel als dat adres 'localhost' of '127.0.0.1' is (dus de pagina werd lokaal geopend
    zonder een echt netwerkadres), vallen we terug op een gok van het eigen lan-ip."""
    host = request.host or ""
    onbruikbaar = any(deel in host for deel in ("localhost", "127.0.0.1", "0.0.0.0"))
    if host and not onbruikbaar:
        return f"{request.scheme}://{host}"
    return f"http://{eigen_ip()}:5000"


def zorg_voor_qr_codes():
    """Genereert de QR-afbeeldingen (opnieuw) als het basisadres veranderd is sinds de
    vorige keer. Dit maakt de links robuust: welk adres iemand ook gebruikt om het
    centrale scherm te openen, de QR-codes wijzen altijd naar een werkend adres."""
    basis_url = bepaal_basis_url()
    if basis_url == _laatst_gebruikte_basis_url["url"]:
        return
    _laatst_gebruikte_basis_url["url"] = basis_url
    for pid in (1, 2):
        token = state["spelers"][pid]["token"]
        url = f"{basis_url}/speler/{pid}?token={token}"
        img = qrcode.make(url)
        img.save(os.path.join(BASISPAD, "static", f"qr_speler{pid}.png"))


def veilige_fase_om_te_verlaten():
    """Bepaalt of er NU zonder problemen afgesloten mag worden. Tijdens een lopende
    pokerhand of blackjackronde mag dat niet, want dan blijft de andere speler voor
    eeuwig wachten op een beurt die nooit komt."""
    if state["spel_keuze"] == "poker":
        return state["fase"] in ("wachten", "showdown", "einde")
    if state["spel_keuze"] == "blackjack":
        return blackjack_state["fase"] in ("inzetten", "afgelopen")
    return True


def sla_chips_op_indien_ingelogd(pid):
    naam = state["spelers"][pid]["gebruikersnaam"]
    if naam:
        db.chips_opslaan(naam, state["spelers"][pid]["chips"])


def verwerk_donaties(gedoneerd_aan_pids):
    for pid in gedoneerd_aan_pids:
        state["spelers"][pid]["donatie"] = True
        sla_chips_op_indien_ingelogd(pid)


def sync_blackjack_chips_naar_hoofdstatus():
    for pid in (1, 2):
        state["spelers"][pid]["chips"] = blackjack_state["spelers"][pid]["chips"]


# ---------------------------------------------------------------------------
# Centraal scherm
# ---------------------------------------------------------------------------

@app.route("/")
def centraal_scherm():
    zorg_voor_qr_codes()
    return render_template("centraal.html")


# ---------------------------------------------------------------------------
# Verbinden, inloggen, registreren
# ---------------------------------------------------------------------------

@app.route("/speler/<int:pid>")
def speler_scherm(pid):
    if pid not in (1, 2):
        return "Onbekende speler.", 404
    token = request.args.get("token", "")
    if not token or token != state["spelers"][pid]["token"]:
        return "Ongeldige of verlopen link. Scan de QR-code opnieuw op het centrale scherm.", 403

    sessie_sleutel = f"gebruikersnaam_{pid}"
    if not session.get(sessie_sleutel):
        return render_template("login.html", speler_id=pid)

    state["spelers"][pid]["verbonden"] = True
    return render_template("speler.html", speler_id=pid)


@app.route("/login/<int:pid>", methods=["POST"])
def login_verwerken(pid):
    if pid not in (1, 2):
        return jsonify({"ok": False, "fout": "Onbekende speler."}), 404
    data = request.get_json(force=True) or {}
    ok, fout, spelerrij = db.inloggen(data.get("gebruikersnaam", ""), data.get("code", ""))
    if not ok:
        return jsonify({"ok": False, "fout": fout}), 400

    ander_pid = 2 if pid == 1 else 1
    if state["spelers"][ander_pid]["gebruikersnaam"] == spelerrij["gebruikersnaam"]:
        return jsonify({"ok": False, "fout": "Deze speler zit al aan de andere kant van de tafel."}), 400

    session[f"gebruikersnaam_{pid}"] = spelerrij["gebruikersnaam"]
    state["spelers"][pid]["gebruikersnaam"] = spelerrij["gebruikersnaam"]
    state["spelers"][pid]["chips"] = spelerrij["chips"]
    state["spelers"][pid]["verbonden"] = True
    return jsonify({"ok": True})


@app.route("/registreer/<int:pid>", methods=["POST"])
def registreer_verwerken(pid):
    if pid not in (1, 2):
        return jsonify({"ok": False, "fout": "Onbekende speler."}), 404
    data = request.get_json(force=True) or {}
    ok, fout = db.account_aanmaken(data.get("gebruikersnaam", ""), data.get("code", ""))
    if not ok:
        return jsonify({"ok": False, "fout": fout}), 400

    naam = data.get("gebruikersnaam", "").strip()
    session[f"gebruikersnaam_{pid}"] = naam
    state["spelers"][pid]["gebruikersnaam"] = naam
    state["spelers"][pid]["chips"] = db.STARTCHIPS
    state["spelers"][pid]["verbonden"] = True
    return jsonify({"ok": True})


@app.route("/verlaat/<int:pid>", methods=["POST"])
def verlaat(pid):
    if pid not in (1, 2):
        return jsonify({"ok": False, "fout": "Onbekende speler."}), 404
    if not veilige_fase_om_te_verlaten():
        return jsonify({"ok": False, "fout": "Wacht tot de huidige hand of ronde afgelopen is voor je afsluit."}), 400

    sla_chips_op_indien_ingelogd(pid)
    session.pop(f"gebruikersnaam_{pid}", None)
    state["spelers"][pid]["gebruikersnaam"] = None
    state["spelers"][pid]["verbonden"] = False
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Spel kiezen en starten
# ---------------------------------------------------------------------------

@app.route("/kies_spel", methods=["POST"])
def kies_spel():
    if state["fase"] != "wachten":
        return jsonify({"ok": False, "fout": "Er loopt al een spel, je kan nu niet meer wisselen."}), 400
    data = request.get_json(force=True) or {}
    keuze = data.get("spel")
    if keuze not in BESCHIKBARE_SPELLEN:
        return jsonify({"ok": False, "fout": "Onbekend spel."}), 400
    if not BESCHIKBARE_SPELLEN[keuze]["beschikbaar"]:
        return jsonify({"ok": False, "fout": "Dit spel is nog niet beschikbaar."}), 400
    state["spel_keuze"] = keuze
    return jsonify({"ok": True})


@app.route("/start_spel", methods=["POST"])
def start_spel():
    if not (state["spelers"][1]["verbonden"] and state["spelers"][2]["verbonden"]):
        return jsonify({"ok": False, "fout": "Nog niet beide spelers verbonden."}), 400
    if state["spel_keuze"] is None:
        return jsonify({"ok": False, "fout": "Er is nog geen spel gekozen."}), 400
    if state["fase"] != "wachten":
        return jsonify({"ok": False, "fout": "Er loopt al een spel."}), 400

    if state["spel_keuze"] == "poker":
        pe.start_nieuwe_hand(state)
    elif state["spel_keuze"] == "blackjack":
        state["fase"] = "blackjack"
        blackjack_state["fase"] = "inzetten"

    return jsonify({"ok": True})


@app.route("/volgende_hand", methods=["POST"])
def volgende_hand():
    if state["spel_keuze"] == "poker":
        if state["fase"] != "showdown":
            return jsonify({"ok": False, "fout": "Er is nog geen hand afgelopen."}), 400
        gedoneerd = pe.herstel_blut_spelers(state)
        verwerk_donaties(gedoneerd)
        pe.start_volgende_hand(state)
    elif state["spel_keuze"] == "blackjack":
        if blackjack_state["fase"] != "afgelopen":
            return jsonify({"ok": False, "fout": "Er is nog geen ronde afgelopen."}), 400
        gedoneerd = bj.herstel_blut_spelers(blackjack_state)
        sync_blackjack_chips_naar_hoofdstatus()
        verwerk_donaties(gedoneerd)
        bj.klaar_voor_nieuwe_ronde(blackjack_state)
    return jsonify({"ok": True})


@app.route("/opnieuw", methods=["POST"])
def opnieuw():
    global state, blackjack_state
    bewaarde_tokens = {pid: state["spelers"][pid]["token"] for pid in (1, 2)}
    bewaarde_namen = {pid: state["spelers"][pid]["gebruikersnaam"] for pid in (1, 2)}
    bewaarde_verbonden = {pid: state["spelers"][pid]["verbonden"] for pid in (1, 2)}

    state = pe.nieuw_spel()
    state["spel_keuze"] = None
    for pid in (1, 2):
        state["spelers"][pid]["token"] = bewaarde_tokens[pid]
        state["spelers"][pid]["gebruikersnaam"] = bewaarde_namen[pid]
        state["spelers"][pid]["verbonden"] = bewaarde_verbonden[pid]
        if bewaarde_namen[pid]:
            chips = db.chips_ophalen(bewaarde_namen[pid])
            if chips is not None:
                state["spelers"][pid]["chips"] = chips
    blackjack_state = bj.nieuw_spel()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Poker-acties
# ---------------------------------------------------------------------------

@app.route("/actie", methods=["POST"])
def actie():
    pe.check_timeout(state)
    data = request.get_json(force=True) or {}
    try:
        pid = int(data.get("speler"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "fout": "Ongeldige speler."}), 400

    fase_voor = state["fase"]
    ok, foutmelding = pe.verwerk_actie(state, pid, data.get("actie"), data.get("bedrag", 0))

    if ok and fase_voor != "showdown" and state["fase"] == "showdown":
        for kpid, speler in state["spelers"].items():
            naam = speler["gebruikersnaam"]
            if not naam:
                continue
            db.chips_opslaan(naam, speler["chips"])
            if not speler["gefold"] and len(state["community"]) == 5:
                handtype = pe.eigen_handtype(speler["hand"], state["community"])
                if handtype:
                    db.update_beste_hand(naam, handtype)
            if state["winnaar"] == kpid:
                db.update_grootste_pot(naam, state["laatste_pot"])

    return jsonify({"ok": ok, "fout": foutmelding})


# ---------------------------------------------------------------------------
# Blackjack-acties
# ---------------------------------------------------------------------------

@app.route("/blackjack_inzet", methods=["POST"])
def blackjack_inzet():
    if blackjack_state["fase"] != "inzetten":
        return jsonify({"ok": False, "fout": "Nu kan je niet inzetten."}), 400
    data = request.get_json(force=True) or {}
    try:
        pid = int(data.get("speler"))
        bedrag = int(data.get("bedrag", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "fout": "Ongeldige gegevens."}), 400

    if pid not in (1, 2):
        return jsonify({"ok": False, "fout": "Onbekende speler."}), 400
    if bedrag <= 0 or bedrag > state["spelers"][pid]["chips"]:
        return jsonify({"ok": False, "fout": "Ongeldig bedrag."}), 400

    blackjack_state.setdefault("wachtende_inzetten", {})[pid] = bedrag

    if len(blackjack_state["wachtende_inzetten"]) == 2:
        inzetten = blackjack_state["wachtende_inzetten"]
        blackjack_state["spelers"][1]["chips"] = state["spelers"][1]["chips"]
        blackjack_state["spelers"][2]["chips"] = state["spelers"][2]["chips"]
        bj.start_ronde(blackjack_state, inzetten)
        blackjack_state["wachtende_inzetten"] = {}
        sync_blackjack_chips_naar_hoofdstatus()

    return jsonify({"ok": True})


@app.route("/blackjack_actie", methods=["POST"])
def blackjack_actie():
    data = request.get_json(force=True) or {}
    try:
        pid = int(data.get("speler"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "fout": "Ongeldige speler."}), 400

    handeling = data.get("actie")
    if handeling == "hit":
        ok, foutmelding = bj.hit(blackjack_state, pid)
    elif handeling == "stand":
        ok, foutmelding = bj.stand(blackjack_state, pid)
    else:
        ok, foutmelding = False, "Onbekende actie."

    if ok and blackjack_state["fase"] == "afgelopen":
        sync_blackjack_chips_naar_hoofdstatus()
        for kpid in (1, 2):
            sla_chips_op_indien_ingelogd(kpid)

    return jsonify({"ok": ok, "fout": foutmelding})


# ---------------------------------------------------------------------------
# Statusopvraging (wordt elke seconde gepolld door beide schermen)
# ---------------------------------------------------------------------------

def kaart_tekst(kaart):
    return kaart[0] + kaart[1]


def blackjack_status(voor_pid=None):
    spelers_info = {}
    for pid, s in blackjack_state["spelers"].items():
        info = {
            "naam": s["naam"], "chips": s["chips"], "inzet": s["inzet"],
            "status": s["status"], "resultaat": s.get("resultaat", ""),
            "ingelogd_als": state["spelers"][pid]["gebruikersnaam"],
        }
        if voor_pid == pid:
            info["hand"] = [kaart_tekst(k) for k in s["hand"]]
        spelers_info[pid] = info

    if blackjack_state["dealer_verborgen"] and blackjack_state["dealer_hand"]:
        dealer_hand = [kaart_tekst(blackjack_state["dealer_hand"][0]), "verborgen"]
    else:
        dealer_hand = [kaart_tekst(k) for k in blackjack_state["dealer_hand"]]

    return {
        "fase": blackjack_state["fase"], "beurt": blackjack_state["beurt"],
        "dealer_hand": dealer_hand, "spelers": spelers_info,
    }


def publieke_status(voor_pid=None):
    if state["spel_keuze"] == "poker":
        pe.check_timeout(state)

    resterende_tijd = None
    if state["deadline"] is not None:
        resterende_tijd = max(0, round(state["deadline"] - time.time()))

    spelers_info = {}
    for pid, s in state["spelers"].items():
        info = {
            "naam": s["naam"], "chips": s["chips"], "street_bet": s["street_bet"],
            "totale_inzet": s["totale_inzet"], "gefold": s["gefold"], "all_in": s["all_in"],
            "verbonden": s["verbonden"], "laatste_actie": state["laatste_actie"][pid],
            "ingelogd_als": s["gebruikersnaam"],
        }
        if voor_pid == pid:
            info["hand"] = pe.zichtbare_hand(s["hand"]) if s["hand"] else []
            info["handtype"] = pe.eigen_handtype(s["hand"], state["community"]) if s["hand"] else None
            if s["donatie"]:
                info["donatie"] = True
                s["donatie"] = False  # eenmalig tonen, dan wissen
        spelers_info[pid] = info

    huidige_call = 0
    minimum_raise = pe.GROTE_BLIND
    if voor_pid is not None and state["fase"] not in ("wachten", "showdown", "einde", "blackjack"):
        speler = state["spelers"][voor_pid]
        huidige_call = max(0, state["huidige_inzet"] - speler["street_bet"])
        minimum_raise = state["huidige_inzet"] + pe.GROTE_BLIND if state["huidige_inzet"] > 0 else pe.GROTE_BLIND

    resultaat = {
        "fase": state["fase"], "spel_keuze": state["spel_keuze"], "spellen": BESCHIKBARE_SPELLEN,
        "community": pe.zichtbare_hand(state["community"]), "pot": state["pot"],
        "beurt": state["beurt"], "dealer": state["dealer"], "huidige_inzet": state["huidige_inzet"],
        "wintekst": state["wintekst"], "winnaar": state["winnaar"],
        "resterende_tijd": resterende_tijd, "spelers": spelers_info,
        "huidige_call": huidige_call, "minimum_raise": minimum_raise,
        "hand_nummer": state["hand_nummer"], "veilig_verlaten": veilige_fase_om_te_verlaten(),
    }
    if state["spel_keuze"] == "blackjack" and state["fase"] == "blackjack":
        resultaat["blackjack"] = blackjack_status(voor_pid=voor_pid)
    return resultaat


@app.route("/status")
def status():
    return jsonify(publieke_status())


@app.route("/status/<int:pid>")
def status_speler(pid):
    if pid not in (1, 2):
        return jsonify({"fout": "Onbekende speler."}), 404
    return jsonify(publieke_status(voor_pid=pid))


@app.route("/leaderboard")
def leaderboard():
    return jsonify(db.leaderboard_ophalen())


if __name__ == "__main__":
    print("\n--- Pokertafel-server gestart ---")
    print(f"Open op je PC/laptop: http://{eigen_ip()}:5000")
    print("(de QR-codes zelf worden automatisch met het juiste adres aangemaakt zodra")
    print(" je het centrale scherm voor het eerst opent)\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
