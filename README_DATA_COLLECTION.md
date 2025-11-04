# Data Collection Server (Flask on Render)

This service accepts gesture frames JSON, waits for your app to provide the prediction label, converts to CSV in the exact `landmarks_recording_YYYY-MM-DDTHH-MM-SS-sssZ.csv` format, and uploads to Google Drive under per-class folders.

## Endpoints
- `GET /health` → readiness check
- `POST /store-data` → body:
```json
{
  "data": [[...numbers...], [...]],
  "prediction": "Hello"
}
```
Response:
```json
{ "status": "ok", "uploadedFileId": "...", "uploadedPath": "Hello/landmarks_recording_...Z.csv" }
```

## Local run
1. Python 3.10+
2. Create a virtualenv and install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Export env vars:
   - `GOOGLE_DRIVE_FOLDER_ID` = Parent folder ID in Google Drive
   - `GOOGLE_CREDENTIALS_JSON` = Entire service account JSON (one line)
4. Run:
   ```bash
   python data_collection_server.py
   ```

## Deploy to Render.com
- New Web Service
  - Root directory: `server_code`
  - Build command: `pip install -r requirements.txt`
  - Start command: `gunicorn data_collection_server:app -b 0.0.0.0:$PORT --workers 2`
  - Environment:
    - `PORT` = 8000
    - `GOOGLE_DRIVE_FOLDER_ID` = your Google Drive parent folder ID
    - `GOOGLE_CREDENTIALS_JSON` = Paste the entire service account JSON (rotate key first and do NOT commit keys to git)

## Google Drive setup
1. Enable Drive API on your GCP project
2. Create/rotate a Service Account key
3. Share your target parent folder in Drive with the service account email as Editor
4. Use that folder ID in `GOOGLE_DRIVE_FOLDER_ID`

## Frontend integration (sequential flow)
After you receive the prediction from your predictor, call the store endpoint:
```javascript
await fetch("https://<your-render-app>.onrender.com/store-data", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ data: recordedFrames, prediction })
});
```
Do not block the UI if this fails; log and continue.

## Security
- Never commit service account keys to the repo
- Provide `GOOGLE_CREDENTIALS_JSON` only via environment variables
- Consider restricting CORS to your domain once verified


