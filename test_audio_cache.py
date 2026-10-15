import queue
import tempfile
import threading
import unittest
import numpy as np
from audio_cache import AudioCache
from chapter_audio import read_book


class CacheTests(unittest.TestCase):
    def test_replay_avoids_engine_and_seek_preserves_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = AudioCache(folder)
            samples = np.arange(24000, dtype=np.float32)
            cache.put('Hello.', 'af_heart', 1, samples, 24000, [])
            played = []
            class Stream:
                def __init__(self, **kwargs): pass
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def write(self, block): played.extend(block[:, 0])
            def engine(): raise AssertionError('Cached replay loaded engine')
            read_book(engine, ['Hello.'], 0, 1, [0], 'af_heart', 1,
                      threading.Event(), threading.Event(), queue.Queue(), Stream,
                      cache=cache, start_seconds=.5, buffer_seconds=12)
            np.testing.assert_array_equal(played, samples[12000:])

    def test_voice_speed_corruption_and_quota(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = AudioCache(folder, limit=10000)
            cache.put('One', 'af_heart', 1, np.ones(1000), 24000, [])
            self.assertIsNone(cache.get('One', 'af_bella', 1))
            self.assertIsNone(cache.get('One', 'af_heart', 2))
            cache.path('One', 'af_heart', 1).write_bytes(b'broken')
            self.assertIsNone(cache.get('One', 'af_heart', 1))
            for i in range(5):
                cache.put(str(i), 'af_heart', 1, np.ones(1000), 24000, [])
            self.assertLessEqual(sum(p.stat().st_size for p in cache.folder.glob('*.npz')), 10000)

    def test_buffer_short_chapters_does_not_deadlock(self):
        cancel = threading.Event()
        class Engine:
            def create(self, text, **kwargs): return np.ones(512), 24000
        class Stream:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, block): pass
            def abort(self): pass
        timer = threading.Timer(3, cancel.set)
        timer.start()
        try:
            read_book(Engine(), ['a', 'b', 'c'], 0, 3, [0, 1, 2], 'af_heart', 1,
                      cancel, threading.Event(), queue.Queue(), Stream, buffer_seconds=12)
            self.assertFalse(cancel.is_set())
        finally:
            timer.cancel()
