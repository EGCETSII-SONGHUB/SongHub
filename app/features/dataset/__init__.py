from flask import Flask, abort, jsonify, request
from flask_login import current_user
from flask_restful import Api
from splent_framework.assets.asset_registry import register_asset
from splent_framework.blueprints.base_blueprint import BaseBlueprint

from app.features.dataset.api import init_blueprint_api

dataset_bp = BaseBlueprint("dataset", __name__, template_folder="templates")


api = Api(dataset_bp)
init_blueprint_api(api)


def init_feature(app: Flask) -> None:
    """Declare this feature's javascript with the framework asset registry."""
    register_asset("js", "dataset.assets", subfolder="js", filename="scripts.js")

    @app.before_request
    def require_verified_email_for_uploads():
        is_upload = request.path in {"/dataset/upload", "/dataset/file/upload"}
        is_dataset_api_write = request.path.startswith("/api/v1/datasets") and request.method in {
            "POST",
            "PUT",
            "PATCH",
        }
        if (
            current_user.is_authenticated
            and not current_user.email_verified
            and request.method in {"POST", "PUT", "PATCH"}
            and (is_upload or is_dataset_api_write)
        ):
            if request.path.startswith("/api/"):
                return jsonify({"message": "Verify your email address before uploading datasets."}), 403
            abort(403)
