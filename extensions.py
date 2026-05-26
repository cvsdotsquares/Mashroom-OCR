"""
Flask extension singletons — Singleton pattern.

Instantiated here WITHOUT an app object.
Each extension is bound to a concrete Flask app inside create_app()
via its .init_app(app) method (Application Factory pattern).

Import from here everywhere — never re-instantiate in other modules.
"""

from flask_bcrypt    import Bcrypt
from flask_login     import LoginManager
from flask_migrate   import Migrate
from flask_sqlalchemy import SQLAlchemy

db            = SQLAlchemy()
bcrypt        = Bcrypt()
login_manager = LoginManager()
migrate       = Migrate()
