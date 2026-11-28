from flask import abort, flash, redirect, render_template, url_for

from app.features.admin import admin_bp
from app.features.admin.forms import RoleForm
from app.features.auth.decorators import role_required
from app.features.auth.models import Role
from app.features.auth.services import AuthenticationService

authentication_service = AuthenticationService()


@admin_bp.route("/admin/users", methods=["GET"])
@role_required(Role.ADMIN)
def list_users():
    return render_template("admin/users.html", users=authentication_service.list_users(), form=RoleForm())


@admin_bp.route("/admin/users/<int:user_id>/role", methods=["POST"])
@role_required(Role.ADMIN)
def change_user_role(user_id: int):
    user = authentication_service.get_user(user_id)
    if user is None:
        abort(404)

    form = RoleForm()
    if not form.validate_on_submit():
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.list_users"))

    try:
        authentication_service.change_role(user, form.role.data)
    except ValueError as exc:
        flash(str(exc), "danger")
    else:
        flash(f"{user.email} is now {form.role.data}.", "success")
    return redirect(url_for("admin.list_users"))
