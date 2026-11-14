"""由 docs/measurements/*.json 產生實測圖表（PNG）：python tools/make_charts.py"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "docs", "measurements")

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BEFORE, AFTER = "#eb6834", "#2a78d6"     # 參考色盤 slot 2（橘）、slot 1（藍）
plt.rcParams.update({
    "font.family": ["Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", "sans-serif"],
    "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "text.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.titleweight": "bold", "axes.titlesize": 13, "axes.titlelocation": "left",
})


def load(name):
    with open(os.path.join(D, name), encoding="utf-8") as f:
        return json.load(f)


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# ------------------------------------------------------------ 1. 準確度
def chart_accuracy():
    a = load("accuracy.json")
    fig, ax = plt.subplots(figsize=(9, 5.4), dpi=150)
    ax.add_patch(Rectangle((0, 0), 1920, 1080, fill=False, edgecolor=INK2, linewidth=1.2))
    for p in a["points"]:
        tx, ty = p["target"]
        mx, my = p["mean"]
        ax.add_patch(Circle((mx, my), p["jitter_px"], facecolor=AFTER, alpha=0.10, edgecolor=AFTER,
                            linewidth=1, linestyle="--"))
        ax.plot([tx - 18, tx + 18], [ty, ty], color=INK, linewidth=2)
        ax.plot([tx, tx], [ty - 18, ty + 18], color=INK, linewidth=2)
        ax.add_patch(FancyArrowPatch((tx, ty), (mx, my), arrowstyle="-|>", mutation_scale=10,
                                     color=AFTER, linewidth=1.5))
        ax.scatter([mx], [my], s=46, color=AFTER, edgecolor=SURFACE, linewidth=2, zorder=5)
        right = tx > 1200
        ax.annotate(f"偏 {p['offset_px']} px\n抖 ±{p['jitter_px']} px", (tx, ty), xytext=(-62 if right else 62, 0),
                    textcoords="offset points", fontsize=10, color=INK2, va="center",
                    ha="right" if right else "left")
    ax.set_xlim(-40, 1960)
    ax.set_ylim(1120, -40)
    ax.set_aspect("equal")
    ax.set_xlabel("螢幕 X（像素）")
    ax.set_ylabel("螢幕 Y（像素）")
    ax.set_title("Tobii Eye Tracker 5 原始注視準確度（5 點）")
    ax.scatter([], [], marker="+", s=120, color=INK, label="目標點")
    ax.scatter([], [], s=46, color=AFTER, label="平均注視位置")
    ax.add_patch(Circle((-999, -999), 1, facecolor=AFTER, alpha=0.10, edgecolor=AFTER, linestyle="--", label="原始抖動範圍（RMS）"))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=False)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(D, "accuracy.png"), facecolor=SURFACE)
    plt.close(fig)


# ------------------------------------------------------------ 2. 任務時間
TASKS = [("click", "點 3 個圓"), ("right", "右鍵"), ("double", "雙擊"), ("drag", "拖曳"), ("scroll", "捲動")]


def chart_tasks():
    b, a = load("handson_before.json")["tasks"], load("handson_after.json")["tasks"]
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=150)
    style(ax)
    ax.grid(axis="y", visible=False)
    h = 0.36
    ys = list(range(len(TASKS)))
    for i, (k, label) in enumerate(TASKS):
        y = ys[i]
        for off, data, col in ((-h / 2 - 0.02, b, BEFORE), (h / 2 + 0.02, a, AFTER)):
            v = data[k]["secs"]
            ax.barh(y + off, v, height=h, color=col, edgecolor=SURFACE, linewidth=2)
            ax.text(v + 1, y + off, f"{v:.0f} 秒", va="center", fontsize=10, color=INK2)
    ax.set_yticks(ys, [t for _, t in TASKS])
    ax.invert_yaxis()
    ax.set_xlabel("完成時間（秒）")
    tb = sum(b[k]["secs"] for k, _ in TASKS)
    ta = sum(a[k]["secs"] for k, _ in TASKS)
    ax.set_title(f"實機操作 5 項任務：總時間 {tb:.0f} 秒 → {ta:.0f} 秒")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BEFORE, label="v1.0.0：未校正、無放大鏡"),
                       Patch(color=AFTER, label="v1.1.0：9 點校正＋放大鏡")], loc="lower right", frameon=False)
    ax.set_xlim(0, max(b[k]["secs"] for k, _ in TASKS) * 1.15)
    fig.tight_layout()
    fig.savefig(os.path.join(D, "task_time.png"), facecolor=SURFACE)
    plt.close(fig)


# ------------------------------------------------------------ 3. 點擊落點
W, H = 1770, 1032                     # 測驗視窗大小（螢幕 1920 寬減工具列 150；高 = 可用高度）
CIRCLES = [((0.25, 0.45), 90), ((0.6, 0.7), 60), ((0.75, 0.35), 38)]


def landing(name):
    out = [[] for _ in CIRCLES]
    ci = 0
    for e in load(name)["events"]:
        if e["task"] == "click" and e["ev"] == "down" and e.get("b") == "L":
            (fx, fy), r = CIRCLES[ci]
            dx, dy = e["x"] - fx * W, e["y"] - fy * H
            out[ci].append((dx, dy))
            if math.hypot(dx, dy) <= r:
                ci += 1
                if ci >= len(CIRCLES):
                    break
    return out


def chart_landing():
    b, a = landing("handson_before.json"), landing("handson_after.json")
    fig, axes = plt.subplots(1, 3, figsize=(10, 4.0), dpi=150)
    for i, ax in enumerate(axes):
        r = CIRCLES[i][1]
        ax.add_patch(Circle((0, 0), r, facecolor="#9FD3FF", alpha=0.45, edgecolor="#5b9bd5"))
        ax.axhline(0, color=GRID, linewidth=0.8)
        ax.axvline(0, color=GRID, linewidth=0.8)
        if b[i]:
            ax.scatter(*zip(*b[i]), marker="x", s=60, color=BEFORE, linewidth=2, label="v1.0.0", zorder=4)
        if a[i]:
            ax.scatter(*zip(*a[i]), s=60, color=AFTER, edgecolor=SURFACE, linewidth=2, label="v1.1.0", zorder=5)
        lim = 110
        ax.set_xlim(-lim, lim)
        ax.set_ylim(lim, -lim)
        ax.set_aspect("equal")
        ax.set_title(f"目標 {i + 1}：半徑 {r} px", fontsize=11)
        ax.text(0.02, 0.02, f"v1.0.0 點了 {len(b[i])} 次\nv1.1.0 點了 {len(a[i])} 次",
                transform=ax.transAxes, fontsize=9, color=INK2)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=8)
    axes[0].legend(loc="upper left", frameon=False, fontsize=9)
    fig.suptitle("每次點擊的落點（相對目標中心，像素）", x=0.01, ha="left", fontweight="bold", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(D, "click_landing.png"), facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    chart_accuracy()
    chart_tasks()
    chart_landing()
    print("charts ok")
