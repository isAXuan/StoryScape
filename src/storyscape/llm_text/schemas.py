from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AudioProfile(BaseModel):
    audio_model: str
    required_fields: list[str] = Field(default_factory=list)
    voice_mapping: dict[str, dict[str, Any]] = Field(default_factory=dict)


class TextTaskRequest(BaseModel):
    audio_profile: AudioProfile


RoleType = Literal["narrator", "character"]


class TextSegment(BaseModel):
    order_index: int
    text: str
    speaker: str
    role_type: RoleType
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def collect_extra_fields(self) -> "TextSegment":
        extras: dict[str, Any] = {}
        for key, value in list(self.__pydantic_extra__.items() if self.__pydantic_extra__ else []):
            extras[key] = value
        self.extra = extras
        return self


class TextAnnotationResult(BaseModel):
    segments: list[TextSegment]


class TextTaskOutput(BaseModel):
    chapter_id: str
    audio_profile: AudioProfile
    result: TextAnnotationResult
    raw_model_output: str
