# PROJECT_MAP.md

**Project:** IEEE Certificate/Badge Batch Generator
**Status:** v1 (MVP) — **Implemented**, 2026-07-14 · 27/27 tests passing
**Owner role:** Staff Engineer / Tech Lead (this document is the source of truth for scope and architecture)

---

## SCOPE DECISIONS (do not re-litigate without updating this file)

| Decision | Answer | Rationale |
|---|---|---|
| Target OS | **Windows only** | Single build target = single PyInstaller pipeline, no cross-compile complexity. |
| Google Drive upload | **OUT OF SCOPE for v1** | Deferred to Phase 2. Ship the core generator first; Drive is an add-on, not a dependency of the core value (batch-generating certificates). |
| Drive auth model (Phase 2, pre-decided so we don't re-debate later) | Per-user OAuth (each member signs in with their own Google account) | Simpler to build (standard OAuth installed-app flow), no service-account credential distribution/security burden on the branch. |
| Containerization (Docker) | **Rejected** | This is a native desktop GUI app shipped as a standalone .exe. Docker solves environment-parity/server problems this project doesn't have, and doesn't natively render GUI windows. A plain Python venv is sufficient for dev; PyInstaller handles distribution. Revisit only if a CI build server is introduced later. |
| Data library | Python stdlib `csv`, not pandas | Task is column→variable mapping only. Pandas is unjustified weight for this. |
| Persistence | Flat JSON project file | No relational needs; a single template + list of text-box definitions doesn't warrant SQLite. |

---

## TECH_STACK

| Layer | Choice | Version (as of Jul 2026) | Why |
|---|---|---|---|
| Language | Python | 3.12 | Stable, fully supported by all deps below. |
| UI framework | PySide6 | ~6.10.x | Official Qt-for-Python bindings, LGPL (no licensing friction vs. PyQt's GPL/commercial split). `QGraphicsView`/`QGraphicsScene` natively supports drag-and-drop bounding boxes on an image canvas. |
| Image rendering | Pillow | 12.3.0 | `ImageDraw` + `ImageFont.truetype()` for drawing text at exact coordinates onto the base PNG. |
| Data parsing | `csv` (stdlib) | — | Zero-dependency column/row parsing. |
| Project persistence | `json` (stdlib) | — | Stores template path + text-box definitions (position, font, size, color, variable binding). |
| Packaging | PyInstaller | ~6.21.x | Single-file/single-folder Windows executable so IEEE members need zero setup. |
| Dev environment | `venv` (stdlib) | — | No Docker (see rejection above). |

**No dependencies beyond:** `PySide6`, `Pillow`, `pyinstaller` (build-time only).

---

## SYSTEM_FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                     1. DESIGN CANVAS (UI)                   │
│  - Import base PNG (template)                                │
│  - Draw/drag bounding boxes on QGraphicsScene                │
│  - Per box: pick local .ttf, hex color, font size             │
│  - Per box: assign variable name (e.g. {{First_Name}})        │
│  - Save/load project as .json                                │
└──────────────────────────┬────────────────────────────────────┘
                           │ project.json (template path + box defs)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     2. DATA ENGINE                            │
│  - Load CSV, read header row → available variable names       │
│  - User confirms/maps CSV columns to box variables             │
│  - Preview Mode: inject row[0] values into canvas text boxes   │
│    so user visually verifies alignment/sizing before batch run │
└──────────────────────────┬────────────────────────────────────┘
                           │ confirmed mapping + full row list
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   3. RENDERING ENGINE (batch)                │
│  for row in csv_rows:                                         │
│      img = base_png.copy()                                    │
│      for box in text_boxes:                                   │
│          draw.text((box.x, box.y), row[box.variable],          │
│                     font=box.font, fill=box.hex_color)          │
│      img.save(output_dir / f"{row[id_col]}.png")               │
└─────────────────────────────────────────────────────────────┘
```

**Data contract (project.json shape):**
```json
{
  "template_path": "assets/certificate_base.png",
  "text_boxes": [
    {
      "id": "box_1",
      "x": 320, "y": 180, "width": 400, "height": 60,
      "font_path": "fonts/Montserrat-Bold.ttf",
      "font_size": 36,
      "hex_color": "#1A1A1A",
      "variable": "First_Name",
      "align": "center"
    }
  ]
}
```

---

## UI_LAYOUT

```
┌──────────────┬─────────────────────────────┬──────────────────┐
│  LEFT (20%)  │       CENTER (55%)          │   RIGHT (25%)    │
│              │                             │                  │
│ ┌──────────┐ │                             │ ┌──────────────┐ │
│ │ Preview  │ │                             │ │  Action      │ │
│ │ (Pillow  │ │                             │ │  Buttons     │ │
│ │ rendered)│ │     DESIGN CANVAS           │ │  (prominent  │ │
│ └──────────┘ │     (QGraphicsView)         │ │   colored)   │ │
│ ┌──────────┐ │                             │ └──────────────┘ │
│ │ CSV Data │ │     Drag/resize text        │ ┌──────────────┐ │
│ │ + Column │ │     boxes on template       │ │  Box         │ │
│ │ Mapping  │ │                             │ │  Properties  │ │
│ └──────────┘ │                             │ │  Editor      │ │
│              │                             │ └──────────────┘ │
├──────────────┴─────────────────────────────┴──────────────────┤
│                      Status Bar + Progress                     │
└────────────────────────────────────────────────────────────────┘
```

- **QSplitter**-based layout (not docks). Center column stretches on resize; sidebars stay fixed width.
- **Dark theme**: Fusion style + custom QPalette (dark grays, blue accent).
- **Action buttons**: Emoji-prefixed, color-coded by category (blue=import, green=data, orange=preview, red=generate).
- **Preview panel**: Renders actual Pillow output (not QPainter approximation) for pixel-accurate verification.
- **Logging**: `logging` module, INFO level, to stdout.

---

## OUT OF SCOPE (v1) — explicitly excluded to prevent feature creep
- Google Drive upload / OAuth (Phase 2)
- macOS / Linux builds
- Multi-line text auto-wrap beyond basic box-width clipping (add only if a real certificate needs it)
- Cloud storage, user accounts, or any server component
- Docker/containerization of any kind

---

## OPEN ITEMS FOR NEXT PLANNING PASS
- Confirm whether any certificate needs an **image variable** (e.g., a per-row QR code or headshot) vs. text-only — not mentioned yet, assumed text-only for v1.
- ~~Confirm output filename convention~~ — **Resolved**: driven by user-selectable CSV "ID" column, defaults to first column.

