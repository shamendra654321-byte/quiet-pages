"""Book import and bounded speech passages; no network access."""
import re
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote
from dataclasses import dataclass


@dataclass
class Chapter:
    title: str
    parts: list[str]


@dataclass
class Book:
    chapters: list[Chapter]

    @property
    def parts(self):
        return [part for chapter in self.chapters for part in chapter.parts]

    @property
    def starts(self):
        result, offset = [], 0
        for chapter in self.chapters:
            result.append(offset)
            offset += len(chapter.parts)
        return result


def _chapter(title, text):
    return Chapter(' '.join(title.split())[:160] or 'Untitled section', passages(text))


CHAPTER_HEADING = re.compile(r'^(?:(?:chapter|part|book)\s+(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)(?:\b.*)?|prologue|epilogue|introduction|preface|conclusion)$', re.I)


def _text_chapters(text, default='Full document'):
    chapters, lines, title = [], [], default
    for line in text.splitlines():
        heading = line.strip()
        if len(heading) <= 100 and CHAPTER_HEADING.fullmatch(heading):
            if '\n'.join(lines).strip():
                chapters.append(_chapter(title, '\n'.join(lines)))
            title, lines = heading, [heading]
        else:
            lines.append(line)
    if '\n'.join(lines).strip():
        chapters.append(_chapter(title, '\n'.join(lines)))
    return chapters


def _check_archive(archive):
    if sum(item.file_size for item in archive.infolist()) > 250_000_000:
        raise ValueError('This document is too large to import (250 MB uncompressed limit).')


def _docx_chapters(path):
    # Read WordprocessingML directly: no Word installation, macros or external links.
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    w = '{' + ns['w'] + '}'
    with zipfile.ZipFile(path) as archive:
        _check_archive(archive)
        document = ET.fromstring(archive.read('word/document.xml'))
        styles = {}
        if 'word/styles.xml' in archive.namelist():
            for style in ET.fromstring(archive.read('word/styles.xml')).findall('w:style', ns):
                styles[style.get(w + 'styleId')] = style

        def style_level(style_id, seen=None):
            seen = set() if seen is None else seen
            if style_id in seen or style_id not in styles:
                return None
            seen.add(style_id)
            style = styles[style_id]
            outline = style.find('w:pPr/w:outlineLvl', ns)
            if outline is not None:
                try:
                    return int(outline.get(w + 'val'))
                except (ValueError, TypeError):
                    return None
            name = style.find('w:name', ns)
            label = name.get(w + 'val', '') if name is not None else style_id
            match = re.fullmatch(r'heading\s*([1-9])', label, re.I)
            if match:
                return int(match[1]) - 1
            base = style.find('w:basedOn', ns)
            return style_level(base.get(w + 'val'), seen) if base is not None else None

        rows = []
        body = document.find('w:body', ns)
        if body is None:
            return []
        # Iterating paragraphs in XML order also preserves table-cell placement.
        for paragraph in body.iter(w + 'p'):
            def text_nodes(node):
                if node.tag in (w + 'del', w + 'moveFrom'):
                    return ''
                if node.tag == w + 't':
                    return node.text or ''
                if node.tag in (w + 'tab', w + 'br', w + 'cr'):
                    return ' '
                return ''.join(text_nodes(child) for child in node)
            text = text_nodes(paragraph).strip()
            if not text:
                continue
            prop = paragraph.find('w:pPr', ns)
            level = None
            if prop is not None:
                outline = prop.find('w:outlineLvl', ns)
                if outline is not None:
                    try:
                        level = int(outline.get(w + 'val'))
                    except (ValueError, TypeError):
                        pass
                else:
                    style = prop.find('w:pStyle', ns)
                    if style is not None:
                        level = style_level(style.get(w + 'val'))
            rows.append((text, level))
        levels = [level for _, level in rows if level is not None and 0 <= level <= 8]
        if not levels:
            return _text_chapters('\n\n'.join(text for text, _ in rows))
        top = min(levels)
        result, texts, title = [], [], 'Opening pages'
        for text, level in rows:
            if level == top:
                if texts:
                    result.append(_chapter(title, '\n\n'.join(texts)))
                title, texts = text, []
            texts.append(text)
        if texts:
            result.append(_chapter(title, '\n\n'.join(texts)))
        return result


