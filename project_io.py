"""project_io.py — Save/load project JSON files.

Data contract matches PROJECT_MAP.md exactly.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List
import uuid


@dataclass
class TextBoxDef:
    """One text overlay region on the certificate template."""
    id: str
    x: float
    y: float
    width: float
    height: float
    font_path: str
    font_size: int
    hex_color: str
    variable: str
    align: str = "center"  # "left", "center", "right"
    linked_csv: str = ""   # ID/name of the linked CSV

    def __post_init__(self):
        if self.align not in ("left", "center", "right"):
            raise ValueError(f"align must be left/center/right, got {self.align!r}")
        if not self.variable:
            raise ValueError("variable must not be empty")
        if self.font_size < 1:
            raise ValueError(f"font_size must be >= 1, got {self.font_size}")


def new_box_id() -> str:
    """Generate a short unique box ID."""
    return f"box_{uuid.uuid4().hex[:8]}"


def save_project(path: str | Path, template_path: str, text_boxes: List[TextBoxDef]) -> None:
    """Write a project file to disk."""
    data = {
        "template_path": template_path,
        "text_boxes": [asdict(box) for box in text_boxes],
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> tuple[str, List[TextBoxDef]]:
    """Read a project file from disk.

    Returns (template_path, text_boxes).
    Raises ValueError on invalid data.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Cannot read project file: {e}") from e

    if not isinstance(raw, dict):
        raise ValueError("Project file must be a JSON object")

    template_path = raw.get("template_path", "")
    if not template_path:
        raise ValueError("Missing template_path in project file")

    boxes_raw = raw.get("text_boxes", [])
    if not isinstance(boxes_raw, list):
        raise ValueError("text_boxes must be a list")

    text_boxes = []
    required = {"id", "x", "y", "width", "height", "font_path", "font_size", "hex_color", "variable"}
    for i, box_data in enumerate(boxes_raw):
        missing = required - set(box_data.keys())
        if missing:
            raise ValueError(f"text_boxes[{i}] missing fields: {missing}")
        try:
            text_boxes.append(TextBoxDef(
                id=str(box_data["id"]),
                x=float(box_data["x"]),
                y=float(box_data["y"]),
                width=float(box_data["width"]),
                height=float(box_data["height"]),
                font_path=str(box_data["font_path"]),
                font_size=int(box_data["font_size"]),
                hex_color=str(box_data["hex_color"]),
                variable=str(box_data["variable"]),
                align=str(box_data.get("align", "center")),
                linked_csv=str(box_data.get("linked_csv", "")),
            ))
        except (TypeError, ValueError) as e:
            raise ValueError(f"text_boxes[{i}] invalid: {e}") from e

    return template_path, text_boxes
