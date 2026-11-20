from collections.abc import Hashable
from pathlib import Path
from typing import Any
import json

import _jsonnet
import yaml


def load_file(path: str) -> dict[Hashable, Any]:
    """Load local spec file as dict; format by extension: .yaml/.yml, .json, .jsonnet."""
    p = Path(path)
    match p.suffix:
        case ".yaml" | ".yml":
            return yaml.safe_load(p.read_text())
        case ".json":
            return json.loads(p.read_text())
        case ".jsonnet":
            return json.loads(_jsonnet.evaluate_file(str(p)))
        case _:
            raise ValueError(f"unsupported spec format: {path}")
