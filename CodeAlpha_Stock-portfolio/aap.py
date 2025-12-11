"""
app.py - Full-featured single-file Flask app
Features:
- Register / Login
- Wallet (add funds)
- Buy / Sell stocks
- Portfolio (avg cost, current price, P/L)
- Transaction history
- User profile
- Dark/Light toggle (localStorage)
- Animated profit graph (Chart.js)
- Candlestick chart (Chart.js using yfinance history)
- 3D Neon Glass UI + embedded SVG icon
- SQLite backend: users, wallet, portfolio, transactions
"""

from flask import (
    Flask, render_template_string, request, redirect, url_for, flash,
    send_file, jsonify
)
from flask_login import (
    LoginManager, UserMixin, login_user, login_required, logout_user, current_user
)
import sqlite3, os, io, time, math
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import yfinance as yf

APP_DB = "app_data.db"
SECRET = os.environ.get("FLASK_SECRET", "change_this_secret_for_dev")

app = Flask(__name__)
app.secret_key = SECRET

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ----- Database helpers -----
def get_db():
    conn = sqlite3.connect(APP_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    # users: id, username unique, password_hash
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS wallet (
        user_id INTEGER PRIMARY KEY,
        balance REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        qty INTEGER NOT NULL,
        avg_price REAL NOT NULL,
        UNIQUE(user_id, symbol),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL, -- buy, sell, deposit
        symbol TEXT,
        qty INTEGER,
        price REAL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()

init_db()

# ----- Auth -----
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"])
    return None

# ----- Utilities -----
FALLBACK_PRICES = {"AAPL": 180.0, "TSLA": 250.0, "GOOGL": 140.0, "AMZN": 155.0, "MSFT": 320.0, "META":220.0}

def get_live_price(symbol: str):
    """Return latest price (float). Try yfinance, fallback to dict or 0."""
    symbol = symbol.strip().upper()
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
        # fallback to fast_info if available
        fast = getattr(t, "fast_info", None)
        if fast and "last_price" in fast:
            return float(fast["last_price"])
    except Exception:
        pass
    # fallback dict
    return float(FALLBACK_PRICES.get(symbol, 0.0))

def record_transaction(user_id, typ, symbol, qty, price):
    ts = datetime.utcnow().isoformat()
    conn = get_db()
    conn.execute("INSERT INTO transactions (user_id,type,symbol,qty,price,timestamp) VALUES (?,?,?,?,?,?)",
                 (user_id, typ, symbol, qty, price, ts))
    conn.commit()
    conn.close()

def get_wallet_balance(user_id):
    conn = get_db()
    row = conn.execute("SELECT balance FROM wallet WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["balance"] if row else 0.0

def ensure_wallet(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO wallet (user_id,balance) VALUES (?,?)", (user_id, 0.0))
    conn.commit()
    conn.close()

# ----- Routes -----

# Home/Market watch
@app.route("/")
@login_required
def home():
    # show a set of popular symbols and user's portfolio summary
    popular = list(FALLBACK_PRICES.keys())
    # include user's symbols
    conn = get_db()
    user_symbols = [r["symbol"] for r in conn.execute("SELECT symbol FROM portfolio WHERE user_id = ?", (current_user.id,)).fetchall()]
    conn.close()
    for sym in user_symbols:
        if sym not in popular:
            popular.append(sym)
    # limit to 12
    popular = popular[:12]
    prices = [{ "symbol": s, "price": f"${get_live_price(s):,.2f}" } for s in popular]
    balance = get_wallet_balance(current_user.id)
    return render_template_string(TEMPLATE_BASE, body=render_template_string(HOME_BODY, prices=prices, balance=balance), title="Home")

# Register
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        if not username or not password:
            flash("username & password required","error")
            return redirect(url_for("register"))
        pw_hash = generate_password_hash(password)
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username,password_hash) VALUES (?,?)", (username,pw_hash))
            conn.commit()
            # create wallet row
            uid = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]
            conn.execute("INSERT INTO wallet (user_id,balance) VALUES (?,?)", (uid, 0.0))
            conn.commit()
            flash("Registered — please login","success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username taken","error")
        finally:
            conn.close()
    return render_template_string(TEMPLATE_BASE, body=render_template_string(REGISTER_BODY), title="Register")

# Login
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        conn = get_db()
        row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if row and check_password_hash(row["password_hash"], password):
            user = User(row["id"], username)
            login_user(user)
            ensure_wallet(user.id)
            flash("Welcome, " + username, "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials","error")
            return redirect(url_for("login"))
    return render_template_string(TEMPLATE_BASE, body=render_template_string(LOGIN_BODY), title="Login")

# Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out","info")
    return redirect(url_for("login"))

# Add funds
@app.route("/wallet/add", methods=["POST"])
@login_required
def wallet_add():
    try:
        amount = float(request.form.get("amount","0"))
        if amount <= 0:
            flash("Enter positive amount","error"); return redirect(url_for("home"))
    except:
        flash("Invalid amount","error"); return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE wallet SET balance = balance + ? WHERE user_id = ?", (amount, current_user.id))
    conn.commit()
    conn.close()
    record_transaction(current_user.id, "deposit", None, None, amount)
    flash(f"Added ₹{amount:.2f} to wallet","success")
    return redirect(url_for("home"))

# Buy stock
@app.route("/buy", methods=["POST"])
@login_required
def buy():
    symbol = request.form.get("symbol","").strip().upper()
    try:
        qty = int(request.form.get("qty","0"))
        if qty <= 0: raise ValueError()
    except:
        flash("Enter positive integer quantity","error"); return redirect(url_for("home"))
    source = request.form.get("source","auto")
    price = get_live_price(symbol) if source in ("auto","live") else float(FALLBACK_PRICES.get(symbol,0.0))
    cost = price * qty
    # check wallet
    balance = get_wallet_balance(current_user.id)
    if cost > balance + 1e-9:
        flash("Insufficient wallet balance — please add funds","error")
        return redirect(url_for("home"))
    conn = get_db()
    cur = conn.cursor()
    # deduct wallet
    cur.execute("UPDATE wallet SET balance = balance - ? WHERE user_id = ?", (cost, current_user.id))
    # upsert portfolio: update avg price
    row = cur.execute("SELECT qty, avg_price FROM portfolio WHERE user_id = ? AND symbol = ?", (current_user.id, symbol)).fetchone()
    if row:
        existing_qty = row["qty"]
        existing_avg = row["avg_price"]
        new_qty = existing_qty + qty
        new_avg = ((existing_qty * existing_avg) + (qty * price)) / new_qty
        cur.execute("UPDATE portfolio SET qty = ?, avg_price = ? WHERE user_id = ? AND symbol = ?",
                   (new_qty, new_avg, current_user.id, symbol))
    else:
        cur.execute("INSERT INTO portfolio (user_id,symbol,qty,avg_price) VALUES (?,?,?,?)",
                   (current_user.id, symbol, qty, price))
    # record transaction
    ts = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO transactions (user_id,type,symbol,qty,price,timestamp) VALUES (?,?,?,?,?,?)",
                (current_user.id, "buy", symbol, qty, price, ts))
    conn.commit()
    conn.close()
    flash(f"Bought {qty} × {symbol} @ {price:.2f} (cost {cost:.2f})","success")
    return redirect(url_for("portfolio"))

# Sell stock
@app.route("/sell", methods=["POST"])
@login_required
def sell():
    symbol = request.form.get("symbol","").strip().upper()
    try:
        qty = int(request.form.get("qty","0"))
        if qty <= 0: raise ValueError()
    except:
        flash("Enter positive integer quantity","error"); return redirect(url_for("portfolio"))
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT qty, avg_price FROM portfolio WHERE user_id = ? AND symbol = ?", (current_user.id, symbol)).fetchone()
    if not row:
        flash("You do not own this stock","error"); conn.close(); return redirect(url_for("portfolio"))
    if qty > row["qty"]:
        flash("You don't have that many shares","error"); conn.close(); return redirect(url_for("portfolio"))
    price = get_live_price(symbol)
    proceeds = price * qty
    # reduce qty or delete
    remaining = row["qty"] - qty
    if remaining == 0:
        cur.execute("DELETE FROM portfolio WHERE user_id = ? AND symbol = ?", (current_user.id, symbol))
    else:
        cur.execute("UPDATE portfolio SET qty = ? WHERE user_id = ? AND symbol = ?", (remaining, current_user.id, symbol))
    # add to wallet
    cur.execute("UPDATE wallet SET balance = balance + ? WHERE user_id = ?", (proceeds, current_user.id))
    # record transaction
    ts = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO transactions (user_id,type,symbol,qty,price,timestamp) VALUES (?,?,?,?,?,?)",
                (current_user.id, "sell", symbol, qty, price, ts))
    conn.commit()
    conn.close()
    flash(f"Sold {qty} × {symbol} @ {price:.2f} (proceeds {proceeds:.2f})","success")
    return redirect(url_for("portfolio"))

