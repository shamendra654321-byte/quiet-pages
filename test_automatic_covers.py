import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import test_bookshelf
from test_online_covers import png


class AutomaticCoverTests(unittest.TestCase):
    setUp = test_bookshelf.ShelfTests.setUp
    wait_import = test_bookshelf.ShelfTests.wait_import

    def tearDown(self):
        self.reader.automatic_covers.stop()
        if self.reader.automatic_covers.worker:
            self.reader.automatic_covers.worker.join(3)
        test_bookshelf.ShelfTests.tearDown(self)

    def add_book(self):
        path = Path(self.temp.name) / 'A Story.txt'
        path.write_text('Once upon a time a traveller walked by the sea.')
        self.reader.open_book(str(path)); self.wait_import()
        return path

    def wait_cover(self):
        deadline = time.monotonic() + 3
        while not self.reader.cover_store.path(self.reader.book_id).exists() and time.monotonic() < deadline:
            self.root.update(); time.sleep(.02)
        self.assertTrue(self.reader.cover_store.path(self.reader.book_id).exists())

    def test_new_import_finds_cover_and_reopening_does_not_search(self):
        self.reader.auto_covers.set(True)
        with patch('online_covers.search', return_value=[{'title': 'A Story', 'author': 'Writer', 'cover_id': 42}]) as search, patch('online_covers.download', return_value=png()):
            path = self.add_book(); self.wait_cover()
            self.reader.open_book(str(path)); self.wait_import()
            self.assertEqual(search.call_count, 1)

    def test_disabled_preference_persists_and_import_stays_offline(self):
        self.reader.auto_covers.set(False); self.reader.change_auto_covers()
        with patch('online_covers.search') as search:
            self.add_book(); search.assert_not_called()
        self.assertFalse(json.loads((Path(self.temp.name) / 'preferences.json').read_text())['auto_covers'])

    def test_local_cover_skips_network(self):
        service = self.reader.automatic_covers
        self.reader.cover_store.path('local').write_bytes(png())
        with patch('online_covers.search') as search:
            service.add({'id': 'local', 'title': 'A Story', 'path': 'missing.txt'})
            deadline = time.monotonic() + 2
            while self.reader.events.empty() and time.monotonic() < deadline: time.sleep(.01)
            service.stop(); service.worker.join(3)
            search.assert_not_called()

    def test_late_result_after_disable_or_removal_is_ignored_and_custom_kept(self):
        self.reader.library.remember('a', 'A Story', 'a.txt')
        service = self.reader.automatic_covers
        target = self.reader.cover_store.path('a'); target.write_bytes(png())
        original = target.read_bytes()
        self.assertTrue(service.apply('a', b'bad image', self.reader.library))
        self.assertEqual(target.read_bytes(), original)
        self.reader.library.remove('a')
        self.assertFalse(service.apply('a', png(), self.reader.library))
        self.reader.auto_covers.set(False); self.reader.change_auto_covers()
        self.assertFalse(service.apply('a', png(), self.reader.library))
