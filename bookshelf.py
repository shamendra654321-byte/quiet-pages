"""Local file references; removing an entry never removes a book or progress."""
import sqlite3
import time
from contextlib import closing
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class Library:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY, title TEXT NOT NULL, path TEXT NOT NULL, opened REAL NOT NULL, finished INTEGER NOT NULL DEFAULT 0)')

    def remember(self, identity, title, path):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO books(id,title,path,opened) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,path=excluded.path,opened=excluded.opened',
                       (identity, title, str(Path(path).resolve()), time.time()))

    def books(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM books ORDER BY opened DESC')]

    def remove(self, identity):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM books WHERE id=?', (identity,))

    def finish(self, identity, value):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE books SET finished=? WHERE id=?', (int(value), identity))


from cover_shelf import CoverShelf
from covers import CoverStore
import threading

class Bookshelf(CoverShelf):
    def build_bookshelf(self, shell):
        self.cover_store = CoverStore(self.library.path.parent / 'covers')
        self.cover_loading = False
        self.cover_attempted = set()
        self.shelf = ttk.Frame(shell)
        self.shelf.columnconfigure(0, weight=1)
        self.shelf.rowconfigure(3, weight=1)
        intro = ttk.Frame(self.shelf)
        intro.grid(row=0, column=0, sticky='ew', pady=(0, 16))
        self.return_button = ttk.Button(intro, text='Back to book', command=self.show_reader)
        self.return_button.pack(side='right')
        ttk.Label(intro, text='Your bookshelf', font=('Georgia', 25)).pack(anchor='w')
        ttk.Label(intro, text='Your stories, ready when you are.', style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        recent = ttk.Frame(self.shelf, padding=18)
        recent.grid(row=1, column=0, sticky='ew', pady=(0, 18))
        recent.columnconfigure(0, weight=1)
        ttk.Label(recent, text='PICK UP WHERE YOU LEFT OFF', style='Muted.TLabel', font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w')
        self.recent_title = ttk.Label(recent, text='Open your first book', font=('Segoe UI Semibold', 17), wraplength=420)
        self.recent_title.grid(row=1, column=0, sticky='w', pady=8)
        recent.bind('<Configure>', lambda e: self.recent_title.configure(wraplength=max(180, e.width - 240)))
        self.recent_position = ttk.Label(recent, style='Muted.TLabel')
        self.recent_position.grid(row=2, column=0, sticky='w')
        self.continue_button = ttk.Button(recent, text='Continue reading', style='Primary.TButton', command=self.continue_recent)
        self.continue_button.grid(row=1, column=1, padx=(12, 0))
        filters = ttk.Frame(self.shelf)
        filters.grid(row=2, column=0, sticky='ew', pady=(0, 10))
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text='Find a book', style='Muted.TLabel').grid(row=0, column=0, padx=(0, 8))
        self.shelf_search = tk.StringVar()
        ttk.Entry(filters, textvariable=self.shelf_search).grid(row=0, column=1, sticky='ew')
        self.shelf_filter = tk.StringVar(value='All books')
        choice = ttk.Combobox(filters, values=['All books', 'In progress', 'Finished'], textvariable=self.shelf_filter, state='readonly', width=13)
        choice.grid(row=0, column=2, padx=(10, 0))
        choice.bind('<<ComboboxSelected>>', lambda e: self.refresh_bookshelf())
        self.shelf_search.trace_add('write', lambda *args: self.refresh_bookshelf())
        self.shelf_view = tk.StringVar(value='Covers')
        view = ttk.Combobox(filters, values=['Covers','List'], textvariable=self.shelf_view, state='readonly', width=7)
        view.grid(row=0,column=3,padx=(8,0))
        view.bind('<<ComboboxSelected>>', lambda e:self.set_shelf_view())
        area = ttk.Frame(self.shelf)
        area.grid(row=3, column=0, sticky='nsew')
        self.build_cover_shelf(area)
        self.list_area = ttk.Frame(area)
        self.book_table = ttk.Treeview(self.list_area, columns=('title', 'place', 'state'), show='headings', selectmode='browse', height=4)
        for name, heading, width in [('title', 'BOOK', 360), ('place', 'SAVED PLACE', 170), ('state', 'STATUS', 120)]:
            self.book_table.heading(name, text=heading)
            self.book_table.column(name, width=width, minwidth=70)
        scroll = ttk.Scrollbar(self.list_area, command=self.book_table.yview)
        scroll.pack(side='right', fill='y')
        self.book_table.configure(yscrollcommand=scroll.set)
        self.book_table.pack(fill='both', expand=True)
        self.book_table.bind('<Double-Button-1>', lambda e: self.open_selected_book())
        self.book_table.bind('<Return>', lambda e: self.open_selected_book())
        self.set_shelf_view()
        actions = ttk.Frame(self.shelf)
        actions.grid(row=4, column=0, sticky='ew', pady=12)
        for title, command in [('Open', self.open_selected_book), ('Finished / unread', self.toggle_finished), ('Choose cover', self.choose_cover), ('Find online', self.find_cover_online), ('Locate file', self.locate_book), ('Remove', self.remove_book)]:
            ttk.Button(actions, text=title, command=command).pack(side='left', padx=(0, 6))
        self.shelf_hint = ttk.Label(self.shelf, style='Muted.TLabel', wraplength=650)
        self.shelf_hint.grid(row=5, column=0, sticky='ew')

    def show_bookshelf(self):
        if self.busy:
            messagebox.showinfo('Bookshelf', 'Stop playback or wait for the book to finish opening before switching books.')
            return
        self.capture_position()
        self.save()
        for panel in self.reading_panels:
            panel.grid_remove()
        self.shelf.grid(row=1, column=0, rowspan=4, sticky='nsew')
        self.refresh_bookshelf()

    def show_reader(self):
        self.shelf.grid_remove()
        for panel in self.reading_panels:
            panel.grid()

    def saved_place(self, identity):
        value = self.saved.get(identity, {})
        if not isinstance(value, dict):
            return 'Saved passage' if value else 'Not started'
        chapter = value.get('chapter_name')
        if chapter:
            return chapter[:32]
        return 'Saved position' if value.get('seconds', 0) or value.get('index', 0) else 'Not started'

    def refresh_bookshelf(self):
        self.return_button.configure(state='normal' if self.parts else 'disabled')
        selected = self.book_table.selection()
        self.shelf_books = {b['id']: b for b in self.library.books()}
        recent = next((b for b in self.shelf_books.values() if not b['finished']), None)
        self.recent_id = recent['id'] if recent else None
        self.recent_title.configure(text=recent['title'] if recent else 'Make room for a new story')
        self.recent_position.configure(text=self.saved_place(recent['id']) if recent else 'Choose Open a book to add Word, EPUB, PDF or TXT files.')
        self.continue_button.configure(state='normal' if recent else 'disabled')
        self.book_table.delete(*self.book_table.get_children())
        query = self.shelf_search.get().casefold().strip()
        mode = self.shelf_filter.get()
        for b in self.shelf_books.values():
            if query not in b['title'].casefold() or mode == 'Finished' and not b['finished'] or mode == 'In progress' and b['finished']:
                continue
            self.book_table.insert('', 'end', iid=b['id'], values=(b['title'], self.saved_place(b['id']), 'Finished' if b['finished'] else 'In progress'))
        ids = self.book_table.get_children()
        if ids:
            self.book_table.selection_set(selected[0] if selected and selected[0] in ids else ids[0])
        self.render_covers()
        self.load_covers()
        self.shelf_hint.configure(text=f'{len(ids)} books shown · Double-click a book to open it. Removing a book from this shelf keeps its file and saved place.' if ids else 'No books found. Open a book to add it, or clear the search and filters.')

    def selected_book(self):
        self.return_button.configure(state='normal' if self.parts else 'disabled')
        selected = self.book_table.selection()
        return self.shelf_books.get(selected[0]) if selected else None

    def continue_recent(self):
        if self.recent_id:
            self.open_library_book(self.shelf_books[self.recent_id], autoplay=True)

    def open_selected_book(self):
        book = self.selected_book()
        if book:
            self.open_library_book(book)

    def open_library_book(self, book, autoplay=False):
        if self.busy:
            return
        if not Path(book['path']).is_file():
            messagebox.showinfo('Book moved', 'This book is no longer at its saved location. Choose its new location to keep your saved place and bookmarks.')
            self.locate_book(book, autoplay)
            return
        self.open_book(book['path'], expected_id=book['id'], autoplay=autoplay)

    def locate_book(self, book=None, autoplay=False):
        if self.busy:
            return
        book = book or self.selected_book()
        if not book:
            return
        name = filedialog.askopenfilename(title='Locate ' + book['title'], filetypes=[('Books', '*.epub *.pdf *.txt *.docx'), ('All files', '*.*')])
        if name:
            self.open_book(name, expected_id=book['id'], autoplay=autoplay)

    def toggle_finished(self):
        book = self.selected_book()
        if book:
            self.library.finish(book['id'], not book['finished'])
            self.refresh_bookshelf()

    def remove_book(self):
        book = self.selected_book()
        if book and messagebox.askyesno('Remove from bookshelf', 'Remove this entry from the bookshelf? The original book, saved place and bookmarks will be kept.'):
            self.library.remove(book['id'])
            self.refresh_bookshelf()

    def load_covers(self):
        if self.cover_loading: return
        pending=[b for b in self.shelf_books.values() if (b['id'],b['path']) not in self.cover_attempted]
        if not pending: return
        self.cover_loading=True
        self.cover_attempted.update((b['id'],b['path']) for b in pending)
        def work():
            try:
                for book in pending:
                    self.cover_store.ensure(book)
            finally:
                self.events.put(('covers_ready',None))
        self.cover_thread = threading.Thread(target=work,daemon=True)
        self.cover_thread.start()
