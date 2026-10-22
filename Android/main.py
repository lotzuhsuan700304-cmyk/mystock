import datetime
import flet as ft
import yfinance as yf
import pandas as pd
import numpy as np

# ==========================================
# 1. 初始投資組合與美股交易日推算設定
# ==========================================
DEFAULT_PORTFOLIO = [
    {"Ticker": "NBIS", "Name": "Nebius Group", "Shares": 550, "Avg_Cost": 226.215, "Target_Kelly_Pct": 15.0, "Hard_Stop": 159.00, "Key_Fib_Target": 195.80},
    {"Ticker": "MRVL", "Name": "Marvell Tech", "Shares": 350, "Avg_Cost": 255.965, "Target_Kelly_Pct": 15.0, "Hard_Stop": 218.00, "Key_Fib_Target": 247.77},
    {"Ticker": "MU",   "Name": "Micron Tech",  "Shares": 50,  "Avg_Cost": 516.017, "Target_Kelly_Pct": 15.0, "Hard_Stop": 880.00, "Key_Fib_Target": 1003.10},
    {"Ticker": "AVGO", "Name": "Broadcom Inc", "Shares": 100, "Avg_Cost": 325.207, "Target_Kelly_Pct": 15.0, "Hard_Stop": 325.20, "Key_Fib_Target": 358.50},
    {"Ticker": "DRAM", "Name": "Roundhill ETF","Shares": 350, "Avg_Cost": 68.393,  "Target_Kelly_Pct": 5.0,  "Hard_Stop": 44.50,  "Key_Fib_Target": 52.55},
    {"Ticker": "PLTR", "Name": "Palantir Tech","Shares": 50,  "Avg_Cost": 178.932, "Target_Kelly_Pct": 10.0, "Hard_Stop": 185.55, "Key_Fib_Target": 200.97},
]

US_HOLIDAYS_2026 = {
    datetime.date(2026, 1, 1),
    datetime.date(2026, 1, 19),
    datetime.date(2026, 2, 16),
    datetime.date(2026, 4, 3),
    datetime.date(2026, 5, 25),
    datetime.date(2026, 6, 19),
    datetime.date(2026, 7, 3),
    datetime.date(2026, 9, 7),
    datetime.date(2026, 11, 26),
    datetime.date(2026, 12, 25),
}

def add_us_trading_days(start_date: datetime.date, trading_days: int) -> datetime.date:
    """從起始基準日向後推算指定美股交易日數（自動跳過週末與美股休市日）"""
    cur_dt = start_date
    added = 0
    while added < trading_days:
        cur_dt += datetime.timedelta(days=1)
        if cur_dt.weekday() < 5 and cur_dt not in US_HOLIDAYS_2026:
            added += 1
    return cur_dt

# ==========================================
# 2. Flet 1.0 跨版本相容 UI 輔助函數
# ==========================================
def safe_border(width: float, color: str):
    try:
        return ft.border.all(width, color)
    except Exception:
        try:
            return ft.Border.all(width, color)
        except Exception:
            return None

