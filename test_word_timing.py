import unittest
from types import SimpleNamespace
from word_timing import word_timings, speech_sections


def sounds(text):
    return [SimpleNamespace(phoneme=character, start=index * .1, end=(index + 1) * .1)
            for index, character in enumerate(text)]


class WordTimingTests(unittest.TestCase):
    def test_words_use_model_timing_and_character_offsets(self):
        text = 'Hello, world!'
        words = word_timings(text, sounds('helo, world!'), lambda word: {'Hello,': 'helo,', 'world!': 'world!'}[word])
        self.assertEqual([text[left:right] for _, _, left, right in words], ['Hello,', 'world!'])
        self.assertAlmostEqual(words[1][0], .6)
        self.assertAlmostEqual(words[1][1], 1.2)

    def test_number_expansion_stays_on_original_number(self):
        text = 'Read 2026 now.'
        mapping = {'Read': 'reed', '2026': 'twenty twenty six', 'now.': 'now.'}
        words = word_timings(text, sounds('reed twenty twenty six now.'), mapping.get)
        self.assertEqual([text[a:b] for _, _, a, b in words], ['Read', '2026', 'now.'])
        self.assertGreater(words[1][1] - words[1][0], 1)

    def test_missing_or_unreliable_timing_is_not_fabricated(self):
        self.assertEqual(word_timings('Hello', [], lambda _: 'hello'), [])
        self.assertEqual(word_timings('Hello', sounds('xxxxxxxxx'), lambda _: 'hello'), [])

    def test_small_opening_and_complete_text_preservation(self):
        text = 'Dr. Jones arrived. ' + 'The rain fell quietly. ' * 70
        sections = list(speech_sections(text, first=True))
        self.assertEqual(sections[0][1], 'Dr. Jones arrived.')
        self.assertEqual(' '.join(section for _, section in sections), ' '.join(text.split()))
        for offset, section in sections:
            self.assertEqual(text[offset:offset + len(section)], section)
            self.assertLessEqual(len(section), 450)

    def test_long_unpunctuated_input_remains_bounded(self):
        text = 'word ' * 1000
        chunks = list(speech_sections(text, first=True))
        self.assertLessEqual(len(chunks[0][1]), 220)
        self.assertEqual(' '.join(s for _, s in chunks), text.strip())
