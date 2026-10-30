import os
import secrets
import socket
import time

import qrcode
from flask import Flask, jsonify, render_template, request, session

import poker_engine as pe
import blackjack_engine as bj
import animalrace_engine as pr
import liarsbar_engine as lb
import roulette_engine as rt
import ridebus_engine as rb
import crash_engine as cr
import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("POKER_SECRET") or secrets.token_hex(16)
BASISPAD = os.path.dirname(os.path.abspath(__file__))

db.maak_tabellen()

state = pe.nieuw_spel()
blackjack_state = bj.nieuw_spel()
animalrace_state = pr.nieuw_spel()
liarsbar_state = lb.nieuw_spel()
roulette_state = rt.nieuw_spel()
ridebus_state = rb.nieuw_spel()
crash_state = cr.nieuw_spel()

BESCHIKBARE_SPELLEN = {
    "poker": {"naam": "Poker (Texas Hold'em)", "beschikbaar": True},
    "blackjack": {"naam": "Blackjack", "beschikbaar": True},
    "animalrace": {"naam": "Animal Racing 🐾", "beschikbaar": True},
    "liarsbar": {"naam": "Liar's Bar", "beschikbaar": True},
    "roulette": {"naam": "Roulette", "beschikbaar": True},
    "ridebus": {"naam": "Ride the Bus", "beschikbaar": True},
    "crash": {"naam": "Crash", "beschikbaar": True},
}
state["spel_keuze"] = None
state["suggestie_spel"] = None
LAATST_GEZIEN = {1: time.time(), 2: time.time()}

for _pid in (1, 2):
    state["spelers"][_pid]["token"] = secrets.token_urlsafe(8)

_laatst_gebruikte_basis_url = {"url": None}


def eigen_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def bepaal_basis_url():
    host = request.host or ""
    onbruikbaar = any(deel in host for deel in ("localhost", "127.0.0.1", "0.0.0.0"))
    if host and not onbruikbaar:
        return f"{request.scheme}://{host}"
    return f"http://{eigen_ip()}:5000"


def zorg_voor_qr_codes():
    basis_url = bepaal_basis_url()
    if basis_url == _laatst_gebruikte_basis_url["url"]:
        return
    _laatst_gebruikte_basis_url["url"] = basis_url
    for pid in (1, 2):
        token = state["spelers"][pid]["token"]
        url = f"{basis_url}/speler/{pid}?token={token}"
        img = qrcode.make(url)
        img.save(os.path.join(BASISPAD, "static", f"qr_speler{pid}.png"))


def controleer_verbindingen():
    now = time.time()
    for pid in (1, 2):
        if state["spelers"][pid]["verbonden"] and (now - LAATST_GEZIEN[pid] > 6):
            state["spelers"][pid]["verbonden"] = False
            state["spelers"][pid]["gebruikersnaam"] = None
            if state["fase"] != "wachten":
                reset_naar_wachten()


def reset_naar_wachten():
    global blackjack_state, animalrace_state, liarsbar_state, roulette_state, ridebus_state, crash_state
    state["fase"] = "wachten"
    state["spel_keuze"] = None
    state["suggestie_spel"] = None
    blackjack_state = bj.nieuw_spel()
    animalrace_state = pr.nieuw_spel()
    liarsbar_state = lb.nieuw_spel()
    roulette_state = rt.nieuw_spel()
    ridebus_state = rb.nieuw_spel()
    crash_state = cr.nieuw_spel()


def sla_chips_op_indien_ingelogd(pid):
    naam = state["spelers"][pid]["gebruikersnaam"]
    if naam:
        db.chips_opslaan(naam, state["spelers"][pid]["chips"])


def geef_donaties():
    for pid in (1, 2):
        if state["spelers"][pid]["chips"] <= 0:
            state["spelers"][pid]["chips"] = pe.HUIS_DONATIE
            state["spelers"][pid]["donatie"] = True
            for spel_state in (blackjack_state, animalrace_state, roulette_state, ridebus_state, crash_state):
                spel_state["spelers"][pid]["chips"] = pe.HUIS_DONATIE
            sla_chips_op_indien_ingelogd(pid)


def sync_chips_naar_hoofdstatus():
    for pid in (1, 2):
        if state["spel_keuze"] == "blackjack":
            state["spelers"][pid]["chips"] = blackjack_state["spelers"][pid]["chips"]
        elif state["spel_keuze"] == "animalrace":
            state["spelers"][pid]["chips"] = animalrace_state["spelers"][pid]["chips"]
        elif state["spel_keuze"] == "roulette":
            state["spelers"][pid]["chips"] = roulette_state["spelers"][pid]["chips"]


