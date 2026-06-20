import asyncio
import json
from pathlib import Path

from storyscape.chapters.store import ChapterStore
from storyscape.llm_text.openrouter_client import complete_json
from storyscape.llm_text.prompt import build_prompt
from storyscape.llm_text.schemas import AudioProfile, TextTaskOutput
from storyscape.tasks.store import TaskStore


def llm_text_job(task_id: str, chapter_id: str, audio_profile_data: dict) -> None:
    store = TaskStore()
    try:
        store.update(task_id, "running")
        chapter = ChapterStore().find_chapter(chapter_id)
        if chapter is None:
            raise ValueError(f"Chapter not found: {chapter_id}")

        audio_profile = AudioProfile.model_validate(audio_profile_data)
        result, raw = asyncio.run(complete_json(build_prompt(chapter, audio_profile)))
        _validate_required_fields(result.model_dump(), audio_profile)

        output = TextTaskOutput(
            chapter_id=chapter_id,
            audio_profile=audio_profile,
            result=result,
            raw_model_output=raw,
        )
        output_path = _output_path(task_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        store.update(task_id, "done", result_path=output_path)
    except Exception as exc:
        store.update(task_id, "failed", error=str(exc))
        raise


def _validate_required_fields(result_data: dict, audio_profile: AudioProfile) -> None:
    required = set(audio_profile.required_fields)
    for segment in result_data["segments"]:
        missing = [field for field in required if field not in segment]
        if missing:
            raise ValueError(f"Segment {segment.get('order_index')} missing required fields: {missing}")


def _output_path(task_id: str) -> Path:
    task = TaskStore().require(task_id)
    return task.run_dir / "text_tasks" / f"{task_id}.json"
