import json
import math
import os
import random
import sys
import threading
import time
import tkinter as tk
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    here = Path(__file__).resolve().parent
    if (here / "Assets").exists():
        return here
    return here.parent


ROOT = resource_root()
ASSETS = ROOT / "Assets" if (ROOT / "Assets").exists() else ROOT
TRANSPARENT = "#010203"
NEAR_PX = 100
DEFAULT_SIZE = 220


def load_json(name: str):
    for base in (ASSETS, ROOT, Path(__file__).resolve().parent.parent / "Assets"):
        path = base / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(name)


def image_path(name: str) -> Path:
    for base in (ASSETS, ROOT, Path(__file__).resolve().parent):
        for candidate in (base / name, base / "Assets" / name):
            if candidate.exists():
                return candidate
    raise FileNotFoundError(name)


class AudioEngine:
    def __init__(self):
        self._ok = False
        self._lock = threading.Lock()
        self._playing = False
        self._start = 0.0
        self._on_end = None
        try:
            import pygame

            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self._pygame = pygame
            self._ok = True
        except Exception:
            self._pygame = None

    @property
    def playing(self) -> bool:
        with self._lock:
            if not self._ok:
                return False
            alive = self._pygame.mixer.get_busy()
            if self._playing and not alive:
                self._playing = False
                cb = self._on_end
                self._on_end = None
                if cb:
                    threading.Thread(target=cb, daemon=True).start()
            return self._playing

    def current_time(self) -> float:
        with self._lock:
            if not self._playing:
                return 0.0
            return max(0.0, time.time() - self._start)

    def stop(self):
        with self._lock:
            if self._ok:
                self._pygame.mixer.stop()
            self._playing = False
            self._on_end = None

    def play(self, path: Path, volume: float, on_end=None) -> bool:
        if not self._ok or not path.exists():
            return False
        with self._lock:
            self._pygame.mixer.stop()
            sound = self._pygame.mixer.Sound(str(path))
            sound.set_volume(max(0.0, min(1.0, volume)))
            sound.play()
            self._playing = True
            self._start = time.time()
            self._on_end = on_end
            return True


