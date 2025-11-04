import io
import json
import os
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.service_account import Credentials


app = FastAPI(title="Drive API Uploader")


def get_drive_service():
    key_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
    if not key_json:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_KEY env var")
    try:
        info = json.loads(key_json)
    except json.JSONDecodeError as e:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_KEY is not valid JSON") from e
    creds = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def find_file_in_folder_by_name(drive, folder_id: str, name: str) -> Optional[str]:
    def _q(s: str) -> str:
        return s.replace("'", "\\'")
    q = (
        f"'{folder_id}' in parents and name = '{_q(name)}' and trashed = false "
        "and mimeType != 'application/vnd.google-apps.folder'"
    )
    resp = drive.files().list(q=q, fields="files(id, name)", pageSize=10).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def generate_renamed_filename(original_name: str, attempt_index: int) -> str:
    base, dot, ext = original_name.partition(".")
    if attempt_index <= 0:
        return original_name
    return f"{original_name} ({attempt_index})" if not dot else f"{base} ({attempt_index}).{ext}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    folder_id: Optional[str] = Form(default=None),
    conflict_policy: str = Form(default=os.getenv("CONFLICT_POLICY", "rename")),
):
    target_folder_id = folder_id or os.getenv("DRIVE_FOLDER_ID")
    if not target_folder_id:
        raise HTTPException(status_code=400, detail="Missing folder_id and DRIVE_FOLDER_ID env var")

    if conflict_policy not in ("rename", "overwrite", "skip"):
        raise HTTPException(status_code=400, detail="conflict_policy must be rename|overwrite|skip")

    try:
        drive = get_drive_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    results = []
    try:
        for uf in files:
            desired_name = uf.filename
            existing_id = find_file_in_folder_by_name(drive, target_folder_id, desired_name)

            if existing_id and conflict_policy == "skip":
                results.append({"name": desired_name, "action": "skipped", "id": None, "link": None})
                continue

            upload_stream = io.BytesIO(await uf.read())
            media = MediaIoBaseUpload(upload_stream, mimetype=uf.content_type or "application/octet-stream", resumable=True)

            if existing_id and conflict_policy == "overwrite":
                updated = drive.files().update(
                    fileId=existing_id,
                    media_body=media,
                    fields="id, name, webViewLink",
                ).execute()
                results.append({
                    "name": updated.get("name", desired_name),
                    "action": "overwritten",
                    "id": updated["id"],
                    "link": updated.get("webViewLink"),
                })
                continue

            final_name = desired_name
            if existing_id and conflict_policy == "rename":
                # find available name name (1).ext ...
                for i in range(1, 1000):
                    candidate = generate_renamed_filename(desired_name, i)
                    if not find_file_in_folder_by_name(drive, target_folder_id, candidate):
                        final_name = candidate
                        break

            metadata = {"name": final_name, "parents": [target_folder_id]}
            created = drive.files().create(body=metadata, media_body=media, fields="id, name, webViewLink").execute()
            results.append({
                "name": created.get("name", final_name),
                "action": "created" if final_name == desired_name else "created_renamed",
                "id": created["id"],
                "link": created.get("webViewLink"),
            })

        return JSONResponse(content={"results": results})
    except HttpError as e:
        raise HTTPException(status_code=500, detail=f"Drive API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


