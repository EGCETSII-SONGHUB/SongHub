from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from splent_framework.utils.form_helpers import form_error

from app.features.auth import auth_bp
from app.features.auth.forms import LoginForm, ResendVerificationForm, SignupForm
from app.features.auth.services import AuthenticationService
from app.features.profile.services import UserProfileService

authentication_service = AuthenticationService()
user_profile_service = UserProfileService()


@auth_bp.route("/signup/", methods=["GET", "POST"])
def show_signup_form():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data
        if not authentication_service.is_email_available(email):
            return form_error("auth/signup_form.html", form, {"email": [f"{email} in use"]})

        user = authentication_service.create_with_profile(**form.data)
        authentication_service.send_verification_email(user)
        login_user(user, remember=True)
        return redirect(url_for("public.index"))

    return render_template("auth/signup_form.html", form=form)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    user = authentication_service.verify_email_token(token)
    if user is None:
        flash("This verification link is invalid or has expired. Please request another email.", "danger")
    else:
        flash("Your email address has been verified.", "success")
    return redirect(url_for("public.index"))


@auth_bp.route("/resend-verification", methods=["POST"])
@login_required
def resend_verification():
    form = ResendVerificationForm()
    if not form.validate_on_submit():
        flash("The request could not be validated. Please try again.", "danger")
        return redirect(request.referrer or url_for("public.index"))
    if current_user.email_verified:
        flash("Your email address is already verified.", "info")
    else:
        authentication_service.send_verification_email(current_user)
        flash("A new verification email has been sent.", "success")
    return redirect(request.referrer or url_for("public.index"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
        if authentication_service.login(form.email.data, form.password.data):
            return redirect(url_for("public.index"))
        return form_error("auth/login_form.html", form, {"credentials": ["Invalid credentials"]})

    return render_template("auth/login_form.html", form=form)


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("public.index"))
