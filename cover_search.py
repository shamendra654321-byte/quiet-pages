"""An explicit search-and-select flow; never guesses or replaces artwork silently."""
import io
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import online_covers
from covers import save_image

class CoverSearch:
    def __init__(self, reader, book):
        self.reader, self.book = reader, dict(book)
        self.cancel = threading.Event(); self.events = queue.Queue(); self.closed = False
        self.rows = {}; self.images = []; self.data = {}; self.busy = False
        self.window = tk.Toplevel(reader.root); self.window.title('Find a cover online - Talevoxa')
        self.window.geometry('760x600'); self.window.minsize(650,500)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        shell = ttk.Frame(self.window,padding=18); shell.pack(fill='both',expand=True)
        shell.columnconfigure(1,weight=1); shell.rowconfigure(4,weight=1)
        ttk.Label(shell,text='Find a real book cover',font=('Georgia',21)).grid(row=0,column=0,columnspan=3,sticky='w')
        ttk.Label(shell,text='Search sends the title and optional author below to Open Library. Your book file and reading history stay on this PC.',wraplength=680,style='Muted.TLabel').grid(row=1,column=0,columnspan=3,sticky='ew',pady=(8,14))
        ttk.Label(shell,text='Book title').grid(row=2,column=0,sticky='w',padx=(0,10))
        self.title = tk.StringVar(value=book['title'].replace('_',' '))
        ttk.Entry(shell,textvariable=self.title).grid(row=2,column=1,sticky='ew')
        self.search_button=ttk.Button(shell,text='Search',command=self.search)
        self.search_button.grid(row=2,column=2,rowspan=2,padx=(10,0))
        ttk.Label(shell,text='Author (optional)').grid(row=3,column=0,sticky='w',padx=(0,10),pady=8)
        self.author=tk.StringVar();ttk.Entry(shell,textvariable=self.author).grid(row=3,column=1,sticky='ew',pady=8)
        area=ttk.Frame(shell);area.grid(row=4,column=0,columnspan=3,sticky='nsew')
        style=ttk.Style(self.window);style.configure('CoverSearch.Treeview',rowheight=112)
        self.table=ttk.Treeview(area,columns=('book','author'),show='tree headings',height=3,selectmode='browse',style='CoverSearch.Treeview')
        self.table.heading('#0',text='COVER');self.table.column('#0',width=92,minwidth=92,stretch=False)
        self.table.heading('book',text='BOOK');self.table.column('book',width=260,minwidth=150)
        self.table.heading('author',text='AUTHOR / FIRST PUBLISHED');self.table.column('author',width=230,minwidth=120)
        scrollbar=ttk.Scrollbar(area,command=self.table.yview);scrollbar.pack(side='right',fill='y')
        self.table.configure(yscrollcommand=scrollbar.set);self.table.pack(fill='both',expand=True)
        self.table.bind('<<TreeviewSelect>>',self.selection_changed)
        self.status=ttk.Label(shell,text='Check the title, then Search. Choose the cover that matches your book.',wraplength=680,style='Muted.TLabel')
        self.status.grid(row=5,column=0,columnspan=3,sticky='ew',pady=12)
        controls=ttk.Frame(shell);controls.grid(row=6,column=0,columnspan=3,sticky='ew')
        self.use_button=ttk.Button(controls,text='Use selected cover',command=self.use,state='disabled');self.use_button.pack(side='left')
        ttk.Button(controls,text='Close',command=self.close).pack(side='right')
        ttk.Label(shell,text='Cover images provided by Open Library. Chosen covers are saved for offline use.',style='Muted.TLabel').grid(row=7,column=0,columnspan=3,sticky='w',pady=(10,0))
        self.window.bind('<Return>',lambda e:self.search() if not self.busy else None)
        self.after_id=self.window.after(100,self.poll)
    def search(self):
        if self.busy or self.closed: return
        title, author=self.title.get().strip(),self.author.get().strip()
        if not title: self.status.configure(text='Enter a book title first.');return
        self.busy=True;self.search_button.configure(state='disabled');self.use_button.configure(state='disabled')
        self.table.delete(*self.table.get_children());self.images=[];self.rows={};self.data={}
        self.status.configure(text='Searching Open Library...')
        def worker():
            try:
                matches=online_covers.search(title,author,self.cancel)
                self.events.put(('matches',matches))
                for match in matches:
                    if self.cancel.is_set(): break
                    key=str(match['cover_id'])
                    try: self.events.put(('image',(key,online_covers.download(match['cover_id'],self.cancel))))
                    except InterruptedError: break
                    except Exception: self.events.put(('missing',key))
            except InterruptedError: pass
            except Exception: self.events.put(('error','Could not reach Open Library. Check your connection and try Search again. Your current cover is unchanged.'))
            finally: self.events.put(('done',None))
        self.worker=threading.Thread(target=worker,daemon=True);self.worker.start()
    def selection_changed(self,event=None):
        selected=self.table.selection()
        self.use_button.configure(state='normal' if selected and selected[0] in self.data else 'disabled')
    def poll(self):
        if self.closed:return
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='matches':
                    for book in value:
                        key=str(book['cover_id']);self.rows[key]=book
                        self.table.insert('','end',iid=key,values=(book['title'],book['author']+(' / '+book['year'] if book['year'] else '')))
                    self.status.configure(text='Loading cover previews...' if value else 'No covers found. Try a shorter title or add the author. You can also use Choose cover on the bookshelf.')
                elif kind=='image':
                    key,data=value
                    with Image.open(io.BytesIO(data)) as image:
                        image.thumbnail((76,104),Image.Resampling.LANCZOS);photo=ImageTk.PhotoImage(image,master=self.window)
                    self.images.append(photo);self.data[key]=data;self.table.item(key,image=photo)
                    self.selection_changed()
                elif kind=='missing':self.table.item(value,text='Unavailable')
                elif kind=='error':self.status.configure(text=value)
                elif kind=='done':
                    self.busy=False;self.search_button.configure(state='normal')
                    if self.data:self.status.configure(text='Select a cover, then Use selected cover. Matches may show a different edition.')
                    elif self.rows:self.status.configure(text='Matches found, but their cover images could not be loaded. Try Search again later.')
        except queue.Empty:pass
        self.after_id=self.window.after(100,self.poll)
    def use(self):
        selected=self.table.selection()
        if not selected or selected[0] not in self.data:return
        if self.book['id'] not in {b['id'] for b in self.reader.library.books()}:
            self.status.configure(text='This book was removed from the shelf. Reopen it before choosing a cover.');return
        try:
            with self.reader.cover_store.lock:
                save_image(io.BytesIO(self.data[selected[0]]),self.reader.cover_store.path(self.book['id']))
        except Exception as error:messagebox.showerror('Cover image',str(error),parent=self.window);return
        self.reader.render_covers();self.close()
    def close(self):
        if self.closed:return
        self.closed=True;self.cancel.set();self.window.after_cancel(self.after_id);self.window.destroy()
