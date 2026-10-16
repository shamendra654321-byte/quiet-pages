"""Talevoxa: an offline Windows book reader."""
import hashlib
import heapq
import time
import json
import os
import queue
import threading
import sys
from bisect import bisect_right
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from reader_core import load_document
from chapter_audio import read_book
from audio_cache import AudioCache
from live_tempo import TempoControl
from app_version import VERSION
import updates

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
        self.chapters = []
        self.chapter_starts = []
        self.index = 0
        self.book_id = None
        self.update_busy = False
        self.available_update = None
        self.installed_update = None
        self.update_cancel = threading.Event()
        self.shown_chapter = None
        self.pending_highlights = []
        self.highlight_sequence = 0
        self.prepared_chapters = set()
        self.cursor = (0, 0)
        self.durations = {}
        self.restart_at = None
        self.sleep_deadline = None
        self.playing = False
        self.audio_settings = None
        self.seeking = False
        self.playback_speed = TempoControl()
        DATA.mkdir(parents=True, exist_ok=True)
        self.audio_cache = AudioCache(DATA / 'audio-cache')
        try:
            self.saved = json.loads((DATA / 'progress.json').read_text())
        except (OSError, ValueError):
            self.saved = {}
        try:
            self.preferences = json.loads((DATA / 'preferences.json').read_text())
        except (OSError, ValueError):
            self.preferences = {}
        self.auto_updates = tk.BooleanVar(value=self.preferences.get('auto_updates', True))
        menu = tk.Menu(root)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label='Check for updates', command=self.check_updates)
        help_menu.add_checkbutton(label='Check for updates when Talevoxa opens', variable=self.auto_updates,
                                  command=self.save_preferences)
        help_menu.add_command(label=f'About Talevoxa ({VERSION})', command=lambda: messagebox.showinfo(
            'Talevoxa', f'Talevoxa {VERSION}\nFree, private book listening.\nUpdates come from the official Talevoxa GitHub project.'))
        menu.add_cascade(label='Help', menu=help_menu)
        root.configure(menu=menu)
        root.title('Talevoxa — Your books, read aloud')
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
        ttk.Label(frame, text='Talevoxa', font=('Georgia', 30)).pack(anchor='w')
        ttk.Label(frame, text='Make time for a good book. Listen at your own pace.').pack(anchor='w', pady=(0, 18))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        self.open_button = ttk.Button(row, text='Open a book', command=self.open_book)
        self.open_button.pack(side='left')
        self.title = ttk.Label(row, text='Word, EPUB, PDF or TXT')
        self.title.pack(side='left', padx=16)
        self.update_button = ttk.Button(row, text='Check updates', command=self.update_action)
        self.update_button.pack(side='right')
        settings = ttk.Frame(frame)
        settings.pack(fill='x', pady=18)
        self.voice = ttk.Combobox(settings, values=list(VOICES), state='readonly', width=32)
        self.voice.current(0)
        self.voice.pack(side='left')
        self.preview = ttk.Button(settings, text='Preview voice', command=lambda: self.start(True))
        self.preview.pack(side='left', padx=10)
        self.speed = tk.DoubleVar(value=1)
        self.speed.trace_add('write', self.change_speed)
        ttk.Label(settings, text='Speed').pack(side='left', padx=(8, 4))
        ttk.Spinbox(settings, from_=0.5, to=2, increment=0.1, textvariable=self.speed, width=5).pack(side='left')
        chapter_row = ttk.Frame(frame)
        chapter_row.pack(fill='x', pady=(0, 8))
        self.chapter_back = ttk.Button(chapter_row, text='← Chapter', command=lambda: self.move_chapter(-1))
        self.chapter_back.pack(side='left')
        self.chapter_picker = ttk.Combobox(chapter_row, state='disabled')
        self.chapter_picker.pack(side='left', fill='x', expand=True, padx=8)
        self.chapter_picker.bind('<<ComboboxSelected>>', self.select_chapter)
        self.chapter_next = ttk.Button(chapter_row, text='Chapter →', command=lambda: self.move_chapter(1))
        self.chapter_next.pack(side='left')
        self.chapter_only = tk.BooleanVar(value=False)
        self.chapter_option = ttk.Checkbutton(frame, text='Stop after this chapter', variable=self.chapter_only)
        self.chapter_option.pack(anchor='w', pady=(0, 8))
        extras = ttk.Frame(frame)
        extras.pack(fill='x', pady=(0, 8))
        self.smooth = tk.BooleanVar(value=False)
        ttk.Checkbutton(extras, text='Extra buffering (slower PCs)', variable=self.smooth).pack(side='left')
        ttk.Label(extras, text='Sleep timer').pack(side='left', padx=(12, 4))
        self.sleep_choice = ttk.Combobox(extras, values=['Off', '15 minutes', '30 minutes', '60 minutes'], state='readonly', width=12)
        self.sleep_choice.current(0)
        self.sleep_choice.pack(side='left')
        self.sleep_choice.bind('<<ComboboxSelected>>', self.set_sleep_timer)
        ttk.Button(extras, text='↶ 15 seconds', command=self.rewind).pack(side='right')
        seek_row = ttk.Frame(frame)
        seek_row.pack(fill='x')
        ttk.Label(seek_row, text='Seek in chapter').pack(side='left')
        self.seek = ttk.Scale(seek_row, from_=0, to=1)
        self.seek.pack(side='left', fill='x', expand=True, padx=8)
        self.seek.bind('<ButtonRelease-1>', self.seek_in_chapter)
        self.seek.bind('<ButtonPress-1>', lambda event: setattr(self, 'seeking', True))
        self.clean_pdf = tk.BooleanVar(value=True)
        help_menu.add_checkbutton(label='Remove repeated PDF headers and page numbers', variable=self.clean_pdf)
        self.text = tk.Text(frame, height=4, wrap='word', font=('Georgia', 17), bg='#fffdf8', fg='#243d38', relief='flat', padx=24, pady=24)
        self.show_text('Welcome to your listening nook.\n\nOpen a book, choose a voice and press Play.\n\nThe first playback downloads the free voice pack (about 350 MB). After that, your books are read entirely on this computer.')
        controls = ttk.Frame(frame)
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
        self.status.pack(side='bottom', anchor='w')
        controls.pack(side='bottom', fill='x', pady=(10, 10))
        self.text.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)
        if getattr(sys, 'frozen', False) and self.auto_updates.get():
            root.after(2000, lambda: self.check_updates(manual=False))

    def save_preferences(self):
        self.preferences['auto_updates'] = self.auto_updates.get()
        (DATA / 'preferences.json').write_text(json.dumps(self.preferences), encoding='utf-8')

    def check_updates(self, manual=True):
        if self.update_busy:
            return
        self.update_busy = True
        self.update_button.configure(text='Checking…', state='disabled')
        def work():
            try:
                self.events.put(('update_found', (updates.check_update(VERSION), manual)))
            except Exception as exc:
                self.events.put(('update_error', (str(exc), manual)))
        threading.Thread(target=work, daemon=True).start()

    def update_action(self):
        if self.installed_update:
            if self.busy:
                messagebox.showinfo('Update ready', 'Stop reading first, then choose Restart to update. Your place is saved.')
                return
            if messagebox.askyesno('Update ready', 'Restart Talevoxa with the new version now? Your books, voices and saved place will be kept.'):
                try:
                    updates.activate_update(DATA, self.installed_update)
                    self.close()
                except Exception as exc:
                    messagebox.showerror('Could not restart', str(exc))
        elif self.available_update:
            if not getattr(sys, 'frozen', False):
                messagebox.showinfo('Development copy', 'In-app installation is available in the downloaded Windows app. This source copy is updated through GitHub.')
                return
            release = self.available_update
            if not messagebox.askyesno('New Talevoxa update', f'{release["name"]}\n\n{release["notes"][:2500]}\n\nDownload and prepare this update? Reading can continue while it downloads.'):
                return
            self.update_busy = True
            self.update_cancel.clear()
            self.update_button.configure(text='Downloading…', state='disabled')
            def work():
                try:
                    result = updates.install_update(release, DATA, self.update_cancel,
                        lambda text: self.events.put(('update_progress', text)))
                    self.events.put(('update_ready', result))
                except InterruptedError:
                    pass
                except Exception as exc:
                    self.events.put(('update_error', (str(exc), True)))
            threading.Thread(target=work, daemon=True).start()
        else:
            self.check_updates()

    def show_text(self, text):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text)
        self.text.configure(state='disabled')

    def display(self):
        chapter = self.current_chapter()
        if self.shown_chapter != chapter:
            self.show_text('\n\n'.join(self.chapters[chapter].parts))
            self.shown_chapter = chapter
        local_index = self.index - self.chapter_starts[chapter]
        offset = sum(len(part) + 2 for part in self.chapters[chapter].parts[:local_index])
        self.text.tag_configure('reading', background='#e2ebd9')
        self.text.tag_remove('reading', '1.0', 'end')
        self.text.tag_remove('word', '1.0', 'end')
        self.text.tag_add('reading', f'1.0+{offset}c', f'1.0+{offset + len(self.parts[self.index])}c')
        self.text.see(f'1.0+{offset}c')
        self.chapter_picker.current(chapter)
        if not self.seeking:
            self.seek.configure(to=len(self.chapters[chapter].parts) - .001)
            self.seek.set(local_index)
        self.position.configure(text=f'{self.index - self.chapter_starts[chapter] + 1} / {len(self.chapters[chapter].parts)} in chapter')
        self.save()

    def show_word(self, value):
        index, left, right = value
        if self.cancel.is_set() or not self.parts:
            return
        if index != self.index:
            self.index = index
            self.display()
        chapter = self.current_chapter()
        local_index = index - self.chapter_starts[chapter]
        offset = sum(len(part) + 2 for part in self.chapters[chapter].parts[:local_index])
        self.text.tag_configure('word', background='#285c4d', foreground='#ffffff')
        self.text.tag_remove('word', '1.0', 'end')
        self.text.tag_add('word', f'1.0+{offset + left}c', f'1.0+{offset + right}c')
        self.text.tag_raise('word')
        self.text.see(f'1.0+{offset + left}c')

    def flush_highlights(self, finish=False):
        now = time.monotonic()
        while self.pending_highlights and (finish or self.pending_highlights[0][0] <= now):
            _, _, kind, value = heapq.heappop(self.pending_highlights)
            if self.cancel.is_set():
                continue
            if kind == 'position':
                self.index = value
                self.display()
            elif kind == 'cursor':
                self.cursor = value
                if not self.seeking and self.parts:
                    index, seconds = value
                    duration = self.durations.get(index, 0)
                    self.seek.set(index - self.chapter_starts[self.current_chapter()] + (seconds / duration if duration else 0))
            else:
                self.show_word(value)

    def set_sleep_timer(self, event=None):
        value = self.sleep_choice.get()
        self.sleep_deadline = None if value == 'Off' else time.monotonic() + int(value.split()[0]) * 60

    def change_speed(self, *args):
        # Tk values are read only on the UI thread. Invalid partial edits keep
        # the last valid tempo while the person finishes typing.
        try:
            self.playback_speed.set(self.speed.get())
        except tk.TclError:
            pass

    def seek_in_chapter(self, event=None):
        self.seeking = False
        if self.parts and (not self.busy or self.playing):
            chapter = self.current_chapter()
            value = self.seek.get()
            local = min(len(self.chapters[chapter].parts) - 1, int(value))
            target = self.chapter_starts[chapter] + local
            seconds = (value - local) * self.durations.get(target, 0)
            self.seek_to(target, seconds)

    def seek_to(self, index, seconds):
        if self.playing:
            self.stop()
            self.restart_at = (index, seconds)
        elif not self.busy:
            self.index = index
            self.cursor = (index, seconds)
            self.display()

    def rewind(self):
        if not self.parts or (self.busy and not self.playing):
            return
        index, seconds = self.cursor if self.cursor[0] == self.index else (self.index, 0)
        seconds -= 15 * self.playback_speed.get()
        while seconds < 0 and index > self.chapter_starts[self.current_chapter()]:
            index -= 1
            duration = self.durations.get(index)
            if duration is None:
                seconds = 0
                break
            seconds += duration
        self.seek_to(index, max(0, seconds))

    def current_chapter(self):
        return max(0, bisect_right(self.chapter_starts, self.index) - 1)

    def select_chapter(self, event=None):
        if self.chapters and not self.busy:
            self.index = self.chapter_starts[self.chapter_picker.current()]
            self.cursor = (self.index, 0)
            self.display()

    def move_chapter(self, step):
        if self.chapters and not self.busy:
            chapter = max(0, min(len(self.chapters) - 1, self.current_chapter() + step))
            self.index = self.chapter_starts[chapter]
            self.cursor = (self.index, 0)
            self.display()

    def save(self):
        if self.book_id:
            self.saved[self.book_id] = self.index
            temp = DATA / 'progress.tmp'
            temp.write_text(json.dumps(self.saved), encoding='utf-8')
            temp.replace(DATA / 'progress.json')

    def open_book(self):
        if self.busy:
            return
        name = filedialog.askopenfilename(filetypes=[('Books and Word documents', '*.epub *.pdf *.txt *.docx *.doc'), ('All files', '*.*')])
        if not name:
            return
        self.set_busy(True)
        self.cancel.clear()
        self.status.configure(text='Opening book…')
        clean_pdf = self.clean_pdf.get()
        def work():
            try:
                book = load_document(name, progress=lambda text: self.events.put(('status', text)), cancel=self.cancel, clean_pdf=clean_pdf)
                parts = book.parts
                identity = hashlib.sha256('\n'.join(parts).encode()).hexdigest()
                self.events.put(('book', (Path(name).stem, book, identity)))
            except InterruptedError:
                pass
            except Exception as exc:
                self.events.put(('error', str(exc)))
            finally:
                self.events.put(('done', None))
        threading.Thread(target=work, daemon=True).start()

    def move(self, step):
        if self.parts and not self.busy:
            self.index = max(0, min(len(self.parts) - 1, self.index + step))
            self.cursor = (self.index, 0)
            self.display()

    def set_busy(self, value):
        self.busy = value
        for widget in (self.open_button, self.preview, self.play, self.back, self.next, self.chapter_back, self.chapter_next, self.chapter_option):
            widget.configure(state='disabled' if value else 'normal')
        self.chapter_picker.configure(state='disabled' if value or not self.chapters else 'readonly')

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
        self.playback_speed.set(speed)
        if not preview and self.audio_settings != (voice, 1):
            self.durations.clear()
            self.cursor = (self.index, 0)
            self.audio_settings = (voice, 1)
        start = self.index
        start_seconds = self.cursor[1] if self.cursor[0] == start and not preview else 0
        reserve = 12 if self.smooth.get() else 0
        parts = ['Settle into your favourite chair and let the story begin. The evening light slipped across the quiet room, and a new adventure waited on the next page.'] if preview else list(self.parts)
        end = len(parts)
        chapter_starts = list(self.chapter_starts)
        if not preview and self.chapter_only.get():
            chapter = self.current_chapter()
            if chapter + 1 < len(self.chapter_starts):
                end = self.chapter_starts[chapter + 1]
        self.cancel.clear()
        self.pending_highlights.clear()
        self.prepared_chapters.clear()
        self.paused.clear()
        self.pause.configure(text='Pause')
        self.set_busy(True)
        self.playing = not preview
        self.status.configure(text='Preparing your voice…')
        def work():
            try:
                import sounddevice as sd
                first = 0 if preview else start
                read_book(self.get_engine, parts, first, end, chapter_starts if not preview else [0],
                          voice, 1, self.cancel, self.paused, self.events, sd.OutputStream, preview,
                          cache=self.audio_cache, start_seconds=start_seconds, buffer_seconds=reserve,
                          live_speed=self.playback_speed.get)
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
        self.restart_at = None
        self.cancel.set()
        self.pending_highlights.clear()
        self.paused.clear()
        self.pause.configure(text='Pause')
        if self.busy:
            self.status.configure(text='Stopping…')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'status':
                    if str(value).startswith('Reading aloud') and self.current_chapter() + 1 in self.prepared_chapters:
                        value = 'Reading aloud · Next chapter ready'
                    self.status.configure(text=value)
                elif kind == 'position':
                    self.index = value
                    self.display()
                elif kind == 'at':
                    due, action, data = value
                    self.highlight_sequence += 1
                    heapq.heappush(self.pending_highlights, (due, self.highlight_sequence, action, data))
                elif kind == 'prepared':
                    self.prepared_chapters.add(value)
                    if value == self.current_chapter() + 1 and str(self.status.cget('text')).startswith('Reading aloud'):
                        self.status.configure(text='Reading aloud · Next chapter ready')
                elif kind == 'duration':
                    self.durations[value[0]] = value[1]
                elif kind == 'book':
                    self.shown_chapter = None
                    name, book, self.book_id = value
                    self.parts = book.parts
                    self.durations.clear()
                    self.chapters = book.chapters
                    self.chapter_starts = book.starts
                    self.chapter_picker.configure(values=[f'{i + 1}. {chapter.title}' for i, chapter in enumerate(self.chapters)])
                    self.index = max(0, min(int(self.saved.get(self.book_id, 0)), len(self.parts) - 1))
                    self.cursor = (self.index, 0)
                    self.title.configure(text=name[:28])
                    self.display()
                elif kind == 'error':
                    self.pending_highlights.clear()
                    messagebox.showerror('Talevoxa', value)
                elif kind == 'done':
                    self.flush_highlights(finish=True)
                    if not self.cancel.is_set():
                        self.cursor = (self.index, 0)
                    self.pending_highlights.clear()
                    self.set_busy(False)
                    self.playing = False
                    self.pause.configure(text='Pause')
                    self.status.configure(text='Ready · Your place is saved')
                    if self.restart_at is not None:
                        self.index, seconds = self.restart_at
                        self.cursor = (self.index, seconds)
                        self.restart_at = None
                        self.display()
                        self.root.after_idle(self.start)
                elif kind == 'update_found':
                    self.available_update, manual = value
                    self.update_busy = False
                    self.update_button.configure(text='Update available' if self.available_update else 'Check updates', state='normal')
                    if manual:
                        if self.available_update:
                            self.update_action()
                        else:
                            messagebox.showinfo('Talevoxa updates', f'You are up to date ({VERSION}).')
                elif kind == 'update_progress':
                    self.update_button.configure(text=value.replace('Downloading update:', 'Update:').replace('Checking and unpacking update…', 'Unpacking…'))
                elif kind == 'update_ready':
                    self.installed_update = value
                    self.update_busy = False
                    self.update_button.configure(text='Restart to update', state='normal')
                elif kind == 'update_error':
                    error, manual = value
                    self.update_busy = False
                    self.update_button.configure(text='Retry update' if self.available_update else 'Check updates', state='normal')
                    if manual:
                        messagebox.showerror('Talevoxa updates', f'Could not finish the update. Your current app is unchanged.\n\n{error}')
        except queue.Empty:
            pass
        self.flush_highlights()
        if self.sleep_deadline is not None and time.monotonic() >= self.sleep_deadline:
            self.sleep_deadline = None
            self.sleep_choice.set('Off')
            self.stop()
        self.root.after(20, self.poll)

    def close(self):
        self.cancel.set()
        self.update_cancel.set()
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
        if (getattr(sys, 'frozen', False) and '--skip-update' not in sys.argv
                and '--updated-start' not in sys.argv and updates.redirect_to_installed(DATA, VERSION)):
            sys.exit(0)
        root = tk.Tk()
        Reader(root)
        root.mainloop()
