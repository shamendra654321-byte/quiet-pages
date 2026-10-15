"""Book import and bounded speech passages; no network access."""
import re
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote


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
    path = Path(path)
    if path.suffix.lower() == '.txt':
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            text = path.read_text(encoding='cp1252')
    elif path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('This PDF is password protected. Open an unlocked copy.')
        text = '\n\n'.join(page.extract_text() or '' for page in reader.pages)
    elif path.suffix.lower() == '.epub':
        from bs4 import BeautifulSoup
        with zipfile.ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) > 250_000_000:
                raise ValueError('This EPUB is too large to import (250 MB uncompressed limit).')
            container = ET.fromstring(archive.read('META-INF/container.xml'))
            package = container.find('.//{*}rootfile').attrib['full-path']
            root = ET.fromstring(archive.read(package))
            manifest = {item.attrib['id']: item.attrib['href'] for item in root.findall('.//{*}manifest/{*}item')}
            sections = []
            for item in root.findall('.//{*}spine/{*}itemref'):
                if item.attrib.get('linear') == 'no':
                    continue
                href = unquote(manifest[item.attrib['idref']].split('#')[0])
                name = posixpath.normpath(posixpath.join(posixpath.dirname(package), href))
                soup = BeautifulSoup(archive.read(name), 'html.parser')
                for tag in soup(['script', 'style', 'nav']):
                    tag.decompose()
                sections.append(soup.get_text(' ', strip=True))
            text = '\n\n'.join(sections)
    else:
        raise ValueError('Choose an EPUB, PDF or TXT file.')
    result = passages(text)
    if not result:
        raise ValueError('No readable text found. Scanned PDFs need OCR first; DRM-protected books are not supported.')
    return result