def werk_animalrace_bij():
    if pr.check_race(animalrace_state):
        sync_chips_naar_hoofdstatus()
        for kpid in (1, 2):
            sla_chips_op_indien_ingelogd(kpid)


@app.route("/")
def centraal_scherm():
    zorg_voor_qr_codes()
    return render_template("centraal.html")


@app.route("/speler/<int:pid>")
def speler_scherm(pid):
    if pid not in (1, 2):
        return "Onbekende speler.", 404
    token = request.args.get("token", "")
    if not token or token != state["spelers"][pid]["token"]:
        return "Ongeldige of verlopen link. Scan de QR-code opnieuw op het centrale scherm.", 403

    sessie_sleutel = f"gebruikersnaam_{pid}"
    if not session.get(sessie_sleutel):
        return render_template("login.html", speler_id=pid, pid=pid, token=token)

    state["spelers"][pid]["verbonden"] = True
    LAATST_GEZIEN[pid] = time.time()
    return render_template("speler.html", speler_id=pid)


def token_geldig(pid):
    token = request.args.get("token", "")
    return bool(token) and token == state["spelers"][pid]["token"]


@app.route("/login/<int:pid>", methods=["POST"])
def login_verwerken(pid):
    if pid not in (1, 2):
        return jsonify({"ok": False, "fout": "Onbekende speler."}), 404
    if not token_geldig(pid):
        return jsonify({"ok": False, "fout": "Ongeldige of verlopen link. Scan de QR-code opnieuw."}), 403
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
    LAATST_GEZIEN[pid] = time.time()
    return jsonify({"ok": True})


@app.route("/registreer/<int:pid>", methods=["POST"])
def registreer_verwerken(pid):
    if pid not in (1, 2):
        return jsonify({"ok": False, "fout": "Onbekende speler."}), 404
    if not token_geldig(pid):
        return jsonify({"ok": False, "fout": "Ongeldige of verlopen link. Scan de QR-code opnieuw."}), 403
    data = request.get_json(force=True) or {}
    ok, fout = db.account_aanmaken(data.get("gebruikersnaam", ""), data.get("code", ""))
    if not ok:
        return jsonify({"ok": False, "fout": fout}), 400

    naam = data.get("gebruikersnaam", "").strip()
    session[f"gebruikersnaam_{pid}"] = naam
    state["spelers"][pid]["gebruikersnaam"] = naam
    state["spelers"][pid]["chips"] = db.STARTCHIPS
    state["spelers"][pid]["verbonden"] = True
    LAATST_GEZIEN[pid] = time.time()
    return jsonify({"ok": True})


@app.route("/verlaat/<int:pid>", methods=["POST"])
def verlaat(pid):
    if pid not in (1, 2):
        return jsonify({"ok": False, "fout": "Onbekende speler."}), 404

    sla_chips_op_indien_ingelogd(pid)
    session.pop(f"gebruikersnaam_{pid}", None)
    state["spelers"][pid]["gebruikersnaam"] = None
    state["spelers"][pid]["verbonden"] = False
    reset_naar_wachten()
    return jsonify({"ok": True})


@app.route("/kies_spel", methods=["POST"])
def kies_spel():
    data = request.get_json(force=True) or {}
    keuze = data.get("spel")
    if keuze not in BESCHIKBARE_SPELLEN:
        return jsonify({"ok": False, "fout": "Onbekend spel."}), 400
    
    speler_id = int(data.get("speler", 1))
    if speler_id != 1:
        return jsonify({"ok": False, "fout": "Alleen Host (Speler 1) kan het spel kiezen of wijzigen."}), 403

    state["spel_keuze"] = keuze
    state["suggestie_spel"] = None
    return jsonify({"ok": True})


@app.route("/suggereer_spel", methods=["POST"])
def suggereer_spel():
    data = request.get_json(force=True) or {}
    keuze = data.get("spel")
    if keuze not in BESCHIKBARE_SPELLEN:
        return jsonify({"ok": False, "fout": "Onbekend spel."}), 400
    state["suggestie_spel"] = keuze
    return jsonify({"ok": True})


