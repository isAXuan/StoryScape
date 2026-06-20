# StoryScape

StoryScape is a local Python MVP for two audiobook preparation tasks:

- Create chapter parsing tasks for registered local TXT/EPUB books.
- Create LLM text annotation tasks for chapter role/narrator segmentation.

The project stores each task run under `data/{resource_id}_{task_uuid}/` and uses a local SQLite queue for async task execution.

## Setup

```bash
uv sync --extra dev
cp .env.example .env
```

Set `OPENROUTER_API_KEY` in `.env` when running real `llm_text` jobs.

## Run

```bash
uv run storyscape-api
uv run storyscape-worker
```

Command entry points:

- `storyscape-api = "storyscape.main:run"`: starts the FastAPI service.
- `storyscape-worker = "storyscape.workers.local_worker:run"`: starts the local SQLite worker for queued tasks.
- `storyscape-inspect = "storyscape.scripts.inspect:run"`: prints registered sample books and task files for local debugging.

## Endpoints

- `POST /books/{book_id}/chapters/parse`
- `POST /chapters/{chapter_id}/text-task`
- `GET /tasks/{task_id}`

## Manual Chapter Parse

Run chapter parsing directly without the API/worker:

```bash
uv run python -c "from storyscape.tasks.store import TaskStore; from storyscape.chapters.jobs import parse_chapters_job; store=TaskStore(); task=store.create('chapter_parse','光阴之外_utf8'); parse_chapters_job(task.task_id,'光阴之外_utf8'); print(task.task_id); print(task.run_dir)"
```

Expected output shape:

```text
task_1ae7575d
data/光阴之外_utf8_1ae7575d
```

Books for local development are registered in `samples/books.yml`.
