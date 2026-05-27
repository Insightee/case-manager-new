from __future__ import annotations

from app.storage.object_io import delete_stored_object, put_stored_bytes, read_stored_bytes

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


def _avatar_mime(ext: str) -> str:
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "image/jpeg"


def save_avatar(user_id: int, content: bytes, ext: str) -> str:
    mime = _avatar_mime(ext)
    key, _provider = put_stored_bytes(
        "avatars",
        f"user_{user_id}",
        filename=f"avatar{ext}",
        data=content,
        content_type=mime,
    )
    return key


def delete_avatar_files(avatar_path: str | None) -> None:
    if avatar_path:
        delete_stored_object(avatar_path)


def read_avatar_bytes(avatar_path: str) -> tuple[bytes, str]:
    data = read_stored_bytes(avatar_path)
    lower = avatar_path.lower()
    if lower.endswith(".png"):
        return data, "image/png"
    if lower.endswith(".webp"):
        return data, "image/webp"
    return data, "image/jpeg"
