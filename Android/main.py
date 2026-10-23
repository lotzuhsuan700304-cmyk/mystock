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
            with urllib.request.urlopen(req, timeout=5) as resp:
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


# --- 零崩潰且支援自適應並排的 UI 輔助函式 ---
def make_btn(text: str, on_click_fn, bg_color: str = "#2563eb", text_color: str = "#ffffff", pad: int = 8, width: int = None, expand: int = None, size: int = 12):
    return ft.Container(
        content=ft.Text(
            text,
            color=text_color,
            size=size,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        ),
        bgcolor=bg_color,
        border_radius=8,
        padding=pad,
        width=width,
        expand=expand,
        on_click=on_click_fn,
    )


def make_grid_rows(items: list, cols: int = 2, spacing: int = 6) -> list:
    """將任意數量的元件自動打包為指定欄數 (預設雙欄) 的並排 Row 清單，100% 適應手機窄螢幕"""
    rows = []
    for i in range(0, len(items), cols):
        chunk = items[i : i + cols]
        rows.append(ft.Row(chunk, spacing=spacing))
    return rows


def make_table_box(title: str, headers: list, rows: list, header_bg: str = "#1e3a8a"):
    header_cells = [
        ft.Container(content=ft.Text(str(h), size=11, weight=ft.FontWeight.BOLD, color="#90cdf4"), expand=1)
        for h in headers
    ]
    table_rows = [
        ft.Container(bgcolor=header_bg, padding=6, border_radius=6, content=ft.Row(header_cells, spacing=4))
    ]
    for idx, r in enumerate(rows):
        row_bg = "#1a2232" if idx % 2 == 0 else "#131824"
        row_cells = [
            ft.Container(content=ft.Text(str(c), size=11, color="#e2e8f0"), expand=1) for c in r
        ]
        table_rows.append(
            ft.Container(
                bgcolor=row_bg,
                padding=6,
                border_radius=4,
                content=ft.Row(row_cells, spacing=4),
            )
        )
    return ft.Container(
        bgcolor="#161b26",
        border_radius=10,
        padding=10,
        content=ft.Column(
            [
                ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                ft.Column(table_rows, spacing=3),
            ],
            spacing=6,
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

        # 1. 費波納契回撤支撐位 (Retracement: 由波段高點 Swing High 往下回撤計算買點支撐)
        ret_236 = round(swing_high - diff * 0.236, 2)
        ret_382 = round(swing_high - diff * 0.382, 2)
        ret_500 = round(swing_high - diff * 0.500, 2)
        ret_618 = round(swing_high - diff * 0.618, 2)
        ret_786 = round(swing_high - diff * 0.786, 2)

        # 2. 費波納契反彈與擴散目標位 (Bounce & Extension: 由波段低點 Swing Low 往上推算壓力與擴散目標)
        fib_236 = round(swing_low + diff * 0.236, 2)
        fib_382 = round(swing_low + diff * 0.382, 2)
        fib_500 = round(swing_low + diff * 0.500, 2)
        fib_618 = round(swing_low + diff * 0.618, 2)
        ext_1272 = round(swing_low + diff * 1.272, 2)
        ext_1618 = round(swing_low + diff * 1.618, 2)

        # 技術分析綜合診斷
        if current_price >= ma20 and ma20 >= ma50:
            trend_diag = "多頭排列 (站穩月/季線)"
        elif current_price >= ma20:
            trend_diag = "短多轉強 (站上20MA)"
        elif current_price >= ma50:
            trend_diag = "中期震盪 (月線下/季線上)"
        else:
            trend_diag = "空頭修正 (月/季線之下)"

        if current_price >= ret_236:
            fib_zone_diag = "強勢區 (高於回撤 0.236)"
        elif current_price >= ret_382:
            fib_zone_diag = "淺回撤支撐 (0.236~0.382)"
        elif current_price >= ret_500:
            fib_zone_diag = "中度回撤區 (0.382~0.500)"
        elif current_price >= ret_618:
            fib_zone_diag = "黃金分割支撐區 (0.5~0.618)"
        else:
            fib_zone_diag = "深度回撤超跌區 (<0.618)"

        res = {
            "Price": round(current_price, 2),
            "Reg_Close": round(reg_close, 2),
            "Day_Chg_Pct": round(day_chg_pct, 2),
            "Session": tk.session_label if get_extended else "日線收盤",
            "Swing_High": round(swing_high, 2),
            "Swing_Low": round(swing_low, 2),
            # 回撤支撐 (Retracement)
            "Ret_0236": ret_236,
            "Ret_0382": ret_382,
            "Ret_0500": ret_500,
            "Ret_0618": ret_618,
            "Ret_0786": ret_786,
            # 反彈與擴散 (Bounce & Extension)
            "Fib_0236": fib_236,
            "Fib_0382": fib_382,
            "Fib_0500": fib_500,
            "Fib_0618": fib_618,
            "Fib_1272": ext_1272,
            "Fib_1618": ext_1618,
            # 技術指標與診斷
            "ATR": round(atr_14, 2),
            "RSI": round(rsi_14, 1),
            "MA20": round(ma20, 2),
            "MA50": round(ma50, 2),
            "MA200": round(ma200, 2),
            "Trend_Diag": trend_diag,
            "Fib_Zone_Diag": fib_zone_diag,
        }
        QUOTE_CACHE[cache_key] = res
        return res
    except Exception:
        return None


def make_fallback_metrics(raw_price: float, sess_lbl: str = "預設/離線"):
    swing_high = round(raw_price * 1.25, 2)
    swing_low = round(raw_price * 0.85, 2)
    diff = max(swing_high - swing_low, 0.01)
    return {
        "Price": round(raw_price, 2),
        "Reg_Close": round(raw_price, 2),
        "Day_Chg_Pct": 0.0,
        "Session": sess_lbl,
        "Swing_High": swing_high,
        "Swing_Low": swing_low,
        "Ret_0236": round(swing_high - diff * 0.236, 2),
        "Ret_0382": round(swing_high - diff * 0.382, 2),
        "Ret_0500": round(swing_high - diff * 0.500, 2),
        "Ret_0618": round(swing_high - diff * 0.618, 2),
        "Ret_0786": round(swing_high - diff * 0.786, 2),
        "Fib_0236": round(swing_low + diff * 0.236, 2),
        "Fib_0382": round(swing_low + diff * 0.382, 2),
        "Fib_0500": round(swing_low + diff * 0.500, 2),
        "Fib_0618": round(swing_low + diff * 0.618, 2),
        "Fib_1272": round(swing_low + diff * 1.272, 2),
        "Fib_1618": round(swing_low + diff * 1.618, 2),
        "ATR": round(raw_price * 0.045, 2),
        "RSI": 50.0,
        "MA20": round(raw_price, 2),
        "MA50": round(raw_price * 0.98, 2),
        "MA200": round(raw_price * 0.92, 2),
        "Trend_Diag": "離線估算模式",
        "Fib_Zone_Diag": "黃金分割支撐區",
    }


async def main(page: ft.Page):
    page.title = "美股量化風控 × 費波納契 × 半凱利"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e1117"
    page.padding = 8
    page.scroll = ft.ScrollMode.AUTO

    try:
        await _build(page)
    except Exception as e:
        import traceback
        page.add(ft.Text(f"啟動錯誤: {e}", color="#fc8181", size=14, selectable=True))
        page.add(ft.Text(traceback.format_exc(), size=11, color="#e2e8f0", selectable=True))
        page.update()


async def _build(page: ft.Page):
    portfolio_data = [dict(item) for item in DEFAULT_PORTFOLIO]
    active_page_idx = [0]       # 頂部 5 大主分頁索引
    page1_sub_mode = [0]        # 分頁 2 子模式: 0=持倉總表, 1=個股編輯/新增
    selected_stock_idx = [0]    # 分頁 2 選中的個股索引
    page2_fib_stock_idx = [0]   # 分頁 3 選中檢視回撤/擴散的個股索引
    page3_calc_sub_tab = [0]    # 分頁 4 試算結果子分頁: 0=技術與回撤, 1=兩批加碼保本, 2=費氏減碼

    sw_live = ft.Switch(label="自動抓報價", value=True)
    sw_ext = ft.Switch(label="含盤前盤後", value=True)
    sw_trading_days = ft.Switch(label="美股交易日", value=True)
    tf_anchor_date = ft.TextField(label="T+0 起始日", value="2026-10-16", expand=1, height=46, text_size=13)
    tf_cash = ft.TextField(label="美元現金池 ($)", value="9616.50", expand=1, height=48, text_size=13)
    tf_tax = ft.TextField(label="累計抵稅虧損 ($)", value="-3461.52", expand=1, height=48, text_size=13)
    tf_shock = ft.TextField(label="大盤衝擊 (%)", value="0", expand=1, height=48, text_size=13)
    tf_beta = ft.TextField(label="Beta敏感倍數", value="1.50", expand=1, height=48, text_size=13)
    status_text = ft.Text("就緒", size=11, color="#68d391")
    loading_bar = ft.ProgressBar(visible=False, color="#ecc94b", bgcolor="#1e2536")

    main_nav_col = ft.Column(spacing=5)
    page0_overview_col = ft.Column(spacing=8, visible=True)   # 分頁1: 總覽設定
    page1_holdings_col = ft.Column(spacing=8, visible=False)  # 分頁2: 風控持倉
    page2_fib_col = ft.Column(spacing=8, visible=False)       # 分頁3: 費氏週期與回撤
    page3_calc_col = ft.Column(spacing=8, visible=False)      # 分頁4: 加減碼與新股試算
    page4_trim_col = ft.Column(spacing=8, visible=False)      # 分頁5: 雙核心減碼

    kpi_grid_col = ft.Column(spacing=6)
    tz_header_text = ft.Text("費波納契時間週期變盤視窗", size=13, weight=ft.FontWeight.BOLD, color="#f7fafc")
    tz_grid_col = ft.Column(spacing=6)
    fib_analysis_col = ft.Column(spacing=6)

    t4_ticker_tf = ft.TextField(label="美股代號 (可填新股)", value="NBIS", expand=1, height=46, text_size=13)
    t4_shares_tf = ft.TextField(label="目前股數 (新股填0)", value="550", expand=1, height=46, text_size=13)
    t4_cost_tf = ft.TextField(label="持有均價 ($)", value="226.215", expand=1, height=46, text_size=13)
    t4_kelly_tf = ft.TextField(label="凱利上限 (%)", value="15.0", expand=1, height=46, text_size=13)
    t4_budget_tf = ft.TextField(label="預計加碼預算 ($)", value="9616.50", expand=1, height=46, text_size=13)
    t4_result_col = ft.Column(spacing=8)

    page_titles = [
        "📊 總覽設定",
        "🛡️ 風控持倉",
        "⏳ 費氏週期/回撤",
        "🧮 加減碼/新股",
        "🎯 雙核心減碼",
    ]

    def render_main_nav():
        main_nav_col.controls.clear()
        btns = []
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

            btns.append(
                make_btn(
                    title,
                    make_page_sw(idx),
                    bg_color="#2563eb" if is_act else "#1e293b",
                    text_color="#ffffff" if is_act else "#a0aec0",
                    pad=7,
                    expand=1,
                    size=12,
                )
            )
        # 頂部導覽固定分成兩排並排 (第一排 3 個、第二排 2 個)，整齊不佔空間
        main_nav_col.controls.append(ft.Row(btns[:3], spacing=5))
        main_nav_col.controls.append(ft.Row(btns[3:], spacing=5))

    def parse_anchor_date() -> datetime.date:
        raw_str = (tf_anchor_date.value or "").strip().replace("/", "-")
        try:
            return datetime.datetime.strptime(raw_str, "%Y-%m-%d").date()
        except Exception:
            tf_anchor_date.value = "2026-10-16"
            return datetime.date(2026, 10, 16)

    def render_time_zones():
        tz_grid_col.controls.clear()
        base_dt = parse_anchor_date()
        use_b_days = sw_trading_days.value
        mode_str = "交易日" if use_b_days else "日曆天"
        tz_header_text.value = f"費氏變盤時間窗 (T+0: {base_dt.strftime('%Y/%m/%d')} | {mode_str})"
        fib_specs = [
            (5, "T+5 短線確認", "檢視短均線翻揚", "#ed8936"),
            (8, "T+8 第一減碼", "0.236~0.382壓力", "#ecc94b"),
            (13, "T+13 波段分水嶺", "20MA扣抵減碼", "#4299e1"),
            (21, "T+21 中期轉折", "0.618黃金分割壓", "#48bb78"),
            (34, "T+34 季線變盤", "季線定調再平衡", "#9f7aea"),
        ]
        today_dt = datetime.date.today()
        computed_tz = []
        for f_num, title, desc, color in fib_specs:
            t_dt = add_us_trading_days(base_dt, f_num) if use_b_days else base_dt + datetime.timedelta(days=f_num)
            d_left = (t_dt - today_dt).days
            computed_tz.append((title, t_dt, d_left, desc, color))
        upcoming = [item[2] for item in computed_tz if item[2] >= 0]
        highlight_days = min(upcoming) if upcoming else None

        tz_cards = []
        for title, t_dt, d_left, desc, color in computed_tz:
            if d_left > 0:
                day_badge = f"剩{d_left}天"
            elif d_left == 0:
                day_badge = "今日變盤"
            else:
                day_badge = f"過{abs(d_left)}天"
            is_hl = highlight_days is not None and d_left == highlight_days
            tz_cards.append(
                ft.Container(
                    expand=1,
                    bgcolor="#1e3a8a" if is_hl else "#131824",
                    border_radius=8,
                    padding=8,
                    content=ft.Column(
                        [
                            ft.Text(f"{title} ({day_badge})", color=color, size=11, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{t_dt.strftime('%Y/%m/%d')} | {desc}", color="#e2e8f0", size=11),
                        ],
                        spacing=2,
                    ),
                )
            )
        # 2x2 + 1 強制雙欄並排，徹底解決第 3 張圖太長的問題
        tz_grid_col.controls.extend(make_grid_rows(tz_cards, cols=2, spacing=6))

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

            if not q:
                fallback_p = float(item.get("Manual_Price", item.get("Avg_Cost", 100.0)))
                q = make_fallback_metrics(fallback_p)

            raw_price = q["Price"]
            sim_price = round(raw_price * shock_factor, 2)
            shares = int(float(item.get("Shares", 0)))
            avg_cost = float(item.get("Avg_Cost", sim_price))
            mkt_val = round(shares * sim_price, 2)
            cost_val = round(shares * avg_cost, 2)
            pnl = round(mkt_val - cost_val, 2)
            pnl_pct = round((pnl / cost_val) * 100.0, 2) if cost_val > 0 else 0.0

            row_dict = dict(q)
            row_dict.update({
                "Ticker": tkr,
                "Name": item.get("Name", tkr),
                "Shares": shares,
                "Avg_Cost": round(avg_cost, 3),
                "Price": sim_price,
                "Market_Value": mkt_val,
                "Total_Cost": cost_val,
                "PnL": pnl,
                "PnL_Pct": pnl_pct,
                "Key_Fib_Target": float(item.get("Key_Fib_Target", q["Fib_0382"])),
                "Hard_Stop": float(item.get("Hard_Stop", round(sim_price - 2 * q["ATR"], 2))),
                "Target_Kelly_Pct": float(item.get("Target_Kelly_Pct", 15.0)),
            })
            live_rows.append(row_dict)

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

        # --- 分頁 1 KPI 卡片改為強制雙欄並排 (2x2 + 1) ---
        kpi_grid_col.controls.clear()
        pnl_color = "#48bb78" if total_pnl >= 0 else "#f56565"
        conc_color = "#ecc94b" if top2_conc > 35 else "#48bb78"
        kpi_specs = [
            ("總淨值 (股+現)", f"${total_portfolio_equity:,.0f}", f"股${total_stock_val:,.0f}/現${cash_pool:,.0f}", "#f7fafc"),
            ("未實現總損益", f"${total_pnl:,.0f} ({total_pnl_pct:+.1f}%)", "持倉浮動損益", pnl_color),
            ("前兩大集中度", f"{top2_conc:.1f}%", "半凱利上限 <= 35%", conc_color),
            ("單週 95% VaR", f"-${weekly_var_95:,.0f}", f"單日VaR -${daily_var_95:,.0f}", "#f56565"),
            ("可動用現金 + 超配減碼釋出資金", f"${releasable_cash:,.0f}", f"含可用現金 ${cash_pool:,.0f} | 累計抵稅額 ${realized_loss_tax:,.0f}", "#48bb78"),
        ]
        kpi_cards = []
        for k_title, k_val, k_sub, k_col in kpi_specs:
            kpi_cards.append(
                ft.Container(
                    expand=1,
                    bgcolor="#161b26",
                    border_radius=8,
                    padding=8,
                    content=ft.Column(
                        [
                            ft.Text(k_title, color="#a0aec0", size=11),
                            ft.Text(k_val, color=k_col, size=15, weight=ft.FontWeight.BOLD),
                            ft.Text(k_sub, color="#718096", size=10),
                        ],
                        spacing=2,
                    ),
                )
            )
        kpi_grid_col.controls.extend(make_grid_rows(kpi_cards, cols=2, spacing=6))

        render_time_zones()
        build_page1_holdings(live_rows)
        build_page2_fib_analysis(live_rows)
        build_page3_calc(live_rows, total_portfolio_equity, cash_pool)
        build_page4_trim(live_rows)
        page.update()

    def refresh_all(force_api: bool = False, use_network: bool = True):
        async def _task():
            loading_bar.visible = True
            status_text.value = "同步報價中..." if use_network else "計算中..."
            page.update()
            try:
                res = await asyncio.to_thread(compute_rows, use_network, force_api)
                update_ui_from_rows(*res)
                status_text.value = f"更新: {datetime.datetime.now().strftime('%H:%M:%S')}"
            except Exception as ex:
                status_text.value = f"異常: {ex}"
            finally:
                loading_bar.visible = False
                page.update()

        page.run_task(_task)

    # --- 分頁 2：風控持倉（拆分為「📋 持倉總表」與「✏️ 編輯/新增個股」子分頁，避免上下疊加過長） ---
    def build_page1_holdings(live_rows: list):
        page1_holdings_col.controls.clear()

        def sw_sub_mode(m):
            def _fn(e):
                page1_sub_mode[0] = m
                build_page1_holdings(live_rows)
                page.update()
            return _fn

        mode_bar = ft.Row([
            make_btn("📋 持倉風控總表", sw_sub_mode(0), "#38a169" if page1_sub_mode[0] == 0 else "#1e293b", expand=1, pad=8),
            make_btn("✏️ 編輯 / 新增個股", sw_sub_mode(1), "#38a169" if page1_sub_mode[0] == 1 else "#1e293b", expand=1, pad=8),
        ], spacing=6)
        page1_holdings_col.controls.append(mode_bar)

        if page1_sub_mode[0] == 0:
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
            page1_holdings_col.controls.append(make_table_box("持倉風控總覽表 (點上方可切換編輯)", headers, rows, "#1e3a8a"))
            return

        # 子模式 1：編輯或新增單一個股
        sub_nav_row = ft.Row(wrap=True, spacing=5)
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
                    bg_color="#2563eb" if is_sel else "#1e293b",
                    text_color="#ffffff" if is_sel else "#90cdf4",
                    pad=7,
                )
            )

        is_add_tab = selected_stock_idx[0] == len(live_rows)

        def sel_add_tab(e):
            selected_stock_idx[0] = len(live_rows)
            build_page1_holdings(live_rows)
            page.update()

        sub_nav_row.controls.append(
            make_btn("+ 新增股票", sel_add_tab, bg_color="#dd6b20" if is_add_tab else "#1e293b", text_color="#ffffff" if is_add_tab else "#fbd38d", pad=7)
        )

        page1_holdings_col.controls.append(
            ft.Container(
                bgcolor="#161b26",
                border_radius=10,
                padding=10,
                content=ft.Column([
                    ft.Text("選擇要修改的持股或新增：", size=12, color="#90cdf4"),
                    sub_nav_row,
                ], spacing=6),
            )
        )

        if not is_add_tab and 0 <= selected_stock_idx[0] < len(live_rows):
            idx = selected_stock_idx[0]
            r = live_rows[idx]
            tf_s = ft.TextField(label="股數", value=str(r["Shares"]), expand=1, height=46, text_size=13)
            tf_c = ft.TextField(label="均價($)", value=str(r["Avg_Cost"]), expand=1, height=46, text_size=13)
            tf_p = ft.TextField(label="離線價($)", value=str(r["Price"]), expand=1, height=46, text_size=13)
            tf_k = ft.TextField(label="凱利(%)", value=str(r["Target_Kelly_Pct"]), expand=1, height=46, text_size=13)
            tf_f = ft.TextField(label="費氏目標", value=str(r["Key_Fib_Target"]), expand=1, height=46, text_size=13)
            tf_h = ft.TextField(label="停損價", value=str(r["Hard_Stop"]), expand=1, height=46, text_size=13)

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
                page1_sub_mode[0] = 0
                refresh_all(force_api=False, use_network=False)

            def _del_cur(e):
                if 0 <= idx < len(portfolio_data):
                    portfolio_data.pop(idx)
                    selected_stock_idx[0] = 0
                    page1_sub_mode[0] = 0
                    refresh_all(force_api=False, use_network=False)

            pnl_c = "#48bb78" if r["PnL"] >= 0 else "#f56565"
            page1_holdings_col.controls.append(
                ft.Container(
                    bgcolor="#161b26",
                    border_radius=10,
                    padding=10,
                    content=ft.Column([
                        ft.Text(f"{r['Ticker']} ({r['Name']}) 現價 ${r['Price']:.2f} [{r['Session']}]", size=13, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ft.Text(f"損益: ${r['PnL']:,.0f} ({r['PnL_Pct']:+.1f}%) | 權重: {r['Weight_Pct']:.1f}% | {r['Action_Signal']}", size=12, color=pnl_c),
                        ft.Row([tf_s, tf_c], spacing=6),
                        ft.Row([tf_p, tf_k], spacing=6),
                        ft.Row([tf_f, tf_h], spacing=6),
                        ft.Row([
                            make_btn("💾 儲存並返回總表", _save_cur, "#2563eb", pad=9, expand=1),
                            make_btn("🗑️ 刪除此股", _del_cur, "#9b2c2c", pad=9, expand=1),
                        ], spacing=8),
                    ], spacing=6),
                )
            )
        else:
            new_tkr_tf = ft.TextField(label="美股代號 (如 INTC)", value="", expand=1, height=46, text_size=13)
            new_sh_tf = ft.TextField(label="股數", value="50", expand=1, height=46, text_size=13)
            new_cost_tf = ft.TextField(label="均價($)", value="100.0", expand=1, height=46, text_size=13)
            new_kelly_tf = ft.TextField(label="凱利(%)", value="15.0", expand=1, height=46, text_size=13)

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
                page1_sub_mode[0] = 0
                refresh_all(force_api=True, use_network=True)

            page1_holdings_col.controls.append(
                ft.Container(
                    bgcolor="#152238",
                    border_radius=10,
                    padding=10,
                    content=ft.Column([
                        ft.Text("新增美股到追蹤主表 (加入後自動聯網抓價)", size=13, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                        ft.Row([new_tkr_tf, new_sh_tf], spacing=6),
                        ft.Row([new_cost_tf, new_kelly_tf], spacing=6),
                        make_btn("➕ 確認加入並抓取最新報價", add_new_stock, "#38a169", pad=9),
                    ], spacing=6),
                )
            )

    # --- 分頁 3：費波納契時間週期 + 空間回撤(Retracement)與擴散(Extension)雙欄分析 ---
    def build_page2_fib_analysis(live_rows: list):
        fib_analysis_col.controls.clear()
        if not live_rows:
            return

        # 1. 各股權重與目標雙欄緊湊小卡 (2x3 並排，高度減半)
        compact_cards = []
        for idx, r in enumerate(live_rows):
            w_pct = r["Weight_Pct"]
            k_pct = r["Target_Kelly_Pct"]
            w_color = "#f56565" if w_pct > k_pct else "#48bb78"
            is_sel = page2_fib_stock_idx[0] == idx

            def make_sel_fib(i):
                def _fn(e):
                    page2_fib_stock_idx[0] = i
                    build_page2_fib_analysis(live_rows)
                    page.update()
                return _fn

            compact_cards.append(
                ft.Container(
                    expand=1,
                    bgcolor="#1e3a8a" if is_sel else "#161b26",
                    border_radius=8,
                    padding=8,
                    on_click=make_sel_fib(idx),
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"{r['Ticker']} ${r['Price']:.1f}", size=12, weight=ft.FontWeight.BOLD, color="#ffffff"),
                            ft.Text(f"{w_pct:.1f}%/{k_pct:.0f}%", size=11, color=w_color, weight=ft.FontWeight.BOLD),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.ProgressBar(value=min(w_pct / 40.0, 1.0), color=w_color, bgcolor="#0e1117"),
                        ft.Text(f"停損${r['Hard_Stop']:.0f} | 目標${r['Key_Fib_Target']:.0f}", size=10, color="#cbd5e0"),
                    ], spacing=3),
                )
            )

        fib_analysis_col.controls.append(
            ft.Text("點選下方股票卡，檢視該股「費氏回撤支撐 & 擴散目標」：", size=12, weight=ft.FontWeight.BOLD, color="#90cdf4")
        )
        fib_analysis_col.controls.extend(make_grid_rows(compact_cards, cols=2, spacing=6))

        # 2. 選中個股的「費波納契回撤 (Retracement) 與擴散 (Extension)」對照表
        if page2_fib_stock_idx[0] >= len(live_rows):
            page2_fib_stock_idx[0] = 0
        sr = live_rows[page2_fib_stock_idx[0]]
        cur_p = sr["Price"]

        def _dist_str(lvl):
            d = ((lvl - cur_p) / cur_p * 100.0) if cur_p else 0.0
            return f"${lvl:.2f} ({d:+.1f}%)"

        fib_headers = ["費氏回撤 (高點回落支撐)", "回撤價位", "費氏反彈/擴散 (低點推升)", "擴散價位"]
        fib_rows = [
            ["波段高點 (Swing High)", f"${sr['Swing_High']:.2f}", "波段低點 (Swing Low)", f"${sr['Swing_Low']:.2f}"],
            ["回撤 0.236 (強勢淺回檔)", _dist_str(sr["Ret_0236"]), "反彈 0.382 (初步壓力)", _dist_str(sr["Fib_0382"])],
            ["回撤 0.382 (波段第一支撐)", _dist_str(sr["Ret_0382"]), "反彈 0.500 (中軸頸線)", _dist_str(sr["Fib_0500"])],
            ["回撤 0.500 (多空二分位)", _dist_str(sr["Ret_0500"]), "反彈 0.618 (黃金分割壓)", _dist_str(sr["Fib_0618"])],
            ["回撤 0.618 (黃金分割買點)", _dist_str(sr["Ret_0618"]), "擴散 1.272 (波段延伸一)", _dist_str(sr["Fib_1272"])],
            ["回撤 0.786 (深度防守底線)", _dist_str(sr["Ret_0786"]), "擴散 1.618 (波段延伸二)", _dist_str(sr["Fib_1618"])],
        ]
        fib_analysis_col.controls.append(
            make_table_box(
                f"📐 {sr['Ticker']} 費波納契回撤支撐 vs 擴散目標 ({sr['Fib_Zone_Diag']})",
                fib_headers,
                fib_rows,
                "#2c5282",
            )
        )

    # --- 分頁 4：加減碼試算 + 非持股新標的即時抓價與技術分析 (搭配 3 子分頁避免頁面過長) ---
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
                    run_tab4_engine(fetch_online=False)
                return _sel
            chip_buttons.append(make_btn(r["Ticker"], make_chip_fn(r), "#1e293b", "#90cdf4", pad=6))

        def set_new_stock_mode(e):
            t4_ticker_tf.value = "NVDA"
            t4_shares_tf.value = "0"
            t4_cost_tf.value = "0"
            t4_kelly_tf.value = "15.0"
            run_tab4_engine(fetch_online=True)

        chip_buttons.append(make_btn("✨ 試算非持股新標的", set_new_stock_mode, "#dd6b20", "#ffffff", pad=6))

        def render_tab4_output(q_info: dict, target_ticker: str, sim_cur_shares: int, sim_cur_cost: float, sim_kelly_pct: float, budget_limit: float):
            t4_result_col.controls.clear()
            live_p = q_info["Price"]
            live_atr = q_info["ATR"]
            live_ma20 = q_info["MA20"]
            live_ma50 = q_info["MA50"]
            live_ma200 = q_info["MA200"]
            live_rsi = q_info["RSI"]
            swing_high = q_info["Swing_High"]
            swing_low = q_info["Swing_Low"]
            ret_382 = q_info["Ret_0382"]
            ret_500 = q_info["Ret_0500"]
            ret_618 = q_info["Ret_0618"]
            fib_236_lvl = q_info["Fib_0236"]
            fib_382_lvl = q_info["Fib_0382"]
            fib_618_lvl = q_info["Fib_0618"]
            fib_1272_lvl = q_info["Fib_1272"]

            is_new_stock = sim_cur_shares <= 0
            if sim_cur_cost <= 0 or is_new_stock:
                sim_cur_cost = live_p

            cur_invested_cost = round(sim_cur_shares * sim_cur_cost, 2)
            cur_mkt_val = round(sim_cur_shares * live_p, 2)
            # 若為非持股新標的，投入後總淨值以目前總淨值計算目標凱利上限
            cur_weight_pct = (cur_mkt_val / total_portfolio_equity * 100.0) if total_portfolio_equity > 0 else 0.0
            max_kelly_val = total_portfolio_equity * (sim_kelly_pct / 100.0)
            max_kelly_shares = int(math.floor(max_kelly_val / live_p)) if live_p > 0 else 0
            remaining_kelly_val = max(0.0, max_kelly_val - cur_mkt_val)
            effective_add_budget = min(remaining_kelly_val, budget_limit) if remaining_kelly_val > 0 else 0.0

            # 進場價位設計：結合現價、ATR 與費氏回撤支撐位
            buy_p1 = round(live_p, 2)
            buy_p2 = round(max(min(live_p - 1.0 * live_atr, ret_382), swing_low, live_p * 0.90), 2)

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

            # 頂部狀態摘要卡
            tag_str = "【非持股新標的建倉試算】" if is_new_stock else "【現有持股補倉試算】"
            msg_col = "#fc8181" if cur_weight_pct >= sim_kelly_pct else "#68d391"
            msg_txt = (
                "權重已超標，禁止向下攤平！請優先減碼。"
                if cur_weight_pct >= sim_kelly_pct
                else f"可動用加碼預算：${effective_add_budget:,.0f} | 兩批完買後保本均價：${final_breakeven_avg:.2f}"
            )
            t4_result_col.controls.append(
                ft.Container(
                    bgcolor="#161b26",
                    border_radius=8,
                    padding=8,
                    content=ft.Column([
                        ft.Text(f"{tag_str} {target_ticker} 現價 ${live_p:.2f} ({q_info['Day_Chg_Pct']:+.2f}%) | 權重 {cur_weight_pct:.1f}% / 上限 {sim_kelly_pct:.1f}% ({max_kelly_shares}股)", size=12, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ft.Text(msg_txt, size=12, color=msg_col, weight=ft.FontWeight.BOLD),
                    ], spacing=3),
                )
            )

            # 結果子分頁切換器 (避免 3 張大表同時堆疊拉長畫面)
            def sw_calc_tab(idx):
                def _fn(e):
                    page3_calc_sub_tab[0] = idx
                    render_tab4_output(q_info, target_ticker, sim_cur_shares, sim_cur_cost, sim_kelly_pct, budget_limit)
                return _fn

            sub_tabs_row = ft.Row([
                make_btn("📊 技術與費氏回撤", sw_calc_tab(0), "#2563eb" if page3_calc_sub_tab[0] == 0 else "#1e293b", expand=1, pad=7),
                make_btn("➕ 兩批加碼保本表", sw_calc_tab(1), "#2563eb" if page3_calc_sub_tab[0] == 1 else "#1e293b", expand=1, pad=7),
                make_btn("🎯 費氏階梯減碼表", sw_calc_tab(2), "#2563eb" if page3_calc_sub_tab[0] == 2 else "#1e293b", expand=1, pad=7),
            ], spacing=5)
            t4_result_col.controls.append(sub_tabs_row)

            if page3_calc_sub_tab[0] == 0:
                tech_headers = ["技術與費氏回撤指標", "數值 / 價位", "實戰量化操作判讀"]
                rsi_diag = "超買區 (留意追高風險)" if live_rsi >= 70 else ("超賣區 (醞釀反彈買點)" if live_rsi <= 35 else "中性動能區間")
                tech_rows = [
                    ["均線趨勢結構", f"20MA ${live_ma20:.2f}", f"{q_info['Trend_Diag']} | 50MA ${live_ma50:.2f} / 200MA ${live_ma200:.2f}"],
                    ["RSI(14) / ATR(14)", f"RSI {live_rsi:.1f} / ATR ${live_atr:.2f}", f"{rsi_diag} | 單日正常波動 ±${live_atr:.2f}"],
                    ["近半年波段高低", f"高 ${swing_high:.2f} / 低 ${swing_low:.2f}", q_info["Fib_Zone_Diag"]],
                    ["費氏回撤 0.382 支撐", f"${ret_382:.2f}", "強勢多頭回檔第一批低接參考價"],
                    ["費氏回撤 0.500 支撐", f"${ret_500:.2f}", "波段中軸支撐，適合分批逢低佈局"],
                    ["費氏回撤 0.618 支撐", f"${ret_618:.2f}", "黃金分割強支撐買點 (跌破轉弱)"],
                    ["費氏擴散 1.272 目標", f"${fib_1272_lvl:.2f}", "突破前高後之波段延伸停利目標"],
                ]
                t4_result_col.controls.append(
                    make_table_box(f"{target_ticker} 即時技術分析與費波納契回撤支撐診斷", tech_headers, tech_rows, "#2c5282")
                )
            elif page3_calc_sub_tab[0] == 1:
                addon_headers = ["階段", "建議買價", "股數", "動用資金", "補倉後保本均價"]
                addon_rows = [
                    ["原持倉", f"${sim_cur_cost:.2f}" if not is_new_stock else "$0 (新股)", f"{sim_cur_shares}股", f"${cur_invested_cost:,.0f}", f"${sim_cur_cost:.2f}" if not is_new_stock else "-"],
                    ["第一批40% (右側現價)", f"${buy_p1:.2f}", f"+{b1_shares}股", f"${b1_fund:,.0f}", f"${after_b1_avg:.2f}"],
                    ["第二批60% (回撤/ATR)", f"${buy_p2:.2f}", f"+{b2_shares}股", f"${b2_fund:,.0f}", f"${final_breakeven_avg:.2f}"],
                    ["兩批合計總結", "-", f"共{final_total_shares}股", f"${total_addon_fund:,.0f}", f"保本 ${final_breakeven_avg:.2f}"],
                ]
                t4_result_col.controls.append(
                    make_table_box(f"{target_ticker} 兩批加碼與補倉保本均價試算表", addon_headers, addon_rows, "#22543d")
                )
            else:
                trim_headers = ["費氏區間", "目標價", "比例", "減碼股數", "回收現金"]
                base_sh = final_total_shares if final_total_shares > 0 else max_kelly_shares
                s_236 = int(math.floor(base_sh * 0.25))
                s_382 = int(math.floor(base_sh * 0.25))
                s_618 = int(math.floor(base_sh * 0.25))
                s_1272 = max(0, base_sh - s_236 - s_382 - s_618)
                trim_rows = [
                    ["Fib 0.236 反彈", f"${fib_236_lvl:.2f}", "25%", f"{s_236}股", f"${s_236 * fib_236_lvl:,.0f}"],
                    ["Fib 0.382 壓力", f"${fib_382_lvl:.2f}", "25%", f"{s_382}股", f"${s_382 * fib_382_lvl:,.0f}"],
                    ["Fib 0.618 分割", f"${fib_618_lvl:.2f}", "25%", f"{s_618}股", f"${s_618 * fib_618_lvl:,.0f}"],
                    ["Fib 1.272 擴散", f"${fib_1272_lvl:.2f}", "25%", f"{s_1272}股", f"${s_1272 * fib_1272_lvl:,.0f}"],
                    ["ATR 破位停損線", f"${hard_stop_price:.2f}", "破位", "強制風控", "跌破無條件停損"],
                ]
                t4_result_col.controls.append(
                    make_table_box(f"{target_ticker} 費波納契階梯減碼與停損表 (以 {base_sh} 股計)", trim_headers, trim_rows, "#1e3a8a")
                )
            page.update()

        def run_tab4_engine(fetch_online: bool = False):
            target_ticker = (t4_ticker_tf.value or "").strip().upper()
            if not target_ticker:
                return
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

            matched = next((x for x in live_rows if x["Ticker"] == target_ticker), None)
            cached = QUOTE_CACHE.get(f"{target_ticker}_{sw_ext.value}")

            # 若點選「抓最新價並技術分析」或輸入了不在持股中的新股票代號，自動在背景聯網抓取 Yahoo Finance 報價與技術指標
            if fetch_online or (not matched and not cached):
                async def _fetch_new_tkr():
                    loading_bar.visible = True
                    status_text.value = f"正在抓取 {target_ticker} 最新報價與費氏指標..."
                    page.update()
                    q_new = await asyncio.to_thread(fetch_quant_metrics, target_ticker, sw_ext.value, True)
                    if not q_new:
                        fb_p = sim_cur_cost if sim_cur_cost > 0 else 100.0
                        q_new = make_fallback_metrics(fb_p, "查無代號/預設")
                        status_text.value = f"{target_ticker} 抓價失敗，改用預設值"
                    else:
                        if sim_cur_shares == 0:
                            t4_cost_tf.value = str(q_new["Price"])
                        status_text.value = f"已載入 {target_ticker} 最新價 ${q_new['Price']:.2f}"
                    loading_bar.visible = False
                    render_tab4_output(q_new, target_ticker, sim_cur_shares, sim_cur_cost, sim_kelly_pct, budget_limit)

                page.run_task(_fetch_new_tkr)
            else:
                q_use = matched if matched else cached
                render_tab4_output(q_use, target_ticker, sim_cur_shares, sim_cur_cost, sim_kelly_pct, budget_limit)

        page3_calc_col.controls.append(
            ft.Container(
                bgcolor="#161b26",
                border_radius=10,
                padding=10,
                content=ft.Column([
                    ft.Text("點選現有持股，或輸入任意美股代號試算新股建倉：", size=12, weight=ft.FontWeight.BOLD, color="#90cdf4"),
                    ft.Row(chip_buttons, wrap=True, spacing=5),
                    ft.Row([t4_ticker_tf, t4_shares_tf, t4_cost_tf], spacing=6),
                    ft.Row([t4_kelly_tf, t4_budget_tf], spacing=6),
                    ft.Row([
                        make_btn("🔍 抓最新價並技術分析", lambda e: run_tab4_engine(True), "#38a169", pad=9, expand=1),
                        make_btn("🧮 依目前數值重算", lambda e: run_tab4_engine(False), "#2563eb", pad=9, expand=1),
                    ], spacing=6),
                ], spacing=6),
            )
        )
        page3_calc_col.controls.append(t4_result_col)
        run_tab4_engine(fetch_online=False)

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

    # 組裝分頁 1 (總覽設定：KPI 雙欄並排 + 參數雙欄並排)
    page0_overview_col.controls.extend([
        kpi_grid_col,
        ft.Container(
            bgcolor="#161b26",
            border_radius=10,
            padding=10,
            content=ft.Column([
                ft.Text("全域資金與大盤壓力測試設定", size=13, weight=ft.FontWeight.BOLD, color="#90cdf4"),
                ft.Row([sw_live, sw_ext], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([tf_cash, tf_tax], spacing=6),
                ft.Row([tf_shock, tf_beta], spacing=6),
                ft.Row([
                    make_btn("⚡ 套用重算", lambda e: refresh_all(False, False), "#38a169", pad=8, expand=1),
                    make_btn("🔄 更新報價", lambda e: refresh_all(True, True), "#2563eb", pad=8, expand=1),
                    make_btn("↩️ 重置", reset_defaults, "#4a5568", pad=8, expand=1),
                ], spacing=6),
            ], spacing=6),
        ),
    ])

    # 組裝分頁 3 (費氏週期雙欄並排 + 費氏回撤與擴散分析)
    page2_fib_col.controls.extend([
        ft.Container(
            bgcolor="#161b26",
            border_radius=10,
            padding=10,
            content=ft.Column([
                tz_header_text,
                ft.Row([
                    tf_anchor_date,
                    make_btn("10/16", lambda e: set_quick_anchor("2026-10-16"), "#1e293b", "#90cdf4", pad=8),
                    make_btn("今天", lambda e: set_quick_anchor(datetime.date.today().strftime("%Y-%m-%d")), "#1e293b", "#fbd38d", pad=8),
                ], spacing=6),
                sw_trading_days,
                tz_grid_col,
            ], spacing=6),
        ),
        fib_analysis_col,
    ])

    render_main_nav()
    page.controls.clear()
    page.add(
        ft.Container(
            bgcolor="#161b26",
            border_radius=10,
            padding=8,
            content=ft.Column([
                ft.Row([
                    ft.Text("美股量化風控 × 費氏 × 半凱利", size=16, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    status_text,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                loading_bar,
                main_nav_col,
            ], spacing=5),
        ),
        page0_overview_col,
        page1_holdings_col,
        page2_fib_col,
        page3_calc_col,
        page4_trim_col,
    )

    # 先以預設/快取數據秒開渲染，再於背景非阻塞更新即時報價
    init_res = compute_rows(use_network=False, force_api=False)
    update_ui_from_rows(*init_res)
    refresh_all(force_api=False, use_network=True)


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)