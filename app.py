"""
Mashroom OCR — Application Factory
====================================
create_app() wires together config, extensions, blueprints, and CLI.
All route logic lives in routes/. All models in models.py.
"""

import logging
import os

import click
from dotenv import load_dotenv
from flask import Flask
from flask_login import current_user

load_dotenv()

from config import config_map, ProductionConfig
from extensions import db, bcrypt, login_manager, migrate
from models import User
from utils import load_ocr_templates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------

def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure a Flask application instance.

    Parameters
    ----------
    config_name : str | None
        One of 'development', 'production', 'testing'.
        Falls back to FLASK_ENV env var, then 'development'.
    """
    app = Flask(__name__)

    # ── Config ──────────────────────────────────────────────────────────────
    env = config_name or os.environ.get("FLASK_ENV", "development")
    cfg = config_map.get(env, config_map["development"])
    app.config.from_object(cfg)

    if env == "production":
        ProductionConfig.validate()   # assert required env vars are set

    # ── Extensions (Singleton pattern — init_app binds each to this app) ────
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view    = "auth.login_page"
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ── OCR Templates (loaded once, stored in app config) ───────────────────
    templates, template_by_id = load_ocr_templates(
        app.config["TEMPLATES_JSON_PATH"]
    )
    app.config["OCR_TEMPLATES"]      = templates
    app.config["OCR_TEMPLATE_BY_ID"] = template_by_id

    # ── Blueprints ───────────────────────────────────────────────────────────
    from auth          import auth_bp
    from routes.main   import main_bp
    from routes.admin  import admin_bp
    from routes.api    import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # ── Admin nav helper (accessible in all templates) ───────────────────────
    @app.context_processor
    def inject_user():
        return {"current_user": current_user}

    logger.info("App created [env=%s]", env)
    return app


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

app = create_app()   # module-level instance for `flask` CLI + direct run


@app.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
def create_admin(email: str, password: str):
    """Create the first admin user. Run once on a fresh install.

    Usage:  flask create-admin admin@example.com 'yourpassword'
    """
    if len(password) < 8:
        click.echo("ERROR: Password must be at least 8 characters.")
        return

    with app.app_context():
        db.create_all()
        if User.query.filter_by(email=email.lower()).first():
            click.echo(f"ERROR: User {email} already exists.")
            return
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        user   = User(email=email.lower(), password_hash=hashed, is_admin=True)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin account created: {email}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    logger.info("Starting Mashroom OCR on http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=debug)
