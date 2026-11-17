"""日志：控制台 + 可选文件双通道。"""
from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(verbose: bool = False, logfile: str | None = None) -> None:
    """初始化 chinaboundary 的日志器（控制台必开，文件可选）。"""
    logger = logging.getLogger("chinaboundary")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(console)

    if logfile:
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(fh)