# Portfolio page
@app.route("/portfolio")
@login_required
def portfolio():
    conn = get_db()
    rows = conn.execute("SELECT symbol,qty,avg_price FROM portfolio WHERE user_id = ?", (current_user.id,)).fetchall()
    conn.close()
    items = []
    total_value = 0.0
    total_cost = 0.0
    for r in rows:
        symbol = r["symbol"]
        qty = r["qty"]
        avg = r["avg_price"]
        price = get_live_price(symbol)
        value = price * qty
        cost = avg * qty
        pl = value - cost
        items.append({
            "symbol": symbol, "qty": qty, "avg": f"{avg:.2f}",
            "price": f"{price:.2f}", "value": f"{value:.2f}", "pl": f"{pl:.2f}"
        })
        total_value += value
        total_cost += cost
    wallet = get_wallet_balance(current_user.id)
    return render_template_string(TEMPLATE_BASE, body=render_template_string(PORTFOLIO_BODY, items=items, wallet=wallet, total_value=f"{total_value:.2f}", total_cost=f"{total_cost:.2f}"), title="Portfolio")

# Transaction history
@app.route("/transactions")
@login_required
def transactions():
    conn = get_db()
    rows = conn.execute("SELECT type,symbol,qty,price,timestamp FROM transactions WHERE user_id = ? ORDER BY id DESC", (current_user.id,)).fetchall()
    conn.close()
    return render_template_string(TEMPLATE_BASE, body=render_template_string(TRANSACTIONS_BODY, rows=rows), title="Transactions")

