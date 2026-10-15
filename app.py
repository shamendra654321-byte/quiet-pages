"""Quiet Pages: an offline Windows book reader."""
import hashlib
import json
import os
import queue
import threading
import time
import sys
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from reader_core import load_book

DATA = Path(os.environ.get('QUIET_PAGES_DATA', Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'QuietPages'))
VOICES = {
    'Heart · American · Female': 'af_heart',
    'Bella · American · Female': 'af_bella',
    'Nicole · American · Female': 'af_nicole',
    'Michael · American · Male': 'am_michael',
    'Fenrir · American · Male': 'am_fenrir',
    'Emma · British · Female': 'bf_emma',
    'Isabella · British · Female': 'bf_isabella',
    'George · British · Male': 'bm_george',
    'Fable · British · Male': 'bm_fable',
}
BASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'


class Reader:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.paused = threading.Event()
        self.busy = False
        self.engine = None
        self.parts = []
        self.index = 0
        self.book_id = None
        DATA.mkdir(parents=True, exist_ok=True)
        try:
            self.saved = json.loads((DATA / 'progress.json').read_text())
        except (OSError, ValueError):
            self.saved = {}
        root.title('Quiet Pages — Your books, read aloud')
        root.geometry('920x700')
        root.minsize(720, 550)
        root.configure(bg='#f5f2eb')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#f5f2eb')
        style.configure('TLabel', background='#f5f2eb', foreground='#243d38', font=('Segoe UI', 11))
        style.configure('TButton', font=('Segoe UI', 11), padding=9)
        frame = ttk.Frame(root, padding=26)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Quiet Pages', font=('Georgia', 30)).pack(anchor='w')
        ttk.Label(frame, text='Make time for a good book. Listen at your own pace.').pack(anchor='w', pady=(0, 18))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        self.open_button = ttk.Button(row, text='Open a book', command=self.open_book)
        self.open_button.pack(side='left')
        self.title = ttk.Label(row, text='EPUB, PDF or TXT')
        self.title.pack(side='left', padx=16)
        settings = ttk.Frame(frame)
        settings.pack(fill='x', pady=18)
        self.voice = ttk.Combobox(settings, values=list(VOICES), state='readonly', width=32)
        self.voice.current(0)
        self.voice.pack(side='left')
        self.preview = ttk.Button(settings, text='Preview voice', command=lambda: self.start(True))
        self.preview.pack(side='left', padx=10)
        self.speed = tk.DoubleVar(value=1)
        ttk.Label(settings, text='Speed').pack(side='left', padx=(8, 4))
        ttk.Spinbox(settings, from_=0.5, to=2, increment=0.1, textvariable=self.speed, width=5).pack(side='left')
        self.text = tk.Text(frame, wrap='word', font=('Georgia', 17), bg='#fffdf8', fg='#243d38', relief='flat', padx=24, pady=24)
        self.text.pack(fill='both', expand=True)
        self.show_text('Welcome to your listening nook.\n\nOpen a book, choose a voice and press Play.\n\nThe first playback downloads the free voice pack (about 350 MB). After that, your books are read entirely on this computer.')
        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(18, 10))
        self.back = ttk.Button(controls, text='Previous', command=lambda: self.move(-1))
        self.back.pack(side='left')
        self.play = ttk.Button(controls, text='Play', command=self.start)
        self.play.pack(side='left', padx=8)
        self.pause = ttk.Button(controls, text='Pause', command=self.toggle_pause)
        self.pause.pack(side='left')
        ttk.Button(controls, text='Stop', command=self.stop).pack(side='left', padx=8)
        self.next = ttk.Button(controls, text='Next', command=lambda: self.move(1))
        self.next.pack(side='left')
        self.position = ttk.Label(controls, text='No book open')
        self.position.pack(side='right')
        self.status = ttk.Label(frame, text='Private listening · Free voices · No account needed')
        self.status.pack(anchor='w')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def show_text(self, text):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text)
        self.text.configure(state='disabled')

    def display(self):
        self.show_text(self.parts[self.index])
        self.position.configure(text=f'Passage {self.index + 1} of {len(self.parts)}')
        self.save()

    def save(self):
        if self.book_id:
            self.saved[self.book_id] = self.index
            temp = DATA / 'progress.tmp'
            temp.write_text(json.dumps(self.saved), encoding='utf-8')
            temp.replace(DATA / 'progress.json')

    def open_book(self):
        if self.busy:
            return
        name = filedialog.askopenfilename(filetypes=[('Books', '*.epub *.pdf *.txt')])
        if not name:
            return
        self.set_busy(True)
        self.status.configure(text='Opening book…')
        def work():
            try:
                parts = load_book(name)
                identity = hashlib.sha256('\n'.join(parts).encode()).hexdigest()
                self.events.put(('book', (Path(name).stem, parts, identity)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=work, daemon=True).start()

    def move(self, step):
        if self.parts and not self.busy:
            self.index = max(0, min(len(self.parts) - 1, self.index + step))
            self.display()

    def set_busy(self, value):
        self.busy = value
        for widget in (self.open_button, self.preview, self.play, self.back, self.next):
            widget.configure(state='disabled' if value else 'normal')

    def get_engine(self):
        if self.engine is None:
            for name in ('kokoro-v1.0.onnx', 'voices-v1.0.bin'):
                target = DATA / name
                if not target.exists():
                    partial = target.with_suffix('.download')
                    try:
                        with urllib.request.urlopen(BASE + name, timeout=30) as response, partial.open('wb') as output:
                            total = int(response.headers.get('Content-Length', 0))
                            count = 0
                            while True:
                                if self.cancel.is_set():
                                    raise InterruptedError()
                                chunk = response.read(1024 * 1024)
                                if not chunk:
                                    break
                                output.write(chunk)
                                count += len(chunk)
                                self.events.put(('status', f'Downloading free voices: {count // 1048576} / {total // 1048576} MB'))
                        partial.replace(target)
                    finally:
                        partial.unlink(missing_ok=True)
            self.events.put(('status', 'Loading voices…'))
            from kokoro_onnx import Kokoro
            self.engine = Kokoro(str(DATA / 'kokoro-v1.0.onnx'), str(DATA / 'voices-v1.0.bin'))
        return self.engine

    def start(self, preview=False):
        if self.busy or (not preview and not self.parts):
            return
        try:
            speed = float(self.speed.get())
            if not 0.5 <= speed <= 2:
                raise ValueError()
        except (ValueError, tk.TclError):
            messagebox.showerror('Speed', 'Choose a speed between 0.5 and 2.0.')
            return
        voice = VOICES[self.voice.get()]
        start = self.index
        parts = ['Settle into your favourite chair and let the story begin. The evening light slipped across the quiet room, and a new adventure waited on the next page.'] if preview else list(self.parts)
        self.cancel.clear()
        self.paused.clear()
        self.pause.configure(text='Pause')
        self.set_busy(True)
        self.status.configure(text='Preparing your voice…')
        def work():
            try:
                engine = self.get_engine()
                import sounddevice as sd
                for i in range(0 if preview else start, len(parts)):
                    if self.cancel.is_set():
                        break
                    self.events.put(('status', 'Preparing next passage…'))
                    samples, rate = engine.create(parts[i], voice=voice, speed=speed, lang='en-gb' if voice.startswith('b') else 'en-us')
                    if self.cancel.is_set():
                        break
                    if not preview:
                        self.events.put(('position', i))
                    self.events.put(('status', 'Reading aloud'))
                    with sd.OutputStream(samplerate=rate, channels=1, dtype='float32') as stream:
                        for offset in range(0, len(samples), 1024):
                            while self.paused.is_set() and not self.cancel.is_set():
                                time.sleep(0.05)
                            if self.cancel.is_set():
                                stream.abort()
                                break
                            stream.write(samples[offset:offset + 1024].reshape(-1, 1))
                    if not preview and not self.cancel.is_set() and i + 1 < len(parts):
                        self.events.put(('position', i + 1))
            except InterruptedError:
                pass
            except Exception as exc:
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=work, daemon=True).start()

    def toggle_pause(self):
        if not self.busy:
            return
        if self.paused.is_set():
            self.paused.clear()
            self.pause.configure(text='Pause')
        else:
            self.paused.set()
            self.pause.configure(text='Resume')

    def stop(self):
        self.cancel.set()
        self.paused.clear()
        self.pause.configure(text='Pause')
        if self.busy:
            self.status.configure(text='Stopping…')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'status':
                    self.status.configure(text=value)
                elif kind == 'position':
                    self.index = value
                    self.display()
                elif kind == 'book':
                    name, self.parts, self.book_id = value
                    self.index = max(0, min(int(self.saved.get(self.book_id, 0)), len(self.parts) - 1))
                    self.title.configure(text=name[:55])
                    self.display()
                elif kind == 'error':
                    messagebox.showerror('Quiet Pages', value)
                elif kind == 'done':
                    self.set_busy(False)
                    self.pause.configure(text='Pause')
                    self.status.configure(text='Ready · Your place is saved')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        self.cancel.set()
        self.root.destroy()


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        from smoke_test import run
        try:
            run()
        except Exception:
            import traceback
            DATA.mkdir(parents=True, exist_ok=True)
            (DATA / 'smoke-error.txt').write_text(traceback.format_exc())
            raise
    else:
        root = tk.Tk()
        Reader(root)
        root.mainloop()
