# Drive API Uploader (Render)

A minimal FastAPI service that uploads files to Google Drive using a Google service account.

## Endpoints

- POST /upload
  - Form fields:
    - files: one or more files (multipart)
    - folder_id (optional): Drive folder ID (defaults to `DRIVE_FOLDER_ID`)
    - conflict_policy (optional): `rename` | `overwrite` | `skip` (defaults to env `CONFLICT_POLICY` or `rename`)

## Deployment (Render.com)

1. Create a new Web Service from this repo.
2. Use the included `render.yaml` or set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set environment variables:
   - `GOOGLE_SERVICE_ACCOUNT_KEY` (Secret): entire JSON of the service account key
   - `DRIVE_FOLDER_ID` (Optional): destination folder ID in Drive
   - `CONFLICT_POLICY` (Optional): `rename` | `overwrite` | `skip`

## Service account setup

- Share the target Drive folder (by ID) with the service account email shown in the JSON key (e.g., `xxx@project.iam.gserviceaccount.com`) with at least `Content manager`.
- Note: Service accounts do not have access to your personal “My Drive” by default; sharing the folder with the service account is required unless using domain‑wide delegation.

## Usage

Example (curl):

```bash
curl -X POST \
  -F "files=@/path/to/file1.txt" \
  -F "files=@/path/to/photo.jpg" \
  -F "folder_id=$DRIVE_FOLDER_ID" \
  -F "conflict_policy=rename" \
  https://<your-render-url>/upload
```

Response:

```json
{
  "results": [
    {"name": "file1.txt", "action": "created", "id": "<drive-id>", "link": "https://drive.google.com/file/d/<drive-id>/view"},
    {"name": "photo.jpg", "action": "created", "id": "<drive-id>", "link": "https://drive.google.com/file/d/<drive-id>/view"}
  ]
}
```

## Security note

Your service account key is extremely sensitive. Store it only in Render env vars. If you have posted the key publicly or shared it, REVOKE and regenerate it in Google Cloud IAM > Service Accounts > Keys.

