"""Wraith klavye: oyuna odaklanınca "Game" profiline, başka uygulamaya geçince normal profile otomatik geçer.

wraith.software sitesinin WebHID ile yaptığı işi doğrudan HID paketiyle yapar;
tarayıcı gerekmez. Sistem tepsisinde çalışır.

  pythonw wraith_auto.py        arka planda çalıştır
  python  wraith_auto.py --test Game profiline geç, 4 sn bekle, normale dön
"""
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import winreg
from pathlib import Path

import hid
import psutil
import pystray
from PIL import Image, ImageDraw

APP = "WraithAutoProfile"
DIR = Path(__file__).resolve().parent
CONFIG = DIR / "config.json"
LOG = DIR / "log.txt"

# profiles.json içindeki profil adları
DEFAULTS = {
    "game_profile": "game",
    "normal_profile": "default",
    "poll_seconds": 0.5,
    "stable_polls": 2,
    # İki profil yüklemesi arasındaki en kısa süre (klavyeyi art arda yeniden yazmamak için)
    "min_switch_seconds": 4,
    # Steam/Epic/Riot klasörlerindeki uygulamaları otomatik oyun say
    "auto_detect": True,
    # Kesin oyun exe adları (küçük/büyük harf fark etmez), örn. "valorant-win64-shipping.exe"
    "games": [],
    # Exe yolunda geçen parçalar; bunlardan biri varsa oyun sayılır ("/" ile yaz)
    "game_path_patterns": ["/steamapps/common/", "/epic games/", "/riot games/", "/battle.net/games/"],
    # Yukarıdaki kalıplara uysa bile oyun sayılmayacaklar
    "ignore_names": ["wallpaper32.exe", "wallpaper64.exe", "webwallpaper32.exe", "steamwebhelper.exe",
                     "steam.exe", "epicgameslauncher.exe", "epicwebhelper.exe"],
    "ignore_path_parts": ["/launcher/", "/_commonredist/", "/wallpaper_engine/", "/riot client/"],
}

VENDOR_USAGE_PAGE = 0xFF1B
VENDOR_USAGE = 0x91
ERROR_ALREADY_EXISTS = 183


def log(msg):
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass


def load_config():
    if not CONFIG.exists():
        CONFIG.write_text(json.dumps(DEFAULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        return {**DEFAULTS, **json.loads(CONFIG.read_text(encoding="utf-8"))}
    except (OSError, ValueError) as e:
        log(f"config okunamadı, varsayılan kullanılıyor: {e}")
        return dict(DEFAULTS)


def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def find_device_path():
    for d in hid.enumerate():
        if d["usage_page"] == VENDOR_USAGE_PAGE and d["usage"] == VENDOR_USAGE:
            return d["path"]
    return None


PROFILES = DIR / "profiles.json"


def load_profiles():
    """profiles.json: ad -> {"packets": [...], "saved": tarih}. Paketler, sitede o profile tıklarken
    klavyeye giden raporlardır (hex, reportId 1, 63 bayt). Eski biçim (düz liste) de okunur."""
    try:
        data = json.loads(PROFILES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v if isinstance(v, dict) else {"packets": v, "saved": ""} for k, v in data.items()}


def save_profile(name, packets):
    profiles = load_profiles()
    profiles[name] = {"packets": packets, "saved": time.strftime("%Y-%m-%d %H:%M")}
    tmp = PROFILES.with_suffix(".tmp")  # tepsi süreci okurken yarım dosya görmesin
    tmp.write_text(json.dumps(profiles), encoding="utf-8")
    os.replace(tmp, PROFILES)


def load_profile_packets(name):
    profiles = load_profiles()
    if name not in profiles:
        raise OSError(f"profiles.json içinde '{name}' tanımlı değil; Ayarlar'dan tanımla")
    return profiles[name]["packets"]


def set_profile(name):
    """Bu klavyede profiller tarayıcıda tutulur; geçiş, profilin tüm ayar paketlerini yüklemektir."""
    packets = load_profile_packets(name)
    path = find_device_path()
    if path is None:
        raise OSError("Wraith klavye bulunamadı")
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(True)
    try:
        for hex_data in [f"0d{'00' * 62}"] + packets:  # 0x0D: sitenin bağlanırken gönderdiği el sıkışma
            if dev.write(b"\x01" + bytes.fromhex(hex_data)) < 0:
                raise OSError(dev.error())
            time.sleep(0.008)
            while dev.read(64):  # klavyenin cevaplarını at, tampon dolmasın
                pass
    finally:
        dev.close()


def foreground_process():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return psutil.Process(pid.value)
    except psutil.Error:
        return None


def any_key_down():
    get_state = ctypes.windll.user32.GetAsyncKeyState
    return any(get_state(vk) & 0x8000 for vk in range(0x08, 0xFF))  # 0x01-0x06 fare düğmeleri


def game_name(cfg):
    """Şu an odaklı pencere bir oyunsa exe adını döndürür."""
    proc = foreground_process()
    if proc is None:
        return None
    try:
        name = proc.name().lower()
    except psutil.Error:
        return None
    if name in {n.lower() for n in cfg["ignore_names"]}:
        return None
    if name in {n.lower() for n in cfg["games"]}:
        return name
    if not cfg["auto_detect"]:
        return None
    try:
        exe = proc.exe().lower().replace("\\", "/")  # yönetici olarak çalışan oyunlarda erişilemeyebilir
    except psutil.Error:
        return None
    patterns = [p.lower() for p in cfg["game_path_patterns"]]
    ignore_parts = [p.lower() for p in cfg["ignore_path_parts"]]
    if any(x in exe for x in patterns) and not any(x in exe for x in ignore_parts):
        return name
    return None


def make_icon(color, size=256):
    """Kenar yumuşatma için 4 kat büyük çizip küçültür; koordinatlar 64'lük ızgarada."""
    big = size * 4
    k = big / 64
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4 * k, 4 * k, 60 * k, 60 * k), fill=color)
    w = [(16, 20), (23, 20), (28, 40), (32, 28), (36, 40), (41, 20), (48, 20), (38, 46), (33, 46),
         (32, 44), (31, 46), (26, 46)]
    d.polygon([(x * k, y * k) for x, y in w], fill="white")
    return img.resize((size, size), Image.LANCZOS)


