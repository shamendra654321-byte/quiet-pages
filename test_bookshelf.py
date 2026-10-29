import tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
import test_playback
from bookshelf import Library

class LibraryTests(unittest.TestCase):
    def test_persistence_dedup_and_non_destructive_remove(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder); book=path/'story.txt'; book.write_text('A story')
            library=Library(path/'library.db')
            library.remember('one','Story',book); library.finish('one',True)
            library.remember('one','Story renamed',book)
            restored=Library(path/'library.db').books()
            self.assertEqual(len(restored),1); self.assertEqual(restored[0]['finished'],1)
            library.remove('one'); self.assertTrue(book.exists()); self.assertEqual(library.books(),[])

class ShelfTests(unittest.TestCase):
    setUp=test_playback.PlaybackTests.setUp
    def tearDown(self):
        if hasattr(self.reader,'cover_thread'): self.reader.cover_thread.join(timeout=5)
        for callback in self.root.tk.call('after','info'):
            self.root.after_cancel(callback)
        test_playback.PlaybackTests.tearDown(self)
    def wait_import(self):
        end=time.monotonic()+5
        while self.reader.busy and time.monotonic()<end:
            self.root.update(); time.sleep(.01)
        self.root.update(); self.assertFalse(self.reader.busy)
    def test_continue_preserves_exact_position_and_starts(self):
        path=Path(self.temp.name)/'Story.txt'; path.write_text('Chapter 1\n\nA long quiet journey began by the sea.\n\nThe next morning the sun rose.')
        self.reader.open_book(str(path)); self.wait_import()
        self.reader.cursor=(0,2.5); self.reader.text_offset=8; self.reader.save()
        self.reader.show_bookshelf()
        with patch.object(self.reader,'start') as start:
            self.reader.continue_recent(); self.wait_import()
            start.assert_called_once(); self.assertEqual(self.reader.cursor,(0,2.5))
        self.assertEqual(len(self.reader.library.books()),1)
    def test_wrong_relocated_file_keeps_original_and_no_autoplay(self):
        path=Path(self.temp.name)/'Other.txt'; path.write_text('Another different story.')
        with patch('app.messagebox.showerror') as error, patch.object(self.reader,'start') as start:
            self.reader.open_book(str(path),expected_id='test-book',autoplay=True); self.wait_import()
            error.assert_called_once(); start.assert_not_called()
        self.assertEqual(self.reader.book_id,'test-book'); self.assertEqual(self.reader.library.books(),[])
    def test_search_and_finished_filter(self):
        self.reader.library.remember('a','River story','river.txt'); self.reader.library.remember('b','Moon story','moon.txt')
        self.reader.library.finish('b',True); self.reader.refresh_bookshelf()
        self.reader.shelf_search.set('RIVER'); self.assertEqual(self.reader.book_table.get_children(),('a',))
        self.reader.shelf_search.set(''); self.reader.shelf_filter.set('Finished'); self.reader.refresh_bookshelf()
        self.assertEqual(self.reader.book_table.get_children(),('b',)); self.assertEqual(self.reader.recent_id,'a')

    def test_cover_selection_and_list_switch_keep_book(self):
        self.reader.library.remember('a','First','a.txt'); self.reader.library.remember('b','Second','b.txt')
        self.reader.refresh_bookshelf(); self.reader.select_cover('b')
        self.assertEqual(self.reader.selected_book()['id'],'b')
        self.assertEqual(len(self.reader.cover_cards),2)
        self.reader.shelf_view.set('List'); self.reader.set_shelf_view()
        self.assertEqual(self.reader.selected_book()['id'],'b')
        self.reader.shelf_search.set('First')
        self.assertEqual(len(self.reader.cover_cards),1)
        self.assertEqual(self.reader.selected_book()['id'],'a')
