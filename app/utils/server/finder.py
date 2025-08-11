from collections import deque
from pathlib import Path

from escudeiro.autodiscovery import RuntimeAutoDiscovery, runtime_child_of

from app.utils.server.controller import DefaultController


def find(root: Path) -> None:
    finder = RuntimeAutoDiscovery(runtime_child_of(DefaultController), root)
    _ = deque(finder.load(), maxlen=0)  # Force the discovery to run
