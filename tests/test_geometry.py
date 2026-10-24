"""Independent geometry checks; run python -m unittest discover -s tests."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_submission import Square, check_pair, read_submission, validate_puzzle


class GeometryTests(unittest.TestCase):
    def test_exact_touching_allowed(self):
        self.assertTrue(check_pair(Square("0.1", "0", "0"), Square("1.1", "0", "0")))

    def test_overlap_below_double_precision_rejected(self):
        a = Square("0", "0", "0")
        b = Square("0.999999999999999999999999999999", "0", "0")
        self.assertFalse(check_pair(a, b))
        self.assertFalse(validate_puzzle(2, [a, b])["valid"])

    def test_rotated_near_contact(self):
        a = Square("0", "0", "0.7853981633974483")
        self.assertTrue(check_pair(a, Square("1.414213562373096", "0", a.angle)))
        self.assertFalse(check_pair(a, Square("1.414213562373094", "0", a.angle)))

    def test_rotation_is_radians(self):
        result = validate_puzzle(1, [Square("0", "0", "0.7853981633974483")])
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(float(result["side_lower"]), 2**0.5)

    def test_translation_invariant_score_and_grid(self):
        a = [Square(str(x), str(y), "0") for x in range(2) for y in range(2)]
        b = [Square(str(x + 100), str(y - 99), "0") for x in range(2) for y in range(2)]
        for squares in (a, b):
            result = validate_puzzle(4, squares)
            self.assertTrue(result["valid"])
            self.assertEqual(float(result["side_lower"]), 2)
            self.assertEqual(float(result["score_upper"]), 0)

    def test_aabb_does_not_miss_tiny_overlap_at_large_translation(self):
        a = Square("1000000", "1000000", "0")
        b = Square("1000000.999999999999999999999999", "1000000", "0")
        self.assertFalse(validate_puzzle(2, [a, b])["valid"])

    def test_reject_invalid_decimal(self):
        for value in ("NaN", "inf", "1e400", "sqrt(2)"):
            with self.assertRaises(ValueError):
                validate_puzzle(1, [Square(value, "0", "0")])


class SchemaTests(unittest.TestCase):
    def read(self, rows, max_n=2):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "submission.csv"
            with path.open("w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["id", "n", "square_id", "x", "y", "angle"])
                writer.writerows(rows)
            return read_submission(path, max_n)

    def test_valid_complete_file(self):
        result = self.read([[0, 1, 0, 0, 0, 0], [1, 2, 0, 0, 0, 0], [2, 2, 1, 1, 0, 0]])
        self.assertEqual(list(result), [1, 2])

    def test_missing_puzzle_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing puzzles"):
            self.read([[0, 1, 0, 0, 0, 0]])

    def test_duplicate_row_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate row id"):
            self.read([[0, 1, 0, 0, 0, 0], [0, 2, 0, 0, 0, 0]])

    def test_duplicate_square_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate square_id"):
            self.read([[0, 1, 0, 0, 0, 0], [1, 2, 0, 0, 0, 0], [2, 2, 0, 1, 0, 0]])


if __name__ == "__main__":
    unittest.main()
