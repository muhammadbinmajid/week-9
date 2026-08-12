import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks."""

    user_id = session["user_id"]

    # Get user's cash
    user = db.execute(
        "SELECT cash FROM users WHERE id = ?",
        user_id
    )[0]

    cash = user["cash"]

    # Get all stocks currently owned
    stocks = db.execute(
        """
        SELECT symbol, SUM(shares) AS shares
        FROM transactions
        WHERE user_id = ?
        GROUP BY symbol
        HAVING SUM(shares) > 0
        """,
        user_id
    )

    portfolio = []
    total = cash

    for stock in stocks:
        quote = lookup(stock["symbol"])

        if quote is None:
            continue

        current_price = quote["price"]
        shares = stock["shares"]
        total_value = shares * current_price

        portfolio.append({
            "symbol": stock["symbol"],
            "name": quote["name"],
            "shares": shares,
            "price": current_price,
            "total": total_value
        })

        total += total_value

    return render_template(
        "index.html",
        stocks=portfolio,
        cash=cash,
        total=total
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    if request.method == "POST":

        symbol = request.form.get("symbol")

        if not symbol:
            return apology("must provide symbol", 400)

        symbol = symbol.upper()

        quote = lookup(symbol)

        if quote is None:
            return apology("invalid symbol", 400)

        shares = request.form.get("shares")

        if not shares:
            return apology("must provide shares", 400)

        try:
            shares = int(shares)
        except ValueError:
            return apology("shares must be a whole number", 400)

        if shares <= 0:
            return apology("shares must be a positive number", 400)

        price = quote["price"]
        cost = shares * price

        user_id = session["user_id"]

        user = db.execute(
            "SELECT cash FROM users WHERE id = ?",
            user_id
        )[0]

        if cost > user["cash"]:
            return apology("can't afford that purchase", 400)

        # Deduct cash
        db.execute(
            "UPDATE users SET cash = cash - ? WHERE id = ?",
            cost,
            user_id
        )

        # Record transaction
        db.execute(
            """
            INSERT INTO transactions
            (user_id, symbol, shares, price)
            VALUES (?, ?, ?, ?)
            """,
            user_id,
            symbol,
            shares,
            price
        )

        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    transactions = db.execute(
        """
        SELECT symbol, shares, price, transacted
        FROM transactions
        WHERE user_id = ?
        ORDER BY transacted DESC
        """,
        session["user_id"]
    )

    return render_template(
        "history.html",
        transactions=transactions
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?",
            request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"],
            request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out."""

    session.clear()

    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # GET: show the quote form
    if request.method == "GET":
        return render_template("quote.html")

    # POST: process the submitted symbol
    symbol = request.form.get("symbol")

    if not symbol:
        return apology("must provide symbol", 400)

    symbol = symbol.upper()

    quote = lookup(symbol)

    if quote is None:
        return apology("invalid symbol", 400)

    # IMPORTANT:
    # Successful quote lookup goes to quoted.html,
    # NOT quote.html.
    return render_template("quoted.html", quote=quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate username
        if not username:
            return apology("must provide username", 400)

        # Validate password
        if not password:
            return apology("must provide password", 400)

        # Validate confirmation
        if not confirmation:
            return apology("must confirm password", 400)

        # Check passwords
        if password != confirmation:
            return apology("passwords do not match", 400)

        # Create user
        try:
            user_id = db.execute(
                """
                INSERT INTO users (username, hash)
                VALUES (?, ?)
                """,
                username,
                generate_password_hash(password)
            )
        except ValueError:
            return apology("username already exists", 400)

        # Log user in
        session["user_id"] = user_id

        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    user_id = session["user_id"]

    if request.method == "POST":

        symbol = request.form.get("symbol")

        if not symbol:
            return apology("must provide symbol", 400)

        symbol = symbol.upper()

        shares = request.form.get("shares")

        if not shares:
            return apology("must provide shares", 400)

        try:
            shares = int(shares)
        except ValueError:
            return apology("shares must be a whole number", 400)

        if shares <= 0:
            return apology("shares must be a positive number", 400)

        # Check how many shares the user owns
        rows = db.execute(
            """
            SELECT SUM(shares) AS shares
            FROM transactions
            WHERE user_id = ? AND symbol = ?
            """,
            user_id,
            symbol
        )

        owned = rows[0]["shares"]

        if owned is None or shares > owned:
            return apology("not enough shares", 400)

        # Get current price
        quote = lookup(symbol)

        if quote is None:
            return apology("invalid symbol", 400)

        price = quote["price"]
        revenue = shares * price

        # Add money to user's cash
        db.execute(
            "UPDATE users SET cash = cash + ? WHERE id = ?",
            revenue,
            user_id
        )

        # Record sale as negative shares
        db.execute(
            """
            INSERT INTO transactions
            (user_id, symbol, shares, price)
            VALUES (?, ?, ?, ?)
            """,
            user_id,
            symbol,
            -shares,
            price
        )

        return redirect("/")

    stocks = db.execute(
        """
        SELECT symbol
        FROM transactions
        WHERE user_id = ?
        GROUP BY symbol
        HAVING SUM(shares) > 0
        """,
        user_id
    )

    return render_template("sell.html", stocks=stocks)
