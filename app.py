import os
import math
from datetime import datetime

from cs50 import SQL
from flask import Flask, session, request, render_template, redirect
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import (
    apology,
    login_required,
    format_hours,
    format_percent,
    calculate_progress,
    calculate_investable_time,
    calculate_unused_time,
    calculate_roi,
    today,
    week_start
)


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

db = SQL("sqlite:///timevestor.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached."""

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"

    return response


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
@login_required
def index():

    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        session["user_id"]
    )[0]

    investments = db.execute(
        """
        SELECT category, hours, notes
        FROM investments
        WHERE user_id = ?
        AND date = DATE('now')
        """,
        session["user_id"]
    )

    return render_template(
        "index.html",
        user=user,
        investments=investments
    )


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    session.clear()

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return apology("Enter username", 400)

        if not password:
            return apology("Enter password", 400)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?",
            username
        )

        if len(rows) != 1:
            return apology("User does not exist", 400)

        if not check_password_hash(rows[0]["hash"], password):
            return apology("Invalid password", 400)

        session["user_id"] = rows[0]["id"]

        return redirect("/")

    return render_template("login.html")

# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():
    """Log user out."""

    session.clear()

    return redirect("/")


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Enter username", 400)

        if not password:
            return apology("Enter password", 400)

        if not confirmation:
            return apology("Enter confirmation", 400)

        if password != confirmation:
            return apology("Passwords do not match", 400)

        user = db.execute(
            "SELECT username FROM users WHERE username = ?",
            username
        )

        if len(user) > 0:
            return apology(
                "Username already exists",
                400
            )

        hashpassword = generate_password_hash(password)

        db.execute(
            """
            INSERT INTO users (username, hash)
            VALUES (?, ?)
            """,
            username,
            hashpassword
        )

        return redirect("/login")

    return render_template("register.html")


# --------------------------------------------------
# GOALS
# --------------------------------------------------

@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():

    rows = db.execute(
        """
        SELECT
            g.category,
            g.target_hours,
            COALESCE(SUM(i.hours), 0) AS invested_hours
        FROM goals AS g

        LEFT JOIN investments AS i
            ON g.user_id = i.user_id
            AND g.category = i.category

        WHERE g.user_id = ?

        GROUP BY g.id
        """,
        session["user_id"]
    )

    for row in rows:

        if row["target_hours"] > 0:
            row["progress"] = round(
                row["invested_hours"]
                * 100
                / row["target_hours"],
                1
            )
        else:
            row["progress"] = 0

        if row["progress"] > 100:
            row["progress"] = 100

    return render_template(
        "goals.html",
        rows=rows
    )


@app.route("/goals/add", methods=["GET", "POST"])
@login_required
def goals_add():

    if request.method == "POST":

        category = request.form.get("category")
        target = request.form.get("target")

        if not category:
            return apology("Enter category", 400)

        if not target:
            return apology("Enter target", 400)

        try:
            target = float(target)
        except (ValueError, TypeError):
            return apology(
                "Target must be a number",
                400
            )

        if not math.isfinite(target):
            return apology(
                "Invalid target",
                400
            )

        if target <= 0:
            return apology(
                "Target must be greater than 0",
                400
            )

        existing = db.execute(
            """
            SELECT id
            FROM goals
            WHERE user_id = ?
            AND category = ?
            """,
            session["user_id"],
            category
        )

        if len(existing) > 0:
            return apology(
                "Goal already exists",
                400
            )

        db.execute(
            """
            INSERT INTO goals
            (user_id, category, target_hours)
            VALUES (?, ?, ?)
            """,
            session["user_id"],
            category,
            target
        )

        return redirect("/goals")

    return render_template("goals_add.html")


# --------------------------------------------------
# TIMELINE
# --------------------------------------------------

@app.route("/timeline", methods=["GET", "POST"])
@login_required
def timeline():

    rows = db.execute(
        """
        SELECT *
        FROM timeline
        WHERE user_id = ?
        ORDER BY date
        """,
        session["user_id"]
    )

    return render_template(
        "timeline.html",
        rows=rows
    )


@app.route("/timeline/add", methods=["GET", "POST"])
@login_required
def timeline_add():

    if request.method == "POST":

        title = request.form.get("title")
        description = request.form.get("description")
        date = request.form.get("date")

        if not title:
            return apology("Enter title", 400)

        if not description:
            return apology("Enter description", 400)

        if not date:
            return apology("Enter date", 400)

        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return apology(
                "Invalid date",
                400
            )

        db.execute(
            """
            INSERT INTO timeline
            (user_id, title, description, date)
            VALUES (?, ?, ?, ?)
            """,
            session["user_id"],
            title,
            description,
            date
        )

        return redirect("/timeline")

    return render_template(
        "timeline_add.html"
    )