@app.route("/start_spel", methods=["POST"])
def start_spel():
    if not (state["spelers"][1]["verbonden"] and state["spelers"][2]["verbonden"]):
        return jsonify({"ok": False, "fout": "Nog niet beide spelers verbonden."}), 400
    if state["spel_keuze"] is None:
        return jsonify({"ok": False, "fout": "Er is nog geen spel gekozen."}), 400

    geef_donaties()

    if state["spel_keuze"] == "poker":
        pe.start_nieuwe_hand(state)
    elif state["spel_keuze"] == "blackjack":
        state["fase"] = "blackjack"
        blackjack_state["fase"] = "inzetten"
    elif state["spel_keuze"] == "animalrace":
        state["fase"] = "animalrace"
        animalrace_state["fase"] = "inzetten"
    elif state["spel_keuze"] == "liarsbar":
        state["fase"] = "liarsbar"
        lb.start_ronde(liarsbar_state)
    elif state["spel_keuze"] == "roulette":
        state["fase"] = "roulette"
        roulette_state["fase"] = "inzetten"
    elif state["spel_keuze"] == "ridebus":
        state["fase"] = "ridebus"
        ridebus_state["fase"] = "inzetten"
    elif state["spel_keuze"] == "crash":
        state["fase"] = "crash"
        crash_state["fase"] = "inzetten"

    return jsonify({"ok": True})


@app.route("/naar_menu", methods=["POST"])
def naar_menu():
    sync_chips_naar_hoofdstatus()
    if state["spel_keuze"] != "poker":
        geef_donaties()
    for pid in (1, 2):
        sla_chips_op_indien_ingelogd(pid)
    reset_naar_wachten()
    return jsonify({"ok": True})


@app.route("/volgende_hand", methods=["POST"])
def volgende_hand():
    if state["spel_keuze"] == "poker":
        pe.start_volgende_hand(state)
    elif state["spel_keuze"] == "blackjack":
        sync_chips_naar_hoofdstatus()
        bj.klaar_voor_nieuwe_ronde(blackjack_state)
    elif state["spel_keuze"] == "animalrace":
        sync_chips_naar_hoofdstatus()
        pr.klaar_voor_nieuwe_ronde(animalrace_state)
    elif state["spel_keuze"] == "liarsbar":
        lb.klaar_voor_nieuwe_ronde(liarsbar_state)
    elif state["spel_keuze"] == "roulette":
        sync_chips_naar_hoofdstatus()
        rt.klaar_voor_nieuwe_ronde(roulette_state)
    elif state["spel_keuze"] == "ridebus":
        rb.klaar_voor_nieuwe_ronde(ridebus_state)
    elif state["spel_keuze"] == "crash":
        cr.klaar_voor_nieuwe_ronde(crash_state)
    if state["spel_keuze"] != "poker":
        geef_donaties()
    return jsonify({"ok": True})


@app.route("/actie", methods=["POST"])
def actie():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    ok, foutmelding = pe.verwerk_actie(state, pid, data.get("actie"), data.get("bedrag", 0))
    return jsonify({"ok": ok, "fout": foutmelding})


@app.route("/blackjack_inzet", methods=["POST"])
def blackjack_inzet():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    bedrag = int(data.get("bedrag", 0))
    blackjack_state.setdefault("wachtende_inzetten", {})[pid] = bedrag
    if len(blackjack_state["wachtende_inzetten"]) == 2:
        inzetten = blackjack_state["wachtende_inzetten"]
        blackjack_state["spelers"][1]["chips"] = state["spelers"][1]["chips"]
        blackjack_state["spelers"][2]["chips"] = state["spelers"][2]["chips"]
        bj.start_ronde(blackjack_state, inzetten)
        blackjack_state["wachtende_inzetten"] = {}
    return jsonify({"ok": True})


@app.route("/blackjack_actie", methods=["POST"])
def blackjack_actie():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    actie = data.get("actie")
    ok, fout = (bj.hit(blackjack_state, pid) if actie == "hit" else bj.stand(blackjack_state, pid))
    return jsonify({"ok": ok, "fout": fout})


@app.route("/animalrace_inzet", methods=["POST"])
def animalrace_inzet():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    bedrag = int(data.get("bedrag", 0))
    dier = int(data.get("dier"))
    animalrace_state.setdefault("wachtende_inzetten", {})[pid] = (dier, bedrag)
    if len(animalrace_state["wachtende_inzetten"]) == 2:
        keuzes = animalrace_state["wachtende_inzetten"]
        pr.start_ronde(animalrace_state, keuzes)
        animalrace_state["wachtende_inzetten"] = {}
    return jsonify({"ok": True})


