"""render_engine.py — Pillow-based batch certificate renderer.

Implements the SYSTEM_FLOW step 3 from PROJECT_MAP.md.
"""

import re
from pathlib import Path
from typing import Callable, List, Optional

from PIL import Image, ImageDraw, ImageFont

from project_io import TextBoxDef


def render_single(template_img: Image.Image, text_boxes: List[TextBoxDef],
                  datasets: dict[str, dict], row_index: int) -> Image.Image:
    """Render one certificate by stamping text onto a copy of the template.

    Args:
        template_img: Base certificate image (not modified).
        text_boxes: List of text overlay definitions.
        datasets: Dict of loaded CSV datasets.
        row_index: The current batch generation index.

    Returns:
        A new PIL Image with text drawn.
    """
    img = template_img.copy()
    draw = ImageDraw.Draw(img)

    for box in text_boxes:
        tab_id = box.linked_csv
        header = box.variable
        if not tab_id or tab_id not in datasets or not header:
            continue
        
        rows = datasets[tab_id]["rows"]
        if not rows:
            continue
        
        # Zip longest logic: if row_index exceeds this CSV's length, use its last row (broadcasting)
        r_idx = min(row_index, len(rows) - 1)
        text = str(rows[r_idx].get(header, ""))
        if not text:
            continue

        try:
            font = ImageFont.truetype(box.font_path, box.font_size)
        except OSError:
            # ponytail: fall back to default font if .ttf not found.
            # Upgrade path: surface this as a warning in the UI.
            font = ImageFont.load_default(size=box.font_size)

        # Compute horizontal offset for alignment within the bounding box
        text_width = font.getlength(text)
        if box.align == "center":
            x_offset = box.x + (box.width - text_width) / 2
        elif box.align == "right":
            x_offset = box.x + box.width - text_width
        else:  # left
            x_offset = box.x

        # Vertical: center text within box height
        bbox = font.getbbox(text)
        text_height = bbox[3] - bbox[1]
        y_offset = box.y + (box.height - text_height) / 2 - bbox[1]

        draw.text((x_offset, y_offset), text, font=font, fill=box.hex_color)

    return img


def render_batch(template_path: str, text_boxes: List[TextBoxDef],
                 datasets: dict[str, dict], max_rows: int,
                 output_dir: str | Path, id_column: str,
                 progress_cb: Optional[Callable[[int, int], None]] = None) -> List[Path]:
    """Batch-render all CSV rows into individual certificate PNGs.

    Args:
        template_path: Path to the base template PNG.
        text_boxes: Text overlay definitions.
        datasets: Dict of loaded CSV datasets.
        max_rows: The total number of rows to iterate.
        output_dir: Directory to write output PNGs.
        id_column: Formatted string like "[tab_id] HeaderName" to get the filename.
        progress_cb: Optional callback(current_index, total_count).

    Returns:
        List of output file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    template_img = Image.open(template_path).convert("RGBA")
    total = max_rows
    outputs = []

    # Parse id_column format e.g. "[tab_id] HeaderName"
    id_tab = None
    id_header = None
    if id_column and id_column.startswith("[") and "]" in id_column:
        id_tab, id_header = id_column[1:].split("]", 1)
        id_header = id_header.strip()

    for i in range(max_rows):
        img = render_single(template_img, text_boxes, datasets, i)
        
        # Get filename
        filename_val = f"cert_{i}"
        if id_tab and id_tab in datasets and id_header:
            rows = datasets[id_tab]["rows"]
            if rows:
                r_idx = min(i, len(rows) - 1)
                filename_val = str(rows[r_idx].get(id_header, filename_val))
                
        filename = _sanitize_filename(filename_val)
        out_path = output_dir / f"{filename}.png"
        img.save(out_path)
        outputs.append(out_path)

        if progress_cb:
            progress_cb(i + 1, total)

    return outputs


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in Windows filenames."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip('. ')
    return cleaned or "unnamed"
