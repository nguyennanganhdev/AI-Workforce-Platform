from io import BytesIO
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from PIL import Image
from vinhomes_api.v3_files import local_only, validate_image


def request(enabled, host="127.0.0.1"):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
        local_file_storage=enabled, dev_user_id=None, demo_mode=False, host=host))))


def test_real_identity_storage_requires_explicit_local_configuration():
    local_only(request(True))
    for value in [request(False), request(True, "0.0.0.0")]:
        with pytest.raises(HTTPException) as exc:
            local_only(value)
        assert exc.value.status_code == 503


def test_images_are_decoded_not_accepted_by_signature_alone():
    stream = BytesIO()
    Image.new("RGB", (2, 2), "white").save(stream, "PNG")
    validate_image(stream.getvalue(), "image/png")
    for data, mime in [(stream.getvalue(), "image/jpeg"), (b"\x89PNG\r\n\x1a\ninvalid", "image/png")]:
        with pytest.raises(HTTPException) as exc:
            validate_image(data, mime)
        assert exc.value.status_code == 422
