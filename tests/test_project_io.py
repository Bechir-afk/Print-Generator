"""Tests for project_io: save/load round-trip and validation."""

import json
import tempfile
import unittest
from pathlib import Path

from project_io import TextBoxDef, save_project, load_project, new_box_id


class TestTextBoxDef(unittest.TestCase):
    def test_valid_creation(self):
        box = TextBoxDef(
            id="box_1", x=100, y=200, width=300, height=50,
            font_path="font.ttf", font_size=36,
            hex_color="#FF0000", variable="Name",
        )
        self.assertEqual(box.align, "center")

    def test_invalid_align_raises(self):
        with self.assertRaises(ValueError):
            TextBoxDef(
                id="box_1", x=0, y=0, width=100, height=50,
                font_path="", font_size=12,
                hex_color="#000", variable="X", align="justify",
            )

    def test_empty_variable_raises(self):
        with self.assertRaises(ValueError):
            TextBoxDef(
                id="box_1", x=0, y=0, width=100, height=50,
                font_path="", font_size=12,
                hex_color="#000", variable="",
            )

    def test_bad_font_size_raises(self):
        with self.assertRaises(ValueError):
            TextBoxDef(
                id="box_1", x=0, y=0, width=100, height=50,
                font_path="", font_size=0,
                hex_color="#000", variable="X",
            )


class TestSaveLoad(unittest.TestCase):
    def _make_boxes(self):
        return [
            TextBoxDef(
                id="box_1", x=10, y=20, width=300, height=50,
                font_path="fonts/Bold.ttf", font_size=36,
                hex_color="#1A1A1A", variable="First_Name", align="center",
            ),
            TextBoxDef(
                id="box_2", x=10, y=100, width=300, height=50,
                font_path="fonts/Regular.ttf", font_size=24,
                hex_color="#333333", variable="Last_Name", align="left",
            ),
        ]

    def test_round_trip(self):
        boxes = self._make_boxes()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name

        save_project(path, "template.png", boxes)
        tpl, loaded = load_project(path)

        self.assertEqual(tpl, "template.png")
        self.assertEqual(len(loaded), 2)
        for orig, back in zip(boxes, loaded):
            self.assertEqual(orig.id, back.id)
            self.assertAlmostEqual(orig.x, back.x)
            self.assertAlmostEqual(orig.y, back.y)
            self.assertAlmostEqual(orig.width, back.width)
            self.assertAlmostEqual(orig.height, back.height)
            self.assertEqual(orig.font_path, back.font_path)
            self.assertEqual(orig.font_size, back.font_size)
            self.assertEqual(orig.hex_color, back.hex_color)
            self.assertEqual(orig.variable, back.variable)
            self.assertEqual(orig.align, back.align)

        Path(path).unlink()

    def test_load_bad_json_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("not json at all")
            path = f.name
        with self.assertRaises(ValueError):
            load_project(path)
        Path(path).unlink()

    def test_load_missing_template_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"text_boxes": []}, f)
            path = f.name
        with self.assertRaises(ValueError):
            load_project(path)
        Path(path).unlink()

    def test_load_missing_fields_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({
                "template_path": "t.png",
                "text_boxes": [{"id": "box_1"}],  # missing most fields
            }, f)
            path = f.name
        with self.assertRaises(ValueError):
            load_project(path)
        Path(path).unlink()


class TestNewBoxId(unittest.TestCase):
    def test_unique(self):
        ids = {new_box_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_format(self):
        self.assertTrue(new_box_id().startswith("box_"))


if __name__ == "__main__":
    unittest.main()
