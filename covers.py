"""Bounded local cover thumbnails; never fetch images or modify original books."""
import io
import threading
from contextlib import closing
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote
from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 20_000_000

def save_image(source, target):
    target = Path(target)
    with Image.open(source) as original:
        if original.width * original.height > 25_000_000:
            raise ValueError('Please choose a smaller cover image (under 25 megapixels).')
        original.load()
        image = ImageOps.exif_transpose(original).convert('RGB')
        image.thumbnail((240, 330), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.tmp')
        image.save(temp, format='PNG')
        temp.replace(target)

def _read(archive, name):
    info = archive.getinfo(name)
    if info.file_size > MAX_IMAGE_BYTES:
        raise ValueError('Cover resource is too large.')
    return archive.read(name)

def extract_cover(book, target):
    """Return False for absent/corrupt artwork; opening a book must still work."""
    try:
        path = Path(book)
        if path.suffix.lower() == '.pdf':
            import pypdfium2 as pdfium
            from pdf_text import PDF_RENDER_LOCK
            with PDF_RENDER_LOCK, pdfium.PdfDocument(str(path)) as pdf:
                if not len(pdf): return False
                with closing(pdf[0]) as page:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0: return False
                    bitmap = page.render(scale=min(240/width, 330/height))
                    try:
                        image = bitmap.to_pil(); data = io.BytesIO(); image.save(data, format='PNG'); data.seek(0)
                        save_image(data, target)
                    finally: bitmap.close()
            return True
        if path.suffix.lower() not in ('.epub', '.docx'): return False
        with zipfile.ZipFile(path) as archive:
            if path.suffix.lower() == '.docx':
                candidates = [n for n in archive.namelist() if n.lower().startswith('docprops/thumbnail.')]
            else:
                container = ET.fromstring(_read(archive, 'META-INF/container.xml'))
                rootfile = container.find('.//{*}rootfile')
                if rootfile is None: return False
                package = rootfile.get('full-path', '')
                root = ET.fromstring(_read(archive, package))
                cover_id = next((m.get('content') for m in root.findall('.//{*}meta') if m.get('name') == 'cover'), None)
                items = root.findall('.//{*}manifest/{*}item')
                covers = [i for i in items if 'cover-image' in i.get('properties','').split() or i.get('id') == cover_id]
                candidates = [posixpath.normpath(posixpath.join(posixpath.dirname(package), unquote(i.get('href','')).split('#')[0])) for i in covers if i.get('media-type','').startswith('image/')]
            for name in candidates:
                try:
                    save_image(io.BytesIO(_read(archive, name)), target)
                    return True
                except (OSError, ValueError, KeyError):
                    continue
    except Exception:
        # Cover metadata is optional, including for encrypted or malformed files.
        return False
    return False

class CoverStore:
    def __init__(self, folder):
        self.lock = threading.RLock()
        self.extraction_lock = threading.Lock()
        self.folder = Path(folder); self.folder.mkdir(parents=True, exist_ok=True)
    def path(self, identity):
        # Hash the key too: library IDs from old versions need not be hex strings.
        import hashlib
        return self.folder / (hashlib.sha256(identity.encode()).hexdigest() + '.png')
    def ensure(self, book):
        with self.extraction_lock:
            self._ensure(book)

    def _ensure(self, book):
        if not Path(book['path']).is_file(): return
        target = self.path(book['id'])
        marker = target.with_suffix('.checked')
        with self.lock:
            if target.exists() or marker.exists(): return
        automatic = target.with_suffix('.auto.png')
        success = extract_cover(book['path'], automatic)
        with self.lock:
            if success:
                if not target.exists(): automatic.replace(target)
                else: automatic.unlink(missing_ok=True)
            else:
                marker.touch()
    def choose(self, identity, source):
        if Path(source).stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError('Please choose an image smaller than 20 MB.')
        with self.lock:
            save_image(source, self.path(identity))
