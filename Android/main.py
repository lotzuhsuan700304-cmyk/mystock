import flet as ft
import yfinance as yf
import pandas as pd
import numpy as np

# ==========================================
# 1. 核心投資組合與現金池設定 (NBIS 550股 + 現金 $9,616.50)
# ==========================================
CASH_POOL = 9616.50
PORTFOLIO = [
    {"Ticker": "NBIS", "Name": "Nebius Group", "Shares": 550, "Avg_Cost": 226.215, "Kelly_Cap": 15.0, "Hard_Stop": 159.00, "Fib_Target": 195.80},
    {"Ticker": "MRVL", "Name": "Marvell Tech", "Shares": 350, "Avg_Cost": 255.965, "Kelly_Cap": 15.0, "Hard_Stop": 218.00, "Fib_Target": 247.77},
    {"Ticker": "MU",   "Name": "Micron Tech",  "Shares": 50,  "Avg_Cost": 516.017, "Kelly_Cap": 15.0, "Hard_Stop": 880.00, "Fib_Target": 1003.10},
    {"Ticker": "AVGO", "Name": "Broadcom Inc", "Shares": 100, "Avg_Cost": 325.207, "Kelly_Cap": 15.0, "Hard_Stop": 325.20, "Fib_Target": 358.50},
    {"Ticker": "DRAM", "Name": "Roundhill ETF","Shares": 350, "Avg_Cost": 68.393,  "Kelly_Cap": 5.0,  "Hard_Stop": 44.50,  "Fib_Target": 52.55},
    {"Ticker": "PLTR", "Name": "Palantir Tech","Shares": 50,  "Avg_Cost": 178.932, "Kelly_Cap": 10.0, "Hard_Stop": 185.55, "Fib_Target": 200.97},
]

# ==========================================
# 2. Flet 1.0 跨版本相容元件輔助函數
# ==========================================
def safe_border(width: float, color: str):
    try:
        return ft.border.all(width, color)
    except Exception:
        try:
            return ft.Border.all(width, color)
        except Exception:
            return None