@app.route("/liarsbar_speel", methods=["POST"])
def liarsbar_speel():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    indices = [int(x) for x in data.get("indices", [])]
    ok, fout = lb.speel_kaarten(liarsbar_state, pid, indices)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/liarsbar_call", methods=["POST"])
def liarsbar_call():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    ok, fout = lb.call_bluff(liarsbar_state, pid)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/liarsbar_coinflip", methods=["POST"])
def liarsbar_coinflip():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    keuze = data.get("keuze")
    ok, fout = lb.verwerk_coinflip(liarsbar_state, pid, keuze)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/roulette_inzet", methods=["POST"])
def roulette_inzet():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    t = data.get("type")
    w = data.get("waarde")
    b = int(data.get("bedrag", 0))
    if state["spelers"][pid]["chips"] <= 0:
        state["spelers"][pid]["chips"] = pe.HUIS_DONATIE
    roulette_state["spelers"][pid]["chips"] = state["spelers"][pid]["chips"]
    ok, fout = rt.plaats_inzet(roulette_state, pid, t, w, b)
    state["spelers"][pid]["chips"] = roulette_state["spelers"][pid]["chips"]
    sla_chips_op_indien_ingelogd(pid)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/roulette_bevestig", methods=["POST"])
def roulette_bevestig():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    rt.bevestig_inzet_klaar(roulette_state, pid)
    return jsonify({"ok": True})


@app.route("/crash_inzet", methods=["POST"])
def crash_inzet():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    if state["spelers"][pid]["chips"] <= 0:
        state["spelers"][pid]["chips"] = pe.HUIS_DONATIE
    crash_voor(pid)
    ok, fout = cr.plaats_inzet(crash_state, pid, data.get("bedrag", 0), data.get("auto"))
    crash_na(pid)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/crash_cashout", methods=["POST"])
def crash_cashout():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    crash_voor(pid)
    ok, fout = cr.cash_out(crash_state, pid)
    crash_na(pid)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/ridebus_inzet", methods=["POST"])
def ridebus_inzet():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    if state["spelers"][pid]["chips"] <= 0:
        state["spelers"][pid]["chips"] = pe.HUIS_DONATIE
    ridebus_voor(pid)
    ok, fout = rb.plaats_inzet(ridebus_state, pid, data.get("bedrag", 0))
    ridebus_na(pid)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/ridebus_gok", methods=["POST"])
def ridebus_gok():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    ridebus_voor(pid)
    ok, fout = rb.gok(ridebus_state, pid, data.get("keuze"))
    ridebus_na(pid)
    return jsonify({"ok": ok, "fout": fout})


@app.route("/ridebus_uitbetaal", methods=["POST"])
def ridebus_uitbetaal():
    data = request.get_json(force=True) or {}
    pid = int(data.get("speler"))
    ridebus_voor(pid)
    ok, fout = rb.uitbetalen(ridebus_state, pid)
    ridebus_na(pid)
    return jsonify({"ok": ok, "fout": fout})


def kaart_tekst(kaart):
    if isinstance(kaart, (list, tuple)):
        return str(kaart[0]) + str(kaart[1])
    return str(kaart)


def blackjack_status(voor_pid=None):
    spelers_info = {}
    for pid, s in blackjack_state["spelers"].items():
        info = {
            "naam": s["naam"], "chips": s["chips"], "inzet": s["inzet"],
            "status": s["status"], "resultaat": s.get("resultaat", ""),
            "ingelogd_als": state["spelers"][pid]["gebruikersnaam"],
            "hand": [kaart_tekst(k) for k in s["hand"]],
        }
        spelers_info[pid] = info

    dealer_hand = [kaart_tekst(k) for k in blackjack_state["dealer_hand"]]
    if blackjack_state["dealer_verborgen"] and len(dealer_hand) > 1:
        dealer_hand[1] = "verborgen"

    return {
        "fase": blackjack_state["fase"], "beurt": blackjack_state["beurt"],
        "dealer_hand": dealer_hand, "spelers": spelers_info,
    }


