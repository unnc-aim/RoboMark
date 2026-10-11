import json
import pytest
from pydantic import ValidationError
from app.schemas.preannotation import Annotation, ProfileInput
from app.services.preannotation_inference import (
    normalize_output, render_template, extract, validate_profile, encrypt_credentials, decrypt_credentials,
)

CATEGORIES = [{"id": 12, "name": "无人机"}]
BOX = {"category_id": 12, "x_center": .5, "y_center": .4, "width": .2, "height": .1}


def test_normalized_output_and_legitimate_empty():
    assert normalize_output({"annotations": [BOX]}, {}, CATEGORIES, "bbox", 1920, 1080)[0]["category_id"] == 12
    assert normalize_output('{"annotations":[]}', {}, CATEGORIES, "bbox", 1920, 1080) == []
    with pytest.raises(KeyError):
        normalize_output({}, {}, CATEGORIES, "bbox", 1920, 1080)


def test_explicit_pixel_and_relative_coordinates():
    for unit, bbox in [("pixels", [192, 108, 576, 324]), ("relative_1000", [100, 100, 300, 300])]:
        config = {"coordinate_system": unit, "box_format": "xyxy", "field_mapping": {"bbox": "bbox_2d", "label": "label"}}
        result = normalize_output({"annotations": [{"label": "无人机", "bbox_2d": bbox}]}, config, CATEGORIES, "bbox", 1920, 1080)[0]
        assert result["x_center"] == pytest.approx(.2)
        assert result["width"] == pytest.approx(.2)


@pytest.mark.parametrize("change", [{"category_id": 999}, {"x_center": float("nan")}, {"width": -1}, {"x_center": .99}, {"annotation_type": "polygon"}, {"width": True}])
def test_invalid_model_results_fail_whole_image(change):
    with pytest.raises((ValueError, ValidationError)):
        normalize_output({"annotations": [BOX, {**BOX, **change}]}, {}, CATEGORIES, "bbox", 1920, 1080)


def test_quad_geometry_recomputed_and_crossed_quad_rejected():
    points = [[.1,.1],[.4,.1],[.5,.4],[.2,.4]]
    result = normalize_output({"annotations": [{"category_id":12,"points":points}]}, {}, CATEGORIES, "parallelogram", 100, 100)[0]
    assert result["width"] == pytest.approx(.4)
    assert result["height"] == pytest.approx(.3)
    points[1], points[2] = points[2], points[1]
    with pytest.raises(ValidationError):
        normalize_output({"annotations": [{"category_id":12,"points":points}]}, {}, CATEGORIES, "parallelogram", 100, 100)


def test_template_preserves_types_and_does_not_execute_code():
    context = {"image":{"data_url":"data:image/png;base64,abc"},"categories":CATEGORIES,"prompt":"标注无人机"}
    result = render_template({"categories":"{{categories}}","messages":[{"content":"{{prompt}}"}],"image":"{{image.data_url}}"}, context)
    assert isinstance(result["categories"], list)
    assert result["messages"][0]["content"] == "标注无人机"
    assert render_template("__import__('os').system('whoami')", context).startswith("__import__")
    assert extract({"choices":[{"message":{"content":"ok"}}]},"choices[0].message.content") == "ok"
    with pytest.raises(ValueError):
        extract({}, "__import__('os')")


def test_profile_validation_and_credentials_roundtrip():
    validate_profile(ProfileInput(name="局域网", endpoint="http://127.0.0.1:8001/v1/chat/completions"))
    with pytest.raises(ValueError):
        validate_profile(ProfileInput(name="非法", endpoint="file:///etc/passwd"))
    secret = {"api_key":"private-key", "headers":{"X-Token":"secret"}}
    ciphertext = encrypt_credentials(secret)
    assert "private-key" not in ciphertext
    assert decrypt_credentials(ciphertext) == secret