# --------------------------------------------------
# INVEST
# --------------------------------------------------

@app.route("/invest", methods=["GET", "POST"])
@login_required
def invest():

    if request.method == "POST":

        category = request.form.get("category")
        hours = request.form.get("hours")
        notes = request.form.get("notes")

        if not category:
            return apology("Enter category", 400)

        if not hours:
            return apology("Enter hours", 400)

        try:
            hours = float(hours)
        except (ValueError, TypeError):
            return apology(
                "Hours must be a number",
                400
            )

        if not math.isfinite(hours):
            return apology(
                "Invalid hours",
                400
            )

        if hours <= 0:
            return apology(
                "Hours must be greater than 0",
                400
            )

        # Make sure this category belongs to the user
        valid = db.execute(
            """
            SELECT id
            FROM goals
            WHERE user_id = ?
            AND category = ?
            """,
            session["user_id"],
            category
        )

        if len(valid) != 1:
            return apology(
                "Invalid category",
                400
            )

        # Get user's available time
        user = db.execute(
            """
            SELECT sleep, freetime
            FROM users
            WHERE id = ?
            """,
            session["user_id"]
        )[0]

        investable = (
            24
            - user["sleep"]
            - user["freetime"]
        )

        # Existing investments today
        invested_today = db.execute(
            """
            SELECT COALESCE(SUM(hours), 0) AS total
            FROM investments
            WHERE user_id = ?
            AND date = DATE('now')
            """,
            session["user_id"]
        )[0]["total"]

        # New total after this investment
        total_after = invested_today + hours

        if total_after > investable:
            return apology(
                "Not enough investable time",
                400
            )

        db.execute(
            """
            INSERT INTO investments
            (user_id, category, hours, date, notes)
            VALUES (?, ?, ?, DATE('now'), ?)
            """,
            session["user_id"],
            category,
            hours,
            notes
        )

        return redirect("/")

    category = db.execute(
        """
        SELECT category
        FROM goals
        WHERE user_id = ?
        ORDER BY category
        """,
        session["user_id"]
    )

    return render_template(
        "invest.html",
        category=category
    )


# --------------------------------------------------
# CHECKLIST
# --------------------------------------------------

@app.route("/checklist", methods=["GET", "POST"])
@login_required
def checklist():

    if request.method == "POST":

        task_id = request.form.get("id")

        if not task_id:
            return apology(
                "Invalid task",
                400
            )

        try:
            task_id = int(task_id)
        except (ValueError, TypeError):
            return apology(
                "Invalid task",
                400
            )

        db.execute(
            """
            UPDATE checklist
            SET completed = 1 - completed
            WHERE id = ?
            AND user_id = ?
            """,
            task_id,
            session["user_id"]
        )

        return redirect("/checklist")

    rows = db.execute(
        """
        SELECT *
        FROM checklist
        WHERE user_id = ?
        AND date = DATE('now')
        ORDER BY id
        """,
        session["user_id"]
    )

    return render_template(
        "checklist.html",
        rows=rows
    )


@app.route("/checklist/add", methods=["GET", "POST"])
@login_required
def check_add():

    if request.method == "POST":

        task = request.form.get("task")

        if not task:
            return apology(
                "Enter task",
                400
            )

        db.execute(
            """
            INSERT INTO checklist
            (user_id, task, completed, date)
            VALUES (?, ?, 0, DATE('now'))
            """,
            session["user_id"],
            task
        )

        return redirect("/checklist")

    return render_template(
        "check_add.html"
    )


# --------------------------------------------------
# ANALYTICS
# --------------------------------------------------

@app.route("/analytics")
@login_required
def analytics():

    user_id = session["user_id"]

    total = db.execute(
        """
        SELECT COALESCE(SUM(hours), 0) AS total
        FROM investments
        WHERE user_id = ?
        """,
        user_id
    )[0]["total"]

    completed_tasks = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM checklist
        WHERE user_id = ?
        AND completed = 1
        """,
        user_id
    )[0]["count"]

    completed_goals = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM goals
        WHERE user_id = ?

        AND target_hours <= (
            SELECT COALESCE(SUM(i.hours), 0)
            FROM investments AS i
            WHERE i.user_id = goals.user_id
            AND i.category = goals.category
        )
        """,
        user_id
    )[0]["count"]

    categories = db.execute(
        """
        SELECT
            category,
            SUM(hours) AS hours
        FROM investments
        WHERE user_id = ?
        GROUP BY category
        ORDER BY hours DESC
        """,
        user_id
    )

    for row in categories:

        if total > 0:
            row["percentage"] = round(
                row["hours"] * 100 / total,
                1
            )
        else:
            row["percentage"] = 0

    return render_template(
        "analytics.html",
        total_hours=total,
        completed_tasks=completed_tasks,
        completed_goals=completed_goals,
        categories=categories
    )
