"""Tests for data_engine: CSV parsing, auto-mapping, validation."""

import unittest

from project_io import TextBoxDef
from data_engine import parse_csv_text, auto_map, validate_mapping


def _box(variable: str) -> TextBoxDef:
    """Shortcut: create a minimal TextBoxDef with just a variable name."""
    return TextBoxDef(
        id="b", x=0, y=0, width=100, height=50,
        font_path="", font_size=12, hex_color="#000", variable=variable,
    )


class TestParseCsv(unittest.TestCase):
    def test_basic(self):
        csv = "Name,Email\nAlice,a@b.com\nBob,b@c.com\n"
        headers, rows = parse_csv_text(csv)
        self.assertEqual(headers, ["Name", "Email"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Name"], "Alice")
        self.assertEqual(rows[1]["Email"], "b@c.com")

    def test_empty_header_raises(self):
        with self.assertRaises(ValueError):
            parse_csv_text("")

    def test_no_data_rows_raises(self):
        with self.assertRaises(ValueError):
            parse_csv_text("A,B\n")


class TestAutoMap(unittest.TestCase):
    def test_exact_match(self):
        headers = ["First_Name", "Last_Name"]
        boxes = [_box("First_Name"), _box("Last_Name")]
        result = auto_map(headers, boxes)
        self.assertEqual(result, {"First_Name": "First_Name", "Last_Name": "Last_Name"})

    def test_case_insensitive(self):
        headers = ["first_name"]
        boxes = [_box("First_Name")]
        result = auto_map(headers, boxes)
        self.assertEqual(result, {"First_Name": "first_name"})

    def test_normalized_match(self):
        headers = ["First Name"]
        boxes = [_box("First_Name")]
        result = auto_map(headers, boxes)
        self.assertEqual(result, {"First_Name": "First Name"})

    def test_no_match(self):
        headers = ["Email"]
        boxes = [_box("Phone")]
        result = auto_map(headers, boxes)
        self.assertEqual(result, {})


class TestValidateMapping(unittest.TestCase):
    def test_all_mapped(self):
        headers = ["A", "B"]
        boxes = [_box("X"), _box("Y")]
        mapping = {"X": "A", "Y": "B"}
        self.assertEqual(validate_mapping(mapping, headers, boxes), [])

    def test_unmapped(self):
        headers = ["A"]
        boxes = [_box("X"), _box("Y")]
        mapping = {"X": "A"}
        self.assertEqual(validate_mapping(mapping, headers, boxes), ["Y"])

    def test_mapped_to_nonexistent_header(self):
        headers = ["A"]
        boxes = [_box("X")]
        mapping = {"X": "NOPE"}
        self.assertEqual(validate_mapping(mapping, headers, boxes), ["X"])


if __name__ == "__main__":
    unittest.main()
