"""深潜 · 带画面和声音的窗口版。

画面：一块画布，越深越黑；鲸鱼是一组多边形；摸到的东西会浮在周围。
声音：首次运行用 numpy 合成几个短音（下潜、摸到、告急、上浮），winsound 异步播。
"""

import math
import os
import sys
import wave

import numpy as np
import tkinter as tk
from tkinter import font as tkfont

try:
    import winsound
except ImportError:  # 非 Windows
    winsound = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deepdelve import Game  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SND = os.path.join(HERE, "snd")

FG = "#dbe7ff"
ACCENT = "#7fb3ff"
SR = 22050


# ── 声音 ────────────────────────────────────────────────
def write_wav(path, samples):
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(data.tobytes())


def sweep(f0, f1, dur=0.35, vol=0.5):
    t = np.linspace(0, dur, int(SR * dur), False)
    f = np.linspace(f0, f1, len(t))
    phase = 2 * np.pi * np.cumsum(f) / SR
    env = np.exp(-3.0 * t / dur)
    return vol * np.sin(phase) * env


def ping(freq=880, dur=0.25, vol=0.4):
    t = np.linspace(0, dur, int(SR * dur), False)
    env = np.exp(-6.0 * t / dur)
    return vol * (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2 * t)) * env


def thump(dur=0.5, vol=0.55):
    t = np.linspace(0, dur, int(SR * dur), False)
    env = np.exp(-5.0 * t / dur)
    return vol * np.sin(2 * np.pi * 70 * t) * env


def ensure_sounds():
    os.makedirs(SND, exist_ok=True)
    files = {
        "dive.wav": sweep(420, 120, 0.4, 0.45),
        "found.wav": ping(880, 0.28, 0.35),
        "warn.wav": thump(0.45, 0.6),
        "up.wav": sweep(160, 520, 0.45, 0.45),
    }
    for name, data in files.items():
        p = os.path.join(SND, name)
        if not os.path.exists(p):
            write_wav(p, data)
    return {k: os.path.join(SND, k) for k in files}



# ── 背景音乐（走 MCI，能和 winsound 的音效同时响） ──────
import ctypes

_MCI_BUF = ctypes.create_unicode_buffer(128)


def mci(cmd):
    try:
        return ctypes.windll.winmm.mciSendStringW(cmd, _MCI_BUF, 128, None)
    except Exception:
        return -1


def music_start(path):
    mci("close bgm")
    if not os.path.exists(path):
        return False
    if mci(f'open "{path}" type waveaudio alias bgm') != 0:
        return False
    mci("play bgm")
    return True


def music_stop():
    mci("close bgm")

SOUNDS = {}


