"""Stable identifiers for image files and analysis configurations."""
import hashlib
import json


def image_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def analysis_id(image_hash: str, settings: dict) -> str:
    encoded = json.dumps({"image": image_hash, "settings": settings}, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]
