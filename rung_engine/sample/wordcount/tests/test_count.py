import unittest

from wordcount import count_words


class CountWords(unittest.TestCase):
    def test_spaces(self):
        self.assertEqual(count_words("one two three"), 3)

    def test_any_whitespace(self):
        self.assertEqual(count_words("one\ttwo\nthree  four"), 4)

    def test_empty(self):
        self.assertEqual(count_words(""), 0)


if __name__ == "__main__":
    unittest.main()
