import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import app
from reader_core import Book, Chapter


class SilentStream:
    def __init__(self, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def write(self, data): pass
    def abort(self): pass


class FakeEngine:
    def __init__(self): self.spoken = []
    def create(self, text, **kwargs):
        self.spoken.append(text)
        return np.zeros(2048, dtype=np.float32), 24000


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(app, 'DATA', Path(self.temp.name))
        self.patch.start()
        self.root = tk.Tk()
        self.reader = app.Reader(self.root)
        self.engine = FakeEngine()
        self.reader.engine = self.engine
        book = Book([Chapter('One', ['First.', 'More.']), Chapter('Two', ['Last.'])])
        self.reader.events.put(('book', ('Test', book, 'test-book')))
        self.reader.poll()
        self.reader.set_busy(False)

    def tearDown(self):
        self.root.destroy()
        self.patch.stop()
        self.temp.cleanup()

    def run_playback(self):
        with patch('sounddevice.OutputStream', SilentStream):
            self.reader.start()
            deadline = time.monotonic() + 5
            while self.reader.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
            self.assertFalse(self.reader.busy)

    def test_stop_after_chapter_then_resume_next(self):
        self.reader.chapter_only.set(True)
        self.run_playback()
        self.assertEqual(self.engine.spoken, ['First.', 'More.'])
        self.assertEqual(self.reader.index, 2)
        self.assertEqual(self.reader.chapter_picker.current(), 1)
        self.run_playback()
        self.assertEqual(self.engine.spoken, ['First.', 'More.', 'Last.'])

    def test_continuous_and_saved_position(self):
        self.run_playback()
        self.assertEqual(self.engine.spoken, ['First.', 'More.', 'Last.'])
        self.reader.move_chapter(-1)
        self.assertEqual(self.reader.index, 0)
        self.reader.chapter_picker.current(1)
        self.reader.select_chapter()
        self.assertEqual(self.reader.saved['test-book'], 2)

    def test_controls_fit_small_window(self):
        self.root.geometry('720x550')
        self.root.update()
        for widget in (self.reader.chapter_picker, self.reader.chapter_option, self.reader.play, self.reader.status):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())


if __name__ == '__main__':
    unittest.main()
