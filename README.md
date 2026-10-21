**Digital Casino Game Table**

An interactive, Raspberry Pi-powered digital casino system for playing Poker (Texas Hold'em), Blackjack and more! Players use their smartphones to scan a QR code from a central display, allowing them to view their private hands and send actions while community cards, pot totals, and game states render live on the main TV screen.

Features
Multi-Game Support: Switch seamlessly between Texas Hold'em Poker and Blackjack.

Central TV Dashboard: Real-time display for community cards, pot sizes, active turn timers, and dynamic sound effects.

Mobile Controller: Web-based interface for players to join seats, log in, check hidden cards, and execute game actions (Fold, Call, Raise, Hit, Stand).

Session Management: Threading locks, auto-fold / auto-stand disconnect detection via heartbeats, turn timers, and multi-device session protection.

Persistent Data: SQLite database handling player accounts with 4-digit PINs, persistent chip balance tracking.

## Repository Structure

```text
digitaal-casino/
├── app.py                  # Flask server routing, state locks, session handling
├── poker_engine.py          # Poker game logic, pot management, hand evaluations via Treys
├── blackjack_engine.py      # Blackjack game logic, dealer AI, turn timers
├── database.py              # SQLite account creation, login, persistent chip tracking
├── pokertafel.db            # SQLite database file
├── static/                  # Audio assets (.mp3 / .wav) and generated QR codes
└── templates/               # Frontend templates
    ├── centraal.html        # Main TV display dashboard
    ├── speler.html          # Mobile controller interface
    └── login.html           # Player authentication page
```
**Requirements**

Install Python 3 dependencies:
```text 
pip install flask qrcode pillow treys werkzeug
```

**Launching the Server**

Run the Flask application:
```text
python app.py
```

**Usage**
Open the hosted local network address (e.g. http://<PI_IP_ADDRESS>:5000) on the TV or PC monitor to serve as the main display.

Players scan their assigned QR code on the central display using a smartphone to connect as Player 1 or Player 2.

Authenticate or create a 4-digit PIN account, pick a game mode on the controller interface, and start the round.

**Tech Stack**
Backend: Python 3, Flask, SQLite3, Treys (Poker Evaluator)

Frontend: HTML5, CSS3, JavaScript (Fetch API, Polling)

Target Hardware: Raspberry Pi 4 (or any computer on the local network)

-------------------------------------------------------------------------