COLOR_NORMAL = (90, 90, 100, 255)
COLOR_GAME = (30, 170, 80, 255)
ICON_NORMAL = make_icon(COLOR_NORMAL)


def set_window_icon(root, ico):
    """Tk simgeyi 32 pikselde verir, yüksek ölçeklemede bulanıklaşır; Windows'a 256 pikseli doğrudan ver."""
    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    root.update_idletasks()
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    for icon_kind, px in ((1, 256), (0, 32)):  # ICON_BIG (görev çubuğu), ICON_SMALL (başlık çubuğu)
        handle = user32.LoadImageW(None, str(ico), 1, px, px, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        if handle:
            user32.SendMessageW(hwnd, 0x80, icon_kind, handle)  # WM_SETICON


def tray_icons():
    """Ekranın gerçek küçük simge boyutunda (DPI'ye göre 16-32 px) çizilmiş tepsi simgeleri."""
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    size = ctypes.windll.user32.GetSystemMetrics(49) or 16  # SM_CXSMICON
    return {False: make_icon(COLOR_NORMAL, size), True: make_icon(COLOR_GAME, size)}


class Monitor:
    def __init__(self, icons):
        self.icons = icons  # {oyun_mu: PIL görüntüsü}
        self.mode = "auto"  # auto | game | normal
        self.in_game = False
        self.reason = ""
        self.error = ""
        self.shown_status = None
        self.stop = threading.Event()
        self.icon = None

    def status(self):
        state = f"Oyun profili ({self.reason})" if self.in_game else "Normal profil"
        return f"{state} - HATA: {self.error}" if self.error else state

    def refresh_icon(self):
        status = self.status()
        if self.icon and status != self.shown_status:
            self.shown_status = status
            self.icon.icon = self.icons[self.in_game]
            self.icon.title = f"Wraith: {status}"
            self.icon.update_menu()

    def run(self):
        pending, stable = False, 0  # odak durumu; stable_polls tarama boyunca aynı kalırsa geçilir
        synced = None  # klavyede yüklü olduğunu bildiğimiz durum (True=oyun); None=bilinmiyor, ilk taramada yüklenir
        last_device_check = retry_at = earliest = 0.0
        wait_since = None
        cfg = dict(DEFAULTS)
        while not self.stop.is_set():
            try:
                cfg = load_config()
                if self.mode == "auto":
                    hit = game_name(cfg)
                    if bool(hit) != pending:
                        pending, stable = bool(hit), 0
                    stable += 1
                    if hit:
                        self.reason = hit
                    if pending != self.in_game and stable >= cfg["stable_polls"]:
                        self.in_game = pending
                else:
                    self.in_game, self.reason = self.mode == "game", "elle"

                now = time.monotonic()
                need_switch = self.in_game != synced
                if not need_switch:
                    wait_since = None
                elif wait_since is None:
                    wait_since = now
                # Yükleme ~1,5 sn klavyenin ayarlarını yeniden yazar: tuşa basılıyken ya da bir önceki
                # yüklemenin hemen ardından yapma (basılı tuş 5 sn'den uzun tutulursa yine de yükle)
                blocked = need_switch and (now < max(retry_at, earliest)
                                           or (any_key_down() and now - wait_since < 5))
                if need_switch and not blocked:
                    target = cfg["game_profile"] if self.in_game else cfg["normal_profile"]
                    try:
                        set_profile(target)
                        synced = self.in_game
                        earliest = time.monotonic() + cfg["min_switch_seconds"]
                        self.error = ""
                        log(f"profil {target} ({self.status()})")
                    except OSError as e:
                        retry_at = time.monotonic() + 3
                        if str(e) != self.error:
                            log(f"profil değiştirilemedi: {e}")
                        self.error = str(e)
                elif synced is not None and time.monotonic() - last_device_check > 5:
                    last_device_check = time.monotonic()
                    if find_device_path() is None:
                        synced = None  # klavye çıkarıldı; geri gelince mevcut profil tekrar yüklenir
            except Exception as e:  # döngü sessizce ölmesin
                log(f"beklenmeyen hata: {e!r}")

            self.refresh_icon()
            self.stop.wait(cfg["poll_seconds"])


def run_command():
    exe = Path(sys.executable).with_name("pythonw.exe")
    return f'"{exe}" "{Path(__file__).resolve()}"'


def startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            winreg.QueryValueEx(k, APP)
            return True
    except FileNotFoundError:
        return False


def toggle_startup():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                        0, winreg.KEY_SET_VALUE) as k:
        if startup_enabled():
            winreg.DeleteValue(k, APP)
        else:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, run_command())


