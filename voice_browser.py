"""Voice discovery UI; all Tk work stays on the main thread."""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from voice_catalog import VOICES, BY_ID, DEFAULT_FAVOURITES, label


class VoiceBrowser:
    def init_voices(self):
        saved = self.preferences.get('favourite_voices', DEFAULT_FAVOURITES)
        self.favourite_voices = [v for v in saved if v in BY_ID] if isinstance(saved, list) else list(DEFAULT_FAVOURITES)
        self.voice_window = None
        self.voice_download_busy = False
        self.voice_download_cancel = threading.Event()
        self.voice_download_status = 'Choose a voice and preview the same story sample.'

    def update_voice_choices(self):
        current = self.voice.get()
        choices = [label(BY_ID[v]) for v in self.favourite_voices]
        if current and current not in choices:
            choices.append(current)
        self.voice.configure(values=choices)

    def show_voices(self):
        if self.voice_window and self.voice_window.winfo_exists():
            self.voice_window.lift()
            return
        w = self.voice_window = tk.Toplevel(self.root)
        w.title('More voices · Talevoxa')
        w.geometry('800x560')
        w.minsize(720, 520)
        ttk.Label(w, text='Find your next narrator', font=('Georgia', 20)).pack(anchor='w', padx=16, pady=(12, 6))
        ttk.Label(w, text='Favourites stay in the main voice selector. Preview before choosing for a long book.', wraplength=740).pack(anchor='w', padx=16)
        self.voice_filter = tk.StringVar(value='All voices')
        filters = ttk.Combobox(w, textvariable=self.voice_filter, values=['All voices', 'Favourites', 'American', 'British', 'Downloaded'], state='readonly', width=20)
        filters.pack(anchor='w', padx=16, pady=8)
        filters.bind('<<ComboboxSelected>>', lambda e: self.refresh_voice_browser())
        area = ttk.Frame(w)
        area.pack(fill='both', expand=True, padx=16)
        self.voice_table = ttk.Treeview(area, columns=('voice', 'accent', 'gender', 'status'), show='headings', selectmode='browse')
        for key, title, width in [('voice', 'Voice / favourite', 210), ('accent', 'Accent', 100), ('gender', 'Voice', 80), ('status', 'Voice file', 130)]:
            self.voice_table.heading(key, text=title)
            self.voice_table.column(key, width=width)
        scroll = ttk.Scrollbar(area, orient='vertical', command=self.voice_table.yview)
        self.voice_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.voice_table.pack(fill='both', expand=True)
        self.voice_table.bind('<<TreeviewSelect>>', lambda e: self.voice_detail())
        self.voice_info = ttk.Label(w, wraplength=740)
        self.voice_info.pack(fill='x', padx=16, pady=8)
        actions = ttk.Frame(w)
        actions.pack(fill='x', padx=16)
        for title, command in [('Preview', lambda: self.voice_action('preview')), ('Stop preview', self.stop_voice_preview), ('Use voice', lambda: self.voice_action('use')), ('Favourite / unfavourite', lambda: self.voice_action('favourite'))]:
            ttk.Button(actions, text=title, command=command).pack(side='left', padx=(0, 5))
        downloads = ttk.Frame(w)
        downloads.pack(fill='x', padx=16, pady=8)
        self.voice_download_buttons = []
        for title, all_voices in [('Download selected', False), ('Download all 28', True)]:
            b = ttk.Button(downloads, text=title, command=lambda a=all_voices: self.download_voices(a))
            b.pack(side='left', padx=(0, 5))
            self.voice_download_buttons.append(b)
        ttk.Button(downloads, text='Cancel download', command=self.voice_download_cancel.set).pack(side='left')
        self.voice_progress = ttk.Label(w, text=self.voice_download_status, wraplength=740)
        self.voice_progress.pack(fill='x', padx=16)
        ttk.Label(w, text='One shared engine: about 326 MB once. Each voice: about 0.5 MB. All 28 voices: about 15 MB. Previews download missing files; afterwards they work offline.', wraplength=740).pack(fill='x', padx=16, pady=(8, 12))
        self.refresh_voice_browser()

    def refresh_voice_browser(self):
        if not self.voice_window or not self.voice_window.winfo_exists():
            return
        selected = self.voice_table.selection()
        self.voice_table.delete(*self.voice_table.get_children())
        mode = self.voice_filter.get()
        for v in sorted(VOICES, key=lambda v: (v['id'] not in self.favourite_voices, VOICES.index(v))):
            key = v['id']
            ready = self.voice_store.ready(key)
            if mode == 'Favourites' and key not in self.favourite_voices or mode in ('American', 'British') and mode != v['accent'] or mode == 'Downloaded' and not ready:
                continue
            self.voice_table.insert('', 'end', iid=key, values=(('★ ' if key in self.favourite_voices else '') + v['name'], v['accent'], v['gender'], 'Downloaded' if ready else 'Not downloaded'))
        ids = self.voice_table.get_children()
        if ids:
            self.voice_table.selection_set(selected[0] if selected and selected[0] in ids else ids[0])
        self.voice_detail()
        for b in self.voice_download_buttons:
            b.configure(state='disabled' if self.voice_download_busy else 'normal')

    def voice_detail(self):
        selected = self.voice_table.selection()
        if not selected:
            self.voice_info.configure(text='No voices match this filter.')
            return
        v = BY_ID[selected[0]]
        advice = 'A good starting point.' if v['id'] in ('af_heart', 'af_bella') else 'Audition with your book; consistency varies.'
        self.voice_info.configure(text=f'{v["name"]}: {advice} Upstream training-data grade: {v["grade"]}. This is not a listening score or a guarantee of audiobook quality.')

    def voice_action(self, action):
        selected = self.voice_table.selection()
        if not selected:
            return
        key = selected[0]
        if action == 'favourite':
            if key in self.favourite_voices:
                self.favourite_voices.remove(key)
            else:
                self.favourite_voices.append(key)
            self.preferences['favourite_voices'] = self.favourite_voices
            self.save_preferences()
            self.update_voice_choices()
            self.refresh_voice_browser()
            return
        if self.busy:
            messagebox.showinfo('Voice preview', 'Stop playback before trying or choosing another voice.', parent=self.voice_window)
            return
        self.voice.set(label(BY_ID[key]))
        self.update_voice_choices()
        if action == 'preview':
            self.start(True)

    def stop_voice_preview(self):
        if self.busy and self.previewing:
            self.stop()

    def download_voices(self, all_voices=False):
        if self.voice_download_busy:
            return
        selected = self.voice_table.selection()
        ids = list(BY_ID) if all_voices else list(selected)
        if not ids:
            return
        self.voice_download_busy = True
        self.voice_download_cancel.clear()
        self.refresh_voice_browser()
        def work():
            try:
                self.voice_store.ensure(ids, self.voice_download_cancel, lambda text: self.events.put(('voice_download_progress', text)))
                result = 'Selected voices and engine are ready for offline listening.'
            except InterruptedError:
                result = 'Download cancelled. Completed files are kept; you can retry.'
            except Exception as exc:
                result = f'Download failed: {exc}. You can retry.'
            self.events.put(('voice_download_done', result))
        threading.Thread(target=work, daemon=True).start()
