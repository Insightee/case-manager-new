from __future__ import annotations

from pathlib import Path

AVATAR_DIR = Path("uploads/avatars")
MAX_AVATAR_BYTES = 1_048_576
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def avatar_public_path(user_id: int) -> str:
    return f"/api/v1/files/avatars/{user_id}"


def validate_avatar_upload(content_type: str | None, size: int, filename: str | None = None) -> str:
    if size > MAX_AVATAR_BYTES:
        raise ValueError("Image must be under 1 MB")
    ext = ALLOWED_CONTENT_TYPES.get(content_type or "")
    if not ext and filename:
        lower = filename.lower()
        if lower.endswith(".jpg") or lower.endswith(".jpeg"):
            ext = ".jpg"
        elif lower.endswith(".png"):
            ext = ".png"
        elif lower.endswith(".webp"):
            ext = ".webp"
    if not ext:
        raise ValueError("Only JPEG, PNG, or WebP images are allowed")
    return ext


def save_avatar(user_id: int, content: bytes, ext: str) -> str:
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    for old in AVATAR_DIR.glob(f"{user_id}.*"):
        old.unlink(missing_ok=True)
    path = AVATAR_DIR / f"{user_id}{ext}"
    path.write_bytes(content)
    return str(path)


def delete_avatar_files(user_id: int) -> None:
    for old in AVATAR_DIR.glob(f"{user_id}.*"):
        old.unlink(missing_ok=True)
