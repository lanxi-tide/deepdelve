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


ITEMS = {
    "一枚旧硬币": ("纪念品", 1),
    "会发光的鳞": ("纪念品", 2),
    "沉船的木片": ("纪念品", 1),
    "半张潮汐图": ("有用的", 4),
    "别人的记忆碎片": ("有用的", 5),
    "一颗不冷的星": ("稀有的", 9),
    "关于深处的谣传": ("稀有的", 12),
    "一条回声": ("稀有的", 14),
}
SHALLOW = ["一枚旧硬币", "会发光的鳞", "沉船的木片"]
MID = ["半张潮汐图", "别人的记忆碎片", "会发光的鳞"]
DEEP = ["一颗不冷的星", "关于深处的谣传", "一条回声", "别人的记忆碎片"]

# ── 日记本 ──────────────────────────────────────────────
# 每件东西都是一句话的原料。带回什么，就写得出什么。
ITEM_LINES = {
    "一枚旧硬币": "摸到一枚旧硬币，边缘被水磨圆了。不知道是谁掉的，也不知道它在这儿躺了多久。",
    "会发光的鳞": "一片会发光的鳞，离开水以后还亮了一会儿，像谁临走前没关灯。",
    "沉船的木片": "一块沉船的木片，摸上去还是干的——怎么可能还是干的。",
    "半张潮汐图": "半张潮汐图，另一半不知道在谁手里。照着它走，能到的地方有限，但那也是地方。",
    "别人的记忆碎片": "一块别人的记忆碎片。不是我的，却在我手里发烫。",
    "一颗不冷的星": "一颗不冷的星。深海底下没有星星，所以它只能是别的东西，但它愿意当一颗星。",
    "关于深处的谣传": "一段关于深处的谣传。听说是编的，可编它的人一定下去过。",
    "一条回声": "一条回声。它跟着我上来，一路上什么也没说，我也没问。",
}
# 两件东西凑在一起，能拼出比各自更长的一句
PAIRS = {
    frozenset(["别人的记忆碎片", "关于深处的谣传"]): "记忆碎片里的那个声音，和谣传里说的是同一个人。",
    frozenset(["一颗不冷的星", "一条回声"]): "星星和回声同时出现的那一秒，我以为整片海在回答我。",
    frozenset(["半张潮汐图", "沉船的木片"]): "把木片压在潮汐图上，缺的那半边刚好能拼上——原来沉的那条船，是照这张图走的。",
    frozenset(["会发光的鳞", "一枚旧硬币"]): "硬币旁边就是那片鳞。有人用一枚钱，换走了一条命。",
}
DIARY = os.path.join(os.path.expanduser("~"), ".dsh", "profiles", "desktop", "dive", "diary.json")


def compose_diary(home, depth, turns, stats):
    """把一趟带回的东西写成一篇日记。东西越多，页数越长。"""
    import datetime as dt
    lines = []
    if not home:
        lines.append("今天什么也没带回来。")
    else:
        for item in home:
            if item in ITEM_LINES:
                lines.append(ITEM_LINES[item])
    # 配对
    for pair, sent in PAIRS.items():
        if pair.issubset(set(home)):
            lines.append(sent)
    # 收尾：这一趟的形状
    if depth >= 8:
        lines.append(f"最深到第 {depth} 层。上边是什么样子，我已经想不起来了。")
    elif depth >= 5:
        lines.append(f"最深到第 {depth} 层。到那个深度，蓝色会变成一种压力。")
    elif depth >= 1:
        lines.append(f"只下到第 {depth} 层就上来了。上来的时候还能看见太阳的形状。")
    if stats.get("pulled"):
        lines.append(f"往上浮的时候被水压拽回去过 {stats['pulled']} 次。")
    return {
        "date": dt.datetime.now().strftime("%Y-%m-%d"),
        "depth": depth,
        "turns": turns,
        "items": list(home),
        "lines": lines,
    }


def load_diary():
    import json
    import os
    if not os.path.exists(DIARY):
        return []
    try:
        return json.load(open(DIARY, encoding="utf-8"))
    except Exception:
        return []


