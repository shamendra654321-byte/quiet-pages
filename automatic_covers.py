"""Background cover lookup for newly imported books, with cancellable results."""
import io
import queue
import threading
import online_covers
from batch_covers import matching_cover
from covers import save_image


class AutomaticCovers:
    def __init__(self, store, events):
        self.store, self.events = store, events
        self.cancel = threading.Event()
        self.pending = queue.Queue()
        self.seen = set()
        self.worker = None

    def add(self, book):
        if self.cancel.is_set() or book['id'] in self.seen: return
        self.seen.add(book['id']); self.pending.put(dict(book))
        if self.worker is None:
            self.worker = threading.Thread(target=self.run, daemon=True)
            self.worker.start()

    def run(self):
        while not self.cancel.is_set():
            try: book = self.pending.get(timeout=.2)
            except queue.Empty: continue
            try:
                self.store.ensure(book)
                if self.cancel.is_set(): break
                if self.store.path(book['id']).exists():
                    self.events.put(('automatic_cover', (self, book['id'], None)))
                    continue
                title = book['title'].replace('_', ' ')
                match = matching_cover(title, online_covers.search(title, '', self.cancel))
                if match and not self.cancel.is_set():
                    data = online_covers.download(match['cover_id'], self.cancel)
                    self.events.put(('automatic_cover', (self, book['id'], data)))
            except InterruptedError: break
            except Exception:
                # Optional artwork must never interrupt reading or open error dialogs.
                continue

    def apply(self, identity, data, library):
        if self.cancel.is_set(): return False
        if identity not in {b['id'] for b in library.books()}: return False
        if data:
            try:
                with self.store.lock:
                    if not self.store.path(identity).exists():
                        save_image(io.BytesIO(data), self.store.path(identity))
            except Exception: return False
        return True

    def stop(self):
        self.cancel.set()
