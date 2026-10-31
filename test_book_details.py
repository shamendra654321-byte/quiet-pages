import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from bookshelf import Library
from book_details import sorted_books, valid_number

class DetailsTests(unittest.TestCase):
    def test_numeric_order(self):
        books = [dict(id=n,title=n,author='Writer',series='Saga',series_number=n) for n in ['10','2','1','2.5']]
        self.assertEqual([b['id'] for b in sorted_books(books,'Series')],['1','2','2.5','10'])
        for value in ['NaN','Infinity','-1','abc']:
            with self.assertRaises(ValueError): valid_number(value)

    def test_old_library_upgrade_and_reopen_preserves_edits(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'library.db'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE books (id TEXT PRIMARY KEY,title TEXT NOT NULL,path TEXT NOT NULL,opened REAL NOT NULL,finished INTEGER NOT NULL DEFAULT 0)')
                db.execute("INSERT INTO books VALUES ('a','Story','story.txt',1,1)")
            library = Library(path)
            library.set_details('a','Writer','Saga','2.5')
            library.remember('a','Story','story.txt')
            book = Library(path).books()[0]
            self.assertEqual((book['author'],book['series'],book['series_number'],book['finished']),('Writer','Saga','2.5',1))
