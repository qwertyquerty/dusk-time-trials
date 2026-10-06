import click
from flask import current_app

from .categories import sync_categories
from .extensions import db


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        click.echo("database ready")

    @app.cli.command("sync-categories")
    def sync():
        count = sync_categories(current_app.config["CATEGORIES_PATH"])
        click.echo(f"synced {count} categories")
