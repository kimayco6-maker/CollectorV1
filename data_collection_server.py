import os
import io
import csv
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


# CSV header to match existing landmarks_recording_*.csv format
CSV_HEADER = [
    "pose_0_x","pose_0_y","pose_1_x","pose_1_y","pose_4_x","pose_4_y",
    "pose_9_x","pose_9_y","pose_10_x","pose_10_y","pose_11_x","pose_11_y",
    "pose_12_x","pose_12_y","pose_13_x","pose_13_y","pose_14_x","pose_14_y",
    "pose_15_x","pose_15_y","pose_16_x","pose_16_y",
    *[f"hand0_{i}_{ax}" for i in range(21) for ax in ("x","y")],
    *[f"hand1_{i}_{ax}" for i in range(21) for ax in ("x","y")],
]


# Environment configuration
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")  # Entire JSON as a single-line string
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def build_drive_service():
    if not GOOGLE_CREDENTIALS_JSON:
        raise RuntimeError("Missing GOOGLE_CREDENTIALS_JSON environment variable")
    info = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    # cache_discovery=False avoids a write attempt in serverless envs
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def find_or_create_class_folder(service, parent_id: str, class_name: str) -> str:
    # Detect if parent is in a shared drive (driveId present)
    parent = service.files().get(fileId=parent_id, fields="id,name,driveId", supportsAllDrives=True).execute()
    drive_id = parent.get("driveId")

    # Search for an existing folder with the same name under the parent
    safe_name = class_name.replace("'", "\\'")
    query = (
        "mimeType='application/vnd.google-apps.folder' and trashed=false "
        f"and name='{safe_name}' and '{parent_id}' in parents"
    )
    list_kwargs = {
        "q": query,
        "spaces": "drive",
        "fields": "files(id,name)",
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }
    if drive_id:
        list_kwargs.update({"corpora": "drive", "driveId": drive_id})
    res = service.files().list(**list_kwargs).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]

    # Create the folder if not found
    metadata = {
        "name": class_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id", supportsAllDrives=True).execute()
    return folder["id"]


def frames_to_csv_bytes(frames: list) -> io.BytesIO:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in frames:
        writer.writerow(row)
    return io.BytesIO(buf.getvalue().encode("utf-8"))


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/store-data")
def store_data():
    try:
        if not GOOGLE_DRIVE_FOLDER_ID:
            return jsonify({"error": "Server misconfigured: missing GOOGLE_DRIVE_FOLDER_ID"}), 500

        payload = request.get_json(force=True, silent=False)
        if not isinstance(payload, dict):
            return jsonify({"error": "Invalid JSON body"}), 400

        frames = payload.get("data")
        prediction = payload.get("prediction")

        if not isinstance(frames, list) or not frames:
            return jsonify({"error": "Missing or invalid 'data' (expected non-empty array)"}), 400
        if not isinstance(prediction, str) or not prediction.strip():
            return jsonify({"error": "Missing 'prediction' (string)"}), 400

        class_name = prediction.strip()
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"
        filename = f"landmarks_recording_{timestamp}.csv"

        csv_bytes = frames_to_csv_bytes(frames)

        service = build_drive_service()
        class_folder_id = find_or_create_class_folder(service, GOOGLE_DRIVE_FOLDER_ID, class_name)

        media = MediaIoBaseUpload(csv_bytes, mimetype="text/csv", resumable=False)
        metadata = {"name": filename, "parents": [class_folder_id]}
        uploaded = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name,parents",
            supportsAllDrives=True,
        ).execute()

        return jsonify({
            "status": "ok",
            "uploadedFileId": uploaded["id"],
            "uploadedPath": f"{class_name}/{filename}",
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)


