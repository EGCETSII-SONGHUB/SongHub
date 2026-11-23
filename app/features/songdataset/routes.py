import os
import re
import uuid

from flask import abort, flash, jsonify, make_response, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from app import db
from app.features.dataset.services import DSDownloadRecordService
from app.features.songdataset import songdataset_bp
from app.features.songdataset.forms import SongDatasetEditForm, SongDatasetForm
from app.features.songdataset.models import SongDataset, SongFile
from app.features.songdataset.services import SongDatasetService
from app.features.songdataset.validation import SongCSVValidationError

song_dataset_service = SongDatasetService()

_AUTHOR_KEY_RE = re.compile(r"^authors-(\d+)-name$")


def _wants_html() -> bool:
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return False
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "text/html" and request.accept_mimetypes["text/html"] > request.accept_mimetypes["application/json"]


def _extract_extra_authors(form_data) -> list[dict]:
    indices = sorted(
        {int(match.group(1)) for key in form_data.keys() if (match := _AUTHOR_KEY_RE.match(key))},
    )
    authors = []
    for idx in indices:
        name = (form_data.get(f"authors-{idx}-name") or "").strip()
        if name:
            authors.append(
                {
                    "name": name,
                    "affiliation": (form_data.get(f"authors-{idx}-affiliation") or "").strip(),
                    "orcid": (form_data.get(f"authors-{idx}-orcid") or "").strip(),
                }
            )
    return authors


@songdataset_bp.route("/songdataset/upload", methods=["GET"])
@login_required
def upload_page():
    return render_template("songdataset/upload.html", form=SongDatasetForm())


@songdataset_bp.route("/songdataset/file/upload", methods=["POST"])
@login_required
def upload_file():
    result = song_dataset_service.save_temp_csv(request.files.get("file"), current_user)
    return jsonify({key: value for key, value in result.items() if key != "status"}), result["code"]


@songdataset_bp.route("/songdataset/file/delete", methods=["POST"])
@login_required
def delete_file():
    filename = (request.get_json(silent=True) or {}).get("file") or request.form.get("file") or ""
    result = song_dataset_service.delete_temp_csv(filename, current_user)
    payload = {key: result[key] for key in ("message", "error") if key in result}
    return jsonify(payload), result["code"]


@songdataset_bp.route("/songdataset/upload", methods=["POST"])
@login_required
def create_dataset():
    uploaded = request.files.get("file")
    if uploaded and uploaded.filename:
        upload_result = song_dataset_service.save_temp_csv(uploaded, current_user)
        if upload_result["status"] != "ok":
            if _wants_html():
                return (
                    render_template(
                        "songdataset/upload.html",
                        form=SongDatasetForm(formdata=request.form),
                        error=upload_result["message"],
                    ),
                    upload_result["code"],
                )
            return jsonify({"message": upload_result["message"]}), upload_result["code"]
        filename = upload_result["filename"]
    else:
        filename = (request.form.get("filename") or "").strip()

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    if not title or not description or not filename:
        message = "title, description and filename are required"
        if _wants_html():
            return (
                render_template(
                    "songdataset/upload.html",
                    form=SongDatasetForm(formdata=request.form),
                    error=message,
                ),
                400,
            )
        return jsonify({"message": message}), 400

    try:
        dataset = song_dataset_service.create_from_upload(
            request.form,
            filename,
            current_user,
            extra_authors=_extract_extra_authors(request.form),
        )
        from app.features.zenodo.services import ZenodoService

        try:
            zenodo_result = ZenodoService().synchronize_dataset(dataset)
        except Exception:
            zenodo_result = {"status": "pending"}

        if _wants_html():
            if not dataset.ds_meta_data.dataset_doi:
                flash(
                    "Song dataset saved locally under Unsynchronized datasets. "
                    "It will appear publicly in Explore once synchronized with Zenodo/Fakenodo.",
                    "warning",
                )
            return redirect(url_for("dataset.list_dataset"))
        return jsonify({"dataset_id": dataset.id, "synchronization": zenodo_result}), 201
    except Exception as exc:
        db.session.rollback()
        if _wants_html():
            return (
                render_template(
                    "songdataset/upload.html",
                    form=SongDatasetForm(formdata=request.form),
                    error=str(exc),
                ),
                400,
            )
        return jsonify({"message": str(exc)}), 400


