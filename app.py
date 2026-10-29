"""Talevoxa: an offline Windows book reader."""
import hashlib
import heapq
import time
import json
import os
import queue
import threading
import sys
import uuid
from bisect import bisect_right
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from reader_core import load_document
from chapter_audio import read_book
from audio_cache import AudioCache
from live_tempo import TempoControl
from app_version import VERSION
import updates
from reading_position import position as restore_position, source_seconds

DATA = Path(os.environ.get('QUIET_PAGES_DATA', Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'QuietPages'))
from voice_catalog import VOICES as CATALOG, label
from voice_store import VoiceStore
from voice_browser import VoiceBrowser
VOICES = {label(v): v['id'] for v in CATALOG}



from bookshelf import Library, Bookshelf

class Reader(VoiceBrowser, Bookshelf):
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
        self.cursor_span = None
        self.text_offset = 0
        self.position_voice = None
        self.active_voice = None
        self.last_save = time.monotonic()
        self.restart_paused = False
        self.bookmark_window = None
        self.durations = {}
        self.restart_at = None
        self.sleep_deadline = None
        self.playing = False
        self.previewing = False
        self.audio_settings = None
        self.seeking = False
        self.playback_speed = TempoControl()
        DATA.mkdir(parents=True, exist_ok=True)
        self.library = Library(DATA / 'library.sqlite3')
        self.opening_path = None
        self.opening_autoplay = False
        self.opening_success = False
        self.audio_cache = AudioCache(DATA / 'audio-cache')
        try:
            self.saved = json.loads((DATA / 'progress.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.saved = {}
        if not isinstance(self.saved, dict):
            self.saved = {}
        try:
            self.preferences = json.loads((DATA / 'preferences.json').read_text())
        except (OSError, ValueError):
            self.preferences = {}
        if not isinstance(self.preferences, dict):
            self.preferences = {}
        self.voice_store = VoiceStore(DATA)
        self.init_voices()
        self.auto_updates = tk.BooleanVar(value=self.preferences.get('auto_updates', True))
        menu = tk.Menu(root)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label='Check for updates', command=self.check_updates)
        help_menu.add_checkbutton(label='Check for updates when Talevoxa opens', variable=self.auto_updates,
                                  command=self.save_preferences)
        help_menu.add_command(label=f'About Talevoxa ({VERSION})', command=lambda: messagebox.showinfo(
            'Talevoxa', f'Talevoxa {VERSION}\nFree, private book listening.\nUpdates come from the official Talevoxa GitHub project.'))
        menu.add_cascade(label='Help', menu=help_menu)
        bookmarks_menu = tk.Menu(menu, tearoff=False)
        bookmarks_menu.add_command(label='Add bookmark…', command=self.add_bookmark, accelerator='Ctrl+B')
        bookmarks_menu.add_command(label='Show bookmarks…', command=self.show_bookmarks)
        menu.add_cascade(label='Bookmarks', menu=bookmarks_menu)
        root.bind('<Control-b>', lambda event: self.add_bookmark())
        root.configure(menu=menu)
        from reader_ui import build_reader
        build_reader(self, help_menu, VOICES)
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
        self.text_offset = left
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
            due, _, kind, value = heapq.heappop(self.pending_highlights)
            if self.cancel.is_set():
                continue
            if kind == 'position':
                self.index = value
                self.cursor = (value, 0)
                self.cursor_span = None
                self.text_offset = 0
                self.display()
            elif kind == 'cursor':
                if self.active_voice:
                    self.position_voice = self.active_voice
                self.cursor = value[:2]
                self.cursor_span = (value[0], value[1], value[2], due, value[3]) if len(value) == 4 else None
                self.refresh_cursor()
                if not self.seeking and self.parts:
                    index, seconds = self.cursor
                    duration = self.durations.get(index, 0)
                    self.seek.set(index - self.chapter_starts[self.current_chapter()] + (seconds / duration if duration else 0))
            else:
                self.show_word(value)

    def refresh_cursor(self):
        if self.cursor_span:
            index, start, end, due, duration = self.cursor_span
            self.cursor = (index, source_seconds(start, end, due, duration, time.monotonic()))

    def capture_position(self):
        # Capture events already queued by the audio thread, even between UI polls.
        retained = []
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'at':
                due, action, data = value
                self.highlight_sequence += 1
                heapq.heappush(self.pending_highlights, (due, self.highlight_sequence, action, data))
            else:
                retained.append((kind, value))
        for event in retained:
            self.events.put(event)
        self.flush_highlights()
        self.refresh_cursor()

    def current_position(self):
        index, seconds = self.cursor if self.cursor[0] == self.index else (self.index, 0)
        return {'index': index, 'seconds': seconds, 'text_offset': self.text_offset,
                'voice': self.position_voice, 'speed': self.playback_speed.get()}

    def apply_position(self, value):
        value = restore_position(value, self.parts)
        self.index = value['index']
        self.cursor = (self.index, value['seconds'])
        self.cursor_span = None
        self.text_offset = value['text_offset']
        self.position_voice = value['voice']
        if self.position_voice in VOICES.values():
            self.voice.set(next(name for name, voice in VOICES.items() if voice == self.position_voice))
        self.speed.set(value['speed'])
        self.display()

    def bookmark_entries(self):
        record = self.saved.get(self.book_id, {})
        values = record.get('bookmarks', []) if isinstance(record, dict) else []
        return [v for v in values if isinstance(v, dict) and isinstance(v.get('position'), dict)] if isinstance(values, list) else []

    def add_bookmark(self):
        if not self.parts or (self.busy and not self.playing):
            return
        self.capture_position()
        point = self.current_position()
        chapter = self.chapters[self.current_chapter()].title
        name = simpledialog.askstring('Add bookmark', 'Name this place:', initialvalue=chapter, parent=self.root)
        if name and name.strip():
            entries = self.bookmark_entries()
            entries.append({'id': uuid.uuid4().hex, 'name': name.strip()[:120], 'position': point})
            self.save(bookmarks=entries)
            self.status.configure(text=f'Bookmark saved: {name.strip()[:60]}')
            if self.bookmark_window and self.bookmark_window.winfo_exists():
                self.refresh_bookmarks()

    def show_bookmarks(self):
        if not self.parts:
            messagebox.showinfo('Bookmarks', 'Open a book to view its bookmarks.')
            return
        if self.bookmark_window and self.bookmark_window.winfo_exists():
            self.bookmark_window.lift()
            return
        window = self.bookmark_window = tk.Toplevel(self.root)
        window.title('Bookmarks · Talevoxa')
        window.geometry('600x320')
        window.transient(self.root)
        self.bookmark_list = tk.Listbox(window, exportselection=False, font=('Segoe UI', 11), relief='flat', borderwidth=0, bg='#fffefb', fg='#213c35', selectbackground='#d7e8dc', selectforeground='#213c35', activestyle='none')
        self.bookmark_list.pack(fill='both', expand=True, padx=12, pady=12)
        buttons = ttk.Frame(window)
        buttons.pack(fill='x', padx=12, pady=(0, 12))
        for label, action in [('Go to', 'go'), ('Rename', 'rename'), ('Delete', 'delete')]:
            ttk.Button(buttons, text=label, command=lambda a=action: self.bookmark_action(a)).pack(side='left', padx=3)
        ttk.Button(buttons, text='Add bookmark', command=self.add_bookmark).pack(side='right')
        self.bookmark_list.bind('<Double-Button-1>', lambda event: self.bookmark_action('go'))
        self.refresh_bookmarks()

    def refresh_bookmarks(self):
        self.bookmark_list.delete(0, 'end')
        for entry in self.bookmark_entries():
            point = restore_position(entry['position'], self.parts)
            chapter = max(0, bisect_right(self.chapter_starts, point['index']) - 1)
            excerpt = self.parts[point['index']][point['text_offset']:][:45]
            self.bookmark_list.insert('end', f'{entry.get("name", "Bookmark")} · {self.chapters[chapter].title} · {excerpt}')

    def bookmark_action(self, action):
        selected = self.bookmark_list.curselection()
        entries = self.bookmark_entries()
        if not selected or selected[0] >= len(entries):
            return
        i = selected[0]
        if action == 'go':
            if self.busy and not self.playing:
                return
            if self.playing:
                was_paused = self.paused.is_set()
                self.stop()
                self.restart_at = restore_position(entries[i]['position'], self.parts)
                self.restart_paused = was_paused
            else:
                self.apply_position(entries[i]['position'])
            self.bookmark_window.destroy()
            return
        if action == 'rename':
            name = simpledialog.askstring('Rename bookmark', 'Bookmark name:', initialvalue=entries[i].get('name', ''), parent=self.bookmark_window)
            if not name or not name.strip():
                return
            entries[i]['name'] = name.strip()[:120]
        elif action == 'delete':
            if not messagebox.askyesno('Delete bookmark', 'Delete this bookmark? Your saved reading position will be kept.', parent=self.bookmark_window):
                return
            entries.pop(i)
        self.save(bookmarks=entries)
        self.refresh_bookmarks()

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
            was_paused = self.paused.is_set()
            self.stop()
            self.restart_at = (index, seconds)
            self.restart_paused = was_paused
        elif not self.busy:
            self.index = index
            self.cursor = (index, seconds)
            self.cursor_span = None
            self.text_offset = 0
            self.display()

    def rewind(self):
        if not self.parts or (self.busy and not self.playing):
            return
        self.capture_position()
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
            self.cursor_span = None
            self.text_offset = 0
            self.display()

    def move_chapter(self, step):
        if self.chapters and not self.busy:
            chapter = max(0, min(len(self.chapters) - 1, self.current_chapter() + step))
            self.index = self.chapter_starts[chapter]
            self.cursor = (self.index, 0)
            self.cursor_span = None
            self.text_offset = 0
            self.display()

    def save(self, bookmarks=None):
        if self.book_id:
            entries = self.bookmark_entries() if bookmarks is None else bookmarks
            self.saved[self.book_id] = {**self.current_position(), 'bookmarks': entries, 'chapter_name': self.chapters[self.current_chapter()].title if self.chapters else ''}
            temp = DATA / 'progress.tmp'
            try:
                temp.write_text(json.dumps(self.saved, ensure_ascii=False), encoding='utf-8')
                temp.replace(DATA / 'progress.json')
                self.last_save = time.monotonic()
            except OSError:
                self.status.configure(text='Could not save your place. Check available disk space and folder permissions.')

    def open_book(self, name=None, expected_id=None, autoplay=False):
        if self.busy:
            return
        name = name or filedialog.askopenfilename(filetypes=[('Books and Word documents', '*.epub *.pdf *.txt *.docx *.doc'), ('All files', '*.*')])
        if not name:
            return
        self.capture_position()
        self.save()
        if self.bookmark_window and self.bookmark_window.winfo_exists():
            self.bookmark_window.destroy()
        self.set_busy(True)
        self.cancel.clear()
        self.opening_path = name
        self.opening_autoplay = autoplay
        self.opening_success = False
        self.status.configure(text='Opening book…')
        clean_pdf = self.clean_pdf.get()
        def work():
            try:
                book = load_document(name, progress=lambda text: self.events.put(('status', text)), cancel=self.cancel, clean_pdf=clean_pdf)
                parts = book.parts
                identity = hashlib.sha256('\n'.join(parts).encode()).hexdigest()
                if self.cancel.is_set():
                    raise InterruptedError()
                if expected_id and identity != expected_id:
                    raise ValueError('This file has different book text. Choose the original book, or use Open a book to add it separately.')
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
            self.cursor_span = None
            self.text_offset = 0
            self.display()

    def set_busy(self, value):
        self.busy = value
        for widget in (self.open_button, self.preview, self.play, self.back, self.next, self.chapter_back, self.chapter_next, self.chapter_option):
            widget.configure(state='disabled' if value else 'normal')
        self.chapter_picker.configure(state='disabled' if value or not self.chapters else 'readonly')

    def get_engine(self, voice='af_heart'):
        # Injected test engines do not need downloaded assets.
        if self.engine is not None and not hasattr(self.engine, 'voices'):
            return self.engine
        self.voice_store.ensure([voice], self.cancel, lambda text: self.events.put(('status', text)))
        if self.engine is None:
            self.events.put(('status', 'Loading voice engine...'))
            from kokoro_onnx import Kokoro
            with self.voice_store.lock:
                pack = self.voice_store.engine_pack(voice)
                self.engine = Kokoro(str(DATA / 'kokoro-v1.0.onnx'), str(pack))
                # Close the archive so future voice changes never overwrite an open file.
                archive = self.engine.voices
                self.engine.voices = {voice: archive[voice]}
                archive.close()
        else:
            self.engine.voices[voice] = self.voice_store.load(voice)
        return self.engine

    def start(self, preview=False, keep_paused=False):
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
        start_char = None
        if not preview and self.position_voice and self.position_voice != voice:
            start_char = self.text_offset
        if not preview and self.audio_settings != (voice, 1):
            self.durations.clear()
            self.audio_settings = (voice, 1)
        if not preview:
            self.active_voice = voice
            self.cursor_span = None
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
        if keep_paused:
            self.paused.set()
        self.pause.configure(text='Resume' if keep_paused else 'Pause')
        self.set_busy(True)
        self.playing = not preview
        self.previewing = preview
        self.status.configure(text='Preparing your voice…')
        def work():
            try:
                import sounddevice as sd
                first = 0 if preview else start
                read_book(lambda: self.get_engine(voice), parts, first, end, chapter_starts if not preview else [0],
                          voice, 1, self.cancel, self.paused, self.events, sd.OutputStream, preview,
                          cache=self.audio_cache, start_seconds=start_seconds, buffer_seconds=reserve,
                          live_speed=self.playback_speed.get, start_char=start_char)
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
        self.capture_position()
        self.save()

    def stop(self):
        self.restart_at = None
        self.restart_paused = False
        self.capture_position()
        self.cursor_span = None
        self.cancel.set()
        self.save()
        self.pending_highlights.clear()
        self.paused.clear()
        self.pause.configure(text='Pause')
        if self.busy:
            self.status.configure(text='Stopping…')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind in ('voice_download_progress', 'voice_download_done'):
                    self.voice_download_status = value
                    if kind == 'voice_download_done':
                        self.voice_download_busy = False
                    if self.voice_window and self.voice_window.winfo_exists():
                        self.voice_progress.configure(text=value)
                        if kind == 'voice_download_done':
                            self.refresh_voice_browser()
                elif kind == 'status':
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
                elif kind == 'covers_ready':
                    self.cover_loading = False
                    self.render_covers()
                    self.load_covers()
                elif kind == 'book':
                    self.shown_chapter = None
                    name, book, self.book_id = value
                    self.parts = book.parts
                    self.durations.clear()
                    self.chapters = book.chapters
                    self.chapter_starts = book.starts
                    self.chapter_picker.configure(values=[f'{i + 1}. {chapter.title}' for i, chapter in enumerate(self.chapters)])
                    self.title.configure(text=name[:100])
                    self.audio_settings = None
                    self.apply_position(self.saved.get(self.book_id, 0))
                    if self.opening_path:
                        self.library.remember(self.book_id, name, self.opening_path)
                        self.opening_success = True
                    self.show_reader()
                elif kind == 'error':
                    self.capture_position()
                    self.cursor_span = None
                    self.save()
                    self.pending_highlights.clear()
                    messagebox.showerror('Talevoxa', value)
                elif kind == 'done':
                    self.flush_highlights(finish=True)
                    self.refresh_cursor()
                    self.cursor_span = None
                    self.save()
                    self.pending_highlights.clear()
                    self.set_busy(False)
                    self.playing = False
                    self.previewing = False
                    self.pause.configure(text='Pause')
                    self.status.configure(text='Ready · Your place is saved')
                    if self.opening_path:
                        autoplay = self.opening_autoplay and self.opening_success and not self.cancel.is_set()
                        self.opening_path = None
                        self.opening_autoplay = self.opening_success = False
                        if autoplay:
                            self.root.after_idle(self.start)
                    if self.restart_at is not None:
                        if isinstance(self.restart_at, dict):
                            self.apply_position(self.restart_at)
                        else:
                            self.index, seconds = self.restart_at
                            self.cursor = (self.index, seconds)
                            self.text_offset = 0
                            self.display()
                        self.restart_at = None
                        keep_paused = self.restart_paused
                        self.restart_paused = False
                        self.root.after_idle(lambda p=keep_paused: self.start(keep_paused=p))
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
        self.refresh_cursor()
        if self.playing and time.monotonic() - self.last_save >= 1:
            self.save()
        if self.sleep_deadline is not None and time.monotonic() >= self.sleep_deadline:
            self.sleep_deadline = None
            self.sleep_choice.set('Off')
            self.stop()
        self.root.after(20, self.poll)

    def close(self):
        self.stop()
        self.update_cancel.set()
        self.voice_download_cancel.set()
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
