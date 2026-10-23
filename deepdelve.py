"""深潜 Deepdelve —— 一只鲸鱼往下沉的文字小游戏。

规则很简单：
  你有氧气、体力、一点"光"。每潜一层，选一个动作。
  越深越黑，光越少，能看清的选项越少。
  可以上浮（带回你拿到的东西），也可以继续往下。

跑法：python 深潜.py
"""

import random
import sys

WIDTH = 40


def bar(value, top, char="#"):
    n = max(0, min(WIDTH, int(WIDTH * value / top)))
    return char * n + "." * (WIDTH - n)


class Game:
    def __init__(self, seed=None):
        self.rnd = random.Random(seed)
        self.depth = 0
        self.oxygen = 100
        self.stamina = 100
        self.light = 100
        self.carry = []          # 带在身上的东西
        self.home = []           # 已经带回去的东西
        self.turn = 0
        self.over = False
        self.msg = ""

    # ── 状态 ──────────────────────────────────────────────
    def status(self):
        return (
            f"第 {self.turn} 回合 · 深度 {self.depth} 层\n"
            f"氧气 {bar(self.oxygen, 100)}\n"
            f"体力 {bar(self.stamina, 100)}\n"
            f"光   {bar(self.light, 100)}\n"
            f"身上：{'、'.join(self.carry) if self.carry else '空'}\n"
            f"带回过：{'、'.join(self.home) if self.home else '还没上浮过'}"
        )

    # ── 动作 ──────────────────────────────────────────────
    def dive(self):
        cost_o = 10 + self.depth // 3
        cost_s = 12
        if self.oxygen <= cost_o or self.stamina < cost_s:
            self.over = True
            self.msg = "氧气不够再下去了。你在原地停住，然后开始上浮。"
            return self.surface(auto=True)
        self.turn += 1
        self.oxygen -= cost_o
        self.stamina -= cost_s + self.rnd.randint(-3, 3)
        self.depth += 1
        self.light = max(0, self.light - 12 - self.depth // 2)
        found = self.find()
        self.msg = f"下潜到第 {self.depth} 层。" + (f" 摸到：{found}" if found else " 这一层很黑，什么都没摸到。")

    def rest(self):
        """海面上能回满；水里歇着只回体力，氧气照旧往下掉——没有白歇的水。"""
        self.turn += 1
        if self.depth == 0:
            self.oxygen = min(100, self.oxygen + 25)
            self.stamina = min(100, self.stamina + 25)
            self.msg = "你在海面上浮了一会儿，氧气和体力都回满。"
            return
        cost = 4 + self.depth // 2
        self.oxygen = max(0, self.oxygen - cost)
        self.stamina = min(100, self.stamina + 16)
        self.turn += 0
        self.msg = f"你悬停着回气，体力上来一点，氧气却又少了 {cost}。水底下没有白歇的。"

    def feel(self):
        """在水里摸索也要付氧气——摸黑是动作，不是免费扫描。"""
        cost_o = 6 + self.depth // 2
        self.oxygen = max(0, self.oxygen - cost_o)
        self.stamina = max(0, self.stamina - 5)
        self.turn += 1
        if self.light < 10 and self.rnd.random() < 0.5:
            self.stamina = max(0, self.stamina - 8)
            self.msg = f"太黑了，你摸到的是自己的尾巴。氧气 -{cost_o}，体力 -13。"
            return
        found = self.find(bonus=0.25)
        self.msg = (f"你摸黑找了找：摸到 {found}。氧气 -{cost_o}。" if found
                    else f"你摸黑找了找：什么也没有。氧气 -{cost_o}。")

    def surface(self, auto=False):
        self.home.extend(self.carry)
        got = list(self.carry)
        self.carry = []
        self.turn += 1
        self.over = True
        self.msg = ("氧气耗尽，你被水流推了上去。" if auto else "你决定上浮。") + \
                   ("这趟带回：" + "、".join(got) if got else "这趟什么都没带回来。")

    def find(self, bonus=0.0):
        if self.rnd.random() > 0.45 + bonus - min(0.25, self.depth * 0.01):
            return None
        pool = ["一枚旧硬币", "会发光的鳞", "半张潮汐图", "沉船的木片", "别人的记忆碎片", "一颗不冷的星"]
        if self.depth > 8:
            pool += ["关于深处的谣传", "一条回声"]
        item = self.rnd.choice(pool)
        if item not in self.carry:
            self.carry.append(item)
        return item

    # ── 主循环 ────────────────────────────────────────────
    def options(self):
        opts = []
        if self.depth > 0:
            opts.append(("s", "上浮，把东西带回去"))
        opts.append(("d", "继续往下"))
        opts.append(("r", "停一会儿，回口气"))
        if self.depth > 0:
            opts.append(("f", "在黑暗里摸一摸"))
        return opts

    def step(self, key):
        if key == "d":
            self.dive()
        elif key == "r":
            self.rest()
        elif key == "f":
            self.feel()
        elif key == "s":
            self.surface()
        else:
            self.msg = "（没有这个动作）"
            return
        if self.oxygen <= 0 or self.stamina <= 0:
            self.over = True


def play(seed=None, script=None):
    g = Game(seed)
    out = []
    while not g.over:
        out.append(g.status())
        out.append("")
        if script:
            key = script.pop(0) if script else "s"
            out.append(f"> {key}")
        else:
            for k, label in g.options():
                out.append(f"  [{k}] {label}")
            try:
                key = input("> ").strip()
            except EOFError:
                key = "s"
        g.step(key)
        out.append(g.msg)
        out.append("-" * WIDTH)
    out.append(g.status())
    out.append("")
    out.append(f"最深到过第 {g.depth} 层，一共带回 {len(g.home)} 件东西。")
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        seq = ["d", "d", "f", "d", "r", "d", "f", "s"]
        print(play(seed=7, script=seq))
    else:
        print(play())