def make_btn(text: str, on_click_fn, bg_color: str = "#2563eb", text_color: str = "#ffffff", expand: bool = False, pad_v: int = 10, pad_h: int = 14, border_col: str = None):
    """Flet 1.0 原生觸控按鈕"""
    return ft.Container(
        content=ft.Row(
            [ft.Text(text, color=text_color, size=13, weight=ft.FontWeight.BOLD)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=bg_color,
        border=safe_border(1.5, border_col) if border_col else None,
        border_radius=8,
        padding=ft.padding.symmetric(vertical=pad_v, horizontal=pad_h) if hasattr(ft, "padding") else 10,
        on_click=on_click_fn,
        expand=expand,
    )

def make_table_box(title: str, headers: list, rows: list, border_color: str = "#2d3748"):
    """高質感原生資料表渲染器"""
    header_cells = [
        ft.Container(
            content=ft.Text(h, size=12, weight=ft.FontWeight.BOLD, color="#90cdf4"),
            expand=True,
        ) for h in headers
    ]
    table_rows = [
        ft.Container(
            bgcolor="#1e293b",
            padding=8,
            border_radius=6,
            content=ft.Row(header_cells),
        )
    ]
    for r in rows:
        row_cells = [
            ft.Container(
                content=ft.Text(str(c), size=12, color="#e2e8f0"),
                expand=True,
            ) for c in r
        ]
        table_rows.append(
            ft.Container(
                padding=8,
                border=safe_border(0.5, "#2d3748"),
                border_radius=4,
                content=ft.Row(row_cells),
            )
        )
    return ft.Container(
        bgcolor="#161b26",
        border=safe_border(1, border_color),
        border_radius=12,
        padding=14,
        content=ft.Column([
            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
            ft.Column(table_rows, spacing=4),
        ], spacing=8)
    )

# ==========================================
# 3. 即時行情與量化指標計算引擎 (支援常規盤 + 盤前/盤後)
# ==========================================
QUOTE_CACHE = {}

def fetch_quant_metrics(ticker: str, get_extended: bool = True, force_refresh: bool = False):
    tkr = ticker.strip().upper()
    cache_key = f"{tkr}_{get_extended}"
    if not force_refresh and cache_key in QUOTE_CACHE:
        return QUOTE_CACHE[cache_key]

    try:
        tk = yf.Ticker(tkr)
        hist = tk.history(period="1y")
        if hist.empty:
            return None

        reg_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else reg_close

        current_price = reg_close
        market_session = "常規收盤"
        if get_extended:
            try:
                ext_hist = tk.history(period="1d", interval="1m", prepost=True)
                if not ext_hist.empty:
                    ext_price = float(ext_hist["Close"].iloc[-1])
                    if ext_price > 0:
                        current_price = round(ext_price, 2)
                        market_session = "即時/盤前盤後"
            except Exception:
                pass

        day_chg_pct = ((current_price - prev_close) / prev_close) * 100.0

        recent = hist.tail(126)
        swing_high = float(recent["High"].max())
        swing_low = float(recent["Low"].min())
        diff = max(swing_high - swing_low, 0.01)

        fib_0236 = swing_low + diff * 0.236
        fib_0382 = swing_low + diff * 0.382
        fib_0618 = swing_low + diff * 0.618
        fib_1272 = swing_low + diff * 1.272

        high_low = hist["High"] - hist["Low"]
        high_close = (hist["High"] - hist["Close"].shift()).abs()
        low_close = (hist["Low"] - hist["Close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr_14 = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else reg_close * 0.04

        delta = hist["Close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi_14 = float((100 - (100 / (1 + rs))).iloc[-1]) if not rs.dropna().empty else 50.0

        ma20 = float(hist["Close"].rolling(20).mean().iloc[-1]) if len(hist) >= 20 else reg_close
        ma50 = float(hist["Close"].rolling(50).mean().iloc[-1]) if len(hist) >= 50 else reg_close
        ma200 = float(hist["Close"].rolling(200).mean().iloc[-1]) if len(hist) >= 200 else ma50

        res = {
            "Price": round(current_price, 2),
            "Reg_Close": round(reg_close, 2),
            "Day_Chg_Pct": round(day_chg_pct, 2),
            "Session": market_session,
            "Swing_High": round(swing_high, 2),
            "Swing_Low": round(swing_low, 2),
            "Fib_0236": round(fib_0236, 2),
            "Fib_0382": round(fib_0382, 2),
            "Fib_0618": round(fib_0618, 2),
            "Fib_1272": round(fib_1272, 2),
            "ATR": round(atr_14, 2),
            "RSI": round(rsi_14, 1),
            "MA20": round(ma20, 2),
            "MA50": round(ma50, 2),
            "MA200": round(ma200, 2),
        }
        QUOTE_CACHE[cache_key] = res
        return res
    except Exception:
        return None

# ==========================================
# 4. Flet 旗艦級操盤系統主視窗
# ==========================================
def main(page: ft.Page):
    page.title = "美股量化風控 × 費波納契 × 半凱利操盤系統"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e1117"
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO

    # 系統狀態變數
    portfolio_data = [dict(item) for item in DEFAULT_PORTFOLIO]
    active_tab_idx = [0]

    # 頂部控制列與費氏週期起始日設定
    sw_live = ft.Switch(label="🌐 自動抓即時報價", value=True)
    sw_ext = ft.Switch(label="🌅 含盤前/盤後延長價", value=True)
    sw_trading_days = ft.Switch(label="📅 按美股交易日推算 (扣週末假日)", value=True)
    tf_anchor_date = ft.TextField(label="🗓️ 費氏週期起始基準日 T+0 (YYYY-MM-DD)", value="2026-10-16", width=220)
    tf_cash = ft.TextField(label="可用美元現金池 ($)", value="9616.50", width=150)
    tf_tax = ft.TextField(label="累計可抵稅虧損 ($)", value="-3461.52", width=150)
    tf_shock = ft.TextField(label="大盤衝擊模擬 (%)", value="0", width=130)
    tf_beta = ft.TextField(label="高Beta敏感倍數", value="1.50", width=130)
    loading_bar = ft.ProgressBar(visible=False, color="#ecc94b", bgcolor="#1e2536")

    # 頂部區域容器
    kpi_row_container = ft.Row(wrap=True, spacing=10)
    tz_header_text = ft.Text("⏱️ 費波納契時間週期變盤視窗 (Fibonacci Time Zones)", size=16, weight=ft.FontWeight.BOLD, color="#f7fafc")
    tz_row_container = ft.Row(wrap=True, spacing=10)
    tab_nav_row = ft.Row(wrap=True, spacing=8)

    # 四大分頁內容容器
    tab1_col = ft.Column(spacing=12, visible=True)
    tab2_col = ft.Column(spacing=12, visible=False)
    tab3_col = ft.Column(spacing=12, visible=False)
    tab4_col = ft.Column(spacing=12, visible=False)

    # Tab 4 專用輸入狀態
    t4_ticker_tf = ft.TextField(label="2️⃣ 輸入或選擇美股代號 (如 NBIS, AVGO, PLD, COHR)", value="NBIS", width=260)
    t4_shares_tf = ft.TextField(label="3️⃣ 目前持有股數 (新股填 0)", value="550", width=180)
    t4_cost_tf = ft.TextField(label="目前持有均價 ($)", value="226.215", width=160)
    t4_kelly_tf = ft.TextField(label="4️⃣ 半凱利目標上限 (%)", value="15.0", width=160)
    t4_budget_tf = ft.TextField(label="預計最大動用加碼資金 ($)", value="9616.50", width=190)
    t4_result_col = ft.Column(spacing=12)

    # ------------------------------------------
    # 建構「⏱️ 費波納契時間週期變盤視窗 (支援自選起始日 T+0)」
    # ------------------------------------------
    def parse_anchor_date() -> datetime.date:
        raw_str = tf_anchor_date.value.strip().replace("/", "-")
        try:
            return datetime.datetime.strptime(raw_str, "%Y-%m-%d").date()
        except Exception:
            tf_anchor_date.value = "2026-10-16"
            return datetime.date(2026, 10, 16)

    def render_time_zones():
        tz_row_container.controls.clear()
        base_dt = parse_anchor_date()
        use_b_days = sw_trading_days.value
        mode_str = "美股交易日" if use_b_days else "自然日曆天"
        tz_header_text.value = f"⏱️ 費波納契時間週期變盤視窗 (起始基準日 T+0：{base_dt.strftime('%Y/%m/%d')} | 推算模式：{mode_str})"

        fib_specs = [
            (5,  "T+5 短線確認窗",  "檢視 NBIS $175 / MRVL $247.77 壓力與 5MA 翻揚", "#ed8936"),
            (8,  "T+8 第一減碼窗",  "觀察反彈測試 0.236~0.382 壓力區動能",         "#ecc94b"),
            (13, "T+13 波段分水嶺", "日線月線 (20MA) 扣抵，執行第一階段減碼",       "#4299e1"),
            (21, "T+21 中期轉折窗", "挑戰 0.618 黃金分割強壓區與財報指引兌現",     "#48bb78"),
            (34, "T+34 季線大變盤窗","60MA 季線方向定調與完成組合再平衡",           "#9f7aea"),
        ]

        today_dt = datetime.date.today()
        computed_tz = []
        for f_num, title, desc, color in fib_specs:
            if use_b_days:
                t_dt = add_us_trading_days(base_dt, f_num)
            else:
                t_dt = base_dt + datetime.timedelta(days=f_num)
            d_left = (t_dt - today_dt).days
            computed_tz.append((f_num, title, t_dt, d_left, desc, color))

        upcoming_positives = [item[3] for item in computed_tz if item[3] >= 0]
        highlight_days = min(upcoming_positives) if upcoming_positives else None

        for f_num, title, t_dt, d_left, desc, color in computed_tz:
            dt_str = t_dt.strftime("%Y/%m/%d")
            if d_left > 0:
                day_badge = f"還有 {d_left} 天"
            elif d_left == 0:
                day_badge = "🔥 今日變盤！"
            else:
                day_badge = f"已過 {abs(d_left)} 天"

            is_hl = (highlight_days is not None and d_left == highlight_days)
            border_c = "#3182ce" if is_hl else "#2d3748"
            bg_c = "#152238" if is_hl else "#131822"

            tz_card = ft.Container(
                width=235,
                bgcolor=bg_c,
                border=safe_border(1.5 if is_hl else 1.0, border_c),
                border_radius=10,
                padding=12,
                content=ft.Column([
                    ft.Text(f"{title} ({day_badge})", color=color, size=12, weight=ft.FontWeight.BOLD),
                    ft.Text(dt_str, color="#ffffff", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(desc, color="#a0aec0", size=11),
                ], spacing=4)
            )
            tz_row_container.controls.append(tz_card)

    def set_quick_anchor(dt_str: str):
        tf_anchor_date.value = dt_str
        render_time_zones()
        page.update()

    # 嘗試掛載 Flet 原生 DatePicker (若環境支援則可彈出日曆選取)
    def open_native_datepicker(e):
        try:
            def on_date_picked(ev):
                if ev.control.value:
                    picked_dt = ev.control.value
                    if hasattr(picked_dt, "strftime"):
                        tf_anchor_date.value = picked_dt.strftime("%Y-%m-%d")
                    else:
                        tf_anchor_date.value = str(picked_dt)[:10]
                    render_time_zones()
                    page.update()

            dp = ft.DatePicker(
                first_date=datetime.datetime(2025, 1, 1),
                last_date=datetime.datetime(2027, 12, 31),
                on_change=on_date_picked,
            )
            if hasattr(page, "open"):
                page.open(dp)
            else:
                page.overlay.append(dp)
                dp.open = True
                page.update()
        except Exception:
            pass

    # ------------------------------------------
    # 核心運算：更新全系統數據與 4 大分頁
    # ------------------------------------------
    def refresh_all(force_api: bool = False):
        loading_bar.visible = True
        page.update()

        try:
            cash_pool = float(tf_cash.value)
        except Exception:
            cash_pool = 9616.50
        try:
            realized_loss_tax = float(tf_tax.value)
        except Exception:
            realized_loss_tax = -3461.52
        try:
            market_shock = float(tf_shock.value)
        except Exception:
            market_shock = 0.0
        try:
            beta_mult = float(tf_beta.value)
        except Exception:
            beta_mult = 1.50

        shock_factor = 1.0 + (market_shock / 100.0) * beta_mult
        live_rows = []

        for item in portfolio_data:
            tkr = str(item["Ticker"]).strip().upper()
            if not tkr:
                continue
            if sw_live.value:
                q = fetch_quant_metrics(tkr, get_extended=sw_ext.value, force_refresh=force_api)
                raw_price = q["Price"] if q else float(item.get("Avg_Cost", 100.0))
                atr_val = q["ATR"] if q else round(raw_price * 0.045, 2)
                fib382 = q["Fib_0382"] if q else round(raw_price * 1.12, 2)
                fib618 = q["Fib_0618"] if q else round(raw_price * 1.22, 2)
                ma20_val = q["MA20"] if q else raw_price
                ma200_val = q["MA200"] if q else raw_price
                sess_lbl = q["Session"] if q else "自訂"
                day_chg = q["Day_Chg_Pct"] if q else 0.0
            else:
                raw_price = float(item.get("Manual_Price", item.get("Avg_Cost", 100.0)))
                atr_val = round(raw_price * 0.045, 2)
                fib382 = round(raw_price * 1.12, 2)
                fib618 = round(raw_price * 1.22, 2)
                ma20_val = raw_price
                ma200_val = raw_price
                sess_lbl = "手動離線"
                day_chg = 0.0

            sim_price = round(raw_price * shock_factor, 2)
            shares = int(float(item.get("Shares", 0)))
            avg_cost = float(item.get("Avg_Cost", sim_price))
            mkt_val = round(shares * sim_price, 2)
            cost_val = round(shares * avg_cost, 2)
            pnl = round(mkt_val - cost_val, 2)
            pnl_pct = round((pnl / cost_val) * 100.0, 2) if cost_val > 0 else 0.0

            live_rows.append({
                "Ticker": tkr,
                "Name": item.get("Name", tkr),
                "Shares": shares,
                "Avg_Cost": round(avg_cost, 3),
                "Price": sim_price,
                "Session": sess_lbl,
                "Day_Chg_Pct": day_chg,
                "Market_Value": mkt_val,
                "Total_Cost": cost_val,
                "PnL": pnl,
                "PnL_Pct": pnl_pct,
                "ATR": atr_val,
                "MA20": ma20_val,
                "MA200": ma200_val,
                "Fib_0382": fib382,
                "Fib_0618": fib618,
                "Key_Fib_Target": float(item.get("Key_Fib_Target", fib382)),
                "Hard_Stop": float(item.get("Hard_Stop", round(sim_price - 2 * atr_val, 2))),
                "Target_Kelly_Pct": float(item.get("Target_Kelly_Pct", 15.0)),
            })

        total_stock_val = sum(r["Market_Value"] for r in live_rows)
        total_portfolio_equity = total_stock_val + cash_pool
        total_cost_val = sum(r["Total_Cost"] for r in live_rows)
        total_pnl = total_stock_val - total_cost_val
        total_pnl_pct = (total_pnl / total_cost_val * 100.0) if total_cost_val > 0 else 0.0

        for r in live_rows:
            if total_portfolio_equity > 0 and r["Price"] > 0:
                r["Weight_Pct"] = round((r["Market_Value"] / total_portfolio_equity) * 100.0, 2)
                r["Optimal_Shares"] = int(np.floor((total_portfolio_equity * (r["Target_Kelly_Pct"] / 100.0)) / r["Price"]))
                r["Share_Diff"] = r["Optimal_Shares"] - r["Shares"]
            else:
                r["Weight_Pct"] = 0.0
                r["Optimal_Shares"] = 0
                r["Share_Diff"] = 0

            if r["Price"] <= r["Hard_Stop"]:
                r["Action_Signal"] = "🚨 觸及底線：強制減碼"
            elif r["Price"] >= r["Key_Fib_Target"] and r["Weight_Pct"] > r["Target_Kelly_Pct"]:
                r["Action_Signal"] = "🎯 達費氏目標：階梯減碼"
            elif r["Weight_Pct"] > r["Target_Kelly_Pct"] + 2.0:
                r["Action_Signal"] = "⚠️ 超配：禁攤平/反彈減碼"
            elif r["Price"] >= r["MA20"] and r["Weight_Pct"] < r["Target_Kelly_Pct"] - 2.0:
                r["Action_Signal"] = "🚀 右側強勢：可順勢加碼"
            else:
                r["Action_Signal"] = "✅ 權重安全：紀律續抱"

        sorted_w = sorted([r["Weight_Pct"] for r in live_rows], reverse=True)
        top2_conc = sum(sorted_w[:2]) if len(sorted_w) >= 2 else sum(sorted_w)
        daily_var_95 = sum(r["Shares"] * r["ATR"] * 1.645 for r in live_rows) * 0.65
        weekly_var_95 = daily_var_95 * np.sqrt(5)
        releasable_cash = sum(max(r["Shares"] - r["Optimal_Shares"], 0) * r["Price"] for r in live_rows) + cash_pool

        # 1. 渲染頂部 5 大 KPI 卡片
        kpi_row_container.controls.clear()
        pnl_color = "#48bb78" if total_pnl >= 0 else "#f56565"
        conc_color = "#ecc94b" if top2_conc > 35 else "#48bb78"

        kpi_specs = [
            ("股票總市值 + 現金總淨值 (USD)", f"${total_portfolio_equity:,.2f}", f"股票: ${total_stock_val:,.0f} / 現金池: ${cash_pool:,.0f}", "#f7fafc"),
            ("未實現總損益 (USD / %)", f"${total_pnl:,.2f}", f"總報酬率: {total_pnl_pct:+.2f}% (壓測: {market_shock*beta_mult:+.1f}%)", pnl_color),
            ("前兩大持股集中度 (NBIS+MRVL)", f"{top2_conc:.2f}%", "半凱利建議安全上限: <= 35.0%", conc_color),
            ("單週 95% 風險價值 (5-Day VaR)", f"-${weekly_var_95:,.0f}", f"單日 95% VaR: -${daily_var_95:,.0f} (基於 ATR)", "#f56565"),
            ("可動用現金 + 減碼釋出資金池", f"${releasable_cash:,.0f}", f"現有美金: ${cash_pool:,.0f} / 可抵稅額: ${realized_loss_tax:,.0f}", "#48bb78"),
        ]
        for k_title, k_val, k_sub, k_col in kpi_specs:
            kpi_row_container.controls.append(
                ft.Container(
                    width=235,
                    bgcolor="#161b26",
                    border=safe_border(1, "#2d3748"),
                    border_radius=12,
                    padding=14,
                    content=ft.Column([
                        ft.Text(k_title, color="#a0aec0", size=12),
                        ft.Text(k_val, color=k_col, size=22, weight=ft.FontWeight.BOLD),
                        ft.Text(k_sub, color="#718096", size=11),
                    ], spacing=4)
                )
            )

        # 2. 渲染費波納契時間週期變盤視窗
        render_time_zones()

        # 3. 渲染 4 大分頁
        build_tab1(live_rows)
        build_tab2(live_rows)
        build_tab3(live_rows)
        build_tab4(live_rows, total_portfolio_equity, cash_pool)

        loading_bar.visible = False
        page.update()

    # ------------------------------------------
    # Tab 1: 📋 互動式風控追蹤主表 (可改價/增刪股票)
    # ------------------------------------------
    def build_tab1(live_rows: list):
        tab1_col.controls.clear()
        tab1_col.controls.append(
            ft.Text("💡 可直接於下方修改各股「持有股數」、「持有均價」、「半凱利上限」、「費氏目標」與「防守底線」，或於底部直接新增/刪除股票：", size=13, color="#90cdf4")
        )

        summary_headers = ["代號", "股數", "均價($)", "即時/盤前價", "總市值($)", "未實現損益", "目前權重", "凱利上限", "建議加減碼", "費氏目標", "硬性停損", "機械化指令"]
        summary_table_rows = []
        for r in live_rows:
            diff_str = f"{r['Share_Diff']:+d} 股"
            summary_table_rows.append([
                r["Ticker"],
                r["Shares"],
                f"${r['Avg_Cost']:.2f}",
                f"${r['Price']:.2f} ({r['Day_Chg_Pct']:+.1f}%)",
                f"${r['Market_Value']:,.0f}",
                f"${r['PnL']:,.0f} ({r['PnL_Pct']:+.1f}%)",
                f"{r['Weight_Pct']:.1f}%",
                f"{r['Target_Kelly_Pct']:.1f}% ({r['Optimal_Shares']}股)",
                diff_str,
                f"${r['Key_Fib_Target']:.2f}",
                f"${r['Hard_Stop']:.2f}",
                r["Action_Signal"],
            ])
        tab1_col.controls.append(make_table_box("📋 互動式風控追蹤總表", summary_headers, summary_table_rows, "#3182ce"))

        edit_cards = []
        for idx, r in enumerate(live_rows):
            tf_s = ft.TextField(label="股數", value=str(r["Shares"]), width=95)
            tf_c = ft.TextField(label="持有均價($)", value=str(r["Avg_Cost"]), width=115)
            tf_p = ft.TextField(label="手動模擬價($)", value=str(r["Price"]), width=115)
            tf_k = ft.TextField(label="凱利上限(%)", value=str(r["Target_Kelly_Pct"]), width=105)
            tf_f = ft.TextField(label="關鍵費氏目標($)", value=str(r["Key_Fib_Target"]), width=125)
            tf_h = ft.TextField(label="硬性防守底線($)", value=str(r["Hard_Stop"]), width=125)

            def make_save_fn(i, s_f, c_f, p_f, k_f, f_f, h_f):
                def _save(e):
                    try:
                        portfolio_data[i]["Shares"] = int(float(s_f.value))
                        portfolio_data[i]["Avg_Cost"] = float(c_f.value)
                        portfolio_data[i]["Manual_Price"] = float(p_f.value)
                        portfolio_data[i]["Target_Kelly_Pct"] = float(k_f.value)
                        portfolio_data[i]["Key_Fib_Target"] = float(f_f.value)
                        portfolio_data[i]["Hard_Stop"] = float(h_f.value)
                    except Exception:
                        pass
                    refresh_all(force_api=False)
                return _save

            def make_del_fn(i):
                def _del(e):
                    if 0 <= i < len(portfolio_data):
                        portfolio_data.pop(i)
                        refresh_all(force_api=False)
                return _del

            pnl_c = "#48bb78" if r["PnL"] >= 0 else "#f56565"
            edit_cards.append(
                ft.Container(
                    bgcolor="#161b26",
                    border=safe_border(1, "#2d3748"),
                    border_radius=10,
                    padding=12,
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"🔹 {r['Ticker']} ({r['Name']}) | 現價 ${r['Price']:.2f} [{r['Session']}] | {r['Action_Signal']}", size=14, weight=ft.FontWeight.BOLD, color="#ffffff", expand=True),
                            ft.Text(f"損益: ${r['PnL']:,.2f} ({r['PnL_Pct']:+.2f}%) | 權重: {r['Weight_Pct']:.2f}% (建議 {r['Share_Diff']:+d} 股)", size=13, weight=ft.FontWeight.BOLD, color=pnl_c),
                        ], wrap=True),
                        ft.Row([
                            tf_s, tf_c, tf_p, tf_k, tf_f, tf_h,
                            make_btn("💾 儲存修改", make_save_fn(idx, tf_s, tf_c, tf_p, tf_k, tf_f, tf_h), "#2563eb"),
                            make_btn("🗑️ 刪除", make_del_fn(idx), "#9b2c2c"),
                        ], wrap=True, spacing=8)
                    ], spacing=8)
                )
            )

        tab1_col.controls.append(ft.Text("✏️ 逐筆調整持股參數與模擬價格：", size=14, weight=ft.FontWeight.BOLD, color="#e2e8f0"))
        tab1_col.controls.extend(edit_cards)

        new_tkr_tf = ft.TextField(label="新美股代號 (如 PLD, COHR)", value="", width=170)
        new_sh_tf = ft.TextField(label="持有股數", value="50", width=110)
        new_cost_tf = ft.TextField(label="持有均價 ($)", value="100.0", width=120)
        new_kelly_tf = ft.TextField(label="半凱利上限 (%)", value="15.0", width=120)

        def add_new_stock(e):
            nt = new_tkr_tf.value.strip().upper()
            if not nt:
                return
            q_new = fetch_quant_metrics(nt, get_extended=sw_ext.value)
            def_p = q_new["Price"] if q_new else float(new_cost_tf.value or 100.0)
            def_atr = q_new["ATR"] if q_new else round(def_p * 0.04, 2)
            def_fib = q_new["Fib_0618"] if q_new else round(def_p * 1.15, 2)
            portfolio_data.append({
                "Ticker": nt,
                "Name": nt,
                "Shares": int(float(new_sh_tf.value or 0)),
                "Avg_Cost": float(new_cost_tf.value or def_p),
                "Target_Kelly_Pct": float(new_kelly_tf.value or 15.0),
                "Hard_Stop": round(def_p - 2.0 * def_atr, 2),
                "Key_Fib_Target": def_fib,
            })
            refresh_all(force_api=False)

        tab1_col.controls.append(
            ft.Container(
                bgcolor="#152238",
                border=safe_border(1.5, "#3182ce"),
                border_radius=10,
                padding=14,
                content=ft.Column([
                    ft.Text("➕ 直接新增美股代號至風控追蹤主表", size=14, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                    ft.Row([new_tkr_tf, new_sh_tf, new_cost_tf, new_kelly_tf, make_btn("➕ 加入主表追蹤", add_new_stock, "#38a169")], wrap=True, spacing=10)
                ], spacing=8)
            )
        )

    # ------------------------------------------
    # Tab 2: 📈 視覺化權重與費氏價位階梯圖
    # ------------------------------------------
    def build_tab2(live_rows: list):
        tab2_col.controls.clear()

        weight_bars = []
        price_ladders = []

        for r in live_rows:
            w_pct = r["Weight_Pct"]
            k_pct = r["Target_Kelly_Pct"]
            w_color = "#f56565" if w_pct > k_pct else "#48bb78"

            weight_bars.append(
                ft.Container(
                    bgcolor="#1e2536",
                    border_radius=8,
                    padding=10,
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"{r['Ticker']} 實際權重: {w_pct:.2f}%", size=13, weight=ft.FontWeight.BOLD, color=w_color, expand=True),
                            ft.Text(f"半凱利安全上限: {k_pct:.1f}% (建議 {r['Optimal_Shares']} 股 / 現有 {r['Shares']} 股)", size=12, color="#a0aec0"),
                        ]),
                        ft.ProgressBar(value=min(w_pct / 40.0, 1.0), color=w_color, bgcolor="#0e1117"),
                        ft.ProgressBar(value=min(k_pct / 40.0, 1.0), color="#48bb78", bgcolor="#0e1117"),
                    ], spacing=5)
                )
            )

            stop_p = r["Hard_Stop"]
            cur_p = r["Price"]
            fib_p = r["Key_Fib_Target"]
            dist_to_fib = ((fib_p - cur_p) / cur_p * 100.0) if cur_p > 0 else 0.0
            dist_to_stop = ((cur_p - stop_p) / cur_p * 100.0) if cur_p > 0 else 0.0

            price_ladders.append(
                ft.Container(
                    bgcolor="#1e2536",
                    border_radius=8,
                    padding=10,
                    content=ft.Column([
                        ft.Text(f"📊 {r['Ticker']} 關鍵防守與費波納契目標位階對照", size=13, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ft.Row([
                            ft.Container(
                                bgcolor="#742a2a", border_radius=6, padding=8, expand=True,
                                content=ft.Column([
                                    ft.Text("🛡️ 硬性防守底線", size=11, color="#feb2b2"),
                                    ft.Text(f"${stop_p:.2f}", size=15, weight=ft.FontWeight.BOLD, color="#fc8181"),
                                    ft.Text(f"緩衝: {dist_to_stop:+.1f}%", size=11, color="#fbd38d"),
                                ], spacing=2)
                            ),
                            ft.Container(
                                bgcolor="#1a365d", border_radius=6, padding=8, expand=True,
                                content=ft.Column([
                                    ft.Text("⚡ 目前即時現價", size=11, color="#bee3f8"),
                                    ft.Text(f"${cur_p:.2f}", size=15, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                                    ft.Text(f"20MA: ${r['MA20']:.2f}", size=11, color="#90cdf4"),
                                ], spacing=2)
                            ),
                            ft.Container(
                                bgcolor="#22543d", border_radius=6, padding=8, expand=True,
                                content=ft.Column([
                                    ft.Text("🎯 費氏減碼/停利目標", size=11, color="#c6f6d5"),
                                    ft.Text(f"${fib_p:.2f}", size=15, weight=ft.FontWeight.BOLD, color="#68d391"),
                                    ft.Text(f"潛在空間: {dist_to_fib:+.1f}%", size=11, color="#9ae6b4"),
                                ], spacing=2)
                            ),
                        ], spacing=8)
                    ], spacing=6)
                )
            )

        tab2_col.controls.append(
            ft.Row([
                ft.Container(
                    bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=12, padding=14, expand=True,
                    content=ft.Column([
                        ft.Text("📈 目前持股權重 vs. 半凱利安全上限 (%) [紅線=超配 / 綠線=安全上限]", size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                        ft.Column(weight_bars, spacing=8),
                    ], spacing=10)
                ),
                ft.Container(
                    bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=12, padding=14, expand=True,
                    content=ft.Column([
                        ft.Text("🪜 各股現價與關鍵防守 / 費氏目標位階階梯圖", size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                        ft.Column(price_ladders, spacing=8),
                    ], spacing=10)
                ),
            ], wrap=True, spacing=12)
        )

    # ------------------------------------------
    # Tab 3: 🧮 NBIS & MRVL 三階梯減碼模擬器
    # ------------------------------------------
    def build_tab3(live_rows: list):
        tab3_col.controls.clear()
        tab3_col.controls.append(ft.Text("🧮 核心超配雙雄 (NBIS & MRVL) 專屬三階梯減碼回收現金試算", size=16, weight=ft.FontWeight.BOLD, color="#f7fafc"))

        nbis_r = next((x for x in live_rows if x["Ticker"] == "NBIS"), None)
        mrvl_r = next((x for x in live_rows if x["Ticker"] == "MRVL"), None)

        nbis_p = nbis_r["Price"] if nbis_r else 171.45
        nbis_sh = nbis_r["Shares"] if nbis_r else 550
        mrvl_p = mrvl_r["Price"] if mrvl_r else 235.00
        mrvl_sh = mrvl_r["Shares"] if mrvl_r else 350

        nbis_headers = ["減碼階段", "掛單價 ($)", "減碼股數", "預計收回現金 ($)"]
        nbis_rows = [
            ["第一階 (0.382 反彈位)", "$195.80", "87 股", f"${87 * 195.80:,.2f}"],
            ["第二階 (前波密集壓力)", "$200.00", "80 股", f"${80 * 200.00:,.2f}"],
            ["第三階 (0.618 黃金位)", "$215.50", "50 股", f"${50 * 215.50:,.2f}"],
            ["⚠️ 破位硬性防禦線", "$159.00", "100 股", f"${100 * 159.00:,.2f}"],
        ]

        mrvl_headers = ["減碼階段", "掛單價 ($)", "減碼股數", "預計收回現金 ($)"]
        mrvl_rows = [
            ["第一階 (0.618 關鍵位 GTC)", "$247.77", "57 股", f"${57 * 247.77:,.2f}"],
            ["第二階 (前高成本區)", "$256.00", "60 股", f"${60 * 256.00:,.2f}"],
            ["第三階 (1.272 擴展位)", "$272.50", "53 股", f"${53 * 272.50:,.2f}"],
            ["⚠️ 破位硬性防禦線", "$218.00", "60 股", f"${60 * 218.00:,.2f}"],
        ]

        tab3_col.controls.append(
            ft.Row([
                ft.Container(
                    expand=True,
                    content=make_table_box(f"🔹 NBIS (現有 {nbis_sh} 股 | 現價 ${nbis_p:.2f} | 目標降至 333 股)", nbis_headers, nbis_rows, "#3182ce")
                ),
                ft.Container(
                    expand=True,
                    content=make_table_box(f"🔸 MRVL (現有 {mrvl_sh} 股 | 現價 ${mrvl_p:.2f} | 目標降至 180 股)", mrvl_headers, mrvl_rows, "#ecc94b")
                ),
            ], wrap=True, spacing=12)
        )

    # ------------------------------------------
    # Tab 4: 🚀 萬用個股加減碼與新股建倉引擎
    # ------------------------------------------
    def build_tab4(live_rows: list, total_portfolio_equity: float, cash_pool: float):
        tab4_col.controls.clear()

        chip_buttons = []
        for r in live_rows:
            def make_chip_fn(row_data):
                def _sel(e):
                    t4_ticker_tf.value = row_data["Ticker"]
                    t4_shares_tf.value = str(row_data["Shares"])
                    t4_cost_tf.value = str(row_data["Avg_Cost"])
                    t4_kelly_tf.value = str(row_data["Target_Kelly_Pct"])
                    run_tab4_engine()
                return _sel
            chip_buttons.append(make_btn(f"既有: {r['Ticker']}", make_chip_fn(r), "#1e293b", "#90cdf4", pad_v=6, pad_h=10, border_col="#3182ce"))

        for new_sym in ["PLD", "COHR", "RMBS", "AAOI", "NVDA"]:
            def make_new_chip_fn(sym):
                def _sel_new(e):
                    t4_ticker_tf.value = sym
                    t4_shares_tf.value = "0"
                    t4_cost_tf.value = "0.0"
                    t4_kelly_tf.value = "15.0"
                    run_tab4_engine()
                return _sel_new
            chip_buttons.append(make_btn(f"➕ 新股: {new_sym}", make_new_chip_fn(new_sym), "#152238", "#68d391", pad_v=6, pad_h=10, border_col="#2f855a"))

        def run_tab4_engine(e=None):
            t4_result_col.controls.clear()
            target_ticker = t4_ticker_tf.value.strip().upper()
            if not target_ticker:
                return

            q_data = fetch_quant_metrics(target_ticker, get_extended=sw_ext.value)
            try:
                sim_cur_shares = int(float(t4_shares_tf.value or 0))
            except Exception:
                sim_cur_shares = 0
            try:
                sim_cur_cost = float(t4_cost_tf.value or 0.0)
            except Exception:
                sim_cur_cost = 0.0
            try:
                sim_kelly_pct = float(t4_kelly_tf.value or 15.0)
            except Exception:
                sim_kelly_pct = 15.0
            try:
                budget_limit = float(t4_budget_tf.value or cash_pool)
            except Exception:
                budget_limit = cash_pool

            live_p = q_data["Price"] if q_data else (sim_cur_cost if sim_cur_cost > 0 else 100.0)
            if sim_cur_cost <= 0:
                sim_cur_cost = live_p
            live_atr = q_data["ATR"] if q_data else round(live_p * 0.04, 2)
            live_ma20 = q_data["MA20"] if q_data else live_p
            live_ma200 = q_data["MA200"] if q_data else live_p
            live_rsi = q_data["RSI"] if q_data else 50.0
            fib_382_lvl = q_data["Fib_0382"] if q_data else round(live_p * 0.96, 2)
            fib_618_lvl = q_data["Fib_0618"] if q_data else round(live_p * 1.08, 2)
            fib_1272_lvl = q_data["Fib_1272"] if q_data else round(live_p * 1.20, 2)
            swing_low_lvl = q_data["Swing_Low"] if q_data else round(live_p * 0.88, 2)

            cur_stock_val = sim_cur_shares * live_p
            cur_weight_pct = (cur_stock_val / total_portfolio_equity * 100.0) if total_portfolio_equity > 0 else 0.0
            max_kelly_val = total_portfolio_equity * (sim_kelly_pct / 100.0)
            max_kelly_shares = int(np.floor(max_kelly_val / live_p)) if live_p > 0 else 0
            remaining_kelly_val = max(0.0, max_kelly_val - cur_stock_val)
            remaining_kelly_shares = max(0, max_kelly_shares - sim_cur_shares)
            excess_trim_shares = max(0, sim_cur_shares - max_kelly_shares)
            effective_add_budget = min(remaining_kelly_val, budget_limit) if remaining_kelly_val > 0 else budget_limit

            sess_note = q_data["Session"] if q_data else "模擬"
            chg_note = f"{q_data['Day_Chg_Pct']:+.2f}% ({sess_note})" if q_data else "手動"
            metrics_row = ft.Row([
                ft.Container(bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=8, padding=10, width=185,
                             content=ft.Column([ft.Text("即時報價", size=11, color="#a0aec0"), ft.Text(f"${live_p:.2f}", size=18, weight=ft.FontWeight.BOLD), ft.Text(chg_note, size=11, color="#63b3ed")], spacing=2)),
                ft.Container(bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=8, padding=10, width=185,
                             content=ft.Column([ft.Text("目前權重 / 凱利上限", size=11, color="#a0aec0"), ft.Text(f"{cur_weight_pct:.1f}% / {sim_kelly_pct:.1f}%", size=18, weight=ft.FontWeight.BOLD), ft.Text(f"差距: {cur_weight_pct - sim_kelly_pct:+.1f}%", size=11, color="#ecc94b")], spacing=2)),
                ft.Container(bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=8, padding=10, width=185,
                             content=ft.Column([ft.Text("凱利建議上限股數", size=11, color="#a0aec0"), ft.Text(f"{max_kelly_shares} 股", size=18, weight=ft.FontWeight.BOLD), ft.Text(f"現有 {sim_cur_shares} 股", size=11, color="#a0aec0")], spacing=2)),
                ft.Container(bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=8, padding=10, width=185,
                             content=ft.Column([ft.Text("20MA / 200MA 均線", size=11, color="#a0aec0"), ft.Text(f"${live_ma20:.2f}", size=18, weight=ft.FontWeight.BOLD), ft.Text(f"年線 ${live_ma200:.2f}", size=11, color="#a0aec0")], spacing=2)),
                ft.Container(bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=8, padding=10, width=185,
                             content=ft.Column([ft.Text("14日 ATR 波動值", size=11, color="#a0aec0"), ft.Text(f"${live_atr:.2f}", size=18, weight=ft.FontWeight.BOLD), ft.Text(f"2ATR停損寬度 ${live_atr*2:.2f}", size=11, color="#fc8181")], spacing=2)),
                ft.Container(bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=8, padding=10, width=185,
                             content=ft.Column([ft.Text("14日 RSI 強弱指標", size=11, color="#a0aec0"), ft.Text(f"{live_rsi:.1f}", size=18, weight=ft.FontWeight.BOLD), ft.Text("超買 >70 / 超賣 <30", size=11, color="#a0aec0")], spacing=2)),
            ], wrap=True, spacing=8)
            t4_result_col.controls.append(metrics_row)

            is_weight_ok = cur_weight_pct < sim_kelly_pct
            is_trend_ok = live_p >= live_ma20 or live_p >= live_ma200

            if not is_weight_ok:
                gate_banner = ft.Container(
                    bgcolor="#2d1215", border=safe_border(1.5, "#ef4444"), border_radius=10, padding=12,
                    content=ft.Column([
                        ft.Text("🚫 【風控守門員攔截：權重超標，禁止向下攤平加碼】", size=14, weight=ft.FontWeight.BOLD, color="#fc8181"),
                        ft.Text(f"• 原因：{target_ticker} 目前佔總資產 {cur_weight_pct:.2f}%（持有 {sim_cur_shares} 股），已超過半凱利安全上限 {sim_kelly_pct:.1f}%（上限 {max_kelly_shares} 股）。", size=12, color="#feb2b2"),
                        ft.Text(f"• 機械化指令：在股數透過右側反彈減碼降至 {max_kelly_shares} 股以下之前，嚴格凍結加碼！請直接執行下方右側「📉 方案 B：三階梯分批減碼方案」（需減碼 {excess_trim_shares} 股）。", size=12, color="#ffffff", weight=ft.FontWeight.BOLD),
                    ], spacing=4)
                )
            else:
                trend_txt = "✅ 股價站上均線（符合右側順勢加碼條件）" if is_trend_ok else "⚠️ 股價仍處均線下方（建議等待突破 20MA 或於費氏支撐試單，勿重倉接刀）"
                gate_banner = ft.Container(
                    bgcolor="#0f291e", border=safe_border(1.5, "#22c55e"), border_radius=10, padding=12,
                    content=ft.Column([
                        ft.Text("✅ 【風控守門員放行：具備加碼 / 新股建倉空間】", size=14, weight=ft.FontWeight.BOLD, color="#68d391"),
                        ft.Text(f"• 可用額度：距離半凱利 {sim_kelly_pct:.1f}% 上限尚可買入 {remaining_kelly_shares} 股（約 ${remaining_kelly_val:,.2f} 美元）；本次規劃動用預算 ${effective_add_budget:,.2f} 美元。", size=12, color="#c6f6d5"),
                        ft.Text(f"• 趨勢位階：{trend_txt}", size=12, color="#ffffff", weight=ft.FontWeight.BOLD),
                    ], spacing=4)
                )
            t4_result_col.controls.append(gate_banner)

            buy_p1 = round(live_p, 2)
            buy_p2 = round(max(live_p + 0.8 * live_atr, live_ma20), 2)
            buy_p3 = round(live_p + 1.6 * live_atr, 2)

            b1_shares = int(np.floor((effective_add_budget * 0.40) / buy_p1)) if buy_p1 > 0 else 0
            b2_shares = int(np.floor((effective_add_budget * 0.35) / buy_p2)) if buy_p2 > 0 else 0
            b3_shares = int(np.floor((effective_add_budget * 0.25) / buy_p3)) if buy_p3 > 0 else 0

            cum_s1 = sim_cur_shares + b1_shares
            cum_c1 = ((sim_cur_shares * sim_cur_cost) + (b1_shares * buy_p1)) / cum_s1 if cum_s1 > 0 else buy_p1
            cum_s2 = cum_s1 + b2_shares
            cum_c2 = ((cum_s1 * cum_c1) + (b2_shares * buy_p2)) / cum_s2 if cum_s2 > 0 else buy_p2
            cum_s3 = cum_s2 + b3_shares
            cum_c3 = ((cum_s2 * cum_c2) + (b3_shares * buy_p3)) / cum_s3 if cum_s3 > 0 else buy_p3

            buy_headers = ["加碼批次", "觸發條件", "建議買價", "買入股數", "動用資金", "買後總股數", "買後新均價", "硬性停損價"]
            buy_rows = [
                ["第 1 批 (底倉 40%)", "現價 / 突破轉折", f"${buy_p1:.2f}", f"{b1_shares} 股", f"${b1_shares*buy_p1:,.0f}", f"{cum_s1} 股", f"${cum_c1:.2f}", f"${buy_p1 - 2.0*live_atr:.2f}"],
                ["第 2 批 (確認 35%)", f"漲破 ${buy_p2:.2f}", f"${buy_p2:.2f}", f"{b2_shares} 股", f"${b2_shares*buy_p2:,.0f}", f"{cum_s2} 股", f"${cum_c2:.2f}", f"${max(cum_c1, buy_p2 - 1.8*live_atr):.2f}"],
                ["第 3 批 (滿倉 25%)", f"突破 ${buy_p3:.2f}", f"${buy_p3:.2f}", f"{b3_shares} 股", f"${b3_shares*buy_p3:,.0f}", f"{cum_s3} 股", f"${cum_c3:.2f}", f"${max(cum_c2, buy_p3 - 1.5*live_atr):.2f}"],
            ]

            base_shares_to_trim = excess_trim_shares if excess_trim_shares > 0 else max(int(sim_cur_shares * 0.5), b1_shares + b2_shares + b3_shares)
            s_t1 = int(np.round(base_shares_to_trim * 0.30))
            s_t2 = int(np.round(base_shares_to_trim * 0.40))
            s_t3 = max(0, base_shares_to_trim - s_t1 - s_t2)
            s_stop = max(int(sim_cur_shares * 0.20), 10) if sim_cur_shares > 0 else b1_shares

            p_t1 = max(fib_382_lvl, round(live_p + 1.2 * live_atr, 2))
            p_t2 = max(fib_618_lvl, round(live_p + 2.5 * live_atr, 2))
            p_t3 = max(fib_1272_lvl, round(live_p + 4.0 * live_atr, 2))
            p_stop = round(max(swing_low_lvl, live_p - 2.0 * live_atr), 2)
            ref_cost = sim_cur_cost if sim_cur_shares > 0 else buy_p1

            sell_headers = ["減碼/停利階段", "目標掛單價", "賣出股數", "收回現金 ($)", "單筆實現損益", "距現價漲幅"]
            sell_rows = [
                ["第一階 (0.382 調節 30%)", f"${p_t1:.2f}", f"{s_t1} 股", f"${s_t1*p_t1:,.0f}", f"${s_t1*(p_t1 - ref_cost):+,.0f}", f"{((p_t1 - live_p)/live_p)*100:+.2f}%"],
                ["第二階 (0.618 強壓 40%)", f"${p_t2:.2f}", f"{s_t2} 股", f"${s_t2*p_t2:,.0f}", f"${s_t2*(p_t2 - ref_cost):+,.0f}", f"{((p_t2 - live_p)/live_p)*100:+.2f}%"],
                ["第三階 (1.272 延伸 30%)", f"${p_t3:.2f}", f"{s_t3} 股", f"${s_t3*p_t3:,.0f}", f"${s_t3*(p_t3 - ref_cost):+,.0f}", f"{((p_t3 - live_p)/live_p)*100:+.2f}%"],
                ["⚠️ 左側破位 (-2 ATR)", f"${p_stop:.2f}", f"{s_stop} 股", f"${s_stop*p_stop:,.0f}", f"${s_stop*(p_stop - ref_cost):+,.0f}", f"{((p_stop - live_p)/live_p)*100:+.2f}%"],
            ]

            t4_result_col.controls.append(
                ft.Row([
                    ft.Container(expand=True, content=make_table_box(f"📈 【方案 A】{target_ticker} 金字塔三階梯加碼 / 建倉試算表 (40% / 35% / 25%)", buy_headers, buy_rows, "#3182ce")),
                    ft.Container(expand=True, content=make_table_box(f"📉 【方案 B】{target_ticker} 費波納契三階梯減碼 / 停利試算表 (30% / 40% / 30%)", sell_headers, sell_rows, "#48bb78")),
                ], wrap=True, spacing=12)
            )

            existing_syms = [x["Ticker"] for x in portfolio_data]
            if target_ticker not in existing_syms and b1_shares > 0:
                def add_t4_to_main(e):
                    portfolio_data.append({
                        "Ticker": target_ticker,
                        "Name": target_ticker,
                        "Shares": b1_shares,
                        "Avg_Cost": buy_p1,
                        "Target_Kelly_Pct": sim_kelly_pct,
                        "Hard_Stop": round(buy_p1 - 2.0 * live_atr, 2),
                        "Key_Fib_Target": fib_618_lvl,
                    })
                    refresh_all(force_api=False)

                t4_result_col.controls.append(
                    make_btn(f"➕ 將新標的 {target_ticker} (第 1 批 {b1_shares} 股 @ ${buy_p1:.2f}) 加入主表模擬", add_t4_to_main, "#38a169")
                )

            page.update()

        tab4_col.controls.append(
            ft.Container(
                bgcolor="#161b26", border=safe_border(1, "#2d3748"), border_radius=12, padding=14,
                content=ft.Column([
                    ft.Text("🚀 萬用個股動態加減碼與新股建倉引擎 (點選下方快速標籤或手動輸入代號)", size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                    ft.Row(chip_buttons, wrap=True, spacing=6),
                    ft.Row([t4_ticker_tf, t4_shares_tf, t4_cost_tf, t4_kelly_tf, t4_budget_tf, make_btn("🔍 立即試算加減碼", run_tab4_engine, "#2563eb")], wrap=True, spacing=10),
                ], spacing=10)
            )
        )
        tab4_col.controls.append(t4_result_col)
        run_tab4_engine()

    # ------------------------------------------
    # 四大導航分頁按鈕列
    # ------------------------------------------
    tab_titles = [
        "📋 互動式風控追蹤主表 (可改價/增刪股票)",
        "📈 視覺化權重與費氏價位階梯圖",
        "🧮 NBIS & MRVL 三階梯減碼模擬器",
        "🚀 萬用個股加減碼與新股建倉引擎 (既有持股 & 任意新股)",
    ]

    def render_tab_nav():
        tab_nav_row.controls.clear()
        for idx, t_label in enumerate(tab_titles):
            is_act = (active_tab_idx[0] == idx)
            bg_c = "#1e3a8a" if is_act else "#161b26"
            txt_c = "#60a5fa" if is_act else "#a0aec0"
            b_col = "#3b82f6" if is_act else "#2d3748"

            def make_switch_fn(i):
                def _sw(e):
                    active_tab_idx[0] = i
                    tab1_col.visible = (i == 0)
                    tab2_col.visible = (i == 1)
                    tab3_col.visible = (i == 2)
                    tab4_col.visible = (i == 3)
                    render_tab_nav()
                    page.update()
                return _sw

            tab_nav_row.controls.append(
                make_btn(t_label, make_switch_fn(idx), bg_c, txt_c, pad_v=10, pad_h=14, border_col=b_col)
            )

    def reset_defaults(e):
        portfolio_data.clear()
        for item in DEFAULT_PORTFOLIO:
            portfolio_data.append(dict(item))
        tf_anchor_date.value = "2026-10-16"
        tf_cash.value = "9616.50"
        tf_tax.value = "-3461.52"
        tf_shock.value = "0"
        tf_beta.value = "1.50"
        refresh_all(force_api=True)

    render_tab_nav()

    # ------------------------------------------
    # 組合旗艦主畫面
    # ------------------------------------------
    page.add(
        # 標題與全域參數控制面板
        ft.Container(
            bgcolor="#161b26",
            border=safe_border(1, "#2d3748"),
            border_radius=12,
            padding=16,
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("📊 美股量化風控 × 費波納契 × 半凱利操盤系統 (Flet 原生旗艦版)", size=22, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ft.Text("結合 Python yfinance 自動化行情抓取、費波納契時空共振 (自選起始日 T+0 推算)、ATR 動態停損與萬用加減碼建倉模型", size=12, color="#a0aec0"),
                    ], expand=True),
                    make_btn("⚡ 立即強制更新即時報價", lambda e: refresh_all(force_api=True), "#2563eb"),
                    make_btn("🔄 重置預設持股", reset_defaults, "#4a5568"),
                ], wrap=True, spacing=10),
                loading_bar,
                ft.Divider(height=10, color="#2d3748"),
                ft.Row([
                    sw_live, sw_ext, tf_cash, tf_tax, tf_shock, tf_beta,
                    make_btn("✅ 套用參數並重算", lambda e: refresh_all(force_api=False), "#38a169"),
                ], wrap=True, spacing=12),
                ft.Divider(height=8, color="#2d3748"),
                # 費波納契時間週期起始日自由設定列
                ft.Row([
                    tf_anchor_date,
                    make_btn("📅 彈出日曆選取", open_native_datepicker, "#3182ce", pad_v=8, pad_h=12),
                    make_btn("📌 設為 10/16 波段基準", lambda e: set_quick_anchor("2026-10-16"), "#1e293b", "#90cdf4", pad_v=8, pad_h=10, border_col="#3182ce"),
                    make_btn("📌 設為 10/20 破底翻日", lambda e: set_quick_anchor("2026-10-20"), "#1e293b", "#68d391", pad_v=8, pad_h=10, border_col="#2f855a"),
                    make_btn("📌 設為今日 (T+0)", lambda e: set_quick_anchor(datetime.date.today().strftime("%Y-%m-%d")), "#1e293b", "#fbd38d", pad_v=8, pad_h=10, border_col="#dd6b20"),
                    sw_trading_days,
                    make_btn("⏱️ 重新推算時間窗", lambda e: (render_time_zones(), page.update()), "#805ad5", pad_v=8, pad_h=12),
                ], wrap=True, spacing=10),
            ], spacing=8)
        ),

        # 5 大核心 KPI 儀表板
        kpi_row_container,

        # ⏱️ 費波納契時間週期變盤視窗 (Fibonacci Time Zones)
        tz_header_text,
        tz_row_container,

        ft.Divider(height=10, color="#2d3748"),

        # 四大核心操作分頁導航列
        tab_nav_row,

        # 四大分頁內容區
        tab1_col,
        tab2_col,
        tab3_col,
        tab4_col,
    )

    refresh_all(force_api=False)

# ==========================================
# 5. 啟動 Web 瀏覽器投影模式 (Port 8550)
# ==========================================
if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8550, host="0.0.0.0")