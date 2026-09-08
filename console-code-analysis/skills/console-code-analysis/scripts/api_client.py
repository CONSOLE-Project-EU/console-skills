import urllib.request
import urllib.parse
import urllib.error
import json
import io
from typing import Optional

MANDATORY_CLUE_KEYS = ["tool", "category", "name", "description", "severity"]


def get_clues(server: str, token: str, job_id: Optional[int] = None) -> list[dict]:
    params = {}
    if job_id:
        params["job_id"] = job_id
    query_string = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{server}/clues?{query_string}",
        headers={"X-API-Key": token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}") from e


def upload_clues(server: str, token: str, clues: list[dict]) -> bool:
    for clue in clues:
        for key in clue:
            if key.endswith("_"):
                raise ValueError(f"forbidden key in clue: '{key}'")
        for key in MANDATORY_CLUE_KEYS:
            if key not in clue:
                raise ValueError(f"missing key '{key}' from clue {clue}")
    req = urllib.request.Request(
        f"{server}/clues",
        data=json.dumps(clues).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": token},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            res = json.load(response)
            if isinstance(res, dict) and res.get("status") == "success":
                return True
            else:
                raise RuntimeError(f"Upload status: {res}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed: {e.reason}") from e


def create_job(
    server: str,
    token: str,
    zip_name: str,
    zip_bytes: bytes,
    project_version: Optional[str],
    details: Optional[str],
) -> int | None:
    # Note: original code had a bug mapping details to project_version; fixed here.
    fields = {"project_version": project_version, "details": details}
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = io.BytesIO()
    for name, value in fields.items():
        if value is None:
            continue
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.write(str(value).encode())
        body.write(b"\r\n")
    body.write(f"--{boundary}\r\n".encode())
    body.write(
        f'Content-Disposition: form-data; name="zip_archive"; filename="{zip_name}"\r\n'.encode()
    )
    body.write("Content-Type: application/zip\r\n\r\n".encode())
    body.write(zip_bytes)
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    body = body.getvalue()
    content_type = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(
        f"{server}/job",
        data=body,
        headers={"Content-Type": content_type, "X-API-Key": token},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            res = json.load(response)
            if isinstance(res, dict) and res.get("status") == "success":
                job_id = res.get("job_id")
                if job_id:
                    return int(job_id)
                return None
            else:
                raise RuntimeError(f"Create job status: {res}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed: {e.reason}") from e


def get_job_status(server: str, token: str, job_id: int) -> dict | None:
    params = {"job_id": job_id}
    query_string = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{server}/job?{query_string}",
        headers={"X-API-Key": token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}") from e
