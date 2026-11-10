import unittest

from prices import total_with_tax


class TotalTests(unittest.TestCase):
    def test_total_with_tax(self):
        result = total_with_tax([10, 20], rate=0.1)
        self.assertEqual(result, total_with_tax([10, 20], rate=0.1))


if __name__ == "__main__":
    unittest.main()
