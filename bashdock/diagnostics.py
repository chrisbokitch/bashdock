"""Make errors available when Windows launches the app without a console."""
import logging
import sys
from .config import config_path


def initialize():
    path = config_path().with_name("bashdock.log")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        if sys.stderr is None or sys.stdout is None:
            stream = path.open("a", encoding="utf-8", buffering=1)
            if sys.stderr is None:
                sys.stderr = stream
            if sys.stdout is None:
                sys.stdout = stream
        logging.info("Starting BashDock (packaged=%s)", bool(getattr(sys, "frozen", False)))
    except OSError:
        pass
