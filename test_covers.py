import io, tempfile, unittest, zipfile
from pathlib import Path
from PIL import Image
from covers import extract_cover, CoverStore

class CoversTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.folder=Path(self.temp.name)
        data=io.BytesIO(); Image.new('RGB',(400,600),'navy').save(data,format='PNG'); self.png=data.getvalue()
    def tearDown(self): self.temp.cleanup()
    def test_epub_two_and_three_embedded_covers(self):
        for version in (2,3):
            p=self.folder/f'{version}.epub'; out=self.folder/f'{version}.png'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
                meta='<meta name="cover" content="art"/>' if version==2 else ''
                properties='properties="cover-image"' if version==3 else ''
                z.writestr('OPS/book.opf',f'<package><metadata>{meta}</metadata><manifest><item id="art" href="images/front%20cover.png" media-type="image/png" {properties}/></manifest></package>')
                z.writestr('OPS/images/front cover.png',self.png)
            self.assertTrue(extract_cover(p,out))
            with Image.open(out) as im: self.assertLessEqual(im.height,330);self.assertLessEqual(im.width,240)
    def test_docx_thumbnail_and_corrupt_archive(self):
        p=self.folder/'book.docx';out=self.folder/'cover.png'
        with zipfile.ZipFile(p,'w') as z: z.writestr('docProps/thumbnail.png',self.png)
        self.assertTrue(extract_cover(p,out))
        p.write_bytes(b'broken');self.assertFalse(extract_cover(p,out))
    def test_pdf_first_page(self):
        from pypdf import PdfWriter
        p=self.folder/'book.pdf';writer=PdfWriter();writer.add_blank_page(width=600,height=800)
        with p.open('wb') as f: writer.write(f)
        self.assertTrue(extract_cover(p,self.folder/'page.png'))
    def test_custom_cover_persists_and_does_not_modify_book(self):
        p=self.folder/'book.txt';p.write_text('My story');art=self.folder/'art.png';art.write_bytes(self.png)
        store=CoverStore(self.folder/'covers');store.ensure({'id':'book','path':p});store.choose('book',art)
        before=store.path('book').read_bytes();store.ensure({'id':'book','path':p})
        self.assertEqual(CoverStore(self.folder/'covers').path('book').read_bytes(),before)
        self.assertEqual(p.read_text(),'My story')
    def test_bad_custom_cover_keeps_existing(self):
        store=CoverStore(self.folder/'covers'); art=self.folder/'art.png';art.write_bytes(self.png);store.choose('id',art)
        before=store.path('id').read_bytes();art.write_bytes(b'not an image')
        with self.assertRaises(OSError): store.choose('id',art)
        self.assertEqual(store.path('id').read_bytes(),before)
