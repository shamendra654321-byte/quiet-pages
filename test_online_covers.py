import io, json, threading, time, unittest
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
from PIL import Image
import online_covers
import test_bookshelf
from cover_search import CoverSearch

def png():
    stream=io.BytesIO();Image.new('RGB',(120,180),'navy').save(stream,format='PNG');return stream.getvalue()

class OnlineCoverTests(unittest.TestCase):
    def test_encoded_search_and_deduplicated_cover_ids(self):
        payload={'docs':[{'title':'A & B','author_name':['Writer'],'cover_i':42,'first_publish_year':2000}, {'cover_i':42},{'cover_i':-1},{'cover_i':'https://bad.example'},{'title':'Other','cover_i':43}]}
        with patch('online_covers.request',return_value=json.dumps(payload).encode()) as request:
            result=online_covers.search(' A & B ','Writer',threading.Event())
        self.assertEqual([r['cover_id'] for r in result],[42,43])
        query=parse_qs(urlparse(request.call_args.args[0]).query)
        self.assertEqual(query['title'],['A & B']);self.assertEqual(query['author'],['Writer'])
    def test_validated_download_and_invalid_image(self):
        with patch('online_covers.request',return_value=png()) as request:
            data=online_covers.download(42,threading.Event())
            self.assertIn('/b/id/42-M.jpg?default=false',request.call_args.args[0])
        with Image.open(io.BytesIO(data)) as im:self.assertEqual(im.format,'PNG')
        with patch('online_covers.request',return_value=b'not an image'):
            with self.assertRaises(OSError):online_covers.download(42,threading.Event())
        with self.assertRaises(ValueError):online_covers.download('../private',threading.Event())
    def test_cancel_prevents_request(self):
        cancel=threading.Event();cancel.set()
        with patch('online_covers.urllib.request.urlopen') as opening:
            with self.assertRaises(InterruptedError):online_covers.request('https://openlibrary.org/search.json',100,cancel)
            opening.assert_not_called()
    def test_bounded_response(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'x'*n
        with patch('online_covers.urllib.request.urlopen',return_value=Response()),patch('online_covers._last_request',0):
            with self.assertRaises(ValueError):online_covers.request('https://openlibrary.org/search.json',10,threading.Event())

class CoverSearchUITests(unittest.TestCase):
    setUp=test_bookshelf.ShelfTests.setUp
    def tearDown(self):
        dialog=getattr(self,'dialog',None)
        if dialog:
            dialog.close()
            if hasattr(dialog,'worker'):dialog.worker.join(2)
        test_bookshelf.ShelfTests.tearDown(self)
    def open_dialog(self):
        self.reader.library.remember('a','A book','a.txt');self.reader.library.remember('b','B book','b.txt');self.reader.refresh_bookshelf()
        self.dialog=CoverSearch(self.reader,self.reader.shelf_books['a'])
    def wait_search(self):
        deadline=time.monotonic()+3
        while self.dialog.busy and time.monotonic()<deadline:self.root.update();time.sleep(.02)
        self.assertFalse(self.dialog.busy)
    def test_open_is_offline_and_use_saves_to_original_book(self):
        with patch('online_covers.search') as search:self.open_dialog();search.assert_not_called()
        with patch('online_covers.search',return_value=[{'cover_id':42,'title':'A book','author':'Writer','year':'2000'}]),patch('online_covers.download',return_value=png()):
            self.dialog.search();self.wait_search()
        self.dialog.table.selection_set('42');self.reader.select_cover('b');self.dialog.use()
        self.assertTrue(self.reader.cover_store.path('a').exists());self.assertFalse(self.reader.cover_store.path('b').exists())
    def test_offline_failure_keeps_cover_and_can_retry(self):
        self.open_dialog();target=self.reader.cover_store.path('a');target.write_bytes(png());original=target.read_bytes()
        with patch('online_covers.search',side_effect=OSError('offline')):
            self.dialog.search();self.wait_search()
        self.assertIn('Could not reach',self.dialog.status.cget('text'));self.assertEqual(target.read_bytes(),original)
        with patch('online_covers.search',return_value=[]):self.dialog.search();self.wait_search()
        self.assertIn('No covers found',self.dialog.status.cget('text'))
    def test_closing_search_never_applies_late_result(self):
        self.open_dialog()
        def search(title,author,cancel):cancel.wait(1);raise InterruptedError()
        with patch('online_covers.search',side_effect=search):
            self.dialog.search();self.dialog.close();self.dialog.worker.join(2);self.root.update()
        self.assertFalse(self.reader.cover_store.path('a').exists())
