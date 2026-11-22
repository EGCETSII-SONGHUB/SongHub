from flask import render_template

from app.features.zenodo import zenodo_bp
from app.features.zenodo.services import ZenodoService

from app.features.auth.decorators import role_required
from app.features.auth.models import Role

@zenodo_bp.route("/zenodo", methods=["GET"])
def index():
    return render_template("zenodo/index.html")


@zenodo_bp.route("/zenodo/test", methods=["GET"])
@role_required(Role.ADMIN)
def zenodo_test() -> dict:
    service = ZenodoService()
    return service.test_full_connection()
