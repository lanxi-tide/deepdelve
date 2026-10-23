"""给《深潜》合成一段底噪一样的背景音乐：低频铺底 + 水声 + 偶尔的钟声。

不是旋律，是环境。目标是"听久了会忘掉它在响"，但一关掉就觉得空。
"""

import os
import wave

import numpy as np

SR = 22050
DUR = 84.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.wav")


def env_adsr(n, a=0.2, d=0.3, s=0.5, r=0.2):
    a_n, d_n, r_n = int(n * a), int(n * d), int(n * r)
    s_n = max(0, n - a_n - d_n - r_n)
    return np.concatenate([
        np.linspace(0, 1, a_n, False),
        np.linspace(1, s, d_n, False),
        np.full(s_n, s),
        np.linspace(s, 0, n - a_n - d_n - s_n, False),
    ])[:n]


def pad(freq, dur, detune=0.6, vol=0.16):
    t = np.linspace(0, dur, int(SR * dur), False)
    sig = np.zeros_like(t)
    for k, mult in enumerate((1.0, 2.0, 3.0)):
        amp = vol / (k + 1.6)
        sig += amp * np.sin(2 * np.pi * (freq * mult + detune * k) * t)
        sig += amp * 0.6 * np.sin(2 * np.pi * (freq * mult - detune * k) * t)
    # 慢速起伏
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.035 * t + freq)
    gate = env_adsr(len(t), 0.18, 0.25, 0.7, 0.25)
    return sig * lfo * gate


def water_noise(dur, vol=0.05):
    n = int(SR * dur)
    rng = np.random.default_rng(11)
    noise = rng.normal(0, 1, n)
    # 一阶低通，砍掉高频，变成"咕噜"感
    b = 0.02
    out = np.zeros(n)
    acc = 0.0
    for i in range(n):
        acc += b * (noise[i] - acc)
        out[i] = acc
    swell = 0.6 + 0.4 * np.sin(2 * np.pi * 0.02 * np.arange(n) / SR)
    return out * swell * vol * 4.0


def bell(freq, dur=3.0, vol=0.1):
    t = np.linspace(0, dur, int(SR * dur), False)
    sig = (np.sin(2 * np.pi * freq * t) * 1.0
           + 0.5 * np.sin(2 * np.pi * freq * 2.01 * t)
           + 0.25 * np.sin(2 * np.pi * freq * 3.02 * t))
    return sig * np.exp(-2.2 * t) * vol


def main():
    n = int(SR * DUR)
    mix = np.zeros(n)

    # 三层铺底：A1 / E2 / A2，非常低，几乎像风
    for freq, vol in ((55.0, 0.20), (82.5, 0.09), (110.0, 0.06)):
        layer = pad(freq, DUR, vol=vol)
        mix[:len(layer)] += layer[:n]

    # 水声
    mix += water_noise(DUR)[:n]

    # 偶尔的钟：每 21 秒一次，音高在 A / C / E 之间轮换
    for i, t0 in enumerate((6.0, 27.0, 48.0, 69.0)):
        freq = (220.0, 261.6, 329.6, 220.0)[i]
        b = bell(freq, 3.0, 0.09)
        start = int(t0 * SR)
        end = min(n, start + len(b))
        mix[start:end] += b[:end - start]

    # 首尾淡入淡出，循环时不炸
    fade = int(SR * 3.0)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)

    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.85
    data = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(OUT, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(data.tobytes())
    print("music:", OUT, round(DUR, 1), "秒", round(os.path.getsize(OUT) / 1024 / 1024, 1), "MB")


if __name__ == "__main__":
    main()
