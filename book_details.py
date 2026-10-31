"""Local bibliographic metadata and numeric series ordering."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox

def valid_number(value):
    value = str(value).strip()
    if not value: return ''
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0: raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError('Use a positive book number such as 1, 2 or 2.5, or leave it blank.')
    return str(number)

def series_label(book):
    name = book.get('series', '')
    return name + (' · Book ' + book['series_number'] if name and book.get('series_number') else '')

def sorted_books(books, mode):
    def text(v): return ' '.join(v.split()).casefold()
    def series(b):
        name = text(b.get('series',''))
        n = b.get('series_number','')
        return (not bool(name), name, not bool(n), Decimal(n or '0'), text(b['title']))
    books = list(books)
    if mode == 'Author': return sorted(books,key=lambda b:(not bool(b.get('author')),text(b.get('author','')),series(b)))
    if mode == 'Series': return sorted(books,key=lambda b:(series(b),text(b.get('author',''))))
    if mode == 'Title': return sorted(books,key=lambda b:text(b['title']))
    return books

def read_details(path):
    try:
        with zipfile.ZipFile(path) as archive:
            def xml(name):
                if archive.getinfo(name).file_size > 2_000_000: raise ValueError()
                return ET.fromstring(archive.read(name))
            if Path(path).suffix.lower() == '.docx':
                root = xml('docProps/core.xml')
                return root.findtext('.//{*}creator',''), '', ''
            if Path(path).suffix.lower() != '.epub': return '', '', ''
            rootfile = xml('META-INF/container.xml').find('.//{*}rootfile')
            root = xml(rootfile.get('full-path'))
            authors = [e.text.strip() for e in root.findall('.//{*}creator') if e.text]
            meta = root.findall('.//{*}meta')
            series = next((m.get('content','') for m in meta if m.get('name') == 'calibre:series'), '')
            number = next((m.get('content','') for m in meta if m.get('name') == 'calibre:series_index'), '')
            if not series:
                for m in meta:
                    if m.get('property') != 'belongs-to-collection': continue
                    ref = '#' + m.get('id','')
                    if not any(x.get('refines') == ref and x.get('property') == 'collection-type' and x.text == 'series' for x in meta): continue
                    series = m.text or ''
                    number = next((x.text or '' for x in meta if x.get('refines') == ref and x.get('property') == 'group-position'), '')
                    break
            try: number = valid_number(number)
            except ValueError: number = ''
            return ', '.join(authors), series, number
    except Exception: return '', '', ''

class DetailsDialog:
    def __init__(self, reader, book):
        self.window = tk.Toplevel(reader.root)
        self.window.title('Book details — Talevoxa')
        shell = ttk.Frame(self.window,padding=20); shell.pack(fill='both',expand=True)
        ttk.Label(shell,text=book['title'],wraplength=420).grid(row=0,column=0,columnspan=2,pady=(0,12))
        fields = []
        for i,(key,label) in enumerate([('author','Author'),('series','Series'),('series_number','Book number')],1):
            ttk.Label(shell,text=label).grid(row=i,column=0,sticky='w',padx=(0,12),pady=5)
            value = tk.StringVar(value=book.get(key,'')); fields.append(value)
            ttk.Entry(shell,textvariable=value,width=36).grid(row=i,column=1)
        ttk.Label(shell,text='Use numbers such as 1, 2, 2.5, 3. Leave series blank for standalone books.',wraplength=420).grid(row=4,column=0,columnspan=2,pady=12)
        def save():
            try: reader.library.set_details(book['id'],*(v.get() for v in fields))
            except ValueError as error: messagebox.showerror('Book details',str(error),parent=self.window); return
            reader.refresh_bookshelf(); self.window.destroy()
        ttk.Button(shell,text='Save',command=save).grid(row=5,column=1,sticky='e')