def running_apps():
    """Çalışan, Windows klasörü dışındaki uygulamaların exe adları."""
    names = set()
    for p in psutil.process_iter(["name", "exe"]):
        exe = (p.info["exe"] or "").lower().replace("\\", "/")
        if exe and "/windows/" not in exe and p.info["name"]:
            names.add(p.info["name"].lower())
    return sorted(names)


def profile_wizard(root, name, title, wording, on_saved):
    """Sitede bir profile tıklanınca giden paketleri yakalayıp `name` olarak kaydeden adım adım sihirbaz.
    wording: (bu profili -i hâli, bu profil -e hâli, önce tıklanacak diğer profil -e hâli)."""
    site_acc, site_dat, other_dat = wording
    import tkinter as tk
    import webbrowser
    from tkinter import messagebox, ttk

    from profile_capture import CaptureSession

    try:
        session = CaptureSession()
    except OSError:
        messagebox.showerror("Sihirbaz açılamadı", "8765 numaralı port kullanımda. Açık başka bir "
                             "sihirbaz penceresi varsa önce onu kapat.", parent=root)
        return

    win = tk.Toplevel(root)
    win.title(f"{title} tanımla")
    win.transient(root)
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=14)
    frm.grid()

    def copy_code(button):
        root.clipboard_clear()
        root.clipboard_append(session.snippet())
        root.update()
        button.config(text="Kopyalandı")

    steps = [
        ("Klavyeyi USB ile bağla, siteyi aç ve Connect ile klavyeni seç.",
         "Siteyi aç", lambda b: webbrowser.open("https://wraith.software")),
        (f"Sitede {site_acc} istediğin gibi ayarla (ışık, tuşlar…). Zaten hazırsa bu adımı geç.",
         None, None),
        ("Sitede F12'ye bas, Console sekmesini aç. Kodu kopyalayıp konsola yapıştır ve Enter'a bas. "
         "Chrome 'allow pasting' yazmanı isterse önce onu yaz; yerel ağ izni sorarsa İzin ver'i seç.",
         "Kodu kopyala", copy_code),
        (f"Sitenin sol menüsünde önce {other_dat}, sonra {site_dat} tıkla. "
         "Site ayarları klavyeye yükler; bitince aşağıda 'Yakalandı' yazar.", None, None),
        ("Yakalanan profil doğruysa Kaydet'e bas.", None, None),
    ]
    for i, (text, button_text, action) in enumerate(steps):
        ttk.Label(frm, text=f"{i + 1}.", font=("Segoe UI", 10, "bold")).grid(row=i, column=0, sticky="nw", pady=4)
        ttk.Label(frm, text=text, wraplength=380, justify="left").grid(row=i, column=1, sticky="w", padx=8, pady=4)
        if button_text:
            btn = ttk.Button(frm, text=button_text)
            btn.config(command=lambda b=btn, a=action: a(b))
            btn.grid(row=i, column=2, sticky="ne", pady=4)

    status = tk.StringVar(value="Bekleniyor…")
    ttk.Label(frm, textvariable=status, font=("Segoe UI", 10, "bold")).grid(
        row=len(steps), column=0, columnspan=3, sticky="w", pady=(10, 4))
    save_btn = ttk.Button(frm, text="Kaydet", state="disabled")
    save_btn.grid(row=len(steps) + 1, column=2, sticky="e")

    def close():
        session.close()
        win.destroy()

    def save():
        burst = session.last_burst()
        if burst:
            save_profile(name, burst[1])
            on_saved()
            messagebox.showinfo("Kaydedildi", f"{title} kaydedildi ({len(burst[1])} paket).", parent=win)
            close()

    save_btn.config(command=save)
    win.protocol("WM_DELETE_WINDOW", close)
    seen = {"n": -1}

    def poll():
        if not win.winfo_exists():
            return
        burst = session.last_burst()
        if burst is None:
            seen["n"] = -1
            status.set("Bekleniyor… (kod yapıştırıldı mı, profile tıkladın mı?)")
            save_btn.state(["disabled"])
        else:
            site_name, packets = burst
            done = len(packets) == seen["n"]  # sayı bir tur boyunca değişmediyse yükleme bitmiştir
            seen["n"] = len(packets)
            status.set(f"Yakalandı: site profili '{site_name}', {len(packets)} paket" if done
                       else f"Yükleniyor… {len(packets)} paket")
            save_btn.state(["!disabled"] if done else ["disabled"])
        win.after(600, poll)

    poll()


