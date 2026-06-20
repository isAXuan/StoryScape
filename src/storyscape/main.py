import uvicorn
from fastapi import FastAPI

from storyscape.chapters.api import router as chapters_router
from storyscape.llm_text.api import router as llm_text_router
from storyscape.logging import setup_logging
from storyscape.tasks.api import router as tasks_router


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="StoryScape", version="0.1.0")
    app.include_router(chapters_router)
    app.include_router(llm_text_router)
    app.include_router(tasks_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("storyscape.main:app", host="127.0.0.1", port=8000, reload=False)
