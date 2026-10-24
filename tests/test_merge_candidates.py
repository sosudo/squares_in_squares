import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from merge_candidates import candidate_file, choose_one
from validate_submission import Square, validate_puzzle


class MergeTests(unittest.TestCase):
    def test_exact_decimal_strings_survive_json_input(self):
        coordinate = '0.50000000000000000000000000000000000000000000000000000000000001'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.json'
            path.write_text(json.dumps({'1': {'squares': [[coordinate, '0.5', '0']]}}))
            self.assertEqual(candidate_file(path)[1][0].x, coordinate)

    def test_invalid_best_looking_candidate_is_rejected(self):
        baseline = [Square('0.5', '0.5', '0'), Square('1.500001', '0.5', '0')]
        valid = [Square('0.5', '0.5', '0'), Square('1.5', '0.5', '0')]
        overlap = [Square('0.5', '0.5', '0'), Square('1.499999999999999999999999', '0.5', '0')]
        result = choose_one((2, baseline, validate_puzzle(2, baseline),
                             [(1.999999, 'invalid', overlap), (2.0, 'exact', valid)]))
        self.assertEqual(result[1], valid)
        self.assertEqual(result[3], 'exact')
        self.assertEqual(result[4][0]['source'], 'invalid')

    def test_duplicate_square_id_rejected_even_if_row_count_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.csv'
            path.write_text('id,n,square_id,x,y,angle\n0,2,0,0.5,0.5,0\n1,2,0,1.5,0.5,0\n')
            self.assertEqual(candidate_file(path), {})


if __name__ == '__main__':
    unittest.main()
