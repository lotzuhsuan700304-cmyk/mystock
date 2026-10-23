import asyncio
import datetime
import json
import math
import urllib.request
import flet as ft


class _YFTicker:
    def __init__(self, symbol):
        self.symbol = symbol.strip().upper()
        self.closes = []
        self.highs = []
        self.lows = []
        try:
            url = (
                "https://query1.finance.yahoo.com/v8/finance/chart/"
                f"{self.symbol}?interval=1d&range=1y"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                r = json.loads(resp.read().decode("utf-8"))
            res = r.get("chart", {}).get("result", [])
            if res:
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
        except Exception:
            pass
        last = self.closes[-1] if self.closes else 0.0
        prev = self.closes[-2] if len(self.closes) > 1 else 0.0
        self.fast_info = {"last_price": last, "previous_close": prev}
        self.info = {
            "regularMarketPrice": last,
            "currentPrice": last,
            "previousClose": prev,
        }


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


def safe_border(width: float, color: str):
    try:
        return ft.border.all(width, color)
    except Exception:
        return None


def safe_padding(vertical: float = 0, horizontal: float = 0):
    try:
        return ft.padding.symmetric(vertical=vertical, horizontal=horizontal)
    except Exception:
        return ft.padding.all(max(vertical, horizontal))


def make_btn(text, on_click_fn, bg_color="#2563eb", text_color="#ffffff", expand=False, pad_v=10, pad_h=14, border_col=None):
    return ft.Container(
        content=ft.Row(
            [ft.Text(text, color=text_color, size=13, weight=ft.FontWeight.BOLD)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=bg_color,
        border=safe_border(1.5, border_col) if border_col else None,
        border_radius=8,
        padding=safe_padding(vertical=pad_v, horizontal=pad_h),
        on_click=on_click_fn,
        expand=expand,
    )


def make_table_box(title: str, headers: list, rows: list, border_color: str = "#2d3748"):
    header_cells = [
        ft.Container(content=ft.Text(h, size=12, weight=ft.FontWeight.BOLD, color="#90cdf4"), expand=True)
        for h in headers
    ]
    table_rows = [
        ft.Container(bgcolor="#1e293b", padding=8, border_radius=6, content=ft.Row(header_cells))
    ]
    for r in rows:
        row_cells = [
            ft.Container(content=ft.Text(str(c), size=12, color="#e2e8f0"), expand=True) for c in r
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
        content=ft.Column(
            [
                ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
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
        tk = yf.Ticker(tkr)
        closes, highs, lows = tk.closes, tk.highs, tk.lows
        if len(closes) < 2:
            return None
        reg_close = closes[-1]
        prev_close = closes[-2]
        current_price = reg_close
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
            "Session": "日線收盤",
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
    page.title = "美股量化風控 × 費波納契 × 半凱利操盤系統"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e1117"
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO
    page.add(ft.Text("App 已啟動，正在建立畫面...", size=20, color="white"))
    page.update()
    await asyncio.sleep(0.05)

    try:
        await _build(page)
    except Exception as e:
        import traceback
        page.add(ft.Text(f"啟動錯誤: {e}", color="#fc8181", size=16, selectable=True))
        page.add(ft.Text(traceback.format_exc(), size=11, color="#e2e8f0", selectable=True))
        page.update()


async def _build(page: ft.Page):
    portfolio_data = [dict(item) for item in DEFAULT_PORTFOLIO]
    active_tab_idx = [0]

    sw_live = ft.Switch(label="自動抓即時報價", value=True)
    sw_ext = ft.Switch(label="含盤前/盤後延長價", value=True)
    sw_trading_days = ft.Switch(label="按美股交易日推算", value=True)
    tf_anchor_date = ft.TextField(label="費氏週期起始日 T+0 (YYYY-MM-DD)", value="2026-10-16", width=220)
    tf_cash = ft.TextField(label="可用美元現金池 ($)", value="9616.50", width=150)
    tf_tax = ft.TextField(label="累計可抵稅虧損 ($)", value="-3461.52", width=150)
    tf_shock = ft.TextField(label="大盤衝擊模擬 (%)", value="0", width=130)
    tf_beta = ft.TextField(label="高Beta敏感倍數", value="1.50", width=130)
    loading_bar = ft.ProgressBar(visible=False, color="#ecc94b", bgcolor="#1e2536")

    kpi_row_container = ft.Row(wrap=True, spacing=10)
    tz_header_text = ft.Text("費波納契時間週期變盤視窗", size=16, weight=ft.FontWeight.BOLD, color="#f7fafc")
    tz_row_container = ft.Row(wrap=True, spacing=10)
    tab_nav_row = ft.Row(wrap=True, spacing=8)
    tab1_col = ft.Column(spacing=12, visible=True)
    tab2_col = ft.Column(spacing=12, visible=False)
    tab3_col = ft.Column(spacing=12, visible=False)
    tab4_col = ft.Column(spacing=12, visible=False)

    t4_ticker_tf = ft.TextField(label="美股代號", value="NBIS", width=260)
    t4_shares_tf = ft.TextField(label="目前持有股數 (新股填 0)", value="550", width=180)
    t4_cost_tf = ft.TextField(label="目前持有均價 ($)", value="226.215", width=160)
    t4_kelly_tf = ft.TextField(label="半凱利目標上限 (%)", value="15.0", width=160)
    t4_budget_tf = ft.TextField(label="預計最大動用加碼資金 ($)", value="9616.50", width=190)
    t4_result_col = ft.Column(spacing=12)

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
        tz_header_text.value = f"費波納契時間週期 (T+0：{base_dt.strftime('%Y/%m/%d')} | {mode_str})"
        fib_specs = [
            (5, "T+5 短線確認窗", "檢視壓力與短均線翻揚", "#ed8936"),
            (8, "T+8 第一減碼窗", "觀察 0.236~0.382 壓力區", "#ecc94b"),
            (13, "T+13 波段分水嶺", "20MA 扣抵，第一階段減碼", "#4299e1"),
            (21, "T+21 中期轉折窗", "0.618 黃金分割強壓", "#48bb78"),
            (34, "T+34 季線大變盤窗", "季線方向定調與再平衡", "#9f7aea"),
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
                    width=235,
                    bgcolor="#152238" if is_hl else "#131822",
                    border=safe_border(1.5 if is_hl else 1.0, "#3182ce" if is_hl else "#2d3748"),
                    border_radius=10,
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text(f"{title} ({day_badge})", color=color, size=12, weight=ft.FontWeight.BOLD),
                            ft.Text(t_dt.strftime("%Y/%m/%d"), color="#ffffff", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(desc, color="#a0aec0", size=11),
                        ],
                        spacing=4,
                    ),
                )
            )

    def set_quick_anchor(dt_str: str):
        tf_anchor_date.value = dt_str
        render_time_zones()
        page.update()

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
                rsi_val = q["RSI"] if q else 50.0
                swing_low = q["Swing_Low"] if q else round(raw_price * 0.88, 2)
                fib1272 = q["Fib_1272"] if q else round(raw_price * 1.20, 2)
            else:
                raw_price = float(item.get("Manual_Price", item.get("Avg_Cost", 100.0)))
                atr_val = round(raw_price * 0.045, 2)
                fib382 = round(raw_price * 1.12, 2)
                fib618 = round(raw_price * 1.22, 2)
                fib1272 = round(raw_price * 1.30, 2)
                ma20_val = raw_price
                ma200_val = raw_price
                sess_lbl = "手動離線"
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
                r["Action_Signal"] = "觸及底線：強制減碼"
            elif r["Price"] >= r["Key_Fib_Target"] and r["Weight_Pct"] > r["Target_Kelly_Pct"]:
                r["Action_Signal"] = "達費氏目標：階梯減碼"
            elif r["Weight_Pct"] > r["Target_Kelly_Pct"] + 2.0:
                r["Action_Signal"] = "超配：禁攤平/反彈減碼"
            elif r["Price"] >= r["MA20"] and r["Weight_Pct"] < r["Target_Kelly_Pct"] - 2.0:
                r["Action_Signal"] = "右側強勢：可順勢加碼"
            else:
                r["Action_Signal"] = "權重安全：紀律續抱"

        sorted_w = sorted([r["Weight_Pct"] for r in live_rows], reverse=True)
        top2_conc = sum(sorted_w[:2]) if len(sorted_w) >= 2 else sum(sorted_w)
        daily_var_95 = sum(r["Shares"] * r["ATR"] * 1.645 for r in live_rows) * 0.65
        weekly_var_95 = daily_var_95 * math.sqrt(5)
        releasable_cash = sum(max(r["Shares"] - r["Optimal_Shares"], 0) * r["Price"] for r in live_rows) + cash_pool

        kpi_row_container.controls.clear()
        pnl_color = "#48bb78" if total_pnl >= 0 else "#f56565"
        conc_color = "#ecc94b" if top2_conc > 35 else "#48bb78"
        kpi_specs = [
            ("股票總市值 + 現金總淨值 (USD)", f"${total_portfolio_equity:,.2f}", f"股票: ${total_stock_val:,.0f} / 現金: ${cash_pool:,.0f}", "#f7fafc"),
            ("未實現總損益 (USD / %)", f"${total_pnl:,.2f}", f"總報酬率: {total_pnl_pct:+.2f}%", pnl_color),
            ("前兩大持股集中度", f"{top2_conc:.2f}%", "半凱利建議上限 <= 35%", conc_color),
            ("單週 95% VaR", f"-${weekly_var_95:,.0f}", f"單日 95% VaR: -${daily_var_95:,.0f}", "#f56565"),
            ("可動用現金 + 減碼釋出", f"${releasable_cash:,.0f}", f"現金 ${cash_pool:,.0f} / 可抵稅 ${realized_loss_tax:,.0f}", "#48bb78"),
        ]
        for k_title, k_val, k_sub, k_col in kpi_specs:
            kpi_row_container.controls.append(
                ft.Container(
                    width=235,
                    bgcolor="#161b26",
                    border=safe_border(1, "#2d3748"),
                    border_radius=12,
                    padding=14,
                    content=ft.Column(
                        [
                            ft.Text(k_title, color="#a0aec0", size=12),
                            ft.Text(k_val, color=k_col, size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(k_sub, color="#718096", size=11),
                        ],
                        spacing=4,
                    ),
                )
            )
        render_time_zones()
        build_tab1(live_rows)
        build_tab2(live_rows)
        build_tab3(live_rows)
        build_tab4(live_rows, total_portfolio_equity, cash_pool)
        loading_bar.visible = False
        page.update()

    def build_tab1(live_rows: list):
        tab1_col.controls.clear()
        tab1_col.controls.append(ft.Text("可修改股數、均價、凱利上限、費氏目標與防守底線，或新增/刪除股票。", size=13, color="#90cdf4"))
        headers = ["代號", "股數", "均價", "現價", "總市值", "損益", "權重", "凱利上限", "建議", "費氏目標", "停損", "指令"]
        rows = []
        for r in live_rows:
            rows.append([
                r["Ticker"], r["Shares"], f"${r['Avg_Cost']:.2f}",
                f"${r['Price']:.2f} ({r['Day_Chg_Pct']:+.1f}%)",
                f"${r['Market_Value']:,.0f}",
                f"${r['PnL']:,.0f} ({r['PnL_Pct']:+.1f}%)",
                f"{r['Weight_Pct']:.1f}%",
                f"{r['Target_Kelly_Pct']:.1f}% ({r['Optimal_Shares']}股)",
                f"{r['Share_Diff']:+d} 股",
                f"${r['Key_Fib_Target']:.2f}",
                f"${r['Hard_Stop']:.2f}",
                r["Action_Signal"],
            ])
        tab1_col.controls.append(make_table_box("互動式風控追蹤總表", headers, rows, "#3182ce"))
        for idx, r in enumerate(live_rows):
            tf_s = ft.TextField(label="股數", value=str(r["Shares"]), width=95)
            tf_c = ft.TextField(label="均價", value=str(r["Avg_Cost"]), width=115)
            tf_p = ft.TextField(label="模擬價", value=str(r["Price"]), width=115)
            tf_k = ft.TextField(label="凱利%", value=str(r["Target_Kelly_Pct"]), width=105)
            tf_f = ft.TextField(label="費氏目標", value=str(r["Key_Fib_Target"]), width=125)
            tf_h = ft.TextField(label="停損", value=str(r["Hard_Stop"]), width=125)

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
                    refresh_all(False)
                return _save

            def make_del_fn(i):
                def _del(e):
                    if 0 <= i < len(portfolio_data):
                        portfolio_data.pop(i)
                        refresh_all(False)
                return _del

            pnl_c = "#48bb78" if r["PnL"] >= 0 else "#f56565"
            tab1_col.controls.append(
                ft.Container(
                    bgcolor="#161b26",
                    border=safe_border(1, "#2d3748"),
                    border_radius=10,
                    padding=12,
                    content=ft.Column([
                        ft.Text(f"{r['Ticker']} ({r['Name']}) ${r['Price']:.2f} | {r['Action_Signal']}", size=14, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ft.Text(f"損益 ${r['PnL']:,.2f} ({r['PnL_Pct']:+.2f}%) | 權重 {r['Weight_Pct']:.2f}%", size=13, color=pnl_c),
                        ft.Row([
                            tf_s, tf_c, tf_p, tf_k, tf_f, tf_h,
                            make_btn("儲存", make_save_fn(idx, tf_s, tf_c, tf_p, tf_k, tf_f, tf_h), "#2563eb"),
                            make_btn("刪除", make_del_fn(idx), "#9b2c2c"),
                        ], wrap=True, spacing=8),
                    ], spacing=8),
                )
            )

        new_tkr_tf = ft.TextField(label="新代號", value="", width=170)
        new_sh_tf = ft.TextField(label="股數", value="50", width=110)
        new_cost_tf = ft.TextField(label="均價", value="100.0", width=120)
        new_kelly_tf = ft.TextField(label="凱利%", value="15.0", width=120)

        def add_new_stock(e):
            nt = (new_tkr_tf.value or "").strip().upper()
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
            refresh_all(False)

        tab1_col.controls.append(
            ft.Container(
                bgcolor="#152238",
                border=safe_border(1.5, "#3182ce"),
                border_radius=10,
                padding=14,
                content=ft.Column([
                    ft.Text("新增美股到追蹤主表", size=14, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                    ft.Row([new_tkr_tf, new_sh_tf, new_cost_tf, new_kelly_tf, make_btn("加入", add_new_stock, "#38a169")], wrap=True, spacing=10),
                ], spacing=8),
            )
        )

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
                        ft.Text(f"{r['Ticker']} 權重 {w_pct:.2f}% / 上限 {k_pct:.1f}%", size=13, weight=ft.FontWeight.BOLD, color=w_color),
                        ft.ProgressBar(value=min(w_pct / 40.0, 1.0), color=w_color, bgcolor="#0e1117"),
                        ft.ProgressBar(value=min(k_pct / 40.0, 1.0), color="#48bb78", bgcolor="#0e1117"),
                    ], spacing=5),
                )
            )
            cur_p, stop_p, fib_p = r["Price"], r["Hard_Stop"], r["Key_Fib_Target"]
            dist_to_fib = ((fib_p - cur_p) / cur_p * 100.0) if cur_p else 0.0
            dist_to_stop = ((cur_p - stop_p) / cur_p * 100.0) if cur_p else 0.0
            price_ladders.append(
                ft.Container(
                    bgcolor="#1e2536",
                    border_radius=8,
                    padding=10,
                    content=ft.Column([
                        ft.Text(f"{r['Ticker']} 停損 ${stop_p:.2f} ({dist_to_stop:+.1f}%) | 現價 ${cur_p:.2f} | 目標 ${fib_p:.2f} ({dist_to_fib:+.1f}%)", size=13, color="#ffffff"),
                    ]),
                )
            )
        tab2_col.controls.append(
            ft.Column([
                ft.Text("權重 vs 半凱利上限", size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                ft.Column(weight_bars, spacing=8),
                ft.Text("現價 / 停損 / 費氏目標", size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                ft.Column(price_ladders, spacing=8),
            ], spacing=10)
        )

    def build_tab3(live_rows: list):
        tab3_col.controls.clear()
        nbis_r = next((x for x in live_rows if x["Ticker"] == "NBIS"), None)
        mrvl_r = next((x for x in live_rows if x["Ticker"] == "MRVL"), None)
        nbis_p = nbis_r["Price"] if nbis_r else 171.45
        nbis_sh = nbis_r["Shares"] if nbis_r else 550
        mrvl_p = mrvl_r["Price"] if mrvl_r else 235.00
        mrvl_sh = mrvl_r["Shares"] if mrvl_r else 350
        tab3_col.controls.append(ft.Text("NBIS 與 MRVL 三階梯減碼試算", size=16, weight=ft.FontWeight.BOLD, color="#f7fafc"))
        tab3_col.controls.append(make_table_box(
            f"NBIS (現有 {nbis_sh} 股 | ${nbis_p:.2f})",
            ["階段", "掛單價", "股數", "收回現金"],
            [
                ["第一階", "$195.80", "87", f"${87 * 195.80:,.2f}"],
                ["第二階", "$200.00", "80", f"${80 * 200.00:,.2f}"],
                ["第三階", "$215.50", "50", f"${50 * 215.50:,.2f}"],
                ["破位", "$159.00", "100", f"${100 * 159.00:,.2f}"],
            ],
            "#3182ce",
        ))
        tab3_col.controls.append(make_table_box(
            f"MRVL (現有 {mrvl_sh} 股 | ${mrvl_p:.2f})",
            ["階段", "掛單價", "股數", "收回現金"],
            [
                ["第一階", "$247.77", "57", f"${57 * 247.77:,.2f}"],
                ["第二階", "$256.00", "60", f"${60 * 256.00:,.2f}"],
                ["第三階", "$272.50", "53", f"${53 * 272.50:,.2f}"],
                ["破位", "$218.00", "60", f"${60 * 218.00:,.2f}"],
            ],
            "#ecc94b",
        ))

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
            chip_buttons.append(make_btn(r["Ticker"], make_chip_fn(r), "#1e293b", "#90cdf4", pad_v=6, pad_h=10, border_col="#3182ce"))

        def run_tab4_engine(e=None):
            t4_result_col.controls.clear()
            target_ticker = (t4_ticker_tf.value or "").strip().upper()
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
            live_rsi = q_data["RSI"] if q_data else 50.0
            fib_382_lvl = q_data["Fib_0382"] if q_data else round(live_p * 0.96, 2)
            fib_618_lvl = q_data["Fib_0618"] if q_data else round(live_p * 1.08, 2)
            fib_1272_lvl = q_data["Fib_1272"] if q_data else round(live_p * 1.20, 2)
            cur_weight_pct = (sim_cur_shares * live_p / total_portfolio_equity * 100.0) if total_portfolio_equity > 0 else 0.0
            max_kelly_val = total_portfolio_equity * (sim_kelly_pct / 100.0)
            max_kelly_shares = int(math.floor(max_kelly_val / live_p)) if live_p > 0 else 0
            remaining_kelly_val = max(0.0, max_kelly_val - sim_cur_shares * live_p)
            effective_add_budget = min(remaining_kelly_val, budget_limit) if remaining_kelly_val > 0 else budget_limit
            t4_result_col.controls.append(ft.Text(
                f"{target_ticker} ${live_p:.2f} | 權重 {cur_weight_pct:.1f}% / 上限 {sim_kelly_pct:.1f}% | 建議上限 {max_kelly_shares} 股 | RSI {live_rsi:.1f} | ATR ${live_atr:.2f} | 20MA ${live_ma20:.2f}",
                color="white",
                size=13,
            ))
            if cur_weight_pct >= sim_kelly_pct:
                t4_result_col.controls.append(ft.Text("權重已超標，禁止向下攤平。請先減碼。", color="#fc8181"))
            else:
                t4_result_col.controls.append(ft.Text(f"尚可加碼約 ${effective_add_budget:,.0f}", color="#68d391"))
            buy_p1 = round(live_p, 2)
            b1 = int(math.floor((effective_add_budget * 0.40) / buy_p1)) if buy_p1 > 0 else 0
            t4_result_col.controls.append(ft.Text(
                f"加碼第一批約 {b1} 股 @ ${buy_p1:.2f}；減碼參考 0.382 ${fib_382_lvl:.2f} / 0.618 ${fib_618_lvl:.2f} / 1.272 ${fib_1272_lvl:.2f}",
                color="#e2e8f0",
                size=12,
            ))
            page.update()

        tab4_col.controls.append(
            ft.Container(
                bgcolor="#161b26",
                border=safe_border(1, "#2d3748"),
                border_radius=12,
                padding=14,
                content=ft.Column([
                    ft.Text("個股加減碼試算", size=15, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                    ft.Row(chip_buttons, wrap=True, spacing=6),
                    ft.Row([t4_ticker_tf, t4_shares_tf, t4_cost_tf, t4_kelly_tf, t4_budget_tf, make_btn("試算", run_tab4_engine, "#2563eb")], wrap=True, spacing=10),
                ], spacing=10),
            )
        )
        tab4_col.controls.append(t4_result_col)

    tab_titles = ["風控主表", "權重與價位", "NBIS/MRVL 減碼", "加減碼試算"]

    def render_tab_nav():
        tab_nav_row.controls.clear()
        for idx, t_label in enumerate(tab_titles):
            is_act = active_tab_idx[0] == idx
            def make_switch_fn(i):
                def _sw(e):
                    active_tab_idx[0] = i
                    tab1_col.visible = i == 0
                    tab2_col.visible = i == 1
                    tab3_col.visible = i == 2
                    tab4_col.visible = i == 3
                    render_tab_nav()
                    page.update()
                return _sw
            tab_nav_row.controls.append(
                make_btn(
                    t_label,
                    make_switch_fn(idx),
                    "#1e3a8a" if is_act else "#161b26",
                    "#60a5fa" if is_act else "#a0aec0",
                    border_col="#3b82f6" if is_act else "#2d3748",
                )
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
        refresh_all(True)

    render_tab_nav()
    page.controls.clear()
    page.add(
        ft.Container(
            bgcolor="#161b26",
            border=safe_border(1, "#2d3748"),
            border_radius=12,
            padding=16,
            content=ft.Column([
                ft.Text("美股量化風控 x 費波納契 x 半凱利", size=22, weight=ft.FontWeight.BOLD, color="#ffffff"),
                ft.Text("不使用 pandas/numpy，避免 Android 啟動卡在灰畫面。", size=12, color="#a0aec0"),
                loading_bar,
                ft.Row([
                    sw_live, sw_ext, tf_cash, tf_tax, tf_shock, tf_beta,
                    make_btn("套用並重算", lambda e: refresh_all(False), "#38a169"),
                    make_btn("更新報價", lambda e: refresh_all(True), "#2563eb"),
                    make_btn("重置", reset_defaults, "#4a5568"),
                ], wrap=True, spacing=12),
                ft.Row([
                    tf_anchor_date,
                    sw_trading_days,
                    make_btn("10/16", lambda e: set_quick_anchor("2026-10-16"), "#1e293b", "#90cdf4", border_col="#3182ce"),
                    make_btn("今天", lambda e: set_quick_anchor(datetime.date.today().strftime("%Y-%m-%d")), "#1e293b", "#fbd38d", border_col="#dd6b20"),
                ], wrap=True, spacing=10),
            ], spacing=8),
        ),
        kpi_row_container,
        tz_header_text,
        tz_row_container,
        tab_nav_row,
        tab1_col,
        tab2_col,
        tab3_col,
        tab4_col,
    )
    page.update()
    await asyncio.sleep(0)
    refresh_all(False)


if __name__ == "__main__":
    ft.run(main)