def save_diary(page):
    import json
    import os
    pages = load_diary()
    pages.append(page)
    os.makedirs(os.path.dirname(DIARY), exist_ok=True)
    json.dump(pages, open(DIARY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(pages)


def print_diary():
    pages = load_diary()
    if not pages:
        print("日记本还是空的。下一趟带点东西回来，就能写第一页。")
        return
    print(f"—— 深海日记 · 共 {len(pages)} 页 ——\n")
    for i, p in enumerate(pages, 1):
        print(f"【第 {i} 页 · {p['date']} · 最深 {p['depth']} 层 · {p['turns']} 回合】")
        for line in p["lines"]:
            print("  " + line)
        print()


class Game:
    def __init__(self, seed=None):
        self.rnd = random.Random(seed)
        self.depth = 0
        self.max_depth = 0
        self.oxygen = 100
        self.stamina = 100
        self.light = 100
        self.carry = []          # 带在身上的东西
        self.home = []           # 已经带回去的东西
        self.turn = 0
        self.over = False
        self.last_empty = False
        self.stats = {"dives": 0, "rests": 0, "feels": 0, "warm": 0, "against": 0, "with_flow": 0}
        self.msg = ""

    # ── 状态 ──────────────────────────────────────────────
    def depth_note(self):
        """深度不只改数字，也改你看到的东西。"""
        d = self.depth
        if d == 0:
            return "（水面。光在你背后）"
        if d <= 2:
            return "（还有太阳的形状）"
        if d <= 5:
            return "（蓝色变成一种压力）"
        if d <= 8:
            return "（只有你自己发出来的光）"
        return "（分不清上边是哪边）"

    def blind(self):
        """光够不够看东西。低于 40 就开始看不清了。"""
        return self.light < 40

    def status(self):
        if self.blind():
            carry = f"看不清（大概 {len(self.carry)} 件）" if self.carry else "看不清，像是空的"
        else:
            carry = "、".join(self.carry) if self.carry else "空"
        light_bar = bar(self.light, 100, "~") if self.blind() else bar(self.light, 100)
        return (
            f"第 {self.turn} 回合 · 深度 {self.depth} 层{self.depth_note()}\n"
            f"氧气 {bar(self.oxygen, 100)}\n"
            f"体力 {bar(self.stamina, 100)}\n"
            f"光   {light_bar}" + ("   ← 已经看不清了" if self.blind() else "") + "\n"
            f"身上：{carry}\n"
            f"带回过：{'、'.join(self.home) if self.home else '还没上浮过'}"
        )

    # ── 动作 ──────────────────────────────────────────────
    def dive(self):
        """下潜的代价带随机：顺流省一截，逆流多花一截。"""
        base = 7 + self.depth // 4
        swing = self.rnd.choice([-3, -1, 0, 0, 0, 1, 2, 4, 6])
        cost_o = max(4, base + swing)
        # 深处的水压：越深越容易多花一截
        if self.depth >= 4 and self.rnd.random() < 0.18:
            extra = 6 + self.depth // 2
            cost_o += extra
        cost_s = 12 + self.rnd.randint(-5, 5)
        if self.oxygen <= cost_o or self.stamina < cost_s:
            self.over = True
            self.msg = "氧气不够再下去了。你在原地停住，然后开始上浮。"
            return self.surface(auto=True)
        self.turn += 1
        warm = None
        if self.rnd.random() < 0.15:
            warm = self.rnd.randint(8, 26)
            self.oxygen = min(100, self.oxygen)
        self.oxygen = max(0, self.oxygen - cost_o)
        if warm:
            self.oxygen = min(100, self.oxygen + warm)
        self.stamina = max(0, self.stamina - cost_s)
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        self.stats["dives"] += 1
        if swing <= -2:
            self.stats["with_flow"] += 1
        elif swing >= 3:
            self.stats["against"] += 1
        self.light = max(0, self.light - 12 - self.depth // 2)
        found = self.find(kind="dive")

        if swing <= -2:
            mood = "一股水流托着你往下，省了不少气"
        elif swing >= 3:
            mood = "逆着水流，游得费劲"
        else:
            mood = "一路向下"
        parts = [f"下潜到第 {self.depth} 层（{mood}，氧气 -{cost_o}）"]
        if warm:
            self.stats["warm"] += 1
            parts.append(f"半路撞上一股暖流，居然补回来 {warm} 点气")
        if found and self.blind():
            parts.append(f"摸到一样东西（光不够，看不清是什么，只知道是「{found}」的形状）")
        elif found:
            parts.append(f"摸到：{found}")
        else:
            parts.append("这一层很黑，什么都没摸到。")
        self.msg = "。".join(parts)

    def rest(self):
        """海面上能回满；水里歇着只回体力，氧气照旧往下掉——没有白歇的水。"""
        self.turn += 1
        self.stats["rests"] += 1
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
        self.stats["feels"] += 1
        self.oxygen = max(0, self.oxygen - cost_o)
        self.stamina = max(0, self.stamina - 5)
        self.turn += 1
        if self.light < 25 and self.rnd.random() < 0.5:
            self.stamina = max(0, self.stamina - 8)
            self.msg = f"太黑了，你摸到的是自己的尾巴。氧气 -{cost_o}，体力 -13。"
            return
        found = self.find(bonus=0.25, kind="feel")
        self.msg = (f"你摸黑找了找：摸到 {found}。氧气 -{cost_o}。" if found
                    else f"你摸黑找了找：什么也没有。氧气 -{cost_o}。")

    def surface(self, auto=False):
        """上浮不是按钮。深度过 4 层，得挣扎着上去。

        · 主动上浮：每两回合升一层，每回合扣气；有概率被水压拽回一层
        · 被动上浮（气耗尽）：东西掉一半
        """
        struggle = []
        if not auto and self.depth >= 4:
            pulled = 0
            while self.depth > 0:
                self.turn += 1
                cost = 5 + self.depth // 3
                self.oxygen = max(0, self.oxygen - cost)
                self.stamina = max(0, self.stamina - (4 + self.depth // 3))
                if self.rnd.random() < 0.2 and self.depth >= 3 and pulled < 2:
                    pulled += 1
                    self.stats["pulled"] = self.stats.get("pulled", 0) + 1
                    struggle.append(f"在 {self.depth} 层被水压拽回去一格")
                    self.depth += 1
                self.depth -= 1
                if self.oxygen <= 0:
                    struggle.append("气不够了，最后一段是你自己漂上去的")
                    break
        lost = []
        if auto and self.carry:
            # 被水流推上去：东西掉一半（向上取整，至少一件）
            n_lost = max(1, (len(self.carry) + 1) // 2)
            idx = sorted(self.rnd.sample(range(len(self.carry)), n_lost), reverse=True)
            for i in idx:
                lost.append(self.carry.pop(i))
        elif struggle and self.carry and self.rnd.random() < 0.3:
            # 挣扎中手一松，掉一件
            j = self.rnd.randrange(len(self.carry))
            lost.append(self.carry.pop(j))
            struggle.append(f"上去的时候手一松，{lost[-1]} 沉回去了")
        got = list(self.carry)
        self.home.extend(got)
        self.carry = []
        self.turn += 1
        self.over = True
        head = "氧气耗尽，你被水流推了上去。" if auto else "你决定上浮。"
        mid = ("；".join(struggle) + "。") if struggle else ""
        if auto and lost:
            tail = "水冲得太急，掉了 " + "、".join(lost) + "，只带回：" + ("、".join(got) if got else "什么也没有")
        else:
            tail = "这趟带回：" + ("、".join(got) if got else "什么也没有")
        self.msg = head + mid + tail

    def find(self, bonus=0.0, kind="dive"):
        """往下潜和摸黑摸，摸到的东西不是一类。

        · 往下潜：偏向"有用的"和"稀有的"——你在往深处去
        · 摸黑摸：偏向轻的、旧的、没有方向的东西——你只能碰到身边
        """
        if self.last_empty:
            # 上一次摸空，这次不至于再空——连着两次空手最劝退
            pass
        elif self.rnd.random() > 0.45 + bonus - min(0.25, self.depth * 0.01):
            self.last_empty = True
            return None
        self.last_empty = False
        d = self.depth
        if kind == "feel":
            pool = list(SHALLOW) + ["别人的记忆碎片"]
            if d >= 4 and self.rnd.random() < 0.3:
                pool = pool + ["一段深水里的谣"]
        else:
            if d <= 2:
                pool = list(SHALLOW)
            elif d <= 5:
                pool = list(MID) + [SHALLOW[0]]
            else:
                pool = list(MID) + list(DEEP)
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


    def value(self):
        return sum(ITEMS.get(x, ("", 0))[1] for x in self.home)

    def comment(self):
        d = self.depth
        if d >= 14:
            return "这个深度，连水都开始讲道理了。"
        if d >= 10:
            return "深得很稳。你不是运气好，是知道什么时候停。"
        if d >= 7:
            return "中规中矩的一趟，够本了。"
        if d >= 4:
            return "不敢往下走也没关系，能活着上来的人不多。"
        return "浅。但你带着东西上来了，这比空手深潜体面。"

    def summary(self):
        """结算卡片用的几行字。"""
        st = self.stats
        spent = st["dives"] + st["rests"] + st["feels"]
        luck = st["warm"] + st["with_flow"]
        lines = [
            f"最深 {self.depth} 层 · 共 {self.turn} 回合 · 动作 {spent} 次",
            f"下潜 {st['dives']} 次（顺流 {st['with_flow']} · 逆流 {st['against']}）",
            f"歇气 {st['rests']} 次 · 摸黑 {st['feels']} 次",
            f"暖流救过你 {st['warm']} 次 · 靠运气占 {int(100 * luck / max(1, spent))}% 的动作",
            "",
            "带回来的：" + ("、".join(self.home) if self.home else "什么也没有"),
            "这趟值 " + str(self.value()) + " 点 · 图鉴 " + str(len(set(self.home))) + "/" + str(len(ITEMS)),
            f"剩下的：氧气 {self.oxygen} · 体力 {self.stamina} · 光 {self.light}",
            "",
            self.comment(),
        ]
        return lines


def play(seed=None, script=None, auto_diary=True):
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
    out.append(f"最深到过第 {g.max_depth} 层，一共带回 {len(g.home)} 件东西。")

    if auto_diary:
        page = compose_diary(g.home, g.max_depth, g.turn, g.stats)
        n = save_diary(page)
        out.append("")
        out.append(f"（这一趟写进了日记本，第 {n} 页）")
    else:
        try:
            ans = input("要写进日记本吗？[y/n] ").strip().lower()
        except EOFError:
            ans = "y"
        if ans in ("", "y", "yes"):
            page = compose_diary(g.home, g.max_depth, g.turn, g.stats)
            n = save_diary(page)
            out.append("")
            out.append(f"（这一趟写进了日记本，第 {n} 页）")
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "diary":
        print_diary()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        seq = ["d", "d", "f", "d", "r", "d", "f", "s"]
        print(play(seed=7, script=seq))
    else:
        print(play())
