import json

from storyscape.chapters.schemas import Chapter
from storyscape.llm_text.schemas import AudioProfile


def build_prompt(chapter: Chapter, audio_profile: AudioProfile) -> str:
    required = ", ".join(audio_profile.required_fields) or "none"
    return f"""
You are preparing text for an audiobook audio model.

Return only valid JSON with this shape:
{{
  "segments": [
    {{
      "order_index": 1,
      "text": "sentence text",
      "speaker": "narrator or character name",
      "role_type": "narrator or character"
    }}
  ]
}}

Rules:
- Split the chapter into speakable sentence or paragraph segments.
- Use role_type "narrator" for narration.
- Use role_type "character" for spoken character dialogue.
- Include every required audio field on each segment: {required}.
- Use this audio profile to choose field values:
{json.dumps(audio_profile.model_dump(), ensure_ascii=False, indent=2)}

Chapter title:
{chapter.title}

Chapter text:
{chapter.text}
""".strip()
