"""English and Turkish text for every visible string.

Usage:  tr("save")  ·  tr("n_events", n=5)  ·  tr.upper("durum")
Following Ubi: plain words, sentence case, talk to "you", no emoji.
"""

STRINGS = {
    "en": {
        # tabs & top level
        "tab_home": "Home", "tab_events": "Events", "tab_settings": "Settings",
        "status": "Status",
        "pill_ready": "Ready", "pill_wait": "Wait", "pill_rec": "REC", "pill_on": "Playing",
        "st_ready": "Ready", "st_get_ready": "Get ready", "st_recording": "Recording", "st_playing": "Playing",
        "st_starts_in": "Starting in {n}",
        "sub_empty": "Press {rec} in your game to record your first macro, or load the Anti-AFK preset.",
        "sub_ready": "{rec} records · {play} plays and stops. Both work while the game is focused.",
        "sub_switch": "Switch to your game now.",
        "sub_recording": "Press {rec} to stop.",
        "sub_recording_n": "{n} events so far · press {rec} to stop",
        "sub_playing": "Press {play} to stop.",
        "sub_playing_n": "Loop {n} of {total} · running for {time} · {play} stops",
        "record": "Record", "stop_recording": "Stop", "play": "Play", "stop_playing": "Stop", "stop": "Stop",
        "stat_events": "Events", "stat_length": "Length", "stat_loops": "Loops done",
        "secs": "{s} s",
        # playback
        "playback": "Playback",
        "repeat": "Repeat", "wait_between": "Wait between (s)", "speed": "Speed (×)",
        "humanize": "Humanize (± %)", "stop_after": "Stop after (min)",
        "playback_hint": "Repeat 0 means forever. Stop after 0 means never. Humanize adds a little random "
                         "variation to the timing.",
        # macro
        "macro": "Macro", "save": "Save…", "load": "Load…", "preset": "Anti-AFK preset", "clear": "Clear",
        "clear_confirm": "Click again to clear",
        "macro_hint": "Your last recording is saved automatically and comes back next time.",
        "hotkeys_line": "Hotkeys: {rec} to record · {play} to play and stop. Change them in Settings.",
        # events
        "events_title": "Events", "n_events": "{n} events", "showing_first": "showing first {n}",
        "col_time": "Time", "col_gap": "Pause", "col_event": "Event",
        "selected_event": "Selected event", "nothing_selected": "Pick an event in the list",
        "n_selected": "{n} selected",
        "time_s": "Time (s)", "pause_before_s": "Pause before (s)", "set": "Set",
        "move_following": "Move the events after it too",
        "trim_start": "Remove start delay", "undo": "Undo", "delete_selected": "Delete",
        "cap_label": "Shorten pauses longer than", "seconds_short": "s", "apply": "Apply",
        "events_hint": "Set a pause to 0 to remove it. Ctrl+Z undoes, Delete removes the selected events.",
        "ev_key_down": "{key} pressed", "ev_key_up": "{key} released",
        "ev_click_down": "{btn} button down at {x}, {y}", "ev_click_up": "{btn} button up at {x}, {y}",
        "ev_move": "Mouse to {x}, {y}", "ev_scroll": "Scroll {dy} (side {dx})",
        "btn_left": "Left", "btn_right": "Right", "btn_middle": "Middle", "btn_x1": "Back", "btn_x2": "Forward",
        # settings
        "language": "Language", "theme": "Theme",
        "theme_system": "System", "theme_light": "Light", "theme_dark": "Dark",
        "hotkeys": "Hotkeys", "hk_record": "Record and stop", "hk_play": "Play and stop",
        "change": "Change", "press_key": "Press a key",
        "hotkeys_hint": "Hotkeys work everywhere, even while the game is focused. Esc cancels choosing a key.",
        "recording": "Recording",
        "record_moves": "Record mouse movement too",
        "auto_trim": "Remove the delay before the first event",
        "countdown": "Countdown when you start from this window (s)",
        "focus_game": "Switch to Roblox when you press Play here",
        "move_to_clicks": "Move the mouse to where you clicked",
        "focus_hint": "If Roblox isn't open, you get the countdown instead. Turn off mouse moving if your "
                      "camera spins in first person.",
        "window": "Window", "topmost": "Keep this window on top",
        "storage": "Storage", "storage_text": "Macros and settings are kept in your AppData folder.",
        "open_folder": "Open folder",
        # background
        "background": "Background (experimental)",
        "bg_switch": "Play in the background",
        "bg_window": "Send input to",
        "refresh": "Refresh",
        "fake_focus": "Make the window think it's active",
        "bg_test": "Run background test",
        "bg_hint": "Sends keys and clicks straight to one window, so it can sit on another screen or behind "
                   "your work. Not every game accepts this. To test: open Roblox, press Run background test, "
                   "then click into another window within 5 seconds. Roblox should jump, walk forward and "
                   "click 3 times. Try it with the switch above on and off.",
        "bg_windows_only": "Background playback only works on Windows.",
        "st_testing": "Testing",
        "sub_test_switch": "Click into another window now and keep Roblox visible.",
        "sub_ready_bg": "{play} plays in the background in {name}. Your keyboard and mouse stay free.",
        "in_background": "in the background in {name}",
        "toast_test_done": "Test done · did Roblox jump, walk and click?",
        "toast_no_window": "Couldn't find a window called {name}",
        "toast_windows": "{n} windows found",
        "toast_bg_on": "Background playback on · sending to {name}",
        # toasts
        "toast_recorded": "Recorded · {n} events", "toast_nothing": "Nothing recorded · old macro kept",
        "toast_no_macro": "No macro yet · record one or load the preset",
        "toast_stopped": "Stopped", "toast_finished": "Finished · {n} loops",
        "toast_time_limit": "Time's up · stopped after {n} loops",
        "toast_saved": "Saved · {name}", "toast_loaded": "Loaded · {name}",
        "toast_nothing_save": "Nothing to save yet",
        "toast_preset": "Anti-AFK preset loaded · repeats every 60 s",
        "toast_cleared": "Macro cleared · Ctrl+Z brings it back",
        "toast_undone": "Undone", "toast_nothing_undo": "Nothing to undo",
        "toast_busy": "Stop recording or playing first",
        "toast_bad_number": "That isn't a number",
        "toast_time_set": "Time set · {t} s", "toast_gap_set": "Pause set · {t} s",
        "toast_trimmed": "Removed {t} s from the start", "toast_no_delay": "There's no delay at the start",
        "toast_capped": "Shortened pauses · {t} s saved",
        "toast_no_long_pauses": "No pauses longer than {t} s",
        "toast_deleted": "Deleted · {n} events",
        "toast_hotkey_set": "Hotkey set · {key}", "toast_hotkey_taken": "That key is already the other hotkey",
        # dialogs
        "file_type": "UbiMacro macro", "all_files": "All files",
        "err_playback": "Playback stopped because of an error:\n{err}",
        "err_record": "Recording couldn't start:\n{err}",
        "err_save": "Couldn't save:\n{err}", "err_load": "Couldn't open that file:\n{err}",
    },
    "tr": {
        "tab_home": "Ana sayfa", "tab_events": "Olaylar", "tab_settings": "Ayarlar",
        "status": "Durum",
        "pill_ready": "Hazır", "pill_wait": "Bekle", "pill_rec": "KAYIT", "pill_on": "Oynatılıyor",
        "st_ready": "Hazır", "st_get_ready": "Hazırlan", "st_recording": "Kaydediliyor",
        "st_playing": "Oynatılıyor",
        "st_starts_in": "{n} sn sonra başlıyor",
        "sub_empty": "İlk makronu kaydetmek için oyundayken {rec} tuşuna bas ya da Anti-AFK hazır ayarını yükle.",
        "sub_ready": "{rec} kaydeder · {play} oynatır ve durdurur. İkisi de oyun açıkken çalışır.",
        "sub_switch": "Şimdi oyununa geç.",
        "sub_recording": "Durdurmak için {rec} tuşuna bas.",
        "sub_recording_n": "Şu ana kadar {n} olay · durdurmak için {rec}",
        "sub_playing": "Durdurmak için {play} tuşuna bas.",
        "sub_playing_n": "Tur {n} / {total} · {time} süredir çalışıyor · {play} durdurur",
        "record": "Kayıt", "stop_recording": "Durdur", "play": "Oynat", "stop_playing": "Durdur", "stop": "Durdur",
        "stat_events": "Olay", "stat_length": "Süre", "stat_loops": "Biten tur",
        "secs": "{s} sn",
        "playback": "Oynatma",
        "repeat": "Tekrar", "wait_between": "Turlar arası (sn)", "speed": "Hız (×)",
        "humanize": "İnsansı (± %)", "stop_after": "Şu kadar sonra dur (dk)",
        "playback_hint": "Tekrar 0 ise sonsuza kadar sürer. Durma süresi 0 ise hiç durmaz. İnsansı ayar "
                         "zamanlamaya biraz rastgelelik katar.",
        "macro": "Makro", "save": "Kaydet…", "load": "Aç…", "preset": "Anti-AFK hazır ayarı", "clear": "Temizle",
        "clear_confirm": "Temizlemek için tekrar tıkla",
        "macro_hint": "Son kaydın otomatik saklanır ve bir dahaki açılışta geri gelir.",
        "hotkeys_line": "Kısayollar: kayıt için {rec} · oynatıp durdurmak için {play}. Ayarlar'dan değiştirebilirsin.",
        "events_title": "Olaylar", "n_events": "{n} olay", "showing_first": "ilk {n} gösteriliyor",
        "col_time": "Zaman", "col_gap": "Bekleme", "col_event": "Olay",
        "selected_event": "Seçili olay", "nothing_selected": "Listeden bir olay seç",
        "n_selected": "{n} seçili",
        "time_s": "Zaman (sn)", "pause_before_s": "Önceki bekleme (sn)", "set": "Uygula",
        "move_following": "Sonraki olayları da kaydır",
        "trim_start": "Baştaki gecikmeyi sil", "undo": "Geri al", "delete_selected": "Sil",
        "cap_label": "Şundan uzun beklemeleri kısalt:", "seconds_short": "sn", "apply": "Uygula",
        "events_hint": "Bir beklemeyi kaldırmak için 0 yap. Ctrl+Z geri alır, Delete seçili olayları siler.",
        "ev_key_down": "{key} basıldı", "ev_key_up": "{key} bırakıldı",
        "ev_click_down": "{btn} fare tuşuna basıldı · {x}, {y}", "ev_click_up": "{btn} fare tuşu bırakıldı · {x}, {y}",
        "ev_move": "Fare {x}, {y} konumuna", "ev_scroll": "Kaydırma {dy} (yan {dx})",
        "btn_left": "Sol", "btn_right": "Sağ", "btn_middle": "Orta", "btn_x1": "Geri", "btn_x2": "İleri",
        "language": "Dil", "theme": "Tema",
        "theme_system": "Sistem", "theme_light": "Açık", "theme_dark": "Koyu",
        "hotkeys": "Kısayol tuşları", "hk_record": "Kaydı başlat ve durdur", "hk_play": "Oynat ve durdur",
        "change": "Değiştir", "press_key": "Bir tuşa bas",
        "hotkeys_hint": "Kısayollar her yerde çalışır, oyun açıkken bile. Tuş seçmekten vazgeçmek için Esc.",
        "recording": "Kayıt",
        "record_moves": "Fare hareketlerini de kaydet",
        "auto_trim": "İlk olaydan önceki gecikmeyi sil",
        "countdown": "Bu pencereden başlatınca geri sayım (sn)",
        "focus_game": "Buradan Oynat'a basınca Roblox'a geç",
        "move_to_clicks": "Fareyi tıkladığın yere götür",
        "focus_hint": "Roblox açık değilse geri sayım başlar. Birinci şahısta kameran dönüyorsa fare "
                      "hareketini kapat.",
        "window": "Pencere", "topmost": "Bu pencere hep üstte kalsın",
        "storage": "Depolama", "storage_text": "Makrolar ve ayarlar AppData klasöründe tutulur.",
        "open_folder": "Klasörü aç",
        "background": "Arka plan (deneysel)",
        "bg_switch": "Arka planda oynat",
        "bg_window": "Girdinin gideceği pencere",
        "refresh": "Yenile",
        "fake_focus": "Pencereye etkin olduğunu düşündür",
        "bg_test": "Arka plan testini çalıştır",
        "bg_hint": "Tuşları ve tıklamaları doğrudan tek bir pencereye gönderir; pencere başka bir ekranda ya da "
                   "işinin arkasında durabilir. Her oyun bunu kabul etmez. Test için: Roblox'u aç, Arka plan "
                   "testini çalıştır'a bas, sonra 5 saniye içinde başka bir pencereye tıkla. Roblox zıplamalı, "
                   "ileri yürümeli ve 3 kez tıklamalı. Yukarıdaki anahtar açıkken ve kapalıyken dene.",
        "bg_windows_only": "Arka planda oynatma yalnızca Windows'ta çalışır.",
        "st_testing": "Test ediliyor",
        "sub_test_switch": "Şimdi başka bir pencereye tıkla ve Roblox'u görünür tut.",
        "sub_ready_bg": "{play} arka planda {name} penceresinde oynatır. Klavyen ve faren serbest kalır.",
        "in_background": "arka planda, {name}",
        "toast_test_done": "Test bitti · Roblox zıpladı, yürüdü ve tıkladı mı?",
        "toast_no_window": "{name} adında bir pencere bulunamadı",
        "toast_windows": "{n} pencere bulundu",
        "toast_bg_on": "Arka planda oynatma açık · {name} penceresine gönderiliyor",
        "toast_recorded": "Kaydedildi · {n} olay", "toast_nothing": "Hiçbir şey kaydedilmedi · eski makro duruyor",
        "toast_no_macro": "Henüz makro yok · bir tane kaydet ya da hazır ayarı yükle",
        "toast_stopped": "Durduruldu", "toast_finished": "Bitti · {n} tur",
        "toast_time_limit": "Süre doldu · {n} turdan sonra durdu",
        "toast_saved": "Kaydedildi · {name}", "toast_loaded": "Açıldı · {name}",
        "toast_nothing_save": "Henüz kaydedilecek bir şey yok",
        "toast_preset": "Anti-AFK hazır ayarı yüklendi · 60 sn'de bir tekrarlar",
        "toast_cleared": "Makro temizlendi · Ctrl+Z geri getirir",
        "toast_undone": "Geri alındı", "toast_nothing_undo": "Geri alınacak bir şey yok",
        "toast_busy": "Önce kaydı ya da oynatmayı durdur",
        "toast_bad_number": "Bu bir sayı değil",
        "toast_time_set": "Zaman ayarlandı · {t} sn", "toast_gap_set": "Bekleme ayarlandı · {t} sn",
        "toast_trimmed": "Baştan {t} sn silindi", "toast_no_delay": "Başta gecikme yok",
        "toast_capped": "Beklemeler kısaltıldı · {t} sn kazanıldı",
        "toast_no_long_pauses": "{t} sn'den uzun bekleme yok",
        "toast_deleted": "Silindi · {n} olay",
        "toast_hotkey_set": "Kısayol ayarlandı · {key}", "toast_hotkey_taken": "Bu tuş zaten diğer kısayol",
        "file_type": "UbiMacro makrosu", "all_files": "Tüm dosyalar",
        "err_playback": "Bir hata yüzünden oynatma durdu:\n{err}",
        "err_record": "Kayıt başlatılamadı:\n{err}",
        "err_save": "Kaydedilemedi:\n{err}", "err_load": "Bu dosya açılamadı:\n{err}",
    },
}


class Translator:
    def __init__(self, lang="en"):
        self.lang = lang

    def set_lang(self, lang):
        self.lang = lang if lang in STRINGS else "en"

    def has(self, key):
        return key in STRINGS["en"]

    def __call__(self, _key, /, **kw):
        text = STRINGS.get(self.lang, {}).get(_key) or STRINGS["en"].get(_key) or _key
        return text.format(**kw) if kw else text

    def upper(self, text):
        """Uppercase with Turkish rules in Turkish (i → İ, ı → I)."""
        if self.lang == "tr":
            text = text.replace("i", "İ").replace("ı", "I")
        return text.upper()


tr = Translator()