def animalrace_status(voor_pid=None):
    werk_animalrace_bij()
    wachtend = animalrace_state.get("wachtende_inzetten", {})
    spelers_info = {}
    for pid, s in animalrace_state["spelers"].items():
        info = {
            "naam": s["naam"], "chips": s["chips"], "inzet": s["inzet"],
            "status": s["status"], "resultaat": s.get("resultaat", ""),
            "ingelogd_als": state["spelers"][pid]["gebruikersnaam"],
            "heeft_ingezet": pid in wachtend or s["status"] != "wacht",
        }
        if animalrace_state["fase"] != "inzetten":
            info["dier"] = s["dier"]
        elif voor_pid == pid and pid in wachtend:
            info["dier"] = wachtend[pid][0]
        spelers_info[pid] = info

    resultaat = {
        "fase": animalrace_state["fase"], "dieren": pr.DIEREN,
        "baan_lengte": pr.BAAN_LENGTE, "tick_duur": pr.TICK_DUUR,
        "posities": pr.huidige_posities(animalrace_state),
        "gestart": animalrace_state["fase"] != "inzetten" and (animalrace_state["start_tijd"] or 0) <= time.time(),
        "spelers": spelers_info,
    }
    if animalrace_state["fase"] == "afgelopen":
        resultaat["winnaar_dier"] = animalrace_state["winnaar_dier"]
    return resultaat


def liarsbar_status(voor_pid=None):
    lb.check_timeout(liarsbar_state)
    return {
        "fase": liarsbar_state["fase"],
        "doel_kaart": liarsbar_state["doel_kaart"],
        "beurt": liarsbar_state["beurt"],
        "vorige_speler": liarsbar_state["vorige_speler"],
        "aantal_op_tafel": len(liarsbar_state["tafel_stapel"]),
        "aantal_laatste_gegooid": len(liarsbar_state["laatste_gegooid"]),
        "melding": liarsbar_state["melding"],
        "reveal_info": liarsbar_state["reveal_info"],
        "coinflip_info": liarsbar_state["coinflip_info"],
        "winnaar": liarsbar_state["winnaar"],
        "spelers": {
            p: {
                "naam": s["naam"],
                "levens": s["levens"],
                "is_levend": s["is_levend"],
                "aantal_kaarten": len(s["hand"]),
                "hand": s["hand"] if voor_pid == p else [],
                "ingelogd_als": state["spelers"][p]["gebruikersnaam"],
            } for p, s in liarsbar_state["spelers"].items()
        }
    }


def crash_voor(pid):
    crash_state["spelers"][pid]["chips"] = state["spelers"][pid]["chips"]


def crash_na(pid):
    state["spelers"][pid]["chips"] = crash_state["spelers"][pid]["chips"]
    sla_chips_op_indien_ingelogd(pid)


def werk_crash_bij():
    for pid in cr.werk_bij(crash_state):
        crash_na(pid)


def crash_status(voor_pid=None):
    werk_crash_bij()
    nu = time.time()
    fase = crash_state["fase"]
    spelers_info = {}
    for pid, s in crash_state["spelers"].items():
        spelers_info[pid] = {
            "naam": s["naam"], "chips": state["spelers"][pid]["chips"], "inzet": s["inzet"],
            "status": s["status"], "resultaat": s["resultaat"],
            "uitbetaald_bij": s["uitbetaald_bij"], "winst": s["winst"],
            "auto": s["auto"] if voor_pid == pid else None,
            "ingelogd_als": state["spelers"][pid]["gebruikersnaam"],
        }
    resultaat = {
        "fase": fase, "groei": cr.GROEI, "start": cr.START_MULTIPLIER, "spelers": spelers_info,
        "verstreken": None, "multiplier": cr.START_MULTIPLIER, "crash_punt": None,
    }
    if fase in ("lopend", "afgelopen"):
        resultaat["verstreken"] = nu - crash_state["start_tijd"]
        resultaat["multiplier"] = cr.multiplier_op(crash_state, nu)
    if fase == "afgelopen":
        resultaat["crash_punt"] = crash_state["crash_punt"]
        resultaat["multiplier"] = crash_state["crash_punt"]
        resultaat["crash_verstreken"] = crash_state["crash_tijd"] - crash_state["start_tijd"]
    return resultaat


def ridebus_voor(pid):
    ridebus_state["spelers"][pid]["chips"] = state["spelers"][pid]["chips"]


def ridebus_na(pid):
    state["spelers"][pid]["chips"] = ridebus_state["spelers"][pid]["chips"]
    sla_chips_op_indien_ingelogd(pid)