def settings_window():
    import tkinter as tk
    from tkinter import filedialog, ttk

    ctypes.windll.kernel32.CreateMutexW(None, False, f"Local\\{APP}Settings")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return

    # Görev çubuğunda pythonw yerine bu pencerenin kendi simgesi görünsün
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP}.Settings")
    ico = DIR / "icon.ico"
    if not ico.exists():
        ICON_NORMAL.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    cfg = load_config()
    root = tk.Tk()
    root.title("Wraith otomatik profil")
    root.iconbitmap(default=str(ico))
    set_window_icon(root, ico)
    root.resizable(False, False)
    frm = ttk.Frame(root, padding=14)
    frm.grid()

    ttk.Label(frm, text="Bu uygulamalara odaklanınca klavye Game profiline geçer:").grid(
        row=0, column=0, columnspan=2, sticky="w")
    box = tk.Listbox(frm, width=36, height=10, selectmode="extended")
    box.grid(row=1, column=0, rowspan=4, pady=8, padx=(0, 10))

    def refresh():
        box.delete(0, "end")
        for name in sorted(cfg["games"]):
            box.insert("end", name)

    def add(names):
        for name in names:
            name = name.lower()
            if name not in [g.lower() for g in cfg["games"]]:
                cfg["games"].append(name)
        save_config(cfg)
        refresh()

    def pick_file():
        files = filedialog.askopenfilenames(parent=root, title="Oyun veya uygulama seç",
                                            filetypes=[("Uygulama", "*.exe")])
        add(os.path.basename(f) for f in files)

    def pick_running():
        win = tk.Toplevel(root)
        win.title("Çalışan uygulamalar")
        win.transient(root)
        lst = tk.Listbox(win, width=36, height=16, selectmode="extended")
        lst.pack(padx=12, pady=(12, 6))
        for name in running_apps():
            lst.insert("end", name)

        def confirm():
            add(lst.get(i) for i in lst.curselection())
            win.destroy()

        ttk.Button(win, text="Ekle", command=confirm).pack(pady=(0, 12))

    def remove():
        selected = {box.get(i) for i in box.curselection()}
        cfg["games"] = [g for g in cfg["games"] if g.lower() not in selected]
        save_config(cfg)
        refresh()

    ttk.Button(frm, text="Uygulama seç…", command=pick_file).grid(row=1, column=1, sticky="ew")
    ttk.Button(frm, text="Çalışanlardan seç…", command=pick_running).grid(row=2, column=1, sticky="ew")
    ttk.Button(frm, text="Seçileni kaldır", command=remove).grid(row=3, column=1, sticky="ew")

    auto_var = tk.BooleanVar(value=cfg["auto_detect"])

    def on_auto():
        cfg["auto_detect"] = auto_var.get()
        save_config(cfg)

    startup_var = tk.BooleanVar(value=startup_enabled())

    def on_startup():
        if startup_var.get() != startup_enabled():
            toggle_startup()

    prof_box = ttk.LabelFrame(frm, text="Klavye profilleri", padding=8)
    prof_box.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 8))
    prof_labels = {}

    def refresh_profiles():
        profiles = load_profiles()
        for key, label in prof_labels.items():
            p = profiles.get(cfg[key])
            label.config(text=f"{len(p['packets'])} paket · {p['saved'] or 'tarih bilinmiyor'}" if p
                         else "tanımlı değil")

    # (config anahtarı, başlık, sihirbaz metni: profili / profile / diğer profile)
    slots = (("game_profile", "Game profili", ("oyun profilini", "oyun profiline", "normal profiline")),
             ("normal_profile", "Normal profil", ("normal profilini", "normal profiline", "oyun profiline")))
    for row, (key, title, wording) in enumerate(slots):
        ttk.Label(prof_box, text=title, width=14).grid(row=row, column=0, sticky="w", pady=2)
        prof_labels[key] = ttk.Label(prof_box, text="")
        prof_labels[key].grid(row=row, column=1, sticky="w", padx=8)
        ttk.Button(prof_box, text="Tanımla…",
                   command=lambda k=key, t=title, w=wording:
                   profile_wizard(root, cfg[k], t, w, refresh_profiles)).grid(row=row, column=2)
    ttk.Label(prof_box, text="Sitede bir profilde değişiklik yaptıysan buradan yeniden tanımla.").grid(
        row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

    ttk.Checkbutton(frm, text="Steam / Epic / Riot klasörlerindeki oyunları otomatik algıla",
                    variable=auto_var, command=on_auto).grid(row=6, column=0, columnspan=2, sticky="w")
    ttk.Checkbutton(frm, text="Windows ile birlikte başlat", variable=startup_var,
                    command=on_startup).grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 0))

    refresh()
    refresh_profiles()
    root.mainloop()