@songdataset_bp.route("/songdataset/file/<path:filename>/preview", methods=["GET"])
@login_required
def preview_file(filename):
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        abort(404)
    path = os.path.join(current_user.temp_folder(), safe_name)
    if not os.path.isfile(path):
        abort(404)
    return jsonify(
        {
            "rows": song_dataset_service.preview_file(path),
            "summary": song_dataset_service.summarize_file(path),
        }
    )


@songdataset_bp.route("/songdataset/<int:dataset_id>/preview", methods=["GET"])
def preview_dataset(dataset_id):
    dataset = SongDataset.query.get_or_404(dataset_id)
    if not dataset.ds_meta_data.dataset_doi and (
        not current_user.is_authenticated or current_user.id != dataset.user_id
    ):
        abort(404)
    limit = min(max(request.args.get("limit", 50, type=int), 1), 500)
    offset = max(request.args.get("offset", 0, type=int), 0)
    query = request.args.get("q", "")
    try:
        payload = song_dataset_service.get_dataset_preview(dataset, limit=limit, offset=offset, query=query)
    except FileNotFoundError:
        abort(404)
    return jsonify(payload)


@songdataset_bp.route("/songdataset/<int:dataset_id>/edit", methods=["GET"])
@login_required
def edit_dataset_page(dataset_id):
    dataset = song_dataset_service.get_for_owner(dataset_id, current_user.id)
    if dataset is None:
        abort(404)
    form = SongDatasetEditForm(
        data={
            "title": dataset.ds_meta_data.title,
            "description": dataset.ds_meta_data.description,
            "publication_type": dataset.ds_meta_data.publication_type.value,
            "publication_doi": dataset.ds_meta_data.publication_doi or "",
            "tags": dataset.ds_meta_data.tags or "",
        }
    )
    return render_template("songdataset/edit.html", form=form, dataset=dataset)


@songdataset_bp.route("/songdataset/<int:dataset_id>/edit", methods=["POST"])
@login_required
def edit_dataset(dataset_id):
    dataset = song_dataset_service.get_for_owner(dataset_id, current_user.id)
    if dataset is None:
        abort(404)
    try:
        song_dataset_service.update_metadata(dataset, request.form)
        uploaded = request.files.get("file")
        if uploaded and uploaded.filename:
            song_dataset_service.replace_file(dataset, uploaded)
    except (ValueError, SongCSVValidationError) as exc:
        if _wants_html():
            return (
                render_template(
                    "songdataset/edit.html",
                    form=SongDatasetEditForm(formdata=request.form),
                    dataset=dataset,
                    error=str(exc),
                ),
                400,
            )
        return jsonify({"message": str(exc)}), 400

    if _wants_html():
        if dataset.ds_meta_data.dataset_doi:
            return redirect(url_for("dataset.subdomain_index", doi=dataset.ds_meta_data.dataset_doi))
        return redirect(url_for("dataset.get_unsynchronized_dataset", dataset_id=dataset.id))
    return jsonify({"message": "Song dataset updated", "dataset_id": dataset.id})


@songdataset_bp.route("/songdataset/file/<int:file_id>/download", methods=["GET"])
def download_song_file(file_id):
    song_file = SongFile.query.get_or_404(file_id)
    dataset = song_file.song_dataset
    if not dataset.ds_meta_data.dataset_doi and (
        not current_user.is_authenticated or current_user.id != dataset.user_id
    ):
        abort(404)
    directory = os.path.abspath(os.path.dirname(dataset.file_path()))
    cookie = request.cookies.get("download_cookie") or str(uuid.uuid4())
    resp = make_response(send_from_directory(directory, song_file.name, as_attachment=True))
    if not request.cookies.get("download_cookie"):
        resp.set_cookie("download_cookie", cookie, max_age=60 * 60 * 24 * 365 * 2)
    DSDownloadRecordService().record_download(current_user, dataset.id, cookie)
    return resp
