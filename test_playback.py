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

    def test_rewind_crosses_passage_and_timer_stops(self):
        self.reader.index = 1
        self.reader.cursor = (1, 5)
        self.reader.durations[0] = 30
        self.reader.rewind()
        self.assertEqual(self.reader.cursor, (0, 20))
        self.reader.sleep_deadline = time.monotonic() - 1
        self.reader.poll()
        self.assertTrue(self.reader.cancel.is_set())
        self.assertIsNone(self.reader.sleep_deadline)

    def test_seek_waits_for_old_worker_before_restart(self):
        self.reader.playing = True
        self.reader.set_busy(True)
        self.reader.seek_to(1, 2)
        self.assertTrue(self.reader.cancel.is_set())
        self.assertEqual(self.reader.restart_at, (1, 2))
        self.assertTrue(self.reader.busy)

    def test_speed_changes_live_without_stop_or_play_and_preserves_pause(self):
        self.reader.playing = True
        self.reader.set_busy(True)
        self.reader.paused.set()
        self.reader.cursor = (1, 5)
        with patch.object(self.reader, 'stop') as stop, patch.object(self.reader, 'start') as start:
            self.reader.speed.set(1.7)
            self.assertEqual(self.reader.playback_speed.get(), 1.7)
            self.assertEqual(self.reader.cursor, (1, 5))
            self.assertTrue(self.reader.paused.is_set())
            stop.assert_not_called()
            start.assert_not_called()

    def test_continuous_and_saved_position(self):
        self.run_playback()
        self.assertEqual(self.engine.spoken, ['First.', 'More.', 'Last.'])
        self.reader.move_chapter(-1)
        self.assertEqual(self.reader.index, 0)
        self.reader.chapter_picker.current(1)
        self.reader.select_chapter()
        self.assertEqual(self.reader.saved['test-book']['index'], 2)

    def test_controls_fit_small_window(self):
        self.root.geometry('720x550')
        self.root.update()
        for widget in (self.reader.chapter_picker, self.reader.chapter_option, self.reader.play, self.reader.status):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())

    def test_chapter_text_stays_visible_with_reading_highlight(self):
        self.assertIn('First.\n\nMore.', self.reader.text.get('1.0', 'end'))
        self.reader.move(1)
        self.assertIn('First.\n\nMore.', self.reader.text.get('1.0', 'end'))
        ranges = self.reader.text.tag_ranges('reading')
        self.assertEqual(self.reader.text.get(*ranges), 'More.')

    def test_background_update_notice_does_not_interrupt_reading(self):
        self.reader.set_busy(True)
        self.reader.events.put(('update_found', ({'name': 'New release'}, False)))
        with patch('app.messagebox.showinfo') as info, patch('app.messagebox.askyesno') as prompt:
            self.reader.poll()
            info.assert_not_called()
            prompt.assert_not_called()
        self.assertTrue(self.reader.busy)
        self.assertEqual(self.reader.update_button.cget('text'), 'Update available')

    def test_restart_waits_until_reading_stops(self):
        self.reader.installed_update = {'tag': 'preview-5-1'}
        self.reader.set_busy(True)
        with patch('app.messagebox.showinfo') as info, patch('updates.activate_update') as activate:
            self.reader.update_action()
            info.assert_called_once()
            activate.assert_not_called()

    def test_word_highlight_uses_exact_passage_offset(self):
        self.reader.show_word((1, 0, 4))
        self.assertEqual(self.reader.index, 1)
        ranges = self.reader.text.tag_ranges('word')
        self.assertEqual(self.reader.text.get(*ranges), 'More')

    def test_future_word_waits_for_audio_clock_and_stop_discards_it(self):
        self.reader.events.put(('at', (time.monotonic() + 60, 'word', (1, 0, 4))))
        self.reader.poll()
        self.assertEqual(self.reader.index, 0)
        self.assertFalse(self.reader.text.tag_ranges('word'))
        self.reader.stop()
        self.reader.flush_highlights(finish=True)
        self.assertEqual(self.reader.index, 0)


if __name__ == '__main__':
    unittest.main()
