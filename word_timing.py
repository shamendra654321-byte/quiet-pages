"""Align visible words to the voice model's phoneme timestamps."""
import difflib
import re


def word_timings(text, spoken, phonemize):
    words = list(re.finditer(r'\S+', text))
    if not spoken or not words:
        return []
    expected, owners = [], []
    for number, word in enumerate(words):
        sounds = phonemize(word.group())
        if expected:
            expected.append(' ')
            owners.append(number)
        expected.extend(sounds)
        owners.extend([number] * len(sounds))
    actual = ''.join(item.phoneme for item in spoken)
    matcher = difflib.SequenceMatcher(None, ''.join(expected), actual, autojunk=False)
    matches = matcher.get_matching_blocks()
    if sum(block.size for block in matches) < len(actual) * 0.45:
        return []  # Never invent evenly-spaced word timestamps.
    assigned = [None] * len(actual)
    for block in matches:
        for offset in range(block.size):
            assigned[block.b + offset] = owners[block.a + offset]
    previous = 0
    for index, owner in enumerate(assigned):
        if owner is not None:
            previous = max(previous, owner)
        assigned[index] = previous
    spans = {}
    for item, owner in zip(spoken, assigned):
        if item.phoneme.isspace():
            continue
        if owner not in spans:
            spans[owner] = [item.start, item.end]
        else:
            spans[owner][1] = item.end
    return [(begin, finish, words[number].start(), words[number].end())
            for number, (begin, finish) in sorted(spans.items()) if finish > begin]


def speech_sections(text, first=False):
    """Small, sentence-aware pieces with exact offsets into the displayed text."""
    offset = 0
    limit = 220 if first else 450
    while offset < len(text):
        while offset < len(text) and text[offset].isspace():
            offset += 1
        if offset >= len(text):
            break
        maximum = min(len(text), offset + limit)
        candidates = []
        for match in re.finditer(r'[.!?][\"\u201d\u2019\x27]*\s+', text[offset:maximum + 1]):
            end = offset + match.end()
            prefix = text[offset:offset + match.start() + 1]
            if not re.search(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St|vs|etc)\.$', prefix, re.I):
                candidates.append(end)
        # Start with one short sentence; later group complete sentences.
        end = (candidates[0] if first else candidates[-1]) if candidates else maximum
        if not candidates and maximum < len(text):
            space = text.rfind(' ', offset, maximum + 1)
            if space > offset:
                end = space
        section = text[offset:end].rstrip()
        if section:
            yield offset, section
        offset = end
        first = False
        limit = 450
