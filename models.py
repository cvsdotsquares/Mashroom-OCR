"""
Database models — User + Job.
db instance imported from extensions (Singleton) — never re-instantiated here.
"""

import json
import uuid
from datetime import datetime

from flask_login import UserMixin

from extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    jobs = db.relationship("Job", backref="user", lazy=True,
                           cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Job(db.Model):
    __tablename__ = "jobs"

    id          = db.Column(db.String(36), primary_key=True,
                            default=lambda: str(uuid.uuid4()))
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"),
                            nullable=False, index=True)
    filename    = db.Column(db.String(255), nullable=False)
    template_id = db.Column(db.String(50),  nullable=True)
    result_json = db.Column(db.Text,         nullable=True)
    created_at  = db.Column(db.DateTime,     default=datetime.utcnow, nullable=False)

    def get_data(self) -> dict:
        """Deserialise stored JSON back to dict. Returns empty dict on null."""
        return json.loads(self.result_json) if self.result_json else {}

    def get_template(self, template_by_id: dict) -> dict:
        """Resolve template dict for this job's template_id."""
        return template_by_id.get(
            self.template_id or "auto",
            template_by_id.get("auto", {})
        )

    def __repr__(self) -> str:
        return f"<Job {self.id} {self.filename}>"
