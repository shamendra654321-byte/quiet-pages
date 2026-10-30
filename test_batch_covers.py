import threading
import time
import unittest
from unittest.mock import patch
import test_bookshelf
from test_online_covers import png
from batch_covers import BatchCovers, matching_cover


class BatchCoverTests(unittest.TestCase):
    setUp = test_bookshelf.ShelfTests.setUp

    def tearDown(self):
        if hasattr(self, 'dialog'):
            self.dialog.close()
            if hasattr(self.dialog, 'worker'): self.dialog.worker.join(3)
        test_bookshelf.ShelfTests.tearDown(self)

    def open_dialog(self):
        for key, title in [('a', 'A book'), ('b', 'B book'), ('c', 'C book')]:
            self.reader.library.remember(key, title, key + '.txt')
        self.reader.refresh_bookshelf()
        self.dialog = BatchCovers(self.reader)

    def wait_batch(self):
        until = time.monotonic() + 4
        while self.dialog.busy and time.monotonic() < until:
            self.root.update(); time.sleep(.02)
        self.assertFalse(self.dialog.busy)

    def test_exact_match_rejects_ambiguous_or_partial_titles(self):
        one = {'title': 'A Book', 'author': 'Writer', 'cover_id': 1}
        self.assertEqual(matching_cover('a_book', [one]), one)
        self.assertIsNone(matching_cover('A', [one]))
        self.assertIsNone(matching_cover('A Book', [one, dict(one, author='Someone else')]))
        self.assertIsNone(matching_cover('A Book', [dict(one, author='')]))

    def test_batch_includes_filtered_books_keeps_existing_and_reviews_uncertain(self):
        self.open_dialog()
        target = self.reader.cover_store.path('a'); target.write_bytes(png())
        before = target.read_bytes()
        self.reader.shelf_search.set('A book')
        def search(title, author, cancel):
            return [{'title': title if title == 'B book' else 'Different title', 'author': 'Writer', 'cover_id': 42}]
        with patch('online_covers.search', side_effect=search) as lookup, patch('online_covers.download', return_value=png()):
            self.dialog.start(); self.wait_batch()
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(target.read_bytes(), before)
        self.assertTrue(self.reader.cover_store.path('b').exists())
        self.assertFalse(self.reader.cover_store.path('c').exists())
        self.assertEqual(self.dialog.table.set('c', 'status'), 'Needs review')

    def test_failure_continues_and_does_not_overwrite_new_cover(self):
        self.open_dialog()
        def search(title, author, cancel):
            if title == 'C book': raise OSError('offline')
            return [{'title': title, 'author': 'Writer', 'cover_id': 42}]
        def download(cover, cancel):
            self.reader.cover_store.path('a').write_bytes(png())
            self.reader.library.remove('b')
            return png()
        with patch('online_covers.search', side_effect=search), patch('online_covers.download', side_effect=download):
            self.dialog.start(); self.wait_batch()
        self.assertEqual(self.dialog.table.set('a', 'status'), 'Existing cover kept')
        self.assertEqual(self.dialog.table.set('b', 'status'), 'Book removed')
        self.assertFalse(self.reader.cover_store.path('b').exists())
        self.assertIn('retry', self.dialog.table.set('c', 'status'))

    def test_close_discards_late_results_and_open_sends_nothing(self):
        with patch('online_covers.search') as search:
            self.open_dialog(); search.assert_not_called()
        def search(title, author, cancel):
            cancel.wait(1)
            return [{'title': title, 'author': 'Writer', 'cover_id': 42}]
        with patch('online_covers.search', side_effect=search), patch('online_covers.download', return_value=png()):
            self.dialog.start(); self.dialog.close(); self.dialog.worker.join(3)
        self.assertFalse(self.reader.cover_store.path('a').exists())
