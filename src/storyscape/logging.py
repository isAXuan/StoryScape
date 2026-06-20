import sys

from loguru import logger

from storyscape.settings import get_settings


def setup_logging() -> None:
    settings = get_settings()
    log_dir = settings.storyscape_log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    # 保留默认 stderr 输出，再加文件 sink
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        log_dir / "storyscape_{time:YYYY-MM-DD}.log",
        rotation="00:00",    # 每天零点换文件
        retention="7 days",  # 保留 7 天
        encoding="utf-8",
        enqueue=True,        # 线程安全（worker 进程也适用）
        level="DEBUG",
    )
