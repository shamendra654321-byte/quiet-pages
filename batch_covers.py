"""User-started, cancellable cover lookup for the entire library."""
import io
import queue
import threading
import unicodedata
import tkinter as tk
from tkinter import ttk

import online_covers
from covers import save_image


def normalized(text):
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in
                            unicodedata.normalize('NFKC', text).casefold()).split())


def matching_cover(title, matches):
    """Only auto-select exact titles with a single, known author attribution."""
    exact = [m for m in matches if normalized(m['title']) == normalized(title)]
    authors = {normalized(m.get('author', '')) for m in exact}
    if exact and len(authors) == 1 and '' not in authors:
        return exact[0]
    return None


class BatchCovers:
    def __init__(self, reader):
        self.reader = reader
        self.closed = False
        self.busy = False
        self.cancel = threading.Event()
        self.events = queue.Queue()
        self.window = tk.Toplevel(reader.root)
        self.window.title('Find missing covers - Talevoxa')
        self.window.geometry('700x500')
        self.window.minsize(580, 420)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        shell = ttk.Frame(self.window, padding=18)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='Find all missing covers', font=('Georgia', 21)).pack(anchor='w')
        ttk.Label(shell, wraplength=630, text='Search the whole bookshelf, including hidden and finished books. Missing-cover titles are sent to Open Library; book files stay on this PC. Existing covers are kept. Exact title matches with one author are saved automatically; editions may differ.').pack(fill='x', pady=12)
        self.table = ttk.Treeview(shell, columns=('title', 'status'), show='headings', selectmode='browse')
        self.table.heading('title', text='BOOK'); self.table.heading('status', text='RESULT')
        self.table.column('title', width=330); self.table.column('status', width=240)
        area = ttk.Frame(shell); area.pack(fill='both', expand=True)
        self.table.pack(in_=area, side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(area, command=self.table.yview)
        scroll.pack(side='right', fill='y'); self.table.configure(yscrollcommand=scroll.set)
        self.progress = ttk.Progressbar(shell, mode='determinate')
        self.progress.pack(fill='x', pady=(12, 6))
        self.status = ttk.Label(shell, text='Ready. Start to check your bookshelf.', wraplength=630)
        self.status.pack(fill='x', pady=(0, 12))
        controls = ttk.Frame(shell); controls.pack(fill='x')
        self.start_button = ttk.Button(controls, text='Find missing covers', command=self.start)
        self.start_button.pack(side='left')
        self.review_button = ttk.Button(controls, text='Review selected book', command=self.review, state='disabled')
        self.review_button.pack(side='left', padx=8)
        self.stop_button = ttk.Button(controls, text='Stop', command=self.stop, state='disabled')
        self.stop_button.pack(side='right')
        self.after_id = self.window.after(100, self.poll)

    def start(self):
        if self.busy or self.closed: return
        self.books = {b['id']: b for b in self.reader.library.books()}
        self.table.delete(*self.table.get_children())
        for key, book in self.books.items():
            self.table.insert('', 'end', iid=key, values=(book['title'], 'Waiting'))
        self.cancel.clear(); self.busy = True; self.saved = 0; self.completed = 0
        self.progress.configure(maximum=max(1, len(self.books)), value=0)
        self.start_button.configure(state='disabled'); self.review_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.status.configure(text='Checking local artwork, then searching for missing covers...')
        local_worker = getattr(self.reader, 'cover_thread', None)
        books = list(self.books.values())
        def work():
            try:
                # Avoid concurrent extraction to the same temporary cover path.
                while local_worker and local_worker.is_alive():
                    if self.cancel.wait(.1): return
                for book in books:
                    if self.cancel.is_set(): break
                    key = book['id']
                    try:
                        self.reader.cover_store.ensure(book)
                        if self.reader.cover_store.path(key).exists():
                            self.events.put(('result', (key, 'Existing cover kept', None))); continue
                        title = book['title'].replace('_', ' ')
                        matches = online_covers.search(title, '', self.cancel)
                        match = matching_cover(title, matches)
                        if not match:
                            result = 'Needs review' if matches else 'No cover found'
                            self.events.put(('result', (key, result, None))); continue
                        data = online_covers.download(match['cover_id'], self.cancel)
                        self.events.put(('result', (key, 'Cover saved', data)))
                    except InterruptedError: break
                    except Exception:
                        self.events.put(('result', (key, 'Could not load — retry later', None)))
            finally:
                self.events.put(('done', None))
        self.worker = threading.Thread(target=work, daemon=True); self.worker.start()

    def poll(self):
        if self.closed: return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'result':
                    key, result, data = value
                    if data and not self.cancel.is_set():
                        try:
                            if key not in {b['id'] for b in self.reader.library.books()}:
                                result = 'Book removed'
                            else:
                                with self.reader.cover_store.lock:
                                    target = self.reader.cover_store.path(key)
                                    if target.exists(): result = 'Existing cover kept'
                                    else:
                                        save_image(io.BytesIO(data), target); self.saved += 1
                        except Exception: result = 'Could not save — retry later'
                    elif data: result = 'Stopped'
                    self.table.set(key, 'status', result)
                    self.completed += 1; self.progress.configure(value=self.completed)
                    self.status.configure(text=f'{self.completed} of {len(self.books)} checked · {self.saved} covers saved')
                elif kind == 'done':
                    self.busy = False
                    self.start_button.configure(state='normal'); self.stop_button.configure(state='disabled')
                    self.review_button.configure(state='normal')
                    for key in self.table.get_children():
                        if self.table.set(key, 'status') == 'Waiting': self.table.set(key, 'status', 'Not checked')
                    prefix = 'Stopped' if self.cancel.is_set() else 'Finished'
                    self.status.configure(text=f'{prefix}: {self.saved} covers saved, {self.completed} of {len(self.books)} books checked. Select a book to review or change its cover.')
                    self.reader.render_covers()
        except queue.Empty: pass
        self.after_id = self.window.after(100, self.poll)

    def review(self):
        selection = self.table.selection()
        if self.busy or not selection: return
        book = next((b for b in self.reader.library.books() if b['id'] == selection[0]), None)
        if not book: return
        previous = getattr(self.reader, 'cover_search', None)
        if previous and not previous.closed: previous.close()
        from cover_search import CoverSearch
        self.reader.cover_search = CoverSearch(self.reader, book)

    def stop(self):
        self.cancel.set(); self.stop_button.configure(state='disabled')
        self.status.configure(text='Stopping... Covers already saved are kept.')

    def close(self):
        if self.closed: return
        self.closed = True; self.cancel.set()
        self.window.after_cancel(self.after_id); self.window.destroy()
        self.reader.render_covers()
