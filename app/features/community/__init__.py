from flask import Flask
from splent_framework.assets.asset_registry import register_asset
from splent_framework.blueprints.base_blueprint import BaseBlueprint
from splent_framework.nav.nav_registry import register_nav_item

community_bp = BaseBlueprint("community", __name__, template_folder="templates")


def init_feature(app: Flask) -> None:
    """Declare community assets and sidebar navigation item."""
    register_asset("js", "community.assets", subfolder="js", filename="scripts.js")
    register_nav_item("communities", "Communities", "/community", order=25, icon="globe")
