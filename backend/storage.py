from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class FileTooLargeError(Exception):
    pass


def data_dir() -> Path:
    root = Path(os.getenv("DATA_DIR", "/data")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_uploaded_file(file: UploadFile, resume_id: str) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    destination_dir = data_dir() / "resumes" / resume_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"original{suffix}"

    size = 0
    with destination.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                output.close()
                destination.unlink(missing_ok=True)
                raise FileTooLargeError("Maximum file size is 10MB")
            output.write(chunk)

    await file.seek(0)
    return str(destination)


def get_file_url(path: str) -> str:
    relative = Path(path).resolve().relative_to(data_dir())
    return f"/api/files/{relative.as_posix()}"


def new_resume_id() -> str:
    return str(uuid4())
