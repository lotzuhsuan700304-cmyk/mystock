import asyncio
import datetime
import json
import math
import urllib.request
import flet as ft


class _YFTicker:
    def __init__(self, symbol, include_prepost: bool = True):
        self.symbol = symbol.strip().upper()
        self.closes = []
        self.highs = []
        self.lows = []
        self.ext_price = None
        self.session_label = "日線收盤"
        try:
            prepost_str = "true" if include_prepost else "false"
            url = (
                "https://query1.finance.yahoo.com/v8/finance/chart/"
                f"{self.symbol}?interval=1d&range=1y&includePrePost={prepost_str}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                r = json.loads(resp.read().decode("utf-8"))
            res = r.get("chart", {}).get("result", [])
            if res:
                meta = res[0].get("meta", {})
                q = res[0].get("indicators", {}).get("quote", [{}])[0]
                closes = q.get("close") or []
                highs = q.get("high") or []
                lows = q.get("low") or []
                for i, c in enumerate(closes):
                    if c is None:
                        continue
                    h = highs[i] if i < len(highs) and highs[i] is not None else c
                    l = lows[i] if i < len(lows) and lows[i] is not None else c
                    self.closes.append(float(c))
                    self.highs.append(float(h))
                    self.lows.append(float(l))

                if include_prepost:
                    post_p = meta.get("postMarketPrice")
                    pre_p = meta.get("preMarketPrice")
                    reg_p = meta.get("regularMarketPrice")
                    if post_p:
                        self.ext_price = float(post_p)
                        self.session_label = "盤後報價"
                    elif pre_p:
                        self.ext_price = float(pre_p)
                        self.session_label = "盤前報價"
                    elif reg_p:
                        self.ext_price = float(reg_p)
                        self.session_label = "盤中/收盤"
        except Exception:
            pass


class _YFModule:
    Ticker = _YFTicker


yf = _YFModule()


DEFAULT_PORTFOLIO = [
    {"Ticker": "NBIS", "Name": "Nebius Group", "Shares": 550, "Avg_Cost": 226.215, "Target_Kelly_Pct": 15.0, "Hard_Stop": 159.00, "Key_Fib_Target": 195.80},
    {"Ticker": "MRVL", "Name": "Marvell Tech", "Shares": 350, "Avg_Cost": 255.965, "Target_Kelly_Pct": 15.0, "Hard_Stop": 218.00, "Key_Fib_Target": 247.77},
    {"Ticker": "MU", "Name": "Micron Tech", "Shares": 50, "Avg_Cost": 516.017, "Target_Kelly_Pct": 15.0, "Hard_Stop": 880.00, "Key_Fib_Target": 1003.10},
    {"Ticker": "AVGO", "Name": "Broadcom Inc", "Shares": 100, "Avg_Cost": 325.207, "Target_Kelly_Pct": 15.0, "Hard_Stop": 325.20, "Key_Fib_Target": 358.50},
    {"Ticker": "DRAM", "Name": "Roundhill ETF", "Shares": 350, "Avg_Cost": 68.393, "Target_Kelly_Pct": 5.0, "Hard_Stop": 44.50, "Key_Fib_Target": 52.55},
    {"Ticker": "PLTR", "Name": "Palantir Tech", "Shares": 50, "Avg_Cost": 178.932, "Target_Kelly_Pct": 10.0, "Hard_Stop": 185.55, "Key_Fib_Target": 200.97},
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
    cur_dt = start_date
    added = 0
    while added < trading_days:
        cur_dt += datetime.timedelta(days=1)
        if cur_dt.weekday() < 5 and cur_dt not in US_HOLIDAYS_2026:
            added += 1
    return cur_dt


# --- 零崩潰按鈕與表格元件 (不使用內層 Row 與 Padding/Border 物件，徹底杜絕灰色 RenderErrorBox) ---
def make_btn(text: str, on_click_fn, bg_color: str = "#2563eb", text_color: str = "#ffffff", pad: int = 10, width: int = None):
    return ft.Container(
        content=ft.Text(
            text,
            color=text_color,
            size=13,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        ),
        bgcolor=bg_color,
        border_radius=8,
        padding=pad,
        width=width,
        on_click=on_click_fn,
    )


def make_table_box(title: str, headers: list, rows: list, header_bg: str = "#1e3a8a"):
    header_cells = [
        ft.Container(content=ft.Text(str(h), size=11, weight=ft.FontWeight.BOLD, color="#90cdf4"), expand=1)
        for h in headers
    ]
    table_rows = [
        ft.Container(bgcolor=header_bg, padding=8, border_radius=6, content=ft.Row(header_cells, spacing=4))
    ]
    for idx, r in enumerate(rows):
        row_bg = "#1a2232" if idx % 2 == 0 else "#131824"
        row_cells = [
            ft.Container(content=ft.Text(str(c), size=11, color="#e2e8f0"), expand=1) for c in r
        ]
        table_rows.append(
            ft.Container(
                bgcolor=row_bg,
                padding=8,
                border_radius=4,
                content=ft.Row(row_cells, spacing=4),
            )
        )
    return ft.Container(
        bgcolor="#161b26",
        border_radius=12,
        padding=12,
        content=ft.Column(
            [
                ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                ft.Column(table_rows, spacing=4),
            ],
            spacing=8,
        ),
    )


QUOTE_CACHE = {}


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def fetch_quant_metrics(ticker: str, get_extended: bool = True, force_refresh: bool = False):
    tkr = ticker.strip().upper()
    cache_key = f"{tkr}_{get_extended}"
    if not force_refresh and cache_key in QUOTE_CACHE:
        return QUOTE_CACHE[cache_key]
    try:
        tk = yf.Ticker(tkr, include_prepost=get_extended)
        closes, highs, lows = tk.closes, tk.highs, tk.lows
        if len(closes) < 2:
            return None
        reg_close = closes[-1]
        prev_close = closes[-2]
        current_price = tk.ext_price if (get_extended and tk.ext_price) else reg_close
        day_chg_pct = ((current_price - prev_close) / prev_close) * 100.0 if prev_close else 0.0
        recent_h = highs[-126:] or closes[-126:]
        recent_l = lows[-126:] or closes[-126:]
        swing_high = max(recent_h)
        swing_low = min(recent_l)
        diff = max(swing_high - swing_low, 0.01)
        trs = []
        for i in range(1, len(closes)):
            h = highs[i] if i < len(highs) else closes[i]
            l = lows[i] if i < len(lows) else closes[i]
            pc = closes[i - 1]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr_14 = _mean(trs[-14:]) if len(trs) >= 14 else reg_close * 0.04
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        last = deltas[-14:] if len(deltas) >= 14 else deltas
        gains = [d for d in last if d > 0]
        losses = [-d for d in last if d < 0]
        avg_gain = _mean(gains) if gains else 0.0
        avg_loss = _mean(losses) if losses else 0.0
        if avg_loss == 0:
            rsi_14 = 100.0 if avg_gain > 0 else 50.0
        else:
            rsi_14 = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

        def sma(n):
            if len(closes) < n:
                return closes[-1]
            return _mean(closes[-n:])

        ma20, ma50, ma200 = sma(20), sma(50), sma(200)
        res = {
            "Price": round(current_price, 2),
            "Reg_Close": round(reg_close, 2),
            "Day_Chg_Pct": round(day_chg_pct, 2),
            "Session": tk.session_label if get_extended else "日線收盤",
            "Swing_High": round(swing_high, 2),
            "Swing_Low": round(swing_low, 2),
            "Fib_0236": round(swing_low + diff * 0.236, 2),
            "Fib_0382": round(swing_low + diff * 0.382, 2),
            "Fib_0618": round(swing_low + diff * 0.618, 2),
            "Fib_1272": round(swing_low + diff * 1.272, 2),
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


async def main(page: ft.Page):
    page.title = "美股量化風控 × 費波納契 × 半凱利"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e1117"
    page.padding = 12
    page.scroll = ft.ScrollMode.AUTO

    try:
        await _build(page)
    except Exception as e:
        import traceback
        page.add(ft.Text(f"啟動錯誤: {e}", color="#fc8181", size=15, selectable=True))
        page.add(ft.Text(traceback.format_exc(), size=11, color="#e2e8f0", selectable=True))
        page.update()


async def _build(page: ft.Page):
    portfolio_data = [dict(item) for item in DEFAULT_PORTFOLIO]
    active_page_idx = [0]      # 頂部 5 大主分頁索引
    selected_stock_idx = [0]   # 分頁 2 個股編輯子分頁索引

    sw_live = ft.Switch(label="自動抓即時報價", value=True)
    sw_ext = ft.Switch(label="含盤前/盤後價", value=True)
    sw_trading_days = ft.Switch(label="按美股交易日推算", value=True)
    tf_anchor_date = ft.TextField(label="費氏起始日 T+0", value="2026-10-16", width=155)
    tf_cash = ft.TextField(label="美元現金池 ($)", value="9616.50", width=145)
    tf_tax = ft.TextField(label="累計抵稅虧損 ($)", value="-3461.52", width=145)
    tf_shock = ft.TextField(label="大盤衝擊 (%)", value="0", width=130)
    tf_beta = ft.TextField(label="Beta敏感倍數", value="1.50", width=130)
    status_text = ft.Text("就緒", size=11, color="#68d391")
    loading_bar = ft.ProgressBar(visible=False, color="#ecc94b", bgcolor="#1e2536")

    # 頂部主分頁導覽列與 5 個獨立頁面容器
    main_nav_row = ft.Row(wrap=True, spacing=6)
    page0_overview_col = ft.Column(spacing=10, visible=True)   # 分頁1: 總覽與設定
    page1_holdings_col = ft.Column(spacing=10, visible=False)  # 分頁2: 風控持倉 (含個股子分頁)
    page2_fib_col = ft.Column(spacing=10, visible=False)       # 分頁3: 費氏週期與階梯
    page3_calc_col = ft.Column(spacing=10, visible=False)      # 分頁4: 加減碼與保本試算
    page4_trim_col = ft.Column(spacing=10, visible=False)      # 分頁5: NBIS/MRVL 減碼專區

    kpi_grid_container = ft.Row(wrap=True, spacing=8)
    tz_header_text = ft.Text("費波納契時間週期變盤視窗", size=15, weight=ft.FontWeight.BOLD, color="#f7fafc")
    tz_row_container = ft.Row(wrap=True, spacing=8)
    ladder_col_container = ft.Column(spacing=8)

    t4_ticker_tf = ft.TextField(label="美股代號", value="NBIS", width=130)
    t4_shares_tf = ft.TextField(label="目前股數", value="550", width=130)
    t4_cost_tf = ft.TextField(label="持有均價 ($)", value="226.215", width=140)
    t4_kelly_tf = ft.TextField(label="凱利上限 (%)", value="15.0", width=130)
    t4_budget_tf = ft.TextField(label="加碼預算 ($)", value="9616.50", width=140)
    t4_result_col = ft.Column(spacing=10)

    page_titles = [
        "📊 總覽設定",
        "🛡️ 風控持倉",
        "⏳ 費氏週期",
        "🧮 加減碼試算",
        "🎯 雙核心減碼",
    ]

    def render_main_nav():
        main_nav_row.controls.clear()
        for idx, title in enumerate(page_titles):
            is_act = active_page_idx[0] == idx

            def make_page_sw(i):
                def _sw(e):
                    active_page_idx[0] = i
                    page0_overview_col.visible = i == 0
                    page1_holdings_col.visible = i == 1
                    page2_fib_col.visible = i == 2
                    page3_calc_col.visible = i == 3
                    page4_trim_col.visible = i == 4
                    render_main_nav()
                    page.update()
                return _sw

            main_nav_row.controls.append(
                make_btn(
                    title,
                    make_page_sw(idx),
                    bg_color="#2563eb" if is_act else "#1e293b",
                    text_color="#ffffff" if is_act else "#a0aec0",
                    pad=9,
                )
            )

    def parse_anchor_date() -> datetime.date:
        raw_str = (tf_anchor_date.value or "").strip().replace("/", "-")
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
        tz_header_text.value = f"費氏時間窗 (T+0: {base_dt.strftime('%Y/%m/%d')} | {mode_str})"
        fib_specs = [
            (5, "T+5 短線確認窗", "檢視壓力與短均線翻揚", "#ed8936"),
            (8, "T+8 第一減碼窗", "觀察 0.236~0.382 壓力區", "#ecc94b"),
            (13, "T+13 波段分水嶺", "20MA 扣抵，第一階段減碼", "#4299e1"),
            (21, "T+21 中期轉折窗", "0.618 黃金分割強壓", "#48bb78"),
            (34, "T+34 季線變盤窗", "季線方向定調與再平衡", "#9f7aea"),
        ]
        today_dt = datetime.date.today()
        computed_tz = []
        for f_num, title, desc, color in fib_specs:
            t_dt = add_us_trading_days(base_dt, f_num) if use_b_days else base_dt + datetime.timedelta(days=f_num)
            d_left = (t_dt - today_dt).days
            computed_tz.append((title, t_dt, d_left, desc, color))
        upcoming = [item[2] for item in computed_tz if item[2] >= 0]
        highlight_days = min(upcoming) if upcoming else None
        for title, t_dt, d_left, desc, color in computed_tz:
            if d_left > 0:
                day_badge = f"還有 {d_left} 天"
            elif d_left == 0:
                day_badge = "今日變盤"
            else:
                day_badge = f"已過 {abs(d_left)} 天"
            is_hl = highlight_days is not None and d_left == highlight_days
            tz_row_container.controls.append(
                ft.Container(
                    width=165,
                    bgcolor="#1e3a8a" if is_hl else "#161b26",
                    border_radius=10,
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Text(f"{title}", color=color, size=12, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{t_dt.strftime('%m/%d')} ({day_badge})", color="#ffffff", size=14, weight=ft.FontWeight.BOLD),
                            ft.Text(desc, color="#a0aec0", size=11),
                        ],
                        spacing=3,
                    ),
                )
            )

    def compute_rows(use_network: bool, force_api: bool):
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
            q = None
            if use_network and sw_live.value:
                q = fetch_quant_metrics(tkr, get_extended=sw_ext.value, force_refresh=force_api)
            elif sw_live.value:
                cache_key = f"{tkr}_{sw_ext.value}"
                q = QUOTE_CACHE.get(cache_key)

            if q:
                raw_price = q["Price"]
                atr_val = q["ATR"]
                fib236 = q["Fib_0236"]
                fib382 = q["Fib_0382"]
                fib618 = q["Fib_0618"]
                fib1272 = q["Fib_1272"]
                ma20_val = q["MA20"]
                ma200_val = q["MA200"]
                sess_lbl = q["Session"]
                day_chg = q["Day_Chg_Pct"]
                rsi_val = q["RSI"]
                swing_low = q["Swing_Low"]
            else:
                raw_price = float(item.get("Manual_Price", item.get("Avg_Cost", 100.0)))
                atr_val = round(raw_price * 0.045, 2)
                fib236 = round(raw_price * 1.05, 2)
                fib382 = round(raw_price * 1.12, 2)
                fib618 = round(raw_price * 1.22, 2)
                fib1272 = round(raw_price * 1.30, 2)
                ma20_val = raw_price
                ma200_val = raw_price
                sess_lbl = "預設/離線"
                day_chg = 0.0
                rsi_val = 50.0
                swing_low = round(raw_price * 0.88, 2)

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
                "RSI": rsi_val,
                "Swing_Low": swing_low,
                "Fib_0236": fib236,
                "Fib_0382": fib382,
                "Fib_0618": fib618,
                "Fib_1272": fib1272,
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
                r["Optimal_Shares"] = int(math.floor((total_portfolio_equity * (r["Target_Kelly_Pct"] / 100.0)) / r["Price"]))
                r["Share_Diff"] = r["Optimal_Shares"] - r["Shares"]
            else:
                r["Weight_Pct"] = 0.0
                r["Optimal_Shares"] = 0
                r["Share_Diff"] = 0

            if r["Price"] <= r["Hard_Stop"]:
                r["Action_Signal"] = "觸底減碼"
            elif r["Price"] >= r["Key_Fib_Target"] and r["Weight_Pct"] > r["Target_Kelly_Pct"]:
                r["Action_Signal"] = "達標減碼"
            elif r["Weight_Pct"] > r["Target_Kelly_Pct"] + 2.0:
                r["Action_Signal"] = "超配禁攤"
            elif r["Price"] >= r["MA20"] and r["Weight_Pct"] < r["Target_Kelly_Pct"] - 2.0:
                r["Action_Signal"] = "右側加碼"
            else:
                r["Action_Signal"] = "紀律續抱"

        return live_rows, total_stock_val, total_portfolio_equity, total_pnl, total_pnl_pct, cash_pool, realized_loss_tax

    def update_ui_from_rows(live_rows, total_stock_val, total_portfolio_equity, total_pnl, total_pnl_pct, cash_pool, realized_loss_tax):
        sorted_w = sorted([r["Weight_Pct"] for r in live_rows], reverse=True)
        top2_conc = sum(sorted_w[:2]) if len(sorted_w) >= 2 else sum(sorted_w)
        daily_var_95 = sum(r["Shares"] * r["ATR"] * 1.645 for r in live_rows) * 0.65
        weekly_var_95 = daily_var_95 * math.sqrt(5)
        releasable_cash = sum(max(r["Shares"] - r["Optimal_Shares"], 0) * r["Price"] for r in live_rows) + cash_pool

        kpi_grid_container.controls.clear()
        pnl_color = "#48bb78" if total_pnl >= 0 else "#f56565"
        conc_color = "#ecc94b" if top2_conc > 35 else "#48bb78"
        kpi_specs = [
            ("總淨值 (股票+現金)", f"${total_portfolio_equity:,.0f}", f"股 ${total_stock_val:,.0f} / 現 ${cash_pool:,.0f}", "#f7fafc"),
            ("未實現總損益", f"${total_pnl:,.0f}", f"報酬率 {total_pnl_pct:+.2f}%", pnl_color),
            ("前兩大持股集中度", f"{top2_conc:.1f}%", "凱利上限 <= 35%", conc_color),
            ("單週 95% VaR 風控", f"-${weekly_var_95:,.0f}", f"單日 -${daily_var_95:,.0f}", "#f56565"),
            ("可動用現金+釋出", f"${releasable_cash:,.0f}", f"抵稅額 ${realized_loss_tax:,.0f}", "#48bb78"),
        ]
        for k_title, k_val, k_sub, k_col in kpi_specs:
            kpi_grid_container.controls.append(
                ft.Container(
                    width=165,
                    bgcolor="#161b26",
                    border_radius=10,
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Text(k_title, color="#a0aec0", size=11),
                            ft.Text(k_val, color=k_col, size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(k_sub, color="#718096", size=10),
                        ],
                        spacing=3,
                    ),
                )
            )

        render_time_zones()
        build_page1_holdings(live_rows)
        build_page2_ladders(live_rows)
        build_page3_calc(live_rows, total_portfolio_equity, cash_pool)
        build_page4_trim(live_rows)
        page.update()

    def refresh_all(force_api: bool = False, use_network: bool = True):
        async def _task():
            loading_bar.visible = True
            status_text.value = "正在同步報價與重算指標..." if use_network else "正在重算指標..."
            page.update()
            try:
                res = await asyncio.to_thread(compute_rows, use_network, force_api)
                update_ui_from_rows(*res)
                status_text.value = f"最後更新: {datetime.datetime.now().strftime('%H:%M:%S')}"
            except Exception as ex:
                status_text.value = f"更新異常: {ex}"
            finally:
                loading_bar.visible = False
                page.update()

        page.run_task(_task)

    # --- 分頁 2：風控持倉（精簡總表 + 個股子分頁切換器，解決頁面過長問題） ---
    def build_page1_holdings(live_rows: list):
        page1_holdings_col.controls.clear()
        headers = ["代號/現價", "股數/均價", "損益%", "權重/上限", "指令"]
        rows = []
        for r in live_rows:
            rows.append([
                f"{r['Ticker']}\n${r['Price']:.2f}",
                f"{r['Shares']}股\n@${r['Avg_Cost']:.1f}",
                f"${r['PnL']:,.0f}\n({r['PnL_Pct']:+.1f}%)",
                f"{r['Weight_Pct']:.1f}%\n(限{r['Target_Kelly_Pct']:.0f}%)",
                f"{r['Action_Signal']}\n({r['Share_Diff']:+d}股)",
            ])
        page1_holdings_col.controls.append(make_table_box("持倉風控總覽表", headers, rows, "#1e3a8a"))

        # 個股子分頁導覽列 (點選切換單一股票編輯卡，還有 [+新增] 頁籤)
        sub_nav_row = ft.Row(wrap=True, spacing=6)
        if selected_stock_idx[0] > len(live_rows):
            selected_stock_idx[0] = 0

        for idx, r in enumerate(live_rows):
            is_sel = selected_stock_idx[0] == idx

            def make_sel_stock(i):
                def _sel(e):
                    selected_stock_idx[0] = i
                    build_page1_holdings(live_rows)
                    page.update()
                return _sel

            sub_nav_row.controls.append(
                make_btn(
                    f"{r['Ticker']}",
                    make_sel_stock(idx),
                    bg_color="#38a169" if is_sel else "#1e293b",
                    text_color="#ffffff" if is_sel else "#90cdf4",
                    pad=8,
                )
            )

        is_add_tab = selected_stock_idx[0] == len(live_rows)

        def sel_add_tab(e):
            selected_stock_idx[0] = len(live_rows)
            build_page1_holdings(live_rows)
            page.update()

        sub_nav_row.controls.append(
            make_btn(
                "+ 新增股票",
                sel_add_tab,
                bg_color="#dd6b20" if is_add_tab else "#1e293b",
                text_color="#ffffff" if is_add_tab else "#fbd38d",
                pad=8,
            )
        )

        page1_holdings_col.controls.append(
            ft.Container(
                bgcolor="#161b26",
                border_radius=10,
                padding=10,
                content=ft.Column([
                    ft.Text("點選下方股票標籤，切換編輯單一個股參數：", size=12, color="#90cdf4"),
                    sub_nav_row,
                ], spacing=6),
            )
        )

        # 僅渲染當前選中的那 1 檔股票編輯卡 (或新增股票卡)
        if not is_add_tab and 0 <= selected_stock_idx[0] < len(live_rows):
            idx = selected_stock_idx[0]
            r = live_rows[idx]
            tf_s = ft.TextField(label="股數", value=str(r["Shares"]), width=105)
            tf_c = ft.TextField(label="均價($)", value=str(r["Avg_Cost"]), width=115)
            tf_p = ft.TextField(label="離線價($)", value=str(r["Price"]), width=115)
            tf_k = ft.TextField(label="凱利(%)", value=str(r["Target_Kelly_Pct"]), width=105)
            tf_f = ft.TextField(label="費氏目標", value=str(r["Key_Fib_Target"]), width=115)
            tf_h = ft.TextField(label="停損價", value=str(r["Hard_Stop"]), width=115)

            def _save_cur(e):
                try:
                    portfolio_data[idx]["Shares"] = int(float(tf_s.value))
                    portfolio_data[idx]["Avg_Cost"] = float(tf_c.value)
                    portfolio_data[idx]["Manual_Price"] = float(tf_p.value)
                    portfolio_data[idx]["Target_Kelly_Pct"] = float(tf_k.value)
                    portfolio_data[idx]["Key_Fib_Target"] = float(tf_f.value)
                    portfolio_data[idx]["Hard_Stop"] = float(tf_h.value)
                except Exception:
                    pass
                refresh_all(force_api=False, use_network=False)

            def _del_cur(e):
                if 0 <= idx < len(portfolio_data):
                    portfolio_data.pop(idx)
                    selected_stock_idx[0] = 0
                    refresh_all(force_api=False, use_network=False)

            pnl_c = "#48bb78" if r["PnL"] >= 0 else "#f56565"
            page1_holdings_col.controls.append(
                ft.Container(
                    bgcolor="#161b26",
                    border_radius=10,
                    padding=12,
                    content=ft.Column([
                        ft.Text(f"編輯 {r['Ticker']} ({r['Name']}) | 現價 ${r['Price']:.2f} [{r['Session']}]", size=14, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ft.Text(f"未實現損益: ${r['PnL']:,.2f} ({r['PnL_Pct']:+.2f}%) | 權重: {r['Weight_Pct']:.2f}% | 訊號: {r['Action_Signal']}", size=12, color=pnl_c),
                        ft.Row([tf_s, tf_c, tf_p, tf_k, tf_f, tf_h], wrap=True, spacing=8),
                        ft.Row([
                            make_btn("💾 儲存修改", _save_cur, "#2563eb", pad=10),
                            make_btn("🗑️ 刪除此股", _del_cur, "#9b2c2c", pad=10),
                        ], wrap=True, spacing=10),
                    ], spacing=8),
                )
            )
        else:
            new_tkr_tf = ft.TextField(label="美股代號", value="", width=130)
            new_sh_tf = ft.TextField(label="股數", value="50", width=110)
            new_cost_tf = ft.TextField(label="均價($)", value="100.0", width=120)
            new_kelly_tf = ft.TextField(label="凱利(%)", value="15.0", width=120)

            def add_new_stock(e):
                nt = (new_tkr_tf.value or "").strip().upper()
                if not nt:
                    return
                def_p = float(new_cost_tf.value or 100.0)
                portfolio_data.append({
                    "Ticker": nt,
                    "Name": nt,
                    "Shares": int(float(new_sh_tf.value or 0)),
                    "Avg_Cost": def_p,
                    "Target_Kelly_Pct": float(new_kelly_tf.value or 15.0),
                    "Hard_Stop": round(def_p * 0.90, 2),
                    "Key_Fib_Target": round(def_p * 1.15, 2),
                })
                selected_stock_idx[0] = len(portfolio_data) - 1
                refresh_all(force_api=False, use_network=True)

            page1_holdings_col.controls.append(
                ft.Container(
                    bgcolor="#152238",
                    border_radius=10,
                    padding=12,
                    content=ft.Column([
                        ft.Text("新增美股到追蹤主表", size=14, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                        ft.Row([new_tkr_tf, new_sh_tf, new_cost_tf, new_kelly_tf], wrap=True, spacing=8),
                        make_btn("➕ 確認加入持倉", add_new_stock, "#38a169", pad=10, width=160),
                    ], spacing=8),
                )
            )

    # --- 分頁 3：費氏時間週期與權重價位階梯 ---
    def build_page2_ladders(live_rows: list):
        ladder_col_container.controls.clear()
        for r in live_rows:
            w_pct = r["Weight_Pct"]
            k_pct = r["Target_Kelly_Pct"]
            w_color = "#f56565" if w_pct > k_pct else "#48bb78"
            cur_p, stop_p, fib_p = r["Price"], r["Hard_Stop"], r["Key_Fib_Target"]
            dist_to_fib = ((fib_p - cur_p) / cur_p * 100.0) if cur_p else 0.0
            dist_to_stop = ((cur_p - stop_p) / cur_p * 100.0) if cur_p else 0.0
            ladder_col_container.controls.append(
                ft.Container(
                    bgcolor="#161b26",
                    border_radius=8,
                    padding=10,
                    content=ft.Column([
                        ft.Text(f"{r['Ticker']} 權重 {w_pct:.1f}% / 凱利上限 {k_pct:.1f}%", size=13, weight=ft.FontWeight.BOLD, color=w_color),
                        ft.ProgressBar(value=min(w_pct / 40.0, 1.0), color=w_color, bgcolor="#0e1117"),
                        ft.Text(f"停損 ${stop_p:.2f} ({dist_to_stop:+.1f}%) | 現價 ${cur_p:.2f} | 費氏目標 ${fib_p:.2f} ({dist_to_fib:+.1f}%)", size=12, color="#e2e8f0"),
                    ], spacing=5),
                )
            )

    # --- 分頁 4：個股加減碼與補倉保本均價試算 ---
    def build_page3_calc(live_rows: list, total_portfolio_equity: float, cash_pool: float):
        page3_calc_col.controls.clear()
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
            chip_buttons.append(make_btn(r["Ticker"], make_chip_fn(r), "#1e293b", "#90cdf4", pad=8))

        def run_tab4_engine(e=None):
            t4_result_col.controls.clear()
            target_ticker = (t4_ticker_tf.value or "").strip().upper()
            if not target_ticker:
                return
            matched = next((x for x in live_rows if x["Ticker"] == target_ticker), None)
            q_data = QUOTE_CACHE.get(f"{target_ticker}_{sw_ext.value}")
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

            if matched:
                live_p = matched["Price"]
                live_atr = matched["ATR"]
                live_ma20 = matched["MA20"]
                live_rsi = matched["RSI"]
                swing_low = matched["Swing_Low"]
                fib_236_lvl = matched["Fib_0236"]
                fib_382_lvl = matched["Fib_0382"]
                fib_618_lvl = matched["Fib_0618"]
                fib_1272_lvl = matched["Fib_1272"]
            elif q_data:
                live_p = q_data["Price"]
                live_atr = q_data["ATR"]
                live_ma20 = q_data["MA20"]
                live_rsi = q_data["RSI"]
                swing_low = q_data["Swing_Low"]
                fib_236_lvl = q_data["Fib_0236"]
                fib_382_lvl = q_data["Fib_0382"]
                fib_618_lvl = q_data["Fib_0618"]
                fib_1272_lvl = q_data["Fib_1272"]
            else:
                live_p = sim_cur_cost if sim_cur_cost > 0 else 100.0
                live_atr = round(live_p * 0.04, 2)
                live_ma20 = live_p
                live_rsi = 50.0
                swing_low = round(live_p * 0.88, 2)
                fib_236_lvl = round(live_p * 0.93, 2)
                fib_382_lvl = round(live_p * 0.96, 2)
                fib_618_lvl = round(live_p * 1.08, 2)
                fib_1272_lvl = round(live_p * 1.20, 2)

            if sim_cur_cost <= 0:
                sim_cur_cost = live_p

            cur_invested_cost = round(sim_cur_shares * sim_cur_cost, 2)
            cur_mkt_val = round(sim_cur_shares * live_p, 2)
            cur_weight_pct = (cur_mkt_val / total_portfolio_equity * 100.0) if total_portfolio_equity > 0 else 0.0
            max_kelly_val = total_portfolio_equity * (sim_kelly_pct / 100.0)
            max_kelly_shares = int(math.floor(max_kelly_val / live_p)) if live_p > 0 else 0
            remaining_kelly_val = max(0.0, max_kelly_val - cur_mkt_val)
            effective_add_budget = min(remaining_kelly_val, budget_limit) if remaining_kelly_val > 0 else 0.0

            t4_result_col.controls.append(ft.Text(
                f"{target_ticker} 現價 ${live_p:.2f} | 權重 {cur_weight_pct:.1f}% / 上限 {sim_kelly_pct:.1f}% ({max_kelly_shares}股) | RSI {live_rsi:.1f} | ATR ${live_atr:.2f}",
                color="white",
                size=13,
                weight=ft.FontWeight.BOLD,
            ))

            if cur_weight_pct >= sim_kelly_pct:
                t4_result_col.controls.append(
                    ft.Text("目前權重已超過半凱利上限，禁止向下攤平！建議優先執行反彈階梯減碼。", color="#fc8181", size=12, weight=ft.FontWeight.BOLD)
                )
            else:
                t4_result_col.controls.append(
                    ft.Text(f"風控允許尚可加碼額度：${effective_add_budget:,.2f}", color="#68d391", size=12)
                )

            buy_p1 = round(live_p, 2)
            buy_p2 = round(max(live_p - 1.0 * live_atr, swing_low, live_p * 0.92), 2)

            b1_shares = int(math.floor((effective_add_budget * 0.40) / buy_p1)) if buy_p1 > 0 else 0
            b1_fund = round(b1_shares * buy_p1, 2)
            after_b1_shares = sim_cur_shares + b1_shares
            after_b1_avg = round((cur_invested_cost + b1_fund) / after_b1_shares, 2) if after_b1_shares > 0 else 0.0

            rem_budget_for_b2 = max(0.0, effective_add_budget - b1_fund)
            b2_shares = int(math.floor(rem_budget_for_b2 / buy_p2)) if buy_p2 > 0 else 0
            b2_fund = round(b2_shares * buy_p2, 2)

            total_addon_fund = round(b1_fund + b2_fund, 2)
            final_total_shares = sim_cur_shares + b1_shares + b2_shares
            final_breakeven_avg = (
                round((cur_invested_cost + total_addon_fund) / final_total_shares, 2)
                if final_total_shares > 0
                else 0.0
            )
            hard_stop_price = round(buy_p2 - 1.5 * live_atr, 2)

            addon_headers = ["階段", "買價", "股數", "動用資金", "補倉後保本均價"]
            addon_rows = [
                ["原持倉", f"${sim_cur_cost:.2f}", f"{sim_cur_shares}股", f"${cur_invested_cost:,.0f}", f"${sim_cur_cost:.2f}"],
                ["第一批40%", f"${buy_p1:.2f}", f"+{b1_shares}股", f"${b1_fund:,.0f}", f"${after_b1_avg:.2f}"],
                ["第二批60%", f"${buy_p2:.2f}", f"+{b2_shares}股", f"${b2_fund:,.0f}", f"${final_breakeven_avg:.2f}"],
                ["合計總結", "-", f"共{final_total_shares}股", f"${total_addon_fund:,.0f}", f"保本 ${final_breakeven_avg:.2f}"],
            ]
            t4_result_col.controls.append(
                make_table_box(f"{target_ticker} 兩批加碼與補倉保本均價試算", addon_headers, addon_rows, "#22543d")
            )

            trim_headers = ["費氏區間", "目標價", "比例", "減碼股數", "回收現金"]
            s_236 = int(math.floor(final_total_shares * 0.25))
            s_382 = int(math.floor(final_total_shares * 0.25))
            s_618 = int(math.floor(final_total_shares * 0.25))
            s_1272 = max(0, final_total_shares - s_236 - s_382 - s_618)
            trim_rows = [
                ["Fib 0.236", f"${fib_236_lvl:.2f}", "25%", f"{s_236}股", f"${s_236 * fib_236_lvl:,.0f}"],
                ["Fib 0.382", f"${fib_382_lvl:.2f}", "25%", f"{s_382}股", f"${s_382 * fib_382_lvl:,.0f}"],
                ["Fib 0.618", f"${fib_618_lvl:.2f}", "25%", f"{s_618}股", f"${s_618 * fib_618_lvl:,.0f}"],
                ["Fib 1.272", f"${fib_1272_lvl:.2f}", "25%", f"{s_1272}股", f"${s_1272 * fib_1272_lvl:,.0f}"],
                ["ATR 停損", f"${hard_stop_price:.2f}", "破位", "強制風控", "跌破無條件減碼"],
            ]
            t4_result_col.controls.append(
                make_table_box(f"{target_ticker} 費波納契階梯減碼與停損表", trim_headers, trim_rows, "#1e3a8a")
            )
            page.update()

        page3_calc_col.controls.append(
            ft.Container(
                bgcolor="#161b26",
                border_radius=12,
                padding=12,
                content=ft.Column([
                    ft.Text("點選持股快速帶入試算：", size=13, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                    ft.Row(chip_buttons, wrap=True, spacing=6),
                    ft.Row([t4_ticker_tf, t4_shares_tf, t4_cost_tf, t4_kelly_tf, t4_budget_tf], wrap=True, spacing=8),
                    make_btn("🧮 立即計算補倉保本均價", run_tab4_engine, "#2563eb", pad=10, width=220),
                ], spacing=8),
            )
        )
        page3_calc_col.controls.append(t4_result_col)
        run_tab4_engine()

    # --- 分頁 5：NBIS 與 MRVL 三階梯減碼專區 ---
    def build_page4_trim(live_rows: list):
        page4_trim_col.controls.clear()
        nbis_r = next((x for x in live_rows if x["Ticker"] == "NBIS"), None)
        mrvl_r = next((x for x in live_rows if x["Ticker"] == "MRVL"), None)
        nbis_p = nbis_r["Price"] if nbis_r else 171.45
        nbis_sh = nbis_r["Shares"] if nbis_r else 550
        mrvl_p = mrvl_r["Price"] if mrvl_r else 235.00
        mrvl_sh = mrvl_r["Shares"] if mrvl_r else 350
        page4_trim_col.controls.append(make_table_box(
            f"NBIS 三階減碼表 (現有 {nbis_sh} 股 | 現價 ${nbis_p:.2f})",
            ["階段", "掛單價", "股數", "收回現金"],
            [
                ["第一階", "$195.80", "87股", f"${87 * 195.80:,.0f}"],
                ["第二階", "$200.00", "80股", f"${80 * 200.00:,.0f}"],
                ["第三階", "$215.50", "50股", f"${50 * 215.50:,.0f}"],
                ["破位防線", "$159.00", "100股", f"${100 * 159.00:,.0f}"],
            ],
            "#1e3a8a",
        ))
        page4_trim_col.controls.append(make_table_box(
            f"MRVL 三階減碼表 (現有 {mrvl_sh} 股 | 現價 ${mrvl_p:.2f})",
            ["階段", "掛單價", "股數", "收回現金"],
            [
                ["第一階", "$247.77", "57股", f"${57 * 247.77:,.0f}"],
                ["第二階", "$256.00", "60股", f"${60 * 256.00:,.0f}"],
                ["第三階", "$272.50", "53股", f"${53 * 272.50:,.0f}"],
                ["破位防線", "$218.00", "60股", f"${60 * 218.00:,.0f}"],
            ],
            "#744210",
        ))

    def set_quick_anchor(dt_str: str):
        tf_anchor_date.value = dt_str
        render_time_zones()
        page.update()

    def reset_defaults(e):
        portfolio_data.clear()
        for item in DEFAULT_PORTFOLIO:
            portfolio_data.append(dict(item))
        tf_anchor_date.value = "2026-10-16"
        tf_cash.value = "9616.50"
        tf_tax.value = "-3461.52"
        tf_shock.value = "0"
        tf_beta.value = "1.50"
        refresh_all(force_api=True, use_network=True)

    # 組裝分頁 1 (總覽與設定)
    page0_overview_col.controls.extend([
        kpi_grid_container,
        ft.Container(
            bgcolor="#161b26",
            border_radius=12,
            padding=12,
            content=ft.Column([
                ft.Text("全域資金與大盤壓力測試設定", size=14, weight=ft.FontWeight.BOLD, color="#90cdf4"),
                ft.Row([sw_live, sw_ext], wrap=True, spacing=10),
                ft.Row([tf_cash, tf_tax, tf_shock, tf_beta], wrap=True, spacing=8),
                ft.Row([
                    make_btn("⚡ 套用並重算", lambda e: refresh_all(False, False), "#38a169", pad=10),
                    make_btn("🔄 聯網更新報價", lambda e: refresh_all(True, True), "#2563eb", pad=10),
                    make_btn("↩️ 重置預設", reset_defaults, "#4a5568", pad=10),
                ], wrap=True, spacing=8),
            ], spacing=8),
        ),
    ])

    # 組裝分頁 3 (費氏週期與階梯)
    page2_fib_col.controls.extend([
        ft.Container(
            bgcolor="#161b26",
            border_radius=12,
            padding=12,
            content=ft.Column([
                tz_header_text,
                ft.Row([
                    tf_anchor_date,
                    sw_trading_days,
                    make_btn("設為 10/16", lambda e: set_quick_anchor("2026-10-16"), "#1e293b", "#90cdf4", pad=8),
                    make_btn("設為今天", lambda e: set_quick_anchor(datetime.date.today().strftime("%Y-%m-%d")), "#1e293b", "#fbd38d", pad=8),
                ], wrap=True, spacing=8),
                tz_row_container,
            ], spacing=8),
        ),
        ft.Text("各股權重上限與停損/目標價位階梯", size=14, weight=ft.FontWeight.BOLD, color="#f7fafc"),
        ladder_col_container,
    ])

    render_main_nav()
    page.controls.clear()
    page.add(
        ft.Container(
            bgcolor="#161b26",
            border_radius=10,
            padding=10,
            content=ft.Column([
                ft.Row([
                    ft.Text("美股量化風控 × 費氏 × 半凱利", size=17, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    status_text,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                loading_bar,
                main_nav_row,
            ], spacing=6),
        ),
        page0_overview_col,
        page1_holdings_col,
        page2_fib_col,
        page3_calc_col,
        page4_trim_col,
    )

    # 第一步：先用離線預設值在 0.01 秒內瞬間渲染所有分頁，保證畫面秒開不卡死
    init_res = compute_rows(use_network=False, force_api=False)
    update_ui_from_rows(*init_res)

    # 第二步：背景非阻塞抓取即時報價
    refresh_all(force_api=False, use_network=True)


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)