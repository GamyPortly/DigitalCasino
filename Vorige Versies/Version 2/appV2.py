import os
import secrets
from flask import Flask, render_template, request, jsonify
import qrcode
import io
import base64

import poker_engine as pe
import blackjack_engine as bj
import database as db

db.maak_tabellen()

app = Flask(__name__)

def initialiseer_state():
    s = pe.nieuw_spel()
    # Ken voor elke speler een uniek token toe als dat er nog niet is
    for pid in s["spelers"]:
        if not s["spelers"][pid].get("token"):
            s["spelers"][pid]["token"] = secrets.token_urlsafe(8)
    return s

state = initialiseer_state()

def check_token(pid, token):
    if pid not in state["spelers"]:
        return True
    return state["spelers"][pid]["token"] == token

def geef_qr_code(url):
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.route("/")
@app.route("/centraal")
def centraal():
    return render_template("centraal.html")

@app.route("/speler/<int:pid>")
def speler_pagina(pid):
    token = request.args.get("token", "")
    if not check_token(pid, token):
        return "Ongeldige of verlopen link.", 403
    return render_template("speler.html", speler_id=pid, token=token)

@app.route("/login/<int:pid>", methods=["GET", "POST"])
def login_pagina(pid):
    token = request.args.get("token", "")
    if request.method == "POST":
        data = request.get_json(force=True)
        gebruikersnaam = data.get("gebruikersnaam", "").strip()
        code = data.get("code", "").strip()
        ok, fout = db.inloggen(gebruikersnaam, code)
        if ok:
            state["spelers"][pid]["naam"] = gebruikersnaam
        return jsonify({"ok": ok, "fout": fout})
    return render_template("login.html", speler_id=pid, token=token)

@app.route("/registreer/<int:pid>", methods=["POST"])
def registreer_pagina(pid):
    data = request.get_json(force=True)
    gebruikersnaam = data.get("gebruikersnaam", "").strip()
    code = data.get("code", "").strip()
    ok, fout = db.account_aanmaken(gebruikersnaam, code)
    if ok:
        state["spelers"][pid]["naam"] = gebruikersnaam
    return jsonify({"ok": ok, "fout": fout})

@app.route("/status")
@app.route("/api/publieke_status")
def publieke_status():
    if state.get("spel_type", "poker") == "poker":
        pe.check_timeout(state)
        return jsonify(pe.publieke_status(state))
    else:
        return jsonify(bj.publieke_status(state))

@app.route("/api/speler_status/<int:pid>")
def speler_status(pid):
    token = request.args.get("token", "")
    if not check_token(pid, token):
        return jsonify({"fout": "Ongeldig token"}), 403
    if state.get("spel_type", "poker") == "poker":
        pe.check_timeout(state)
        return jsonify(pe.speler_status(state, pid))
    else:
        return jsonify(bj.speler_status(state, pid))

@app.route("/api/actie/<int:pid>", methods=["POST"])
def actie(pid):
    data = request.get_json(force=True)
    if not check_token(pid, data.get("token")):
        return jsonify({"ok": False, "fout": "Ongeldig token"}), 403

    if state.get("spel_type", "poker") == "poker":
        pe.check_timeout(state)
        actie_type = data.get("actie")
        bedrag = int(data.get("bedrag", 0))
        ok, msg = pe.verwerk_actie(state, pid, actie_type, bedrag)
        return jsonify({"ok": ok, "fout": msg})
    else:
        actie_type = data.get("actie")
        ok, msg = bj.verwerk_actie(state, pid, actie_type)
        return jsonify({"ok": ok, "fout": msg})

@app.route("/api/admin/start_poker", methods=["POST"])
def start_poker():
    pe.start_nieuwe_hand(state)
    return jsonify({"ok": True})

@app.route("/api/admin/start_blackjack", methods=["POST"])
def start_blackjack():
    bj.start_nieuwe_ronde(state)
    return jsonify({"ok": True})

@app.route("/api/admin/reset", methods=["POST"])
def reset_server():
    global state
    state = initialiseer_state()
    return jsonify({"ok": True})

@app.route("/api/admin/qr_codes")
def admin_qr_codes():
    host = request.host_url.rstrip('/')
    qrs = {}
    for pid, s in state["spelers"].items():
        url = f"{host}/speler/{pid}?token={s['token']}"
        qrs[pid] = {
            "url": url,
            "qr": geef_qr_code(url),
            "naam": s["naam"]
        }
    return jsonify(qrs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)