"""Local PDF extraction, conservative margin cleanup and offline scan OCR."""
from collections import Counter
import re
import threading

PDF_RENDER_LOCK = threading.RLock()


def clean_pages(pages, clean=True):
    def key(text):
        return re.sub(r'\d+', '#', ' '.join(text.lower().split()))
    counts = Counter()
    for page in pages:
        counts.update({key(text) for text, y in page if (y < .08 or y > .92) and len(text.strip()) <= 160})
    result = []
    for page in pages:
        lines = []
        for text, y in page:
            margin = y < .08 or y > .92
            number = re.fullmatch(r'\s*(?:page\s+)?(?:\d+|[ivxlcdm]+)(?:\s*(?:of|/)\s*\d+)?\s*', text, re.I)
            repeated = counts[key(text)] >= max(3, len(pages) * .5)
            if clean and margin and (number or repeated):
                continue
            lines.append(text)
        result.append('\n'.join(lines))
    return result


def extract_pages(path, reader, progress=None, cancel=None, clean=True):
    # PDFium is shared with background cover rendering and is not thread-safe.
    with PDF_RENDER_LOCK:
        return _extract_pages(path, reader, progress, cancel, clean)


def _extract_pages(path, reader, progress=None, cancel=None, clean=True):
    progress = progress or (lambda text: None)
    def check():
        if cancel is not None and cancel.is_set():
            raise InterruptedError()
    pages, renderer, ocr = [], None, None
    try:
        for index, page in enumerate(reader.pages):
            check()
            progress(f'Opening PDF page {index + 1} of {len(reader.pages)}…')
            fragments = []
            height = float(page.mediabox.height) or 1
            bottom = float(page.mediabox.bottom)
            def visit(text, cm, tm, font, size):
                if text.strip():
                    y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                    fragments.append((text.rstrip('\n'), (y - bottom) / height))
            text = page.extract_text(visitor_text=visit) or ''
            if sum(c.isalpha() for c in text) < 30 and list(page.images):
                progress(f'Reading scanned page {index + 1} of {len(reader.pages)} on your computer…')
                if renderer is None:
                    import pypdfium2 as pdfium
                    from rapidocr_onnxruntime import RapidOCR
                    renderer = pdfium.PdfDocument(str(path))
                    ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
                check()
                rendered_page = renderer[index]
                width, page_height = rendered_page.get_size()
                scale = min(2.5, 2400 / max(width, page_height))
                bitmap = rendered_page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    detected, _ = ocr(image)
                    check()
                    fragments = [(row[1], 1 - sum(p[1] for p in row[0]) / (4 * image.height)) for row in (detected or [])]
                finally:
                    bitmap.close()
                    rendered_page.close()
            pages.append(fragments or [(text, .5)])
        return clean_pages(pages, clean)
    finally:
        if renderer is not None:
            renderer.close()
