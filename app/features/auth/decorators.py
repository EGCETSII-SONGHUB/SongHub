from functools import wraps

from flask import abort, current_app
from flask_login import current_user

from app.features.auth.models import Role


def role_required(*roles: str):
    if not roles:
        raise ValueError("role_required needs at least one role")
    unknown = set(roles) - set(Role.ALL)
    if unknown:
        raise ValueError(f"Unknown role(s): {sorted(unknown)}")

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if not current_user.has_role(*roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
