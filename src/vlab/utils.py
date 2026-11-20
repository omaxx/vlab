from collections.abc import Hashable
from pathlib import Path
from typing import Any
import json

import _jsonnet
import yaml


def load_file(path: str) -> dict[Hashable, Any]:
    """Load local spec file as dict; format by extension: .yaml/.yml, .json, .jsonnet."""
    p = Path(path)
    data: object
    match p.suffix:
        case ".yaml" | ".yml":
            data = yaml.safe_load(p.read_text())
        case ".json":
            data = json.loads(p.read_text())
        case ".jsonnet":
            data = json.loads(_jsonnet.evaluate_file(str(p)))
        case _:
            raise ValueError(f"unsupported spec format: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"spec must be a mapping, got {type(data).__name__}: {path}")
    return data
