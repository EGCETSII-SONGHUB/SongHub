from flask import Flask
from splent_framework.assets.asset_registry import register_asset
from splent_framework.blueprints.base_blueprint import BaseBlueprint

songdataset_bp = BaseBlueprint("songdataset", __name__, template_folder="templates")


def init_feature(app: Flask) -> None:
    """Keep the musical dataset feature independently deployable."""
    register_asset("js", "songdataset.assets", subfolder="js", filename="scripts.js")
