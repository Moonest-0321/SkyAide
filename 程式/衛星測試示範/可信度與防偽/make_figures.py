"""v7 新增圖：SOP 流程、可信度驗證結果。風格沿用 charts/t6_layers.png（淺灰藍框、青灰箭頭）。"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]:
    if os.path.exists(p):
        font_manager.fontManager.addfont(p)
plt.rcParams["font.family"] = ["Noto Sans CJK TC", "Noto Sans CJK JP", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts_v7")
os.makedirs(OUT, exist_ok=True)
FILL, EDGE, ARROW, TXT = "#eef3f5", "#b9c8cf", "#5d8a94", "#2b2b2b"
ACC, ACC_FILL = "#9a5b2e", "#f7efe8"


def box(ax, x, y, w, h, fc=FILL, ec=EDGE, lw=1.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                fc=fc, ec=ec, lw=lw, mutation_aspect=1))


def arrow(ax, x0, y0, x1, y1, color=ARROW, lw=1.8, style="-|>"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=12,
                                 color=color, lw=lw, shrinkA=0, shrinkB=0))


# ------------------------------------------------------------------ 圖：標準作業流程
def fig_sop():
    fig = plt.figure(figsize=(16.5, 9.2), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    groups = [("資料輸入", 0.015, 0.30), ("模型計算", 0.345, 0.30), ("輸出與查驗", 0.675, 0.31)]
    steps = {
        "資料輸入": [("S1 輸入登錄與檢核", "影像、地籍、申報、App 照片\n逐檔記錄來源編號與雜湊\n檢核有效像素、數值範圍、新鮮度")],
        "模型計算": [("S2 計算環境鎖定", "程式碼、參數、套件版本\n各算雜湊，事件開始即凍結"),
                 ("S3 判讀與分級", "計算前重新比對輸入雜湊；判讀 → 損失區間\n→ 三道關卡；長時間對照 L1–L4、原因碼"),
                 ("S4 可信度評定", "五項檢核（即關卡一、三的細項）\n給高／中／低；只有「高」才可能判 A")],
        "輸出與查驗": [("S5 存證報告簽發與先行通知", "雜湊 → 數位簽章 → 時戳 → 查驗碼；\n初步結果通知農民，可補照片或更正"),
                  ("S6 公所判定", "承辦以機關憑證另行簽章，與系統結果並列"),
                  ("S7 批次封存", "同批報告組成 Merkle 根交公所留存"),
                  ("S8 災後品質評估", "以法定抽查樣本評估各作物 A 級精確度，\n信賴下界未達 95% 者下次停判 A")],
    }
    top, bottom = 0.95, 0.27
    for name, gx, gw in groups:
        box(ax, gx, bottom, gw, top - bottom, fc="white", ec=EDGE, lw=1.0)
        ax.text(gx + 0.015, top - 0.035, name, fontsize=17, color=TXT, va="center", weight="bold")
        items = steps[name]
        n = len(items)
        avail = top - 0.075 - bottom - 0.02
        bh = min(0.17, (avail - 0.02 * (n - 1)) / n) if n > 1 else 0.165
        y = top - 0.075 - bh
        for i, (t, d) in enumerate(items):
            box(ax, gx + 0.015, y, gw - 0.03, bh)
            ax.text(gx + 0.03, y + bh - 0.032, t, fontsize=14, color=TXT, va="center", weight="bold")
            ax.text(gx + 0.03, y + bh - 0.062, d, fontsize=11, color="#444", va="top", linespacing=1.55)
            if i < n - 1:
                arrow(ax, gx + gw / 2, y - 0.002, gx + gw / 2, y - 0.018)
            y -= bh + 0.02
    arrow(ax, 0.315, 0.62, 0.345, 0.62); arrow(ax, 0.645, 0.62, 0.675, 0.62)

    # 未通過時的處理
    box(ax, 0.03, 0.555, 0.27, 0.13, fc=ACC_FILL, ec="#d9b99c")
    ax.text(0.045, 0.655, "檢核未通過", fontsize=13, color=ACC, va="center", weight="bold")
    ax.text(0.045, 0.625, "停止計算，記錄原因；\n補件、改用其他日期影像或改列 C", fontsize=11.5, color="#444", va="top", linespacing=1.55)
    arrow(ax, 0.165, 0.71, 0.165, 0.69, color=ACC)
    ax.text(0.36, 0.29, "可信度非「高」→ 列 C，附原因碼", fontsize=11.5, color=ACC, va="center")

    # 作業日誌（雜湊鏈）
    ly, lh = 0.15, 0.085
    box(ax, 0.015, ly, 0.97, lh, fc=ACC_FILL, ec="#d9b99c")
    ax.text(0.03, ly + lh / 2, "作業日誌", fontsize=14, color=ACC, va="center", weight="bold")
    xs = [0.16, 0.42, 0.50, 0.58, 0.725, 0.79, 0.855, 0.92]
    for i, x in enumerate(xs):
        ax.add_patch(FancyBboxPatch((x - 0.028, ly + 0.02), 0.056, lh - 0.04, boxstyle="round,pad=0,rounding_size=0.008",
                                    fc="white", ec="#c9a27f", lw=1))
        ax.text(x, ly + lh / 2, f"S{i + 1}", fontsize=11, color=ACC, ha="center", va="center")
        if i:
            ax.plot([xs[i - 1] + 0.028, x - 0.028], [ly + lh / 2] * 2, color="#c9a27f", lw=1.4)
        ax.plot([x, x], [ly + lh, bottom], color="#d9b99c", lw=0.9, ls=(0, (2, 2)))
    ax.text(0.03, ly - 0.03, "每一步寫入一筆紀錄，並記下前一筆的雜湊；刪除或改動任何一筆，其後的鏈結即斷開。",
            fontsize=11.5, color="#555", va="center")
    ax.text(0.03, 0.055, "查驗：農民與公所掃描查驗碼確認報告未經改動；縣府抽查比對 Merkle 根；審計以同一批輸入與同一版程式重算；S8 參考歐盟面積監測系統的年度品質評估。",
            fontsize=11.5, color="#555", va="center")
    fig.savefig(os.path.join(OUT, "v7_sop.png"), dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ 圖：可信度等級與實際誤差
def fig_cred(path):
    r = json.load(open(path, encoding="utf-8"))
    lv = [k for k in "高中低" if k in r["各可信度等級"]]
    d = r["各可信度等級"]
    fig, axs = plt.subplots(1, 3, figsize=(12.5, 3.9), dpi=150)
    cols = ["#4f7f8a", "#a8bfc6", "#c98b5d"]
    specs = [("中間值平均誤差_百分點", "損失中間值平均誤差（百分點）", lambda v: f"{v:.1f}"),
             ("誤差大於15個百分點比例", "誤差超過 15 個百分點的比例", lambda v: f"{v:.0%}"),
             ("錯邊比例", "中間值落在 20% 門檻錯邊的比例", lambda v: f"{v:.0%}")]
    for ax, (k, title, fmt) in zip(axs, specs):
        vals = [d[x][k] for x in lv]
        bars = ax.bar(lv, vals, color=cols[:len(lv)], width=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), fmt(v), ha="center", va="bottom", fontsize=11)
        ax.set_title(title, fontsize=12)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_yticks([])
        ax.set_xticklabels([f"{x}\n（{d[x]['坵塊數']} 筆）" for x in lv], fontsize=11)
        ax.set_ylim(0, max(vals) * 1.25 if max(vals) > 0 else 1)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "v7_credibility.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    fig_sop()
    fig_cred(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sop_output", "credibility_eval.json"))
    print("ok")
