from flask import Flask
from splent_framework.assets.asset_registry import register_asset
from splent_framework.blueprints.base_blueprint import BaseBlueprint

admin_bp = BaseBlueprint("admin", __name__, template_folder="templates")


def init_feature(app: Flask) -> None:
    register_asset("js", "admin.assets", subfolder="js", filename="scripts.js")