def self_test():
    cfg = load_config()
    print("Game profiline geçiliyor:", cfg["game_profile"])
    set_profile(cfg["game_profile"])
    time.sleep(4)
    print("Normal profile dönülüyor:", cfg["normal_profile"])
    set_profile(cfg["normal_profile"])
    print("Tamam.")


def main():
    if "--test" in sys.argv:
        self_test()
        return
    if "--settings" in sys.argv:
        settings_window()
        return

    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"Local\\{APP}")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return

    icons = tray_icons()
    mon = Monitor(icons)

    def choose(mode):
        def handler(icon, item):
            mon.mode = mode
        return handler

    def quit_app(icon, item):
        mon.stop.set()
        icon.stop()

    def open_settings(icon, item):
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        subprocess.Popen([str(pythonw), str(Path(__file__).resolve()), "--settings"])

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: mon.status(), None, enabled=False),
        pystray.MenuItem("Ayarlar…", open_settings, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Otomatik", choose("auto"), checked=lambda i: mon.mode == "auto", radio=True),
        pystray.MenuItem("Oyun profili (elle)", choose("game"), checked=lambda i: mon.mode == "game", radio=True),
        pystray.MenuItem("Normal profil (elle)", choose("normal"), checked=lambda i: mon.mode == "normal", radio=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Windows ile başlat", lambda i, m: toggle_startup(), checked=lambda i: startup_enabled()),
        pystray.MenuItem("Çıkış", quit_app),
    )
    mon.icon = pystray.Icon(APP, icons[False], "Wraith otomatik profil", menu)
    load_config()  # ilk çalıştırmada config.json oluştur
    threading.Thread(target=mon.run, daemon=True).start()
    mon.icon.run()
    del mutex


if __name__ == "__main__":
    main()