# Profile
@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    conn = get_db()
    if request.method=="POST":
        newname = request.form.get("username","").strip()
        if newname:
            try:
                conn.execute("UPDATE users SET username = ? WHERE id = ?", (newname, current_user.id))
                conn.commit()
                flash("Username updated — please re-login","success")
                conn.close()
                logout_user()
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username already taken","error")
    row = conn.execute("SELECT u.username, w.balance FROM users u LEFT JOIN wallet w ON u.id = w.user_id WHERE u.id = ?", (current_user.id,)).fetchone()
    conn.close()
    return render_template_string(TEMPLATE_BASE, body=render_template_string(PROFILE_BODY, username=row["username"], balance=f"{row['balance']:.2f}"), title="Profile")

# API: profit data for Chart.js
@app.route("/api/profit-data")
@login_required
def api_profit():
    conn = get_db()
    rows = conn.execute("SELECT symbol, qty, avg_price FROM portfolio WHERE user_id = ?", (current_user.id,)).fetchall()
    conn.close()
    labels = []
    data = []
    for r in rows:
        symbol = r["symbol"]
        qty = r["qty"]
        avg = r["avg_price"]
        price = get_live_price(symbol)
        pl = (price - avg) * qty
        labels.append(symbol)
        data.append(round(pl,2))
    return jsonify({"labels": labels, "data": data})