class PetWindow:
    def __init__(self, app: "App", role: str, name: str, image: Path, x: int, y: int):
        self.app = app
        self.role = role
        self.name = name
        self.size = DEFAULT_SIZE
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.win.configure(bg=TRANSPARENT)
        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._photo = None
        self._caption = None
        self._drag = None
        self._speak_phase = 0.0
        self.speaking = False
        self._src = image
        self.reload_image()
        self.win.geometry(f"+{x}+{y}")
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_menu)
        self.canvas.bind("<Button-2>", self.on_menu)
        self.tick()

    def reload_image(self):
        img = tk.PhotoImage(file=str(self._src))
        w, h = img.width(), img.height()
        target = self.size
        factor = max(1, int(round(max(w, h) / target)))
        if factor > 1:
            img = img.subsample(factor, factor)
        self._base = img
        self.redraw()

    def set_size(self, size: int):
        self.size = size
        self.reload_image()

    def redraw(self, bob: int = 0):
        img = self._base
        self._photo = img
        w, h = img.width(), img.height()
        pad_x, pad_y = 48, 56
        self.win.geometry(f"{w + pad_x * 2}x{h + pad_y * 2}")
        self.canvas.config(width=w + pad_x * 2, height=h + pad_y * 2)
        self.canvas.delete("all")
        self.canvas.create_image(pad_x + w // 2, pad_y + h // 2 + bob, image=self._photo, anchor="center")
        if self._caption:
            self.canvas.create_text(
                pad_x + w // 2,
                20,
                text=self._caption,
                fill="#FFE566",
                font=("Microsoft YaHei UI", 11, "bold"),
                width=max(120, w + 24),
                justify="center",
            )

    def set_caption(self, text: str):
        self._caption = text.strip() if text else None
        self.redraw(int(math.sin(self._speak_phase) * 6) if self.speaking else 0)

    def on_press(self, e):
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y(), e.x_root, e.y_root, False)

    def on_drag(self, e):
        if not self._drag:
            return
        dx0, dy0, ox, oy, moved = self._drag
        moved = moved or abs(e.x_root - ox) + abs(e.y_root - oy) > 4
        self._drag = (dx0, dy0, ox, oy, moved)
        self.win.geometry(f"+{e.x_root - dx0}+{e.y_root - dy0}")

    def on_release(self, e):
        dragged = bool(self._drag and self._drag[4])
        self._drag = None
        if not dragged:
            self.app.on_click(self.role)

    def on_menu(self, e):
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label=f"{self.name}桌宠", state="disabled")
        menu.add_separator()
        menu.add_command(label="随机说一段", command=lambda: self.app.play_solo(self.role))
        menu.add_command(label="两人对话一句", command=self.app.play_pair)
        menu.add_command(label="完整对话", command=self.app.play_full)
        voice = tk.Menu(menu, tearoff=0)
        voice.add_command(label="原声", command=lambda: self.app.set_helium(False))
        voice.add_command(label="1.5倍氦气版", command=lambda: self.app.set_helium(True))
        menu.add_cascade(label="声音模式", menu=voice)
        menu.add_command(label="停止播放", command=self.app.stop_all)
        menu.add_separator()
        size_menu = tk.Menu(menu, tearoff=0)
        for label, val in (("小", 170), ("中", 220), ("大", 290)):
            size_menu.add_command(label=label, command=lambda v=val: self.app.set_size(v))
        menu.add_cascade(label="人物大小", menu=size_menu)
        menu.add_command(label="退出", command=self.app.quit)
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def center(self):
        return (
            self.win.winfo_x() + self.win.winfo_width() // 2,
            self.win.winfo_y() + self.win.winfo_height() // 2,
        )

    def tick(self):
        if self.speaking:
            self._speak_phase += 0.45
            self.redraw(int(math.sin(self._speak_phase) * 6))
        self.win.after(50, self.tick)


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("雷余双桌宠")
        self.clips = load_json("clips.json")
        self.helium_clips = load_json("clips-helium.json")
        self.pairs = load_json("pairs.json")
        self.helium = False
        self.volume = 0.7
        self.audio = AudioEngine()
        self.active_role = None
        self.active_clip = None
        self.active_lines = []
        self.full_queue = []
        self.mode = None
        self._pending_yu = None
        self.epilogue = None
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.pets = {
            "lei": PetWindow(self, "lei", "雷军", image_path("lei.png"), 40, max(40, sh - 380)),
            "yu": PetWindow(self, "yu", "余承东", image_path("yu.png"), min(sw - 320, 380), max(40, sh - 380)),
        }
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.poll()

    def clip_map(self):
        data = self.helium_clips if self.helium else self.clips
        return {c["id"]: c for c in data}

    def clip_dir(self) -> Path:
        for base in (ASSETS, ROOT):
            d = base / ("Clips-helium" if self.helium else "Clips")
            if d.exists():
                return d
            d = base / "Assets" / ("Clips-helium" if self.helium else "Clips")
            if d.exists():
                return d
        return ASSETS / ("Clips-helium" if self.helium else "Clips")

    def own_clips(self, role: str):
        return [c for c in (self.helium_clips if self.helium else self.clips) if c["role"] == role]

    def near(self) -> bool:
        ax, ay = self.pets["lei"].center()
        bx, by = self.pets["yu"].center()
        return math.hypot(ax - bx, ay - by) <= NEAR_PX + self.pets["lei"].size

    def set_helium(self, value: bool):
        self.stop_all()
        self.helium = value
        self.toast("已切换到 1.5 倍氦气版" if value else "已切换回原声")

    def set_size(self, size: int):
        for pet in self.pets.values():
            pet.set_size(size)

    def toast(self, text: str, role: str = "lei"):
        pet = self.pets[role]
        pet.set_caption(text)
        self.root.after(2200, lambda: pet.set_caption("") if not pet.speaking else None)

    def on_click(self, role: str):
        if self.near():
            self.play_pair()
        else:
            self.play_solo(role)

    def play_solo(self, role: str):
        clips = self.own_clips(role)
        if not clips:
            return
        self.mode = "solo"
        self.full_queue = []
        self._play_clip(random.choice(clips), role)

    def play_pair(self, pair_id=None):
        if not self.near():
            self.toast("先把两位拖近一点")
            return
        if not self.pairs:
            return
        pair = next((p for p in self.pairs if p["id"] == pair_id), None) if pair_id else random.choice(self.pairs)
        self.mode = "pair"
        self.full_queue = []
        self._start_pair(pair)

    def play_full(self):
        if not self.near():
            self.toast("先把两位拖近一点，再听完整对话")
            return
        self.mode = "full"
        self.full_queue = [p for p in sorted(self.pairs, key=lambda x: x["id"])]
        paired = {x for p in self.pairs for x in (p["lei"], p["yu"])}
        self.epilogue = next((c for c in self.clip_map().values() if c["role"] == "lei" and c["id"] not in paired), None)
        if not self.full_queue:
            return
        self.toast("开始完整对话")
        self._start_pair(self.full_queue.pop(0))

    def _start_pair(self, pair: dict):
        clips = self.clip_map()
        lei = clips.get(pair["lei"])
        if not lei:
            return
        self._pending_yu = clips.get(pair["yu"])
        self._play_clip(lei, "lei", after=self._after_lei)

    def _after_lei(self):
        yu = self._pending_yu
        self._pending_yu = None
        if yu:
            self._play_clip(yu, "yu", after=self._after_yu)
        else:
            self._after_yu()

    def _after_yu(self):
        if self.mode == "full" and self.full_queue:
            self._start_pair(self.full_queue.pop(0))
            return
        if self.mode == "full" and self.epilogue:
            epi = self.epilogue
            self.epilogue = None
            self._play_clip(epi, "lei", after=self._finish)
            return
        self._finish()

    def _finish(self):
        self.mode = None
        self.full_queue = []
        for pet in self.pets.values():
            pet.speaking = False
            self.root.after(400, lambda p=pet: p.set_caption("") if not p.speaking else None)

    def _play_clip(self, clip: dict, role: str, after=None):
        path = self.clip_dir() / clip["file"]
        self.audio.stop()
        for pet in self.pets.values():
            pet.speaking = False
            if pet.role != role:
                pet.set_caption("")
        self.active_role = role
        self.active_clip = clip
        self.active_lines = clip.get("lines") or [{"start": 0, "end": clip["duration"], "text": clip["text"]}]
        pet = self.pets[role]
        pet.speaking = True
        pet.set_caption(self.active_lines[0]["text"])

        def done():
            self.root.after(0, lambda: self._on_audio_end(after))

        if not self.audio.play(path, self.volume, on_end=done):
            self.root.after(int(max(0.4, clip["duration"]) * 1000), lambda: self._on_audio_end(after))

    def _on_audio_end(self, after):
        if self.active_role:
            self.pets[self.active_role].speaking = False
        self.active_role = None
        self.active_clip = None
        if after:
            after()

    def stop_all(self):
        self.mode = None
        self.full_queue = []
        self._pending_yu = None
        self.epilogue = None
        self.audio.stop()
        self.active_role = None
        self.active_clip = None
        for pet in self.pets.values():
            pet.speaking = False
            pet.set_caption("")

    def poll(self):
        self.audio.playing
        if self.active_role and self.active_clip and self.pets[self.active_role].speaking:
            t = self.audio.current_time()
            text = self.active_lines[0]["text"]
            for line in self.active_lines:
                if t >= line["start"]:
                    text = line["text"]
            self.pets[self.active_role].set_caption(text)
        self.root.after(80, self.poll)

    def quit(self):
        self.stop_all()
        for pet in list(self.pets.values()):
            try:
                pet.win.destroy()
            except tk.TclError:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        os._exit(0)

    def run(self):
        self.toast("点我说一段 · 靠近可对话 · 右键完整对话", "lei")
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
