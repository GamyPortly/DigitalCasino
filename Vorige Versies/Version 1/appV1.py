import os
import secrets
import socket

import qrcode
from flask import Flask, jsonify, render_template, request

import poker_engine as pe

app = Flask(__name__)
BASISPAD = os.path.dirname(os.path.abspath(__file__))

state = pe.nieuw_spel()

# Welk spel er gekozen is. Dit staat los van een individuele hand, want de
# keuze gebeurt EENMALIG per sessie, voordat er ook maar een hand gespeeld wordt.
# Voeg hier later "blackjack" of "paardenrace" toe zodra je die spellogica bouwt,
# op dezelfde manier als poker_engine.py is opgebouwd.
BESCHIKBARE_SPELLEN = {
    "poker": {"naam": "Poker (Texas Hold'em)", "beschikbaar": True},
    "blackjack": {"naam": "Blackjack", "beschikbaar": False},
    "paardenrace": {"naam": "Paardenrennen", "beschikbaar": False},
}
state["spel_keuze"] = None


def eigen_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def genereer_qr(pid):
    token = secrets.token_urlsafe(6)
    state["spelers"][pid]["token"] = token
    url = f"http://{eigen_ip()}:5000/speler/{pid}?token={token}"
    img = qrcode.make(url)
    img.save(os.path.join(BASISPAD, "static", f"qr_speler{pid}.png"))
    return url


for pid in (1, 2):
    link = genereer_qr(pid)
    print(f"Speler {pid} link: {link}")


@app.route("/")
def centraal_scherm():
    return render_template("centraal.html")


@app.route("/speler/<int:pid>")
def speler_scherm(pid):
    token = request.args.get("token")
    if pid not in state["spelers"] or token != state["spelers"][pid]["token"]:
        return "Ongeldige of verlopen link. Scan de QR-code opnieuw.", 403
    state["spelers"][pid]["verbonden"] = True
    return render_template("speler.html", speler_id=pid)


@app.route("/kies_spel", methods=["POST"])
def kies_spel():
    if state["fase"] != "wachten":
        return jsonify({"ok": False, "fout": "Er loopt al een spel, je kan nu niet meer wisselen."}), 400
    data = request.get_json(force=True)
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
    pe.start_nieuwe_hand(state)
    return jsonify({"ok": True})


@app.route("/volgende_hand", methods=["POST"])
def volgende_hand():
    if state["fase"] not in ("showdown",):
        return jsonify({"ok": False, "fout": "Er is nog geen hand afgelopen."}), 400
    pe.start_volgende_hand(state)
    return jsonify({"ok": True})


@app.route("/opnieuw", methods=["POST"])
def opnieuw():
    global state
    oude_tokens = {1: state["spelers"][1]["token"], 2: state["spelers"][2]["token"]}
    oude_verbonden = {1: state["spelers"][1]["verbonden"], 2: state["spelers"][2]["verbonden"]}
    state = pe.nieuw_spel()
    state["spel_keuze"] = None
    for pid in (1, 2):
        state["spelers"][pid]["token"] = oude_tokens[pid]
        state["spelers"][pid]["verbonden"] = oude_verbonden[pid]
    return jsonify({"ok": True})


@app.route("/actie", methods=["POST"])
def actie():
    pe.check_timeout(state)
    data = request.get_json(force=True)
    pid = int(data.get("speler"))
    handeling = data.get("actie")
    bedrag = data.get("bedrag", 0)
    ok, foutmelding = pe.verwerk_actie(state, pid, handeling, bedrag)
    return jsonify({"ok": ok, "fout": foutmelding})


def publieke_status(voor_pid=None):
    pe.check_timeout(state)

    resterende_tijd = None
    if state["deadline"] is not None:
        import time
        resterende_tijd = max(0, round(state["deadline"] - time.time()))

    spelers_info = {}
    for pid, s in state["spelers"].items():
        info = {
            "naam": s["naam"],
            "chips": s["chips"],
            "street_bet": s["street_bet"],
            "totale_inzet": s["totale_inzet"],
            "gefold": s["gefold"],
            "all_in": s["all_in"],
            "verbonden": s["verbonden"],
            "laatste_actie": state["laatste_actie"][pid],
        }
        if voor_pid == pid:
            info["hand"] = pe.zichtbare_hand(s["hand"]) if s["hand"] else []
        spelers_info[pid] = info

    huidige_call = 0
    minimum_raise = pe.GROTE_BLIND
    if voor_pid is not None and state["fase"] not in ("wachten", "showdown", "einde"):
        speler = state["spelers"][voor_pid]
        huidige_call = max(0, state["huidige_inzet"] - speler["street_bet"])
        minimum_raise = state["huidige_inzet"] + pe.GROTE_BLIND if state["huidige_inzet"] > 0 else pe.GROTE_BLIND

    return {
        "fase": state["fase"],
        "spel_keuze": state["spel_keuze"],
        "spellen": BESCHIKBARE_SPELLEN,
        "community": pe.zichtbare_hand(state["community"]),
        "pot": state["pot"],
        "beurt": state["beurt"],
        "dealer": state["dealer"],
        "huidige_inzet": state["huidige_inzet"],
        "wintekst": state["wintekst"],
        "winnaar": state["winnaar"],
        "resterende_tijd": resterende_tijd,
        "spelers": spelers_info,
        "huidige_call": huidige_call,
        "minimum_raise": minimum_raise,
        "hand_nummer": state["hand_nummer"],
    }


@app.route("/status")
def status():
    return jsonify(publieke_status())


@app.route("/status/<int:pid>")
def status_speler(pid):
    return jsonify(publieke_status(voor_pid=pid))


if __name__ == "__main__":
    print("\n--- Pokertafel-server gestart ---")
    print(f"Open op je PC/laptop: http://{eigen_ip()}:5000")
    print("Scan de QR-codes met je GSM (zelfde wifi-netwerk!)\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
