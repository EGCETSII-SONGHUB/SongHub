from flask import Flask
from splent_framework.blueprints.base_blueprint import BaseBlueprint

songdataset_bp = BaseBlueprint("songdataset", __name__, template_folder="templates")


def init_feature(app: Flask) -> None:
    """Keep the musical dataset feature independently deployable."""
