import queue
import threading
import unittest
import numpy as np
from chapter_audio import read_chapter


class ChapterAudioTests(unittest.TestCase):
    def test_entire_chapter_generated_before_single_stream_and_no_missing_samples(self):
        order, played = [], []
        class Engine:
            def create(self, text, **kwargs):
                order.append(text)
                return np.full(1700, int(text), dtype=np.float32), 24000
        class Stream:
            def __init__(self, **kwargs):
                self.assert_generated = list(order)
                order.append('stream')
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data): played.extend(data[:, 0])
        events = queue.Queue()
        read_chapter(Engine(), ['1', '2', '3'], 0, 3, 'af_heart', 1,
                     threading.Event(), threading.Event(), events, Stream)
        self.assertEqual(order, ['1', '2', '3', 'stream'])
        self.assertEqual(played, [1] * 1700 + [2] * 1700 + [3] * 1700)
        self.assertEqual([v for k, v in list(events.queue) if k == 'position'], [0, 1, 2])

    def test_cancel_during_preparation_never_opens_audio(self):
        cancel = threading.Event()
        class Engine:
            def create(self, text, **kwargs):
                cancel.set()
                return np.ones(100), 24000
        def stream(**kwargs):
            self.fail('Cancelled chapter should not play')
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
        self.assertEqual([v for k, v in list(events.queue) if k == 'position'], [0])
