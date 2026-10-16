import json
import queue
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from reading_position import position, source_seconds
from chapter_audio import read_book
import test_playback


class PositionTests(unittest.TestCase):
    def test_old_progress_and_damaged_values(self):
        self.assertEqual(position(1, ['A', 'B'])['index'], 1)
        result = position({'index': 900, 'seconds': float('nan'), 'text_offset': -3}, ['A', 'B'])
        self.assertEqual((result['index'], result['seconds'], result['text_offset']), (1, 0, 0))
        self.assertEqual(position(None, ['A'])['seconds'], 0)

    def test_source_clock_handles_speed_latency_and_pause(self):
        # A 2x block covers one source second in half a wall-clock second.
        self.assertEqual(source_seconds(10, 11, 20, .5, 19), 10)
        self.assertEqual(source_seconds(10, 11, 20, .5, 20.25), 10.5)
        self.assertEqual(source_seconds(10, 11, 20, .5, 90), 11)

    def test_resume_plays_exact_remaining_samples(self):
        played = []
        class Engine:
            def create(self, text, **kwargs):
                return np.arange(24000, dtype=np.float32), 24000
        class Stream:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data): played.extend(data[:, 0])
        events = queue.Queue()
        read_book(Engine(), ['One.'], 0, 1, [0], 'af_heart', 1,
                  threading.Event(), threading.Event(), events, Stream, start_seconds=.375)
        np.testing.assert_array_equal(played, np.arange(9000, 24000))
        cursors = [v[2] for k, v in events.queue if k == 'at' and v[1] == 'cursor']
        self.assertEqual(cursors[0][1], .375)
        self.assertEqual(cursors[-1][1], 1)

    def test_different_voice_uses_word_time_instead_of_old_seconds(self):
        played = []
        class Cache:
            def get(self, *args):
                return np.arange(24000, dtype=np.float32), 24000, [(0, .3, 0, 3), (.3, 1, 4, 8)]
        class Stream:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data): played.extend(data[:, 0])
        read_book(None, ['One two.'], 0, 1, [0], 'af_bella', 1,
                  threading.Event(), threading.Event(), queue.Queue(), Stream,
                  cache=Cache(), start_seconds=.8, start_char=4)
        self.assertEqual(played[0], 7200)
        self.assertEqual(len(played), 16800)


class ResumeAndBookmarkTests(unittest.TestCase):
    setUp = test_playback.PlaybackTests.setUp
    tearDown = test_playback.PlaybackTests.tearDown

    def test_stop_persists_audible_cursor_not_prepared_future(self):
        r = self.reader
        r.playing = True
        r.position_voice = 'af_heart'
        now = time.monotonic()
        r.events.put(('at', (now - .25, 'cursor', (0, 4, 5, .5))))
        r.events.put(('at', (now + 60, 'position', 2)))
        r.stop()
        data = json.loads((__import__('app').DATA / 'progress.json').read_text())['test-book']
        self.assertEqual(data['index'], 0)
        self.assertAlmostEqual(data['seconds'], 4.5, delta=.15)
        self.assertEqual(data['voice'], 'af_heart')
        r.flush_highlights(finish=True)
        self.assertEqual(r.index, 0)

    def test_reopen_restores_seconds_voice_and_speed(self):
        r = self.reader
        point = {'index': 1, 'seconds': 2.35, 'voice': 'bf_emma', 'text_offset': 2, 'speed': 1.6}
        r.apply_position(point)
        r.audio_settings = None
        with patch('app.read_book') as read:
            r.start()
            deadline = time.monotonic() + 2
            while not read.called and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(read.call_args.kwargs['start_seconds'], 2.35)
            self.assertIsNone(read.call_args.kwargs['start_char'])
            self.assertEqual(read.call_args.args[5], 'bf_emma')
        self.assertEqual(r.playback_speed.get(), 1.6)

    def test_bookmarks_survive_progress_changes_and_file_reload(self):
        r = self.reader
        r.cursor = (0, 1.25)
        r.position_voice = 'af_heart'
        with patch('app.simpledialog.askstring', return_value='Favourite scene'):
            r.add_bookmark()
        r.move(1)
        r.saved = json.loads((__import__('app').DATA / 'progress.json').read_text())
        mark = r.bookmark_entries()[0]
        self.assertEqual(mark['name'], 'Favourite scene')
        self.assertEqual(mark['position']['seconds'], 1.25)
        self.assertEqual(r.saved['test-book']['index'], 1)
        r.apply_position(mark['position'])
        self.assertEqual(r.cursor, (0, 1.25))

    def test_rename_delete_and_jump_bookmark(self):
        r = self.reader
        r.cursor = (0, 1.5)
        with patch('app.simpledialog.askstring', return_value='Scene'):
            r.add_bookmark()
        r.show_bookmarks()
        r.bookmark_list.selection_set(0)
        with patch('app.simpledialog.askstring', return_value='New name'):
            r.bookmark_action('rename')
        self.assertEqual(r.bookmark_entries()[0]['name'], 'New name')
        r.bookmark_list.selection_set(0)
        r.move(1)
        r.bookmark_action('go')
        self.assertEqual(r.cursor, (0, 1.5))
        r.show_bookmarks()
        r.bookmark_list.selection_set(0)
        with patch('app.messagebox.askyesno', return_value=True):
            r.bookmark_action('delete')
        self.assertEqual(r.bookmark_entries(), [])
        self.assertEqual(r.cursor, (0, 1.5))

    def test_old_integer_progress_migrates_without_losing_bookmark(self):
        r = self.reader
        r.saved['test-book'] = 1
        r.apply_position(r.saved['test-book'])
        self.assertEqual(r.cursor, (1, 0))
        self.assertEqual(r.saved['test-book']['index'], 1)

    def test_pause_drain_cannot_run_cursor_into_future_audio(self):
        r = self.reader
        r.cursor_span = (0, 2, 2.25, time.monotonic() - 100, .25)
        r.paused.set()
        r.refresh_cursor()
        self.assertEqual(r.cursor, (0, 2.25))

    def test_preview_done_preserves_book_position(self):
        r = self.reader
        r.cursor = (0, 1.7)
        r.events.put(('done', None))
        r.poll()
        self.assertEqual(r.cursor, (0, 1.7))

    def test_stop_during_new_voice_preparation_preserves_old_location(self):
        r = self.reader
        r.apply_position({'index': 0, 'seconds': 2.35, 'voice': 'af_heart', 'text_offset': 2})
        r.voice.set(next(name for name, voice in __import__('app').VOICES.items() if voice == 'bf_emma'))
        with patch('app.read_book'):
            r.start()
            r.stop()
        self.assertEqual(r.saved['test-book']['seconds'], 2.35)
        self.assertEqual(r.saved['test-book']['voice'], 'af_heart')

    def test_fresh_reader_loads_saved_position_and_unicode_bookmark(self):
        import app
        from reader_core import Book, Chapter
        r = self.reader
        r.cursor = (0, 1.25)
        r.position_voice = 'af_heart'
        with patch('app.simpledialog.askstring', return_value='Scène préférée'):
            r.add_bookmark()
        with patch.object(self.root, 'destroy'):
            r.close()
        window = app.tk.Toplevel(self.root)
        fresh = app.Reader(window)
        fresh.events.put(('book', ('Test', Book([Chapter('One', ['First.', 'More.']), Chapter('Two', ['Last.'])]), 'test-book')))
        fresh.poll()
        self.assertEqual(fresh.cursor, (0, 1.25))
        self.assertEqual(fresh.bookmark_entries()[0]['name'], 'Scène préférée')
        window.destroy()
