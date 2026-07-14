"""Tests for render_engine: single-image render correctness."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from project_io import TextBoxDef
from render_engine import render_single, render_batch, _sanitize_filename


class TestRenderSingle(unittest.TestCase):
    def _white_template(self, w=800, h=600):
        return Image.new("RGBA", (w, h), (255, 255, 255, 255))

    def _box(self, variable="Name", x=100, y=100, w=400, h=60, align="center", linked_csv="0"):
        return TextBoxDef(
            id="b1", x=x, y=y, width=w, height=h,
            font_path="",  # will use default font fallback
            font_size=36, hex_color="#000000", variable=variable, align=align,
            linked_csv=linked_csv
        )

    def test_renders_text(self):
        """Render a single row and verify pixels changed in the text region."""
        template = self._white_template()
        box = self._box(variable="Name")
        datasets = {"0": {"headers": ["Name"], "rows": [{"Name": "Alice"}]}}

        result = render_single(template, [box], datasets, 0)

        # Sample a region where text should be — the center of the box
        cx = int(box.x + box.width / 2)
        cy = int(box.y + box.height / 2)
        region = result.crop((cx - 20, cy - 10, cx + 20, cy + 10))
        pixels = list(region.get_flattened_data())
        non_white = [p for p in pixels if p[:3] != (255, 255, 255)]
        self.assertTrue(len(non_white) > 0, "Expected non-white pixels where text was drawn")

    def test_unmapped_variable_skipped(self):
        """If a variable has no mapping, the template should be unchanged."""
        template = self._white_template()
        box = self._box(variable="MissingVar")
        datasets = {"0": {"headers": ["Name"], "rows": [{"Name": "Alice"}]}}

        result = render_single(template, [box], datasets, 0)
        self.assertEqual(list(template.get_flattened_data()), list(result.get_flattened_data()))

    def test_empty_text_skipped(self):
        """If the CSV value is empty string, no text drawn."""
        template = self._white_template()
        box = self._box(variable="Name")
        datasets = {"0": {"headers": ["Name"], "rows": [{"Name": ""}]}}

        result = render_single(template, [box], datasets, 0)
        self.assertEqual(list(template.get_flattened_data()), list(result.get_flattened_data()))


class TestRenderBatch(unittest.TestCase):
    def test_batch_produces_files(self):
        """Batch render 3 rows → 3 PNG files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal template
            tpl_path = Path(tmpdir) / "template.png"
            Image.new("RGBA", (400, 300), "white").save(tpl_path)

            box = TextBoxDef(
                id="b1", x=50, y=50, width=300, height=50,
                font_path="", font_size=24,
                hex_color="#000000", variable="Name", linked_csv="0"
            )
            rows = [
                {"ID": "cert_001", "Name": "Alice"},
                {"ID": "cert_002", "Name": "Bob"},
                {"ID": "cert_003", "Name": "Carol"},
            ]
            datasets = {"0": {"headers": ["ID", "Name"], "rows": rows}}
            out_dir = Path(tmpdir) / "output"

            progress_log = []
            outputs = render_batch(
                str(tpl_path), [box], datasets, 3,
                str(out_dir), "[0] ID",
                progress_cb=lambda c, t: progress_log.append((c, t)),
            )

            self.assertEqual(len(outputs), 3)
            for p in outputs:
                self.assertTrue(p.exists())
                self.assertTrue(p.name.endswith(".png"))

            self.assertEqual(
                [p.stem for p in outputs],
                ["cert_001", "cert_002", "cert_003"],
            )
            self.assertEqual(progress_log, [(1, 3), (2, 3), (3, 3)])


class TestSanitizeFilename(unittest.TestCase):
    def test_removes_invalid_chars(self):
        self.assertEqual(_sanitize_filename('a<b>c:d"e'), "a_b_c_d_e")

    def test_empty_becomes_unnamed(self):
        self.assertEqual(_sanitize_filename(""), "unnamed")

    def test_normal_passthrough(self):
        self.assertEqual(_sanitize_filename("cert_001"), "cert_001")


if __name__ == "__main__":
    unittest.main()