def ridebus_status(voor_pid=None):
    spelers_info = {}
    for pid, s in ridebus_state["spelers"].items():
        klaar = s["status"] in ("verloren", "uitbetaald", "gewonnen")
        spelen = s["status"] == "spelen"
        spelers_info[pid] = {
            "naam": s["naam"], "chips": state["spelers"][pid]["chips"], "inzet": s["inzet"],
            "status": s["status"], "resultaat": s["resultaat"],
            "ingelogd_als": state["spelers"][pid]["gebruikersnaam"],
            "kaarten": [rb.kaart_tekst(k) for k in s["kaarten"]],
            "stap": s["stap"],
            "vraag": rb.VRAGEN[s["stap"]] if spelen else None,
            "uitbetaal_waarde": rb.huidige_waarde(s) if spelen else 0,
            "klaar": klaar,
        }
    return {
        "fase": ridebus_state["fase"],
        "multipliers": rb.MULTIPLIERS,
        "vragen": [v["titel"] for v in rb.VRAGEN],
        "spelers": spelers_info,
    }


def publieke_status(voor_pid=None):
    if voor_pid in (1, 2):
        LAATST_GEZIEN[voor_pid] = time.time()

    controleer_verbindingen()

    if state["spel_keuze"] == "poker":
        pe.check_timeout(state)
    elif state["spel_keuze"] == "roulette" and state["fase"] == "roulette":
        if rt.check_draai_klaar(roulette_state):
            sync_chips_naar_hoofdstatus()
            for kpid in (1, 2):
                sla_chips_op_indien_ingelogd(kpid)

    huidige_call = 0
    if voor_pid is not None and state["fase"] not in ("wachten", "showdown", "einde", "blackjack", "animalrace", "liarsbar", "roulette", "ridebus", "crash"):
        speler = state["spelers"][voor_pid]
        huidige_call = max(0, state["huidige_inzet"] - speler["street_bet"])

    spelers_info = {}
    for pid, s in state["spelers"].items():
        info = {
            "naam": s["naam"], "chips": s["chips"], "street_bet": s["street_bet"],
            "totale_inzet": s["totale_inzet"], "gefold": s["gefold"], "all_in": s["all_in"],
            "verbonden": s["verbonden"], "ingelogd_als": s["gebruikersnaam"],
        }
        if voor_pid == pid:
            if s.get("donatie"):
                info["donatie"] = True
                s["donatie"] = False
            info["hand"] = pe.zichtbare_hand(s["hand"]) if s["hand"] else []
            info["handtype"] = pe.eigen_handtype(s["hand"], state["community"]) if s["hand"] else None
        spelers_info[pid] = info

    resultaat = {
        "fase": state["fase"],
        "spel_keuze": state["spel_keuze"],
        "suggestie_spel": state.get("suggestie_spel"),
        "spellen": BESCHIKBARE_SPELLEN,
        "community": pe.zichtbare_hand(state["community"]),
        "pot": state.get("pot", 0),
        "beurt": state.get("beurt"),
        "wintekst": state.get("wintekst", ""),
        "spelers": spelers_info,
        "huidige_call": huidige_call,
        "veilig_verlaten": True,
    }

    if state["spel_keuze"] == "blackjack" and state["fase"] == "blackjack":
        resultaat["blackjack"] = blackjack_status(voor_pid=voor_pid)
    elif state["spel_keuze"] == "animalrace" and state["fase"] == "animalrace":
        resultaat["animalrace"] = animalrace_status(voor_pid=voor_pid)
    elif state["spel_keuze"] == "liarsbar" and state["fase"] == "liarsbar":
        resultaat["liarsbar"] = liarsbar_status(voor_pid=voor_pid)
    elif state["spel_keuze"] == "roulette" and state["fase"] == "roulette":
        resultaat["roulette"] = {
            "fase": roulette_state["fase"],
            "winnend_nummer": roulette_state["winnend_nummer"],
            "spelers": {
                p: {
                    "inzetten": s["inzetten"],
                    "status": s["status"],
                    "resultaat": s.get("resultaat", ""),
                    "ingelogd_als": state["spelers"][p]["gebruikersnaam"],
                } for p, s in roulette_state["spelers"].items()
            }
        }
    elif state["spel_keuze"] == "ridebus" and state["fase"] == "ridebus":
        resultaat["ridebus"] = ridebus_status(voor_pid=voor_pid)
    elif state["spel_keuze"] == "crash" and state["fase"] == "crash":
        resultaat["crash"] = crash_status(voor_pid=voor_pid)

    return resultaat


@app.route("/status")
def status():
    return jsonify(publieke_status())


@app.route("/status/<int:pid>")
def status_speler(pid):
    if pid not in (1, 2):
        return jsonify({"fout": "Onbekende speler."}), 404
    return jsonify(publieke_status(voor_pid=pid))


if __name__ == "__main__":
    print(f"\n--- Digital Casino Gestart op http://{eigen_ip()}:5000 ---\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)