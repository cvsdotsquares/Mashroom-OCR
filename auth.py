"""
Authentication routes — login, logout.
Public registration is disabled; accounts created by admin only.
bcrypt imported from extensions (Singleton) — never re-instantiated here.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import bcrypt, db
from models import User

logger  = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("login.html")


@auth_bp.post("/login")
def login():
    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        logger.warning("Failed login attempt for email: %s", email)
        return render_template("login.html", error="Invalid email or password."), 401

    login_user(user, remember=True)
    logger.info("User logged in: %s", email)
    return redirect(request.args.get("next") or url_for("main.index"))


@auth_bp.get("/register")
@auth_bp.post("/register")
def register():
    """Public registration is disabled. Accounts are created by admins only."""
    return render_template(
        "login.html",
        error="Registration is closed. Contact your administrator."
    ), 403


@auth_bp.get("/logout")
@login_required
def logout():
    logger.info("User logged out: %s", current_user.email)
    logout_user()
    return redirect(url_for("auth.login_page"))