def _epub_chapters(path):
    from bs4 import BeautifulSoup, NavigableString, Tag
    with zipfile.ZipFile(path) as archive:
        _check_archive(archive)
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        package = container.find('.//{*}rootfile').attrib['full-path']
        root = ET.fromstring(archive.read(package))
        manifest = {item.attrib['id']: item for item in root.findall('.//{*}manifest/{*}item')}
        def resolve(base, href):
            location, _, fragment = href.partition('#')
            name = posixpath.normpath(posixpath.join(posixpath.dirname(base), unquote(location))) if location else base
            return name, unquote(fragment)
        labels = {}
        for item in manifest.values():
            name, _ = resolve(package, item.attrib['href'])
            if 'nav' in item.get('properties', '').split():
                soup = BeautifulSoup(archive.read(name), 'html.parser')
                toc = next((nav for nav in soup.find_all('nav') if 'toc' in nav.get('epub:type', '').split() or nav.get('role') == 'doc-toc'), None)
                if toc:
                    for link in toc.find_all('a', href=True):
                        labels.setdefault(resolve(name, link['href']), link.get_text(' ', strip=True))
            elif item.get('media-type') == 'application/x-dtbncx+xml':
                ncx = ET.fromstring(archive.read(name))
                for point in ncx.findall('.//{*}navPoint'):
                    content, label = point.find('{*}content'), point.find('{*}navLabel/{*}text')
                    if content is not None and label is not None:
                        labels.setdefault(resolve(name, content.get('src', '')), label.text or '')
        result = []
        for itemref in root.findall('.//{*}spine/{*}itemref'):
            item = manifest[itemref.attrib['idref']]
            if itemref.get('linear') == 'no' or 'nav' in item.get('properties', '').split():
                continue
            name, _ = resolve(package, item.attrib['href'])
            soup = BeautifulSoup(archive.read(name), 'html.parser')
            for tag in soup(['head', 'script', 'style', 'nav']):
                tag.decompose()
            body = soup.body or soup
            title_tag = body.find(['h1', 'h2', 'h3'])
            title = labels.get((name, '')) or (title_tag.get_text(' ', strip=True) if title_tag else f'Section {len(result) + 1}')
            fragments = {fragment: label for (target, fragment), label in labels.items() if target == name and fragment}
            headings = body.find_all('h1') or body.find_all('h2')
            texts = []
            def flush():
                text = ''.join(texts).strip()
                if text:
                    result.append(_chapter(title, text))
                texts.clear()
            for node in body.descendants:
                if isinstance(node, Tag):
                    label = fragments.get(node.get('id'))
                    if not fragments and node in headings:
                        label = node.get_text(' ', strip=True)
                    if label:
                        flush()
                        title = label
                    if node.name in ('p', 'div', 'h1', 'h2', 'h3', 'li', 'tr', 'br'):
                        texts.append('\n\n')
                elif isinstance(node, NavigableString):
                    texts.append(str(node))
            flush()
        return result


def load_document(path, progress=None, cancel=None, clean_pdf=True):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.docx':
        chapters = _docx_chapters(path)
    elif suffix == '.doc':
        raise ValueError('Older .doc files need conversion. Open the file in Word or LibreOffice and save it as Word Document (.docx), then open that copy here.')
    elif suffix == '.epub':
        chapters = _epub_chapters(path)
    elif suffix == '.txt':
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            text = path.read_text(encoding='cp1252')
        chapters = _text_chapters(text)
    elif suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('This PDF is password protected. Open an unlocked copy.')
        from pdf_text import extract_pages
        pages = extract_pages(path, reader, progress, cancel, clean_pdf)
        boundaries = {}
        # Prefer top-level PDF bookmarks; page-based boundaries cannot split a page.
        for item in reader.outline:
            if isinstance(item, list):
                continue
            try:
                page = reader.get_destination_page_number(item)
                if page is not None and 0 <= page < len(pages):
                    boundaries.setdefault(page, str(item.title))
            except (ValueError, AttributeError):
                continue
        if boundaries:
            boundaries.setdefault(0, 'Opening pages')
            starts = sorted(boundaries)
            chapters = [_chapter(boundaries[start], '\n\n'.join(pages[start:starts[i + 1] if i + 1 < len(starts) else len(pages)])) for i, start in enumerate(starts)]
        else:
            chapters = _text_chapters('\n\n'.join(pages))
    else:
        raise ValueError('Choose a Word (.docx), EPUB, PDF or TXT file.')
    chapters = [chapter for chapter in chapters if chapter.parts]
    if not chapters:
        raise ValueError('No readable text found. This may be an empty, unreadable scan or DRM-protected book.')
    return Book(chapters)


def passages(text, limit=650):
    result = []
    for paragraph in re.split(r'\n\s*\n', text):
        words = paragraph.split()
        current = ''
        for word in words:
            # Bound even malformed books containing huge unbroken strings.
            for part in [word[i:i + limit] for i in range(0, len(word), limit)]:
                if current and len(current) + len(part) + 1 > limit:
                    result.append(current)
                    current = ''
                current = (current + ' ' + part).strip()
        if current:
            result.append(current)
    return result


def load_book(path):
    return load_document(path).parts