# API: candlestick (ohlc) for Chart.js (returns arrays)
@app.route("/api/candles/<symbol>")
@login_required
def api_candles(symbol):
    symbol = symbol.strip().upper()
    period = request.args.get("period","1mo")  # 1mo, 3mo, 6mo, 1y
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period, interval="1d")
        if hist is None or hist.empty:
            return jsonify({"error":"no data"})
        result = []
        for idx,row in hist.iterrows():
            # format: [timestamp_ms, open, high, low, close]
            ts = int(time.mktime(idx.timetuple())) * 1000
            result.append([ts, round(row["Open"],2), round(row["High"],2), round(row["Low"],2), round(row["Close"],2)])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

# App icon (SVG) route
@app.route("/favicon.svg")
def favicon_svg():
    svg = """<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 24 24'><defs><linearGradient id='g' x1='0' x2='1'><stop offset='0' stop-color='#00eaff'/><stop offset='1' stop-color='#7effc7'/></linearGradient></defs><rect width='24' height='24' rx='5' fill='url(#g)'/><text x='50%' y='58%' text-anchor='middle' font-size='10' font-weight='700' fill='#021'>STK</text></svg>"""
    return app.response_class(svg, mimetype='image/svg+xml')

# ----- Templates -----
# Base template with CSS/JS (3D glass, dark/light toggle and Chart.js)
# ... (rest of the app.py code remains the same until TEMPLATE_BASE)

