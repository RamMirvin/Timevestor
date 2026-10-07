from functools import wraps
from flask import Flask, flash, session, request, render_template, redirect
from datetime import date, timedelta

def apology(message, code=400):
    return render_template(
        "apology.html",
        top=code,
        bottom=message
    ), code

def login_required(f):
    """
    Require user to be logged in before accessing a route.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash("Please log in first.", "warning")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def format_hours(hours):
    """
    Format hours to one decimal place.
    """
    return f"{hours:.1f} hrs"


def format_percent(value):
    """
    Format percentage.
    """
    return f"{value:.1f}%"


def calculate_progress(current, target):
    """
    Return progress percentage.
    """
    if target <= 0:
        return 0
    return round((current / target) * 100, 1)


def calculate_investable_time(sleep, college, free_time):
    """
    Calculate remaining investable hours in a day.
    """
    investable = 24 - (sleep + college + free_time)
    return max(0, investable)


def calculate_unused_time(investable, invested):
    """
    Calculate unused investable time.
    """
    return max(0, investable - invested)


def calculate_roi(invested_hours, milestones):
    """
    Simple ROI score based on completed milestones.
    """
    if invested_hours == 0:
        return 0
    return round(milestones / invested_hours * 100, 2)


def today():
    """
    Return today's date.
    """
    return date.today()


def week_start():
    """
    Return Monday of the current week.
    """
    return date.today() - timedelta(days=date.today().weekday())
