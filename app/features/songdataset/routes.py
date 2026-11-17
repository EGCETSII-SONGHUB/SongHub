import os

from flask import abort, jsonify, render_template, request, send_from_directory
from flask_login import current_user, login_required

from app.features.songdataset import songdataset_bp
from app.features.songdataset.services import SongDatasetService

song_dataset_service = SongDatasetService()


@songdataset_bp.route("/songdataset/upload", methods=["GET"])
@login_required
def upload_page():
    return render_template("songdataset/upload.html")


@songdataset_bp.route("/songdataset/file/upload", methods=["POST"])
@login_required
def upload_file():
    result = song_dataset_service.save_temp_csv(request.files.get("file"), current_user)
    return jsonify({key: value for key, value in result.items() if key != "status"}), result["code"]


@songdataset_bp.route("/songdataset/upload", methods=["POST"])
@login_required
def create_dataset():
    uploaded = request.files.get("file")
    if uploaded:
        upload_result = song_dataset_service.save_temp_csv(uploaded, current_user)
        if upload_result["status"] != "ok":
            return jsonify({"message": upload_result["message"]}), upload_result["code"]
        filename = upload_result["filename"]
    else:
        filename = (request.form.get("filename") or "").strip()
    if not request.form.get("title") or not request.form.get("description") or not filename:
        return jsonify({"message": "title, description and filename are required"}), 400
    try:
        dataset = song_dataset_service.create_from_upload(request.form, filename, current_user)
        from app.features.zenodo.services import ZenodoService

        zenodo_result = {"status": "local"}
        try:
            zenodo_result = ZenodoService().synchronize_dataset(dataset)
        except Exception:

            zenodo_result = {"status": "pending"}
        return jsonify({"dataset_id": dataset.id, "synchronization": zenodo_result}), 201
    except Exception as exc:
        from app import db

        db.session.rollback()
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
    from app.features.songdataset.models import SongDataset

    dataset = SongDataset.query.get_or_404(dataset_id)
    path = os.path.join(
        current_user.temp_folder() if current_user.is_authenticated and current_user.id == dataset.user_id else "",
        dataset.song_metadata.csv_filename,
    )
    if not os.path.isfile(path):
        path = os.path.join(
            os.getenv("WORKING_DIR", ""),
            "uploads",
            f"user_{dataset.user_id}",
            f"dataset_{dataset.id}",
            dataset.song_metadata.csv_filename,
        )
    if not os.path.isfile(path):
        abort(404)
    limit = min(max(request.args.get("limit", 50, type=int), 1), 500)
    offset = max(request.args.get("offset", 0, type=int), 0)
    rows = song_dataset_service.preview_file(path, limit=offset + limit)[offset:]
    return jsonify({"rows": rows, "summary": song_dataset_service.summarize_file(path)})


@songdataset_bp.route("/songdataset/<int:dataset_id>/edit", methods=["POST"])
@login_required
def edit_dataset(dataset_id):
    from app.features.songdataset.models import SongDataset

    dataset = SongDataset.query.filter_by(id=dataset_id, user_id=current_user.id).first_or_404()
    song_dataset_service.update_metadata(dataset, request.form)
    if request.files.get("file"):
        song_dataset_service.replace_file(dataset, request.files["file"])
    return jsonify({"message": "Song dataset updated", "dataset_id": dataset.id})


@songdataset_bp.route("/songdataset/file/<int:file_id>/download", methods=["GET"])
def download_song_file(file_id):
    from app.features.songdataset.models import SongFile

    song_file = SongFile.query.get_or_404(file_id)
    dataset = song_file.song_dataset
    directory = os.path.join(
        os.getenv("WORKING_DIR", ""), "uploads", f"user_{dataset.user_id}", f"dataset_{dataset.id}"
    )
    return send_from_directory(directory, song_file.name, as_attachment=True)