# ----- Templates -----
# Base template with CSS/JS (3D glass, dark/light toggle and Chart.js)
TEMPLATE_BASE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ title or "Neon Stock App" }}</title>
  <link rel="icon" href="{{ url_for('favicon_svg') }}" type="image/svg+xml">
  <style>
    :root{
      /* NEON COLORS */
      --neon-blue: #00eaff;
      --neon-green: #7effc7;
      --neon-pink: #ff00ff;
      --neon-yellow: #fff700;
      
      --bg1: #071028; /* Deep Blue/Black */
      --bg2: #04060a;
      --glass: rgba(255,255,255,0.08); /* Slightly more opaque glass */
      --accent: var(--neon-blue);
      --accent2: var(--neon-green);
      --muted: rgba(255,255,255,0.6);
      --text-color: #eaf6ff;
    }
    html,body{height:100%;margin:0;font-family:Poppins,system-ui; background: linear-gradient(135deg,var(--bg1),var(--bg2)); color:var(--text-color);}
    .container{max-width:1100px;margin:20px auto;padding:12px;}
    header { display:flex; align-items:center; gap:12px; justify-content:space-between; margin-bottom:12px;}
    .brand { display:flex; align-items:center; gap:10px;}
    .logo { width:42px; height:42px; border-radius:10px; box-shadow:0 0 10px var(--neon-blue), 0 0 20px var(--neon-green); }
    .title { font-weight:800; letter-spacing:0.6px; text-shadow:0 0 12px var(--accent), 0 0 20px var(--accent2); }
    .subtitle { color:var(--muted); font-size:0.9rem; }

    /* NAV buttons */
    .nav { display:flex; gap:8px; align-items:center; }
    /* Primary Neon Button */
    .btn { 
      background:linear-gradient(180deg,var(--accent),#0091b5); 
      border:none; 
      color:#012; 
      padding:8px 12px; 
      border-radius:10px; 
      cursor:pointer; 
      font-weight:700; 
      box-shadow:0 0 5px var(--accent), 0 0 15px rgba(0,234,255,0.5); /* Neon glow */
      transition: all 0.2s;
    }
    .btn:hover { 
      box-shadow:0 0 10px var(--accent), 0 0 20px rgba(0,234,255,0.8);
      transform: translateY(-2px);
    }
    .btn-sell {
      background: linear-gradient(180deg, var(--neon-pink), #a00);
      color: #fff;
      box-shadow: 0 0 5px var(--neon-pink), 0 0 15px rgba(255,0,255,0.5);
    }
    .btn-sell:hover {
      box-shadow: 0 0 10px var(--neon-pink), 0 0 20px rgba(255,0,255,0.8);
    }
    .btn-buy {
      background: linear-gradient(180deg, var(--neon-green), #0b0);
      color: #fff;
      box-shadow: 0 0 5px var(--neon-green), 0 0 15px rgba(126,255,199,0.5);
    }
    .btn-buy:hover {
      box-shadow: 0 0 10px var(--neon-green), 0 0 20px rgba(126,255,199,0.8);
    }
    .btn-ghost { 
      background:var(--glass); 
      border:2px solid rgba(255,255,255,0.06); 
      color:var(--text-color); 
      padding:8px 12px; 
      border-radius:10px; 
      cursor:pointer; 
      transition: all 0.2s;
    }
    .btn-ghost:hover {
      border-color: var(--accent);
      box-shadow: 0 0 8px rgba(0,234,255,0.5);
    }

    /* Glass Effect Card */
    .glass { 
      background:var(--glass); 
      border-radius:14px; 
      padding:16px; 
      border:1px solid rgba(255,255,255,0.15); /* Stronger border */
      box-shadow: 0 0 20px rgba(0,234,255,0.1), 6px 10px 30px rgba(0,0,0,0.6); /* Subtle neon border + shadow */
      transition: transform .25s, box-shadow .25s; 
      backdrop-filter: blur(10px); 
    }
    .glass:hover{ transform: translateY(-4px); box-shadow:0 0 30px rgba(0,234,255,0.2), 10px 18px 40px rgba(0,0,0,0.7); }
    
    input,select { 
      padding:10px;
      border-radius:10px;
      border:none;
      background:rgba(255,255,255,0.08); /* Darker input background */
      color:var(--text-color); 
      box-shadow: inset 0 0 4px rgba(0,0,0,0.5);
    }
    .row { display:flex; gap:12px; flex-wrap:wrap; }

    /* grid for cards */
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:18px; margin-top:16px; } /* Slightly larger cards */

    table { width:100%; border-collapse:collapse; color:var(--text-color); }
    th,td { padding:12px 10px; border-bottom:1px solid rgba(255,255,255,0.06); text-align:left; }
    th { color:var(--neon-blue); font-size:0.9rem; text-transform:uppercase; }

    footer { text-align:center; margin-top:24px; color:rgba(255,255,255,0.5); font-size:0.9rem; }

    /* Flash Messages */
    .flash { padding:10px; margin-bottom:10px; border-radius:8px; font-weight:700; }
    .flash.success { background: rgba(126,255,199,0.2); color: var(--neon-green); border: 1px solid var(--neon-green); }
    .flash.error { background: rgba(255,0,0,0.2); color: var(--neon-pink); border: 1px solid var(--neon-pink); }
    .flash.info { background: rgba(0,234,255,0.2); color: var(--neon-blue); border: 1px solid var(--neon-blue); }

    /* Dark/Light support toggled by body.light */
    body.light { 
      background: linear-gradient(135deg,#f6fbff,#e8f7ff); 
      color:#022; 
      --text-color: #022;
      --glass: rgba(255,255,255,0.9);
      --muted: rgba(0,0,0,0.6);
    }
    body.light .glass { 
      background: var(--glass); 
      color:var(--text-color); 
      border:1px solid rgba(0,0,0,0.06); 
      box-shadow: 6px 10px 30px rgba(0,0,0,0.2);
    }
    body.light .glass:hover { transform: translateY(-4px); box-shadow: 10px 18px 40px rgba(0,0,0,0.3); }
    body.light input, body.light select { 
      background:#fff; 
      color:var(--text-color);
      box-shadow: inset 0 0 4px rgba(0,0,0,0.1);
    }
    body.light .btn { color:#fff; box-shadow: 0 4px 0 rgba(0,0,0,0.35); }
    body.light .btn-ghost { border-color: rgba(0,0,0,0.1); color: #022; }
    body.light .flash.success { background: #e6ffe6; color: #080; border: 1px solid #080; }
    body.light .flash.error { background: #ffe6e6; color: #800; border: 1px solid #800; }


    /* small */
    .muted { color:var(--muted); font-size:0.9rem; }

    /* responsive */
    @media (max-width:600px){
      header { flex-direction:column; align-items:flex-start; gap:8px; }
      .nav { flex-wrap: wrap; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  <div class="container">
    <header>
      <div class="brand">
        <img src="{{ url_for('favicon_svg') }}" class="logo">
        <div>
          <div class="title">Neon Stocks</div>
          <div class="subtitle">Portfolio & Market — 3D Neon UI</div>
        </div>
      </div>

      <div class="nav">
        {% if current_user.is_authenticated %}
        <div class="muted" style="margin-right:8px;">Hi, {{ current_user.username }}</div>
        <a class="btn-ghost" href="{{ url_for('home') }}">Home</a>
        <a class="btn-ghost" href="{{ url_for('portfolio') }}">Portfolio</a>
        <a class="btn-ghost" href="{{ url_for('transactions') }}">History</a>
        <a class="btn-ghost" href="{{ url_for('profile') }}">Profile</a>
        <button class="btn" id="toggleTheme">Theme</button>
        <a class="btn-ghost" href="{{ url_for('logout') }}">Logout</a>
        {% else %}
        <a class="btn-ghost" href="{{ url_for('login') }}">Login</a>
        <a class="btn-ghost" href="{{ url_for('register') }}">Register</a>
        {% endif %}
      </div>
    </header>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div style="margin-bottom:15px;">
        {% for category, message in messages %}
          <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}
        </div>
      {% endif %}
    {% endwith %}

    <main>
      {{ body|safe }}
    </main>

    <footer>
      <small>Built with Flask • yfinance • Chart.js</small>
    </footer>
  </div>

<script>
  // Theme toggle persisted in localStorage
  (function(){
    const key = "neon_theme";
    const saved = localStorage.getItem(key) || "dark";
    document.body.classList.toggle("light", saved === "light");
    document.getElementById("toggleTheme").addEventListener("click", ()=>{
      const mode = document.body.classList.toggle("light") ? "light" : "dark";
      localStorage.setItem(key, mode);
    });
  })();
</script>
</body>
</html>
"""

# ----- Modified HOME_BODY with separate Buy/Sell forms -----
HOME_BODY = """
<div class="glass">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div><strong>Wallet balance:</strong> <span style="color:var(--neon-green);">₹{{ balance }}</span></div>
    <form method="post" action="{{ url_for('wallet_add') }}" style="display:flex; gap:8px; align-items:center;">
      <input name="amount" placeholder="Add funds" style="width:120px;" required />
      <button class="btn btn-buy">Add Funds</button>
    </form>
  </div>
</div>

<div class="grid">
  {% for p in prices %}
    <div class="glass" style="display:flex; flex-direction:column;">
      <div style="flex-grow:1;">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-weight:800;font-size:1.2rem; color:var(--neon-blue);">{{ p.symbol }}</div>
            <div class="muted">Live Market Price</div>
          </div>
          <div style="text-align:right;">
            <div style="font-weight:800;font-size:1.2rem; color:var(--neon-green);">{{ p.price }}</div>
          </div>
        </div>
      </div>

      <div style="margin-top:15px; border-top:1px dashed rgba(255,255,255,0.1); padding-top:15px;">
        <form method="post" action="{{ url_for('buy') }}" style="margin-bottom:10px;">
          <input type="hidden" name="symbol" value="{{ p.symbol }}">
          <div style="display:flex; gap:8px; align-items:center;">
            <input name="qty" type="number" min="1" placeholder="Buy Qty" style="flex:1;" required />
            <select name="source" style="width:100px;">
              <option value="auto">Auto</option>
              <option value="live">Live</option>
              <option value="hardcoded">Fixed</option>
            </select>
            <button class="btn btn-buy" type="submit">BUY</button>
          </div>
        </form>

        <form method="post" action="{{ url_for('sell') }}" onsubmit="return confirm('Sell {{ p.symbol }}?');">
          <input type="hidden" name="symbol" value="{{ p.symbol }}">
          <div style="display:flex; gap:8px; align-items:center;">
            <input name="qty" type="number" min="1" placeholder="Sell Qty" style="flex:1;" required />
            <div style="width:100px;">&nbsp;</div> <button class="btn btn-sell" type="submit">SELL</button>
          </div>
        </form>
      </div>

    </div>
  {% endfor %}
</div>

<div style="text-align:center; margin-top:20px;">
    <a class="btn-ghost" href="{{ url_for('portfolio') }}">Go to My Portfolio &rarr;</a>
</div>
"""

# ... (rest of the body templates remain the same)

PORTFOLIO_BODY = """
<div class="glass">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div><strong>Total Value:</strong> ₹{{ total_value }}</div>
    <div><strong>Cost Basis:</strong> ₹{{ total_cost }}</div>
  </div>
  <table style="margin-top:12px;">
    <thead><tr><th>Symbol</th><th>Qty</th><th>Avg Cost</th><th>Current</th><th>Value</th><th>P/L</th><th>Actions</th></tr></thead>
    <tbody>
      {% for it in items %}
        <tr>
          <td>{{ it.symbol }}</td>
          <td>{{ it.qty }}</td>
          <td>₹{{ it.avg }}</td>
          <td>₹{{ it.price }}</td>
          <td>₹{{ it.value }}</td>
          <td {% if (it.pl | float) >= 0 %} style="color:lime;" {% else %} style="color:#ff7b7b;" {% endif %}>₹{{ it.pl }}</td>
          <td>
            <form method="post" action="{{ url_for('sell') }}" style="display:inline-block;">
              <input type="hidden" name="symbol" value="{{ it.symbol }}">
              <input name="qty" placeholder="qty" style="width:70px;padding:6px;border-radius:6px;border:none;">
              <button class="btn" type="submit">Sell</button>
            </form>
            <a class="btn-ghost" href="{{ url_for('transactions') }}">History</a>
            <a class="btn-ghost" href="#" onclick="showCandles('{{ it.symbol }}')">Candles</a>
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>

  <div style="margin-top:18px" class="glass">
    <h4>Profit / Loss (per holding)</h4>
    <canvas id="plChart" width="600" height="200"></canvas>
  </div>

  <div id="candlesModal" class="glass" style="margin-top:14px; display:none;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h5 id="candleTitle">Candlestick</h5>
      <button onclick="document.getElementById('candlesModal').style.display='none'">Close</button>
    </div>
    <div style="display:flex;gap:10px;align-items:center;margin-top:8px;">
      <label>Symbol:</label><input id="candleSymbol" readonly />
      <label>Period:</label>
      <select id="candlePeriod">
        <option value="1mo">1 month</option>
        <option value="3mo">3 months</option>
        <option value="6mo">6 months</option>
        <option value="1y">1 year</option>
      </select>
      <button class="btn" onclick="loadCandles()">Load</button>
    </div>
    <canvas id="candlesChart" width="800" height="320" style="margin-top:10px;"></canvas>
  </div>

</div>

<script>
  // profit/loss chart
  async function loadPL(){
    const res = await fetch("/api/profit-data");
    const j = await res.json();
    const ctx = document.getElementById('plChart').getContext('2d');
    new Chart(ctx, {
      type: 'bar',
      data: { labels: j.labels, datasets: [{ label: 'P/L (₹)', data: j.data, backgroundColor: j.data.map(v=> v>=0 ? 'rgba(126,255,199,0.8)':'rgba(255,120,120,0.8)') }] },
      options: { responsive:true, plugins:{ legend:{display:false} } }
    });
  }
  loadPL();

  // Candles modal handlers using Chart.js financial (we'll emulate OHLC with bar & line)
  async function showCandles(sym){
    document.getElementById('candlesModal').style.display='block';
    document.getElementById('candleSymbol').value = sym;
    document.getElementById('candleTitle').innerText = 'Candles — ' + sym;
    await loadCandles();
  }
  let candleChart = null;
  async function loadCandles(){
    const sym = document.getElementById('candleSymbol').value;
    const period = document.getElementById('candlePeriod').value;
    if(!sym) return;
    const res = await fetch('/api/candles/' + sym + '?period=' + period);
    const data = await res.json();
    if(data.error){ alert(data.error); return; }
    // data: [[ts, open, high, low, close], ...]
    const labels = data.map(d => new Date(d[0]));
    const closes = data.map(d => d[4]);
    const highs = data.map(d => d[2]);
    const lows = data.map(d => d[3]);
    const opens = data.map(d => d[1]);

    // simple candlestick representation: use dataset for high-low as "bar" + close line
    const ctx = document.getElementById('candlesChart').getContext('2d');
    if(candleChart){ candleChart.destroy(); }
    candleChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label:'Range (low-high)', data: highs.map((h,i)=> h - lows[i]), backgroundColor: 'rgba(255,255,255,0.08)', barPercentage: 0.6 },
          { label:'Close', type:'line', data: closes, borderColor:'rgba(0,234,255,0.9)', tension:0.2, pointRadius:1, fill:false }
        ]
      },
      options:{
        scales:{ x:{ type:'time', time:{unit:'day'} } },
        plugins:{ legend:{display:true} },
        responsive:true
      }
    });
  }
</script>
"""

TRANSACTIONS_BODY = """
<div class="glass">
  <h3>Transaction History</h3>
  <table style="margin-top:12px;">
    <thead><tr><th>Type</th><th>Symbol</th><th>Qty</th><th>Price</th><th>Time (UTC)</th></tr></thead>
    <tbody>
      {% for r in rows %}
        <tr>
          <td>{{ r['type'] }}</td>
          <td>{{ r['symbol'] or '-' }}</td>
          <td>{{ r['qty'] or '-' }}</td>
          <td>{{ r['price'] or '-' }}</td>
          <td>{{ r['timestamp'] }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
"""

PROFILE_BODY = """
<div class="glass" style="max-width:720px;">
  <h3>Profile</h3>
  <p><strong>Username:</strong> {{ username }}</p>
  <p><strong>Wallet balance:</strong> ₹{{ balance }}</p>

  <h4>Change username</h4>
  <form method="post">
    <input name="username" placeholder="New username" />
    <button class="btn" type="submit">Update</button>
  </form>

  <hr/>
  <h4>App Info</h4>
  <p class="muted">Neon Stocks — demo app. For real trading use broker APIs.</p>
</div>
"""

LOGIN_BODY = """
<div class="glass" style="max-width:480px;margin:auto;">
  <h3>Login</h3>
  <form method="post">
    <div style="margin-top:8px"><input name="username" placeholder="Username" /></div>
    <div style="margin-top:8px"><input name="password" type="password" placeholder="Password" /></div>
    <div style="margin-top:12px; display:flex; gap:8px;">
      <button class="btn">Login</button>
      <a class="btn-ghost" href="{{ url_for('register') }}">Register</a>
    </div>
  </form>
</div>
"""

REGISTER_BODY = """
<div class="glass" style="max-width:480px;margin:auto;">
  <h3>Create account</h3>
  <form method="post">
    <div style="margin-top:8px"><input name="username" placeholder="Username" /></div>
    <div style="margin-top:8px"><input name="password" type="password" placeholder="Password" /></div>
    <div style="margin-top:12px; display:flex; gap:8px;">
      <button class="btn">Register</button>
      <a class="btn-ghost" href="{{ url_for('login') }}">Login</a>
    </div>
  </form>
</div>
"""

# ----- Run -----
if __name__ == "__main__":
    # ensure DB exists
    init_db()
    app.run(debug=True)

















