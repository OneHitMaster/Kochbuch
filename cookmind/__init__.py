from pathlib import Path

from flask import Flask

from .db import init_db
from .blueprints.recipes_api import recipes_api
from .blueprints.favorites_api import favorites_api
from .blueprints.shopping_api import shopping_api
from .blueprints.suggestions_api import suggestions_api


def create_app() -> Flask:
    # Flask sucht Templates/Static standardmäßig relativ zum Package-Ordner.
    # Da das Projekt aber Templates/Static im Projekt-Root hat, setzen wir die Ordner explizit.
    root_dir = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder=str(root_dir / "templates"),
        static_folder=str(root_dir / "static"),
    )

    # API blueprints
    app.register_blueprint(recipes_api)
    app.register_blueprint(favorites_api)
    app.register_blueprint(shopping_api)
    app.register_blueprint(suggestions_api)

    # Initialize DB + seed data (idempotent).
    init_db()

    return app

