from storyscape.logging import setup_logging
from storyscape.tasks.queue import work_forever


def run() -> None:
    setup_logging()
    work_forever()
