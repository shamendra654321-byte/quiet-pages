"""Opt-in Open Library search. Only entered title/author and cover IDs leave the PC."""
import io
import json
import threading
import time
import urllib.parse
import urllib.request
from PIL import Image, ImageOps

_lock = threading.Lock()
_last_request = 0.0
USER_AGENT = 'Talevoxa/1.0 (+https://github.com/shamendra654321-byte/quiet-pages)'

def request(url, limit, cancel):
    global _last_request
    with _lock:
        delay = max(0, 1.1 - (time.monotonic() - _last_request))
        if cancel.wait(delay): raise InterruptedError()
        _last_request = time.monotonic()
    if cancel.is_set(): raise InterruptedError()
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = response.read(limit + 1)
    if cancel.is_set(): raise InterruptedError()
    if len(data) > limit: raise ValueError('The cover service returned too much data.')
    return data

def search(title, author, cancel):
    title, author = title.strip(), author.strip()
    if not title: raise ValueError('Enter a book title first.')
    params = {'title': title[:300], 'limit': 12, 'fields': 'key,title,author_name,first_publish_year,cover_i'}
    if author: params['author'] = author[:200]
    payload = json.loads(request('https://openlibrary.org/search.json?' + urllib.parse.urlencode(params), 1_000_000, cancel))
    result, seen = [], set()
    for doc in payload.get('docs', []):
        cover = doc.get('cover_i')
        if type(cover) is not int or cover <= 0 or cover in seen: continue
        seen.add(cover)
        authors = doc.get('author_name') or []
        result.append({'cover_id': cover, 'title': str(doc.get('title') or title)[:300],
                       'author': ', '.join(str(a) for a in authors[:3]),
                       'year': str(doc.get('first_publish_year') or '')})
        if len(result) == 6: break
    return result

def download(cover_id, cancel):
    if type(cover_id) is not int or cover_id <= 0: raise ValueError('Invalid cover identifier.')
    data = request(f'https://covers.openlibrary.org/b/id/{cover_id}-M.jpg?default=false', 3_000_000, cancel)
    with Image.open(io.BytesIO(data)) as image:
        if image.width * image.height > 25_000_000 or min(image.size) < 5:
            raise ValueError('No usable cover image was returned.')
        image.load()
        thumb = ImageOps.exif_transpose(image).convert('RGB')
        thumb.thumbnail((240,330), Image.Resampling.LANCZOS)
        output = io.BytesIO(); thumb.save(output, format='PNG')
        return output.getvalue()
