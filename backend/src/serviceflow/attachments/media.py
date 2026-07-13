"""Upload validation and image processing (docs/11 §3, docs/02 §9).

Security rule: images are always re-encoded — this kills embedded payloads and
converts HEIC in one step, so the stored bytes are never the client's raw upload.
PDFs are stored as-is (no re-encoding requirement documented for documents).
"""

import io

import pillow_heif
from PIL import Image

pillow_heif.register_heif_opener()

THUMBNAIL_SIZE = (320, 320)
JPEG_QUALITY = 85

# (sniffer, canonical_mime) — checked in order; first match wins.
_SIGNATURES: list[tuple[bytes, int, str]] = [
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"%PDF", 0, "application/pdf"),
]


class UnsupportedFileError(Exception):
    pass


def sniff_mime(data: bytes) -> str | None:
    """Magic-byte check (docs/11 §3) — a small fixed set, no libmagic dependency."""
    for signature, offset, mime in _SIGNATURES:
        if data[offset:offset + len(signature)] == signature:
            return mime
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "image/heic"
    return None


def is_image(mime: str) -> bool:
    return mime.startswith("image/")


def reencode_image(data: bytes) -> bytes:
    """Strips metadata/embedded payloads and normalizes HEIC/PNG/WEBP to JPEG."""
    with Image.open(io.BytesIO(data)) as img:
        rgb = img.convert("RGB")
        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue()


def make_thumbnail(jpeg_data: bytes) -> bytes:
    with Image.open(io.BytesIO(jpeg_data)) as img:
        img.thumbnail(THUMBNAIL_SIZE)
        out = io.BytesIO()
        img.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY)
        return out.getvalue()
