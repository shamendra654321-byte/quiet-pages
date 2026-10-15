import tempfile
import threading
import unittest
from pathlib import Path
from pdf_text import clean_pages
from reader_core import load_document


class PDFTests(unittest.TestCase):
    def test_margin_cleanup_preserves_body_and_unique_heading(self):
        pages = [[('A repeated title', .96), ('Chapter One', .8), ('A repeated title', .5), (str(i), .03)] for i in range(4)]
        self.assertEqual(clean_pages(pages), ['Chapter One\nA repeated title'] * 4)
        self.assertIn('0', clean_pages(pages, False)[0])

    def test_offline_scanned_pdf(self):
        from PIL import Image, ImageDraw, ImageFont
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scan.pdf'
            image = Image.new('RGB', (1200, 1600), 'white')
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 40)
            draw.text((100, 200), 'Chapter One', fill='black', font=font)
            draw.text((100, 300), 'The quiet garden was full of flowers.', fill='black', font=font)
            image.save(path, 'PDF')
            book = load_document(path)
            self.assertIn('quiet garden', ' '.join(book.parts).lower())
            self.assertIn('Chapter', book.chapters[0].title)
            cancel = threading.Event()
            cancel.set()
            with self.assertRaises(InterruptedError):
                load_document(path, cancel=cancel)
