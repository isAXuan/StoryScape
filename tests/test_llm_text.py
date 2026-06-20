import pytest

from storyscape.llm_text.openrouter_client import parse_annotation_json
from storyscape.llm_text.schemas import AudioProfile
from storyscape.llm_text.jobs import _validate_required_fields


def test_parse_annotation_json_repairs_model_output():
    result = parse_annotation_json('{segments: [{order_index: 1, text: "hello", speaker: "narrator", role_type: "narrator"}]}')

    assert result.segments[0].speaker == "narrator"


def test_required_fields_missing_fails():
    profile = AudioProfile(audio_model="audio", required_fields=["voice_id"], voice_mapping={})

    with pytest.raises(ValueError):
        _validate_required_fields(
            {"segments": [{"order_index": 1, "text": "hello", "speaker": "narrator", "role_type": "narrator"}]},
            profile,
        )
