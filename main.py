*** Begin Patch
*** Update File: main.py
@@
-from fastapi.responses import JSONResponse
+from fastapi.responses import JSONResponse, HTMLResponse
@@
 @app.get("/health")
 def health():
     return {"status": "ok"}
 
 
+@app.get("/", response_class=HTMLResponse)
+def index():
+    return """
+<!doctype html>
+<html lang=\"en\">
+<head>
+  <meta charset=\"utf-8\" />
+  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
+  <title>Drive Uploader</title>
+  <style>
+    body { font-family: system-ui, Arial, sans-serif; margin: 2rem; }
+    form { border: 1px solid #e5e7eb; padding: 1rem; border-radius: 8px; max-width: 720px; }
+    .row { margin-bottom: .75rem; }
+    input[type=file] { width: 100%; }
+    code { background: #f3f4f6; padding: .15rem .4rem; border-radius: 4px; }
+    pre { background: #0b1020; color: #d1d5db; padding: 1rem; border-radius: 8px; overflow:auto; }
+    button { background: #2563eb; color: white; border: 0; padding: .6rem 1rem; border-radius: 6px; cursor: pointer; }
+    button:disabled { opacity: .6; cursor: not-allowed; }
+    label { display:block; font-weight:600; margin-bottom:.25rem }
+  </style>
+  <script>
+    async function doUpload(ev) {
+      ev.preventDefault();
+      const form = ev.target;
+      const url = form.action;
+      const fd = new FormData(form);
+      const out = document.getElementById('output');
+      out.textContent = 'Uploading...';
+      try {
+        const res = await fetch(url, { method: 'POST', body: fd });
+        const txt = await res.text();
+        out.textContent = txt;
+      } catch (e) {
+        out.textContent = 'Error: ' + (e && e.message ? e.message : e);
+      }
+    }
+  </script>
+  </head>
+<body>
+  <h1>Upload files to Google Drive</h1>
+  <p>
+    This page posts to <code>/upload</code>. Ensure your Render service has <code>GOOGLE_SERVICE_ACCOUNT_KEY</code> set
+    and the target Drive folder shared with the service account. Optionally set a default <code>DRIVE_FOLDER_ID</code>.
+  </p>
+  <form method=\"post\" action=\"/upload\" enctype=\"multipart/form-data\" onsubmit=\"doUpload(event)\">
+    <div class=\"row\">
+      <label>Files</label>
+      <input type=\"file\" name=\"files\" multiple required />
+    </div>
+    <div class=\"row\">
+      <label>Folder ID (optional, overrides server default)</label>
+      <input type=\"text\" name=\"folder_id\" placeholder=\"1xEQ5uQs...\" style=\"width:100%\" />
+    </div>
+    <div class=\"row\">
+      <label>Conflict policy</label>
+      <select name=\"conflict_policy\">
+        <option value=\"rename\" selected>rename</option>
+        <option value=\"overwrite\">overwrite</option>
+        <option value=\"skip\">skip</option>
+      </select>
+    </div>
+    <button type=\"submit\">Upload</button>
+  </form>
+  <h2>Response</h2>
+  <pre id=\"output\"></pre>
+</body>
+</html>
+"""
+
*** End PatchtById('output');
      out.textContent = 'Uploading...';
      try {
        const res = await fetch(url, { method: 'POST', body: fd });
        const txt = await res.text();
        out.textContent = txt;
      } catch (e) {
        out.textContent = 'Error: ' + (e && e.message ? e.message : e);
      }
    }
  </script>
  </head>
<body>
  <h1>Upload files to Google Drive</h1>
  <p>
    This page posts to <code>/upload</code>. Ensure your Render service has <code>GOOGLE_SERVICE_ACCOUNT_KEY</code> set
    and the target Drive folder shared with the service account. Optionally set a default <code>DRIVE_FOLDER_ID</code>.
  </p>
  <form method=\"post\" action=\"/upload\" enctype=\"multipart/form-data\" onsubmit=\"doUpload(event)\">
    <div class=\"row\">
      <label>Files</label>
      <input type=\"file\" name=\"files\" multiple required />
    </div>
    <div class=\"row\">
      <label>Folder ID (optional, overrides server default)</label>
      <input type=\"text\" name=\"folder_id\" placeholder=\"1xEQ5uQs...\" style=\"width:100%\" />
    </div>
    <div class=\"row\">
      <label>Conflict policy</label>
      <select name=\"conflict_policy\">
        <option value=\"rename\" selected>rename</option>
        <option value=\"overwrite\">overwrite</option>
        <option value=\"skip\">skip</option>
      </select>
    </div>
    <button type=\"submit\">Upload</button>
  </form>
  <h2>Response</h2>
  <pre id=\"output\"></pre>
</body>
</html>
"""

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


