import tempfile
import unittest
import zipfile
from pathlib import Path
from reader_core import load_book, load_document, passages


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
            with self.assertRaisesRegex(ValueError, 'No readable text'):
                load_book(path)

    def test_word_headings_tables_and_deleted_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'chapters.docx'
            ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('word/styles.xml', f'<w:styles xmlns:w="{ns}"><w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style><w:style w:styleId="Custom"><w:basedOn w:val="Heading1"/></w:style></w:styles>')
                z.writestr('word/document.xml', f'''<w:document xmlns:w="{ns}"><w:body>
                <w:p><w:r><w:t>Opening.</w:t></w:r></w:p>
                <w:p><w:pPr><w:pStyle w:val="Custom"/></w:pPr><w:r><w:t>First chapter</w:t></w:r></w:p>
                <w:p><w:r><w:t>Keep this.</w:t></w:r><w:del><w:r><w:delText>Discard this.</w:delText></w:r></w:del></w:p>
                <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table entry.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
                <w:p><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:r><w:t>Second chapter</w:t></w:r></w:p>
                <w:p><w:hyperlink><w:r><w:t>The end.</w:t></w:r></w:hyperlink></w:p>
                </w:body></w:document>''')
            book = load_document(path)
            self.assertEqual([c.title for c in book.chapters], ['Opening pages', 'First chapter', 'Second chapter'])
            self.assertEqual(book.parts, ['Opening.', 'First chapter', 'Keep this.', 'Table entry.', 'Second chapter', 'The end.'])
            self.assertEqual(book.starts, [0, 1, 4])

    def test_plain_text_chapters_and_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'book.txt'
            path.write_text('Chapter 1\nFirst scene.\n\nChapter Two\nSecond scene.')
            book = load_document(path)
            self.assertEqual([c.title for c in book.chapters], ['Chapter 1', 'Chapter Two'])
            path.write_text('A short document without headings.')
            self.assertEqual(len(load_document(path).chapters), 1)

    def test_old_word_explains_conversion(self):
        with self.assertRaisesRegex(ValueError, 'save it as Word Document'):
            load_document('old.doc')

    def test_epub_navigation_fragments_same_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nav.epub'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
                z.writestr('OPS/book.opf', '<package><manifest><item id="nav" href="nav.xhtml" properties="nav"/><item id="a" href="book.xhtml"/></manifest><spine><itemref idref="nav"/><itemref idref="a"/></spine></package>')
                z.writestr('OPS/nav.xhtml', '<nav epub:type="toc"><a href="book.xhtml#one">The beginning</a><a href="book.xhtml#two">The ending</a></nav>')
                z.writestr('OPS/book.xhtml', '<html><head><title>Never speak metadata</title></head><body><h1 id="one">One</h1><p>First <em>scene</em>.</p><h1 id="two">Two</h1><p>Last scene.</p></body></html>')
            book = load_document(path)
            self.assertEqual([c.title for c in book.chapters], ['The beginning', 'The ending'])
            self.assertEqual(book.parts, ['One', 'First scene.', 'Two', 'Last scene.'])

    def test_pdf_bookmark_chapters(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'book.pdf'
            writer = PdfWriter()
            for text in ('First page', 'Second page'):
                page = writer.add_blank_page(width=600, height=800)
                font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
                page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
                stream = DecodedStreamObject()
                stream.set_data(f'BT /F1 12 Tf 50 700 Td ({text}) Tj ET'.encode())
                page[NameObject('/Contents')] = stream
            writer.add_outline_item('Start', 0)
            writer.add_outline_item('Finish', 1)
            writer.write(path)
            book = load_document(path)
            self.assertEqual([c.title for c in book.chapters], ['Start', 'Finish'])
            self.assertEqual(book.parts, ['First page', 'Second page'])


if __name__ == '__main__':
    unittest.main()