def make_button(text: str, on_click_fn, bg_color: str = "#2563eb", expand: bool = False):
    """Flet 1.0 原生深色觸控按鈕 (取代舊版 ElevatedButton)"""
    return ft.Container(
        content=ft.Row(
            [ft.Text(text, color="#ffffff", size=14, weight=ft.FontWeight.BOLD)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=bg_color,
        border_radius=8,
        padding=10,
        on_click=on_click_fn,
        expand=expand,
    )

# ==========================================
# 3. 行情與量化指標抓取函數 (支援盤前/盤後 prepost=True)
# ==========================================
def fetch_mobile_quant(ticker: str, include_ext: bool = True):
    try:
        tk = yf.Ticker(ticker.strip().upper())
        hist = tk.history(period="6mo")
        if hist.empty:
            return None
        reg_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else reg_close

        price = reg_close
        session_tag = "常規盤"
        if include_ext:
            try:
                ext = tk.history(period="1d", interval="1m", prepost=True)
                if not ext.empty and float(ext["Close"].iloc[-1]) > 0:
                    price = round(float(ext["Close"].iloc[-1]), 2)
                    session_tag = "盤前/即時"
            except Exception:
                pass

        chg_pct = ((price - prev_close) / prev_close) * 100.0
        high_low = hist["High"] - hist["Low"]
        high_close = (hist["High"] - hist["Close"].shift()).abs()
        low_close = (hist["Low"] - hist["Close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else price * 0.04

        ma20 = float(hist["Close"].rolling(20).mean().iloc[-1]) if len(hist) >= 20 else price
        swing_high = float(hist["High"].max())
        swing_low = float(hist["Low"].min())
        diff = max(swing_high - swing_low, 0.01)

        return {
            "Price": round(price, 2),
            "Chg_Pct": round(chg_pct, 2),
            "Session": session_tag,
            "ATR": round(atr, 2),
            "MA20": round(ma20, 2),
            "Fib_382": round(swing_low + diff * 0.382, 2),
            "Fib_618": round(swing_low + diff * 0.618, 2),
        }
    except Exception:
        return None

# ==========================================
# 4. Flet 1.0 原生手機 App 主介面
# ==========================================
def main(page: ft.Page):
    page.title = "美股量化風控 App"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e1117"
    page.padding = 14
    page.scroll = ft.ScrollMode.AUTO

    # 頂部狀態元件
    total_equity_txt = ft.Text("$0.00", size=28, weight=ft.FontWeight.BOLD, color="#f7fafc")
    total_pnl_txt = ft.Text("連線計算中...", size=14, weight=ft.FontWeight.BOLD, color="#a0aec0")
    ext_switch = ft.Switch(label="🌅 含盤前/盤後延長報價", value=True)
    loading_bar = ft.ProgressBar(visible=False, color="#ecc94b", bgcolor="#1e2536")

    # 三大分頁容器
    tab_overview_col = ft.Column(spacing=10, visible=True)
    tab_trim_col = ft.Column(spacing=10, visible=False)
    tab_pyramid_col = ft.Column(spacing=10, visible=False)

    # 萬用加減碼輸入元件
    input_ticker = ft.TextField(label="美股代號 (如 AVGO, PLD, COHR, NBIS)", value="AVGO", width=240)
    input_budget = ft.TextField(label="預計動用加碼預算 ($)", value="9616", width=180)
    pyramid_result_col = ft.Column(spacing=8)

    # 更新持股與總覽資料
    def refresh_portfolio(e=None):
        loading_bar.visible = True
        page.update()

        tab_overview_col.controls.clear()
        total_stock_val = 0.0
        total_cost_val = 0.0
        use_ext = ext_switch.value

        fetched_items = []
        for item in PORTFOLIO:
            q = fetch_mobile_quant(item["Ticker"], include_ext=use_ext)
            p = q["Price"] if q else item["Avg_Cost"]
            chg = q["Chg_Pct"] if q else 0.0
            sess = q["Session"] if q else "離線"
            atr = q["ATR"] if q else round(p * 0.04, 2)
            mkt = item["Shares"] * p
            cost = item["Shares"] * item["Avg_Cost"]
            total_stock_val += mkt
            total_cost_val += cost
            fetched_items.append((item, p, chg, sess, atr, mkt, cost))

        total_equity = total_stock_val + CASH_POOL
        total_pnl = total_stock_val - total_cost_val
        total_pnl_pct = (total_pnl / total_cost_val * 100.0) if total_cost_val > 0 else 0.0

        total_equity_txt.value = f"${total_equity:,.2f}"
        total_pnl_txt.value = f"未實現損益: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%) / 現金池: ${CASH_POOL:,.0f}"
        total_pnl_txt.color = "#48bb78" if total_pnl >= 0 else "#f56565"

        for item, p, chg, sess, atr, mkt, cost in fetched_items:
            pnl = mkt - cost
            pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0
            weight_pct = (mkt / total_equity * 100.0) if total_equity > 0 else 0.0
            kelly_cap = item["Kelly_Cap"]
            opt_shares = int(np.floor((total_equity * (kelly_cap / 100.0)) / p)) if p > 0 else 0

            pnl_color = "#48bb78" if pnl >= 0 else "#f56565"
            is_overweight = weight_pct > kelly_cap
            badge_text = f"🚨 超配 ({weight_pct:.1f}% > {kelly_cap:.0f}%) 禁攤平" if is_overweight else f"✅ 權重安全 ({weight_pct:.1f}%)"
            badge_color = "#f56565" if is_overweight else "#48bb78"

            card = ft.Container(
                bgcolor="#161b26",
                border=safe_border(1, "#2d3748"),
                border_radius=12,
                padding=14,
                content=ft.Column([
                    ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text(item["Ticker"], size=20, weight=ft.FontWeight.BOLD, color="#ffffff"),
                                ft.Text(f"[{sess}]", size=11, color="#63b3ed"),
                            ], spacing=6),
                            ft.Text(f"{item['Shares']} 股 | 均價 ${item['Avg_Cost']:.2f} | 凱利上限 {opt_shares} 股", size=12, color="#a0aec0"),
                        ], expand=True),
                        ft.Column([
                            ft.Text(f"${p:.2f} ({chg:+.2f}%)", size=18, weight=ft.FontWeight.BOLD, color="#ffffff"),
                            ft.Text(f"${pnl:,.0f} ({pnl_pct:+.2f}%)", size=13, weight=ft.FontWeight.BOLD, color=pnl_color),
                        ]),
                    ]),
                    ft.Divider(height=8, color="#2d3748"),
                    ft.Row([
                        ft.Text(badge_text, size=12, color=badge_color, weight=ft.FontWeight.BOLD, expand=True),
                        ft.Text(f"防守: ${item['Hard_Stop']:.2f} | 目標: ${item['Fib_Target']:.2f}", size=11, color="#cbd5e0"),
                    ])
                ], spacing=4)
            )
            tab_overview_col.controls.append(card)

        loading_bar.visible = False
        page.update()

    # 建立 Tab 2：NBIS & MRVL 三階梯減碼專屬卡片
    def build_trim_tab():
        tab_trim_col.controls.clear()
        tab_trim_col.controls.append(
            ft.Container(
                bgcolor="#161b26", border=safe_border(1, "#3182ce"), border_radius=12, padding=14,
                content=ft.Column([
                    ft.Text("🔹 NBIS 三階梯減碼計畫 (現有 550 股 ➔ 目標 333 股)", size=16, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                    ft.Text("• 第一階 (0.382 關鍵阻力)：掛單 $195.80 賣出 87 股 (回收 $17,035)", size=13, color="#e2e8f0"),
                    ft.Text("• 第二階 (前波密集壓力區)：掛單 $200.00 賣出 80 股 (回收 $16,000)", size=13, color="#e2e8f0"),
                    ft.Text("• 第三階 (0.618 黃金分割)：掛單 $215.50 賣出 50 股 (回收 $10,775)", size=13, color="#e2e8f0"),
                    ft.Text("• ⚠️ 破位硬性防禦底線：跌破 $159.00 強制減碼 100 股保護本金", size=13, color="#fc8181", weight=ft.FontWeight.BOLD),
                ], spacing=6)
            )
        )
        tab_trim_col.controls.append(
            ft.Container(
                bgcolor="#161b26", border=safe_border(1, "#ecc94b"), border_radius=12, padding=14,
                content=ft.Column([
                    ft.Text("🔸 MRVL 三階梯減碼計畫 (現有 350 股 ➔ 目標 180 股)", size=16, weight=ft.FontWeight.BOLD, color="#ecc94b"),
                    ft.Text("• 第一階 (0.618 關鍵位 GTC)：掛單 $247.77 賣出 57 股 (回收 $14,123)", size=13, color="#e2e8f0"),
                    ft.Text("• 第二階 (前高成本壓力區)：掛單 $256.00 賣出 60 股 (回收 $15,360)", size=13, color="#e2e8f0"),
                    ft.Text("• 第三階 (1.272 波段擴展)：掛單 $272.50 賣出 53 股 (回收 $14,443)", size=13, color="#e2e8f0"),
                    ft.Text("• ⚠️ 破位硬性防禦底線：跌破 $218.00 強制減碼 60 股", size=13, color="#fc8181", weight=ft.FontWeight.BOLD),
                ], spacing=6)
            )
        )

    # 計算 Tab 3：萬用個股加減碼與新股建倉引擎
    def calc_pyramid_plan(e=None):
        tkr = input_ticker.value.strip().upper()
        try:
            budget = float(input_budget.value)
        except Exception:
            budget = CASH_POOL

        loading_bar.visible = True
        page.update()

        q = fetch_mobile_quant(tkr, include_ext=ext_switch.value)
        pyramid_result_col.controls.clear()

        if not q:
            pyramid_result_col.controls.append(ft.Text(f"❌ 找不到代號 {tkr} 的報價資料，請確認代號是否正確。", color="#f56565"))
            loading_bar.visible = False
            page.update()
            return

        p = q["Price"]
        atr = q["ATR"]
        ma20 = q["MA20"]
        fib382 = q["Fib_382"]
        fib618 = q["Fib_618"]

        matched = [x for x in PORTFOLIO if x["Ticker"] == tkr]
        cur_shares = matched[0]["Shares"] if matched else 0
        is_over = (tkr in ["NBIS", "MRVL"] and cur_shares > 333)

        bp1 = round(p, 2)
        bp2 = round(max(p + 0.8 * atr, ma20), 2)
        bp3 = round(p + 1.6 * atr, 2)

        s1 = int(np.floor((budget * 0.40) / bp1)) if bp1 > 0 else 0
        s2 = int(np.floor((budget * 0.35) / bp2)) if bp2 > 0 else 0
        s3 = int(np.floor((budget * 0.25) / bp3)) if bp3 > 0 else 0

        gate_msg = (
            f"🚫 【風控守門員攔截】{tkr} 目前持有 {cur_shares} 股已超過半凱利 15% 上限！嚴禁向下攤平，請優先執行減碼！"
            if is_over else
            f"✅ 【風控守門員放行】{tkr} 具備建倉/加碼空間！即時價 ${p:.2f} | 20MA ${ma20:.2f} | 14D ATR ${atr:.2f}"
        )
        gate_color = "#f56565" if is_over else "#48bb78"

        pyramid_result_col.controls.append(
            ft.Container(
                bgcolor="#161b26", border=safe_border(1.5, gate_color), border_radius=10, padding=12,
                content=ft.Column([
                    ft.Text(gate_msg, size=13, weight=ft.FontWeight.BOLD, color=gate_color),
                    ft.Divider(height=8, color="#2d3748"),
                    ft.Text(f"📈 【金字塔三階梯右側買入計畫 (預算 ${budget:,.0f})】", size=15, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                    ft.Text(f"• 第 1 批 (底倉 40%)：現價 ${bp1:.2f} 買入 {s1} 股 (動用 ${s1*bp1:,.0f}) | 停損 ${bp1 - 2*atr:.2f}", size=13, color="#e2e8f0"),
                    ft.Text(f"• 第 2 批 (突破確認 35%)：漲破 ${bp2:.2f} 買入 {s2} 股 (動用 ${s2*bp2:,.0f}) | 停損上移保本", size=13, color="#e2e8f0"),
                    ft.Text(f"• 第 3 批 (趨勢滿倉 25%)：突破 ${bp3:.2f} 買入 {s3} 股 (動用 ${s3*bp3:,.0f}) | 鎖利防守", size=13, color="#e2e8f0"),
                    ft.Divider(height=8, color="#2d3748"),
                    ft.Text("📉 【費波納契分批停利 / 減碼目標價】", size=15, weight=ft.FontWeight.BOLD, color="#68d391"),
                    ft.Text(f"• 短線 0.382 調節位：${max(fib382, round(p + 1.2*atr, 2)):.2f} (賣出 30%)", size=13, color="#e2e8f0"),
                    ft.Text(f"• 波段 0.618 黃金位：${max(fib618, round(p + 2.5*atr, 2)):.2f} (賣出 40%)", size=13, color="#e2e8f0"),
                    ft.Text(f"• 硬性 -2 ATR 停損線：${round(p - 2.0*atr, 2):.2f} (跌破無條件出場)", size=13, color="#fc8181"),
                ], spacing=5)
            )
        )
        loading_bar.visible = False
        page.update()

    tab_pyramid_col.controls.extend([
        ft.Text("🚀 支援現有持股與未來任意新購美股 (如 PLD, COHR, RMBS, NVDA)", size=13, color="#a0aec0"),
        ft.Row([input_ticker, input_budget, make_button("🔍 試算加減碼", calc_pyramid_plan, "#2563eb")], spacing=10),
        pyramid_result_col
    ])

    # 分頁切換邏輯
    def switch_tab(tab_idx: int):
        tab_overview_col.visible = (tab_idx == 0)
        tab_trim_col.visible = (tab_idx == 1)
        tab_pyramid_col.visible = (tab_idx == 2)
        if tab_idx == 2 and len(pyramid_result_col.controls) == 0:
            calc_pyramid_plan()
        page.update()

    build_trim_tab()

    page.add(
        ft.Container(
            bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=14, padding=16,
            content=ft.Column([
                ft.Row([
                    ft.Text("📊 美股量化風控 App (原生版)", size=16, weight=ft.FontWeight.BOLD, color="#a0aec0", expand=True),
                    make_button("🔄 刷新報價", refresh_portfolio, "#3182ce"),
                ]),
                total_equity_txt,
                total_pnl_txt,
                ext_switch,
                loading_bar,
            ], spacing=6)
        ),
        ft.Row([
            make_button("📊 持股總覽", lambda e: switch_tab(0), "#1e293b", expand=True),
            make_button("🧮 雙雄減碼", lambda e: switch_tab(1), "#1e293b", expand=True),
            make_button("🚀 萬用加減碼", lambda e: switch_tab(2), "#1e293b", expand=True),
        ], spacing=8),
        tab_overview_col,
        tab_trim_col,
        tab_pyramid_col,
    )

    refresh_portfolio()

# ==========================================
# 5. 啟動 Web 瀏覽器投影模式 (Port 8550)
# ==========================================
if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550, host="0.0.0.0")