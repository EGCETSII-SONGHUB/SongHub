import os

from flask import abort, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from splent_framework.utils.form_helpers import form_error, form_success

from app.features.community import community_bp
from app.features.community.forms import AddCuratorForm, AddDatasetToCommunityForm, CommunityForm, ReviewRequestForm
from app.features.community.services import CommunityService

community_service = CommunityService()


def _curator_redirect_endpoint() -> str:
    return "community.edit_community" if request.args.get("next") == "edit" else "community.detail"


@community_bp.route("/community", methods=["GET"])
def index():
    """List all communities."""
    communities = community_service.list_communities()
    return render_template("community/index.html", communities=communities)


@community_bp.route("/community/create", methods=["GET", "POST"])
@login_required
def create_community():
    """Create a new community with the logged-in user as its initial curator."""
    form = CommunityForm()
    if form.is_submitted():
        community, errors = community_service.create_community(form=form, creator=current_user)
        if errors:
            return form_error("community/create.html", form, errors)
        return form_success("community.detail", "Community created successfully", community_id=community.id)

    return render_template("community/create.html", form=form)


@community_bp.route("/community/<int:community_id>", methods=["GET"])
def detail(community_id):
    """Display a single community and its datasets."""
    community = community_service.get_or_404(community_id)
    available_datasets = (
        community_service.get_available_datasets_for_user(community, current_user.id)
        if current_user.is_authenticated
        else []
    )
    add_dataset_form = AddDatasetToCommunityForm()
    add_curator_form = AddCuratorForm()
    return render_template(
        "community/show.html",
        community=community,
        datasets=community.datasets,
        is_curator=community.is_curator(current_user),
        available_datasets=available_datasets,
        add_dataset_form=add_dataset_form,
        add_curator_form=add_curator_form,
    )


@community_bp.route("/community/<int:community_id>/edit", methods=["GET", "POST"])
@login_required
def edit_community(community_id):
    """Edit an existing community; restricted to its curators."""
    community = community_service.get_or_404(community_id)
    if not community.is_curator(current_user):
        abort(403)

    form = CommunityForm(obj=community)
    add_curator_form = AddCuratorForm()
    if form.is_submitted():
        _, errors = community_service.update_community(community=community, form=form, editor=current_user)
        if errors:
            return form_error(
                "community/edit.html",
                form,
                errors,
                community=community,
                add_curator_form=add_curator_form,
            )
        return form_success("community.detail", "Community updated successfully", community_id=community.id)

    return render_template("community/edit.html", form=form, community=community, add_curator_form=add_curator_form)


@community_bp.route("/community/<int:community_id>/datasets/propose", methods=["POST"])
@login_required
def propose_dataset(community_id):
    """Propose one of the current user's datasets to *community_id* for curator review."""
    community = community_service.get_or_404(community_id)
    form = AddDatasetToCommunityForm()
    if not form.validate_on_submit():
        abort(400)

    try:
        community_service.propose_dataset(community=community, dataset_id=form.dataset_id.data, user=current_user)
    except LookupError:
        abort(404)
    except PermissionError:
        abort(403)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("community.detail", community_id=community.id))

    return form_success("community.detail", "Request sent. A curator will review it.", community_id=community.id)


@community_bp.route("/community/<int:community_id>/requests", methods=["GET"])
@login_required
def pending_requests(community_id):
    """List pending dataset requests; restricted to curators."""
    community = community_service.get_or_404(community_id)
    try:
        requests = community_service.list_pending_requests(community, current_user)
    except PermissionError:
        abort(403)
    return render_template(
        "community/requests.html",
        community=community,
        requests=requests,
        review_form=ReviewRequestForm(),
    )


def _resolve_request(community_id, request_id, action):
    community = community_service.get_or_404(community_id)
    dataset_request = community_service.request_repository.get_by_id(request_id)
    if dataset_request is None or dataset_request.community_id != community.id:
        abort(404)

    form = ReviewRequestForm()
    if not form.validate_on_submit():
        abort(400)

    try:
        getattr(community_service, action)(dataset_request, current_user, form.comment.data)
    except PermissionError:
        abort(403)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("community.pending_requests", community_id=community.id))

    message = "Request accepted" if action == "accept_request" else "Request rejected"
    return form_success("community.pending_requests", message, community_id=community.id)


@community_bp.route("/community/<int:community_id>/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(community_id, request_id):
    """Accept a pending dataset request; restricted to curators."""
    return _resolve_request(community_id, request_id, "accept_request")


@community_bp.route("/community/<int:community_id>/requests/<int:request_id>/reject", methods=["POST"])
@login_required
def reject_request(community_id, request_id):
    """Reject a pending dataset request; restricted to curators."""
    return _resolve_request(community_id, request_id, "reject_request")


@community_bp.route("/community/my-requests", methods=["GET"])
@login_required
def my_requests():
    """Show the status of the current user's dataset requests."""
    requests = community_service.list_user_requests(current_user)
    return render_template("community/my_requests.html", requests=requests)


@community_bp.route("/community/<int:community_id>/datasets/<int:dataset_id>/remove", methods=["POST"])
@login_required
def remove_dataset(community_id, dataset_id):
    """Remove *dataset_id* from *community_id*."""
    community = community_service.get_or_404(community_id)
    try:
        community_service.remove_dataset(community=community, dataset_id=dataset_id, user=current_user)
    except LookupError:
        abort(404)
    except PermissionError:
        abort(403)

    return form_success("community.detail", "Dataset removed from community", community_id=community.id)


@community_bp.route("/community/<int:community_id>/curators/add", methods=["POST"])
@login_required
def add_curator(community_id):
    """Add a registered user by email as curator of *community_id*."""
    community = community_service.get_or_404(community_id)
    if not community.is_curator(current_user):
        abort(403)

    target_endpoint = _curator_redirect_endpoint()
    form = AddCuratorForm()
    if not form.validate_on_submit():
        flash("Please enter a valid email address.", "error")
        return redirect(url_for(target_endpoint, community_id=community.id))

    _, error_msg = community_service.add_curator_by_email(
        community=community,
        email=form.email.data,
        actor=current_user,
    )
    if error_msg:
        flash(error_msg, "error")
        return redirect(url_for(target_endpoint, community_id=community.id))

    return form_success(target_endpoint, "Curator added successfully", community_id=community.id)


@community_bp.route("/community/<int:community_id>/curators/<int:user_id>/remove", methods=["POST"])
@login_required
def remove_curator(community_id, user_id):
    """Remove *user_id* from the curators of *community_id*, preserving at least one curator."""
    community = community_service.get_or_404(community_id)
    if not community.is_curator(current_user):
        abort(403)

    target_endpoint = _curator_redirect_endpoint()
    try:
        removed, error_msg = community_service.remove_curator(
            community=community,
            curator_id=user_id,
            actor=current_user,
        )
    except LookupError:
        abort(404)

    if not removed:
        flash(error_msg, "error")
        return redirect(url_for(target_endpoint, community_id=community.id))

    if not community.is_curator(current_user):
        target_endpoint = "community.detail"

    return form_success(target_endpoint, "Curator removed successfully", community_id=community.id)


@community_bp.route("/community/logos/<path:filename>", methods=["GET"])
def serve_logo(filename):
    """Serve an uploaded community logo file."""
    logos_dir = os.path.abspath(community_service.logos_directory())
    return send_from_directory(logos_dir, filename)