def play(name):
    if not winsound or name not in SOUNDS:
        return
    try:
        winsound.PlaySound(SOUNDS[name], winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


# ── 窗口 ────────────────────────────────────────────────
def bg_for(depth):
    """深度越大越黑，从 #16335e 收到 #04070f。"""
    t = min(1.0, depth / 18.0)
    r = int(22 * (1 - t) + 4 * t)
    g = int(51 * (1 - t) + 7 * t)
    b = int(94 * (1 - t) + 15 * t)
    return f"#{r:02x}{g:02x}{b:02x}"


class App:
    def __init__(self, root):
        self.root = root
        self.g = Game(seed=None)
        root.title("深潜 Deepdelve")
        root.geometry("760x700")
        root.configure(bg="#04070f")

        big = tkfont.Font(family="Microsoft YaHei", size=12)
        small = tkfont.Font(family="Microsoft YaHei", size=10)

        bar = tk.Frame(root, bg="#04070f")
        bar.pack(side="bottom", fill="x", pady=10, padx=16)
        self.buttons = {}
        for key, label in (("d", "下潜"), ("r", "停一会儿"), ("f", "摸一摸"), ("s", "上浮")):
            b = tk.Button(bar, text=label, font=small, bg="#16294d", fg=FG,
                          activebackground=ACCENT, activeforeground="#04070f", bd=0,
                          highlightthickness=0, padx=16, pady=7,
                          command=lambda k=key: self.act(k))
            b.pack(side="left", padx=5)
            self.buttons[key] = b
        tk.Button(bar, text="再来一局", font=small, bg="#26406e", fg=FG, bd=0,
                  activebackground=ACCENT, activeforeground="#04070f", highlightthickness=0,
                  padx=16, pady=7, command=self.restart).pack(side="right", padx=5)

        self.msg = tk.Label(root, text="", bg="#04070f", fg=ACCENT, font=small, anchor="w", padx=18)
        self.msg.pack(side="bottom", fill="x")

        self.canvas = tk.Canvas(root, height=300, bg="#16335e", highlightthickness=0)
        self.canvas.pack(side="top", fill="x")

        self.text = tk.Text(root, bg="#04070f", fg=FG, font=big, bd=0, padx=18, pady=8,
                            height=8, insertwidth=0, wrap="word")
        self.text.pack(side="top", fill="both", expand=True)
        self.text.configure(state="disabled")

        for k in "drfs":
            root.bind(f"<Key-{k}>", lambda e, kk=k: self.act(kk))

        global SOUNDS
        SOUNDS = ensure_sounds()
        self.music_on = music_start(os.path.join(HERE, "music.wav"))
        self.root.after(2000, self.music_tick)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.redraw()

    def music_tick(self):
        """音乐停了就续上，等于循环。"""
        if not self.music_on:
            return
        if mci("status bgm mode") == 0 and _MCI_BUF.value == "stopped":
            mci("play bgm")
        self.root.after(3000, self.music_tick)

    def on_close(self):
        music_stop()
        self.root.destroy()

    # ── 画 ──────────────────────────────────────────────
    def draw_scene(self):
        c = self.canvas
        c.delete("all")
        W = 760
        H = 300
        g = self.g
        c.configure(bg=bg_for(g.depth))

        # 水面的光：深度 0 时最亮
        if g.depth == 0:
            c.create_rectangle(0, 0, W, 60, fill="#1d4270", outline="")
            for i in range(6):
                y = 40 + i * 3
                c.create_line(0, y, W, y, fill="#2a5588", width=1)

        # 鲸鱼：用立绘当精灵，深度越大往下挪，轻微上下浮动
        cy = 96 + min(140, g.depth * 7)
        cx = W // 2
        bob = int(math.sin(g.turn * 0.9) * 4)
        if getattr(self, "sprite", None) is None:
            try:
                self.sprite = tk.PhotoImage(file=os.path.join(HERE, "art", "whale.png"))
            except Exception:
                self.sprite = None
        if self.sprite is not None:
            c.create_image(cx + 40, cy + 40 + bob, image=self.sprite)
        else:
            body = [cx - 90, cy, cx - 40, cy - 34, cx + 50, cy - 26,
                    cx + 92, cy - 6, cx + 50, cy + 22, cx - 40, cy + 26]
            c.create_polygon(body, fill="#1b3a66", outline="#2c5c95", smooth=True)

        # 身上的东西：浮在周围的小点
        for i, item in enumerate(g.carry[:6]):
            ang = (i / 6) * 2 * math.pi + g.turn * 0.2
            px = cx + 150 * math.cos(ang)
            py = cy + 60 * math.sin(ang)
            c.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#c8dcff", outline="")

        # 气泡
        for i in range(10):
            bx = (i * 79 + g.turn * 13) % W
            by = (H - ((i * 41 + g.turn * 17) % H))
            r = 2 + (i % 3)
            c.create_oval(bx - r, by - r, bx + r, by + r, outline="#4a7ab5")

        # 氧气快没了：画面边缘发红
        if g.oxygen < 30:
            c.create_rectangle(0, 0, W - 1, H - 1, outline="#8b2f3a", width=6)
        c.create_text(14, 14, anchor="nw", fill="#9fc7ff",
                      text=f"深度 {g.depth} 层", font=("Microsoft YaHei", 11))

    def redraw(self):
        g = self.g
        lines = [
            f"第 {g.turn} 回合 · 深度 {g.depth} 层",
            f"氧气 {bar(g.oxygen)} {g.oxygen}",
            f"体力 {bar(g.stamina)} {g.stamina}",
            f"光   {bar(g.light)} {g.light}",
            "身上：" + ("、".join(g.carry) if g.carry else "空"),
            "带回过：" + ("、".join(g.home) if g.home else "还没上浮过"),
        ]
        if g.over:
            lines += ["", g.msg, f"最深第 {g.depth} 层，带回 {len(g.home)} 件。"]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")
        self.msg.configure(text="" if not g.msg else "— " + g.msg)
        for k, b in self.buttons.items():
            st = "disabled" if g.over or (k in ("f", "s") and g.depth == 0) else "normal"
            b.configure(state=st)
        self.draw_scene()

    def act(self, key):
        if self.g.over:
            return
        before_carry = len(self.g.carry)
        before_o = self.g.oxygen
        self.g.step(key)
        if key == "f":
            play("found" if len(self.g.carry) > before_carry else "dive")
        elif key == "d":
            play("dive")
        elif key == "s":
            play("up")
        if self.g.oxygen < 25 or (self.g.oxygen <= 0):
            play("warn")
        if self.g.oxygen <= 0 or self.g.stamina <= 0:
            self.g.over = True
        self.redraw()

    def restart(self):
        self.g = Game(seed=None)
        self.redraw()


def bar(v, width=26, char="#", empty="."):
    n = max(0, min(width, int(width * v / 100)))
    return char * n + empty * (width - n)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
