import os

from cs50 import SQL
from flask import Flask, redirect, render_template, request

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///birthdays.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        # Get form data
        name = request.form.get("name")
        month = request.form.get("month")
        day = request.form.get("day")

        # Validate name
        if not name:
            return redirect("/")

        # Validate month
        if not month:
            return redirect("/")

        try:
            month = int(month)
        except ValueError:
            return redirect("/")

        if month < 1 or month > 12:
            return redirect("/")

        # Validate day
        if not day:
            return redirect("/")

        try:
            day = int(day)
        except ValueError:
            return redirect("/")

        if day < 1 or day > 31:
            return redirect("/")

        # Insert birthday into database
        db.execute(
            "INSERT INTO birthdays (name, month, day) VALUES (?, ?, ?)",
            name,
            month,
            day
        )

        return redirect("/")

    else:

        # Get all birthdays
        birthdays = db.execute("SELECT * FROM birthdays")

        # Display birthdays
        return render_template("index.html", birthdays=birthdays)
