import tempfile
import unittest
import zipfile
from pathlib import Path
from reader_core import load_book, passages


class ImportTests(unittest.TestCase):
    def test_bound_and_preserve_words(self):
        text = ' '.join('word' + str(i) for i in range(1000))
        chunks = passages(text)
        self.assertEqual(' '.join(chunks), text)
        self.assertTrue(all(len(c) <= 650 for c in chunks))

    def test_long_token(self):
        chunks = passages('a' * 2000)
        self.assertEqual(''.join(chunks), 'a' * 2000)
        self.assertTrue(all(len(c) <= 650 for c in chunks))

    def test_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'empty.txt'
            path.write_text('  \n ')
            with self.assertRaisesRegex(ValueError, 'No readable text'):
                load_book(path)

    def test_epub_spine_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sample.epub'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
                z.writestr('OPS/book.opf', '<package><manifest><item id="b" href="b.xhtml"/><item id="a" href="a.xhtml"/></manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
                z.writestr('OPS/b.xhtml', '<html><p>Second chapter.</p></html>')
                z.writestr('OPS/a.xhtml', '<html><script>Ignore me</script><p>First chapter.</p></html>')
            self.assertEqual(load_book(path), ['First chapter.', 'Second chapter.'])

    def test_pdf_no_text(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'blank.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=600, height=800)
            writer.write(path)
            with self.assertRaisesRegex(ValueError, 'OCR'):
                load_book(path)


if __name__ == '__main__':
    unittest.main()
