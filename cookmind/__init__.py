from flask import Flask

from .db import init_db
from .blueprints.recipes_api import recipes_api
from .blueprints.favorites_api import favorites_api
from .blueprints.shopping_api import shopping_api
from .blueprints.suggestions_api import suggestions_api


def create_app() -> Flask:
    app = Flask(__name__)

    # API blueprints
    app.register_blueprint(recipes_api)
    app.register_blueprint(favorites_api)
    app.register_blueprint(shopping_api)
    app.register_blueprint(suggestions_api)

    # Initialize DB + seed data (idempotent).
    init_db()

    return app

