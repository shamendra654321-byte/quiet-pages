"""Scrollable cover cards, with a compact list retained for keyboard navigation."""
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

class CoverShelf:
    def find_missing_covers(self):
        previous = getattr(self, 'batch_covers', None)
        if previous and not previous.closed:
            previous.window.lift(); return
        from batch_covers import BatchCovers
        self.batch_covers = BatchCovers(self)

    def build_cover_shelf(self, area):
        self.cover_area = ttk.Frame(area)
        self.cover_canvas = tk.Canvas(self.cover_area, bg='#f2f4f1', highlightthickness=0, height=100)
        scroll = ttk.Scrollbar(self.cover_area, command=self.cover_canvas.yview)
        scroll.pack(side='right', fill='y'); self.cover_canvas.pack(side='left', fill='both', expand=True)
        self.cover_canvas.configure(yscrollcommand=scroll.set)
        self.cover_frame = ttk.Frame(self.cover_canvas)
        self.cover_window = self.cover_canvas.create_window(0, 0, window=self.cover_frame, anchor='nw')
        self.cover_frame.bind('<Configure>', lambda e: self.cover_canvas.configure(scrollregion=self.cover_canvas.bbox('all')))
        self.cover_columns = 0; self.cover_cards = []; self.cover_images = []
        self.cover_canvas.bind('<Configure>', self.layout_covers)
        self.cover_canvas.bind('<MouseWheel>', self.scroll_covers)
    def scroll_covers(self, event):
        self.cover_canvas.yview_scroll(-int(event.delta/120), 'units')
        return 'break'
    def layout_covers(self, event=None):
        width = max(1, self.cover_canvas.winfo_width())
        self.cover_canvas.itemconfigure(self.cover_window, width=width)
        columns = max(1, width//176)
        for i in range(max(columns, self.cover_columns)):
            self.cover_frame.columnconfigure(i, weight=1 if i<columns else 0, uniform='cards')
        self.cover_columns = columns
        for i, card in enumerate(self.cover_cards):
            card.grid(row=i//columns, column=i%columns, sticky='n', padx=8, pady=9)
    def set_shelf_view(self):
        if self.shelf_view.get() == 'Covers':
            self.list_area.pack_forget(); self.cover_area.pack(fill='both', expand=True)
        else:
            self.cover_area.pack_forget(); self.list_area.pack(fill='both', expand=True)
    def render_covers(self):
        for widget in self.cover_frame.winfo_children(): widget.destroy()
        self.cover_cards=[]; self.cover_images=[]; self.card_borders={}
        colors=['#31574c','#5b5276','#935e4b','#456578','#777044','#784f64']
        for identity in self.book_table.get_children():
            book=self.shelf_books[identity]
            card=ttk.Frame(self.cover_frame, width=160)
            art=tk.Canvas(card,width=144,height=180,highlightthickness=3,highlightbackground='#f2f4f1',bg='#fffefb',cursor='hand2',takefocus=True)
            art.pack()
            path=self.cover_store.path(identity)
            try:
                with Image.open(path) as image:
                    image.thumbnail((140,176),Image.Resampling.LANCZOS)
                    photo=ImageTk.PhotoImage(image,master=self.root)
                self.cover_images.append(photo); art.create_image(74,92,image=photo)
            except (OSError,ValueError):
                color=colors[int(hashlib.sha256(identity.encode()).hexdigest()[:4],16)%len(colors)]
                art.create_rectangle(3,3,148,184,fill=color,outline='')
                art.create_line(12,4,12,183,fill='#ffffff',stipple='gray50')
                art.create_text(80,86,text=book['title'][:95],width=112,fill='white',font=('Georgia',14),justify='center')
                art.create_text(80,162,text='TALEVOXA',fill='#e5e8e2',font=('Segoe UI',8))
            title=ttk.Label(card,text=book['title'][:80],wraplength=155,font=('Segoe UI Semibold',10),justify='center',anchor='center');title.pack(fill='x',pady=(6,2))
            from book_details import series_label
            ttk.Label(card,text=' - '.join(filter(None,[book.get('author',''),series_label(book)])),wraplength=155,justify='center',anchor='center').pack(fill='x')
            detail=ttk.Label(card,text='Finished' if book['finished'] else self.saved_place(identity),wraplength=155,style='Muted.TLabel',anchor='center');detail.pack(fill='x')
            for widget in (card,art,title,detail):
                widget.bind('<Button-1>', lambda e,k=identity:self.select_cover(k))
                widget.bind('<Double-Button-1>',lambda e,k=identity:self.open_library_book(self.shelf_books[k]))
                widget.bind('<MouseWheel>',self.scroll_covers)
            art.bind('<Return>',lambda e,k=identity:self.open_library_book(self.shelf_books[k]))
            art.bind('<space>',lambda e,k=identity:self.select_cover(k))
            art.bind('<FocusIn>',lambda e,k=identity:self.select_cover(k))
            self.card_borders[identity]=art;self.cover_cards.append(card)
        self.layout_covers();self.select_cover(self.book_table.selection()[0] if self.book_table.selection() else None)
    def select_cover(self, identity):
        if identity: self.book_table.selection_set(identity)
        for key,widget in self.card_borders.items():
            widget.configure(highlightbackground='#245e4d' if key==identity else '#f2f4f1')
    def choose_cover(self):
        book=self.selected_book()
        if not book: return
        name=filedialog.askopenfilename(title='Choose a cover for '+book['title'],filetypes=[('Cover images','*.png *.jpg *.jpeg *.webp'),('All files','*.*')])
        if not name: return
        try: self.cover_store.choose(book['id'],name)
        except Exception as error:
            messagebox.showerror('Cover image',str(error));return
        self.render_covers()

    def find_cover_online(self):
        book = self.selected_book()
        if not book: return
        previous = getattr(self, 'cover_search', None)
        if previous and not previous.closed:
            previous.close()
        from cover_search import CoverSearch
        self.cover_search = CoverSearch(self, book)
