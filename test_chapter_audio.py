import queue
import threading
import unittest
import numpy as np
from chapter_audio import read_chapter, read_book


def positions(events):
    return [value[2] for kind, value in list(events.queue) if kind == 'at' and value[1] == 'position']


class ChapterAudioTests(unittest.TestCase):
    def test_starts_before_remaining_audio_and_preserves_every_sample(self):
        first_write = threading.Event()
        played, opened = [], []
        class Engine:
            def create(self, text, **kwargs):
                if text == '2':
                    assert first_write.wait(2), 'Playback waited for the whole chapter'
                return np.full(1700, int(text), dtype=np.float32), 24000
        class Stream:
            def __init__(self, **kwargs): opened.append(True)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data):
                first_write.set()
                played.extend(data[:, 0])
        events = queue.Queue()
        read_chapter(Engine(), ['1', '2', '3'], 0, 3, 'af_heart', 1,
                     threading.Event(), threading.Event(), events, Stream)
        self.assertEqual(opened, [True])
        self.assertEqual(played, [1] * 1700 + [2] * 1700 + [3] * 1700)
        self.assertEqual(positions(events), [0, 1, 2])

    def test_next_chapter_prepares_during_first_and_uses_same_stream(self):
        following_ready = threading.Event()
        played, opened = [], []
        class Engine:
            def create(self, text, **kwargs):
                if text == '2': following_ready.set()
                return np.full(1700, int(text), dtype=np.float32), 24000
        class Stream:
            def __init__(self, **kwargs): opened.append(True)
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data):
                if not played:
                    assert following_ready.wait(2), 'Next chapter was not prepared during playback'
                played.extend(data[:, 0])
        read_book(Engine(), ['1', '2'], 0, 2, [0, 1], 'af_heart', 1,
                  threading.Event(), threading.Event(), queue.Queue(), Stream)
        self.assertEqual(opened, [True])
        self.assertEqual(played, [1] * 1700 + [2] * 1700)

    def test_cancel_during_preparation_never_opens_audio(self):
        cancel = threading.Event()
        class Engine:
            def create(self, text, **kwargs):
                cancel.set()
                return np.ones(100), 24000
        def stream(**kwargs): self.fail('Cancelled chapter should not play')
        read_chapter(Engine(), ['One', 'Two'], 0, 2, 'af_heart', 1, cancel,
                     threading.Event(), queue.Queue(), stream)

    def test_stop_during_playback_aborts_without_advancing_bookmark(self):
        cancel, events = threading.Event(), queue.Queue()
        calls = []
        class Engine:
            def create(self, text, **kwargs): return np.ones(3000), 24000
        class Stream:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data): cancel.set()
            def abort(self): calls.append('abort')
        read_chapter(Engine(), ['One', 'Two'], 0, 2, 'af_heart', 1, cancel,
                     threading.Event(), events, Stream)
        self.assertEqual(calls, ['abort'])
        self.assertEqual(positions(events), [0])

    def test_generation_error_propagates_without_hanging(self):
        class Engine:
            def create(self, text, **kwargs): raise ValueError('generation failed')
        with self.assertRaisesRegex(ValueError, 'generation failed'):
            read_chapter(Engine(), ['One'], 0, 1, 'af_heart', 1, threading.Event(),
                         threading.Event(), queue.Queue(), lambda **kwargs: None)

    def test_pause_holds_audio_but_allows_preparation(self):
        paused, prepared = threading.Event(), threading.Event()
        calls = []
        class Engine:
            def create(self, text, **kwargs):
                if text == 'Two': prepared.set()
                return np.ones(3000), 24000
        class Stream:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data):
                if not calls:
                    calls.append('write')
                    paused.set()
            def stop(self):
                assert prepared.wait(2)
                calls.append('pause')
                paused.clear()
            def start(self): calls.append('resume')
        read_chapter(Engine(), ['One', 'Two'], 0, 2, 'af_heart', 1,
                     threading.Event(), paused, queue.Queue(), Stream)
        self.assertEqual(calls, ['write', 'pause', 'resume'])
