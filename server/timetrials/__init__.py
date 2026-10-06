from dotenv import load_dotenv
from flask import Flask

from .config import Config
from .extensions import db


def create_app(config_object=Config):
    load_dotenv()
    app = Flask(__name__, template_folder="templates", static_folder=None)
    app.config.from_object(config_object)

    db.init_app(app)

    from .api import api_bp
    from .auth import auth_bp
    from .cli import register_cli

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp)
    register_cli(app)

    return app
