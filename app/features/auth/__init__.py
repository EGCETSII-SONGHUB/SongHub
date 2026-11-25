from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from splent_framework.assets.asset_registry import register_asset
from splent_framework.blueprints.base_blueprint import BaseBlueprint

auth_bp = BaseBlueprint("auth", __name__, template_folder="templates")
mail = Mail()


def init_feature(app: Flask) -> None:
    """Configure Flask-Login when the auth feature is registered.

    Lives here (not in app/__init__.py) so the central app factory stays
    feature-agnostic — login is an auth concern, not a product concern.
    """
    register_asset("js", "auth.assets", subfolder="js", filename="scripts.js")
    mail.init_app(app)

    from app.features.auth.forms import ResendVerificationForm

    @app.context_processor
    def inject_resend_verification_form():
        return {"resend_verification_form": ResendVerificationForm()}

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        from app.features.auth.models import User

        return User.query.get(int(user_id))
