"""
Admin routes — user management (create, list, delete).
All routes require is_admin=True via admin_required decorator.
"""

import logging

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db, bcrypt
from models import User
from utils import admin_required

logger   = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.asc()).all()
    return render_template("admin_users.html", users=all_users)


@admin_bp.post("/users/create")
@admin_required
def create_user():
    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    is_admin = request.form.get("is_admin") == "on"

    all_users = User.query.order_by(User.created_at.asc()).all()

    if not email or not password:
        return render_template("admin_users.html", users=all_users,
                               error="Email and password are required."), 400
    if len(password) < 8:
        return render_template("admin_users.html", users=all_users,
                               error="Password must be at least 8 characters."), 400
    if User.query.filter_by(email=email).first():
        return render_template("admin_users.html", users=all_users,
                               error=f"User {email} already exists."), 409

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user   = User(email=email, password_hash=hashed, is_admin=is_admin)
    db.session.add(user)
    db.session.commit()
    logger.info("Admin %s created user: %s", current_user.email, email)
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/delete")
@admin_required
def delete_user(user_id: int):
    if user_id == current_user.id:
        all_users = User.query.order_by(User.created_at.asc()).all()
        return render_template("admin_users.html", users=all_users,
                               error="You cannot delete your own account."), 400

    user = db.get_or_404(User, user_id)
    logger.info("Admin %s deleted user: %s", current_user.email, user.email)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for("admin.users"))
