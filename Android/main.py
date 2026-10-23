import asyncio
import datetime
import json
import math
import random
import ssl
import urllib.request
import flet as ft


def _make_ssl_ctx():
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except Exception:
        return None


SSL_CTX = _make_ssl_ctx()


class _YFTicker:
    """多層報價架構：Yahoo Q1主線 -> Yahoo Q2備援 -> Stooq獨立美股備援 -> 外層離線降級"""

    def __init__(self, symbol, include_prepost: bool = True):
        self.symbol = symbol.strip().upper()
        self.closes = []
        self.highs = []
        self.lows = []
        self.dates = []
        self.ext_price = None
        self.session_label = "日線收盤"
        self.fetch_ok = False
        self.source_node = "離線"

        prepost_str = "true" if include_prepost else "false"
        hosts = [
            ("query1.finance.yahoo.com", "Q1"),
            ("query2.finance.yahoo.com", "Q2"),
        ]
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }

        for host, node_lbl in hosts:
            try:
                url = (
                    f"https://{host}/v8/finance/chart/"
                    f"{self.symbol}?interval=1d&range=1y&includePrePost={prepost_str}"
                )
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=7, context=SSL_CTX) as resp:
                    r = json.loads(resp.read().decode("utf-8"))
                res = r.get("chart", {}).get("result", [])
                if res:
                    meta = res[0].get("meta", {})
                    timestamps = res[0].get("timestamp") or []
                    q = res[0].get("indicators", {}).get("quote", [{}])[0]
                    closes = q.get("close") or []
                    highs = q.get("high") or []
                    lows = q.get("low") or []
                    for i, c in enumerate(closes):
                        if c is None:
                            continue
                        h = highs[i] if i < len(highs) and highs[i] is not None else c
                        l = lows[i] if i < len(lows) and lows[i] is not None else c
                        dt = (
                            datetime.date.fromtimestamp(timestamps[i])
                            if i < len(timestamps)
                            else datetime.date.today()
                        )
                        self.closes.append(float(c))
                        self.highs.append(float(h))
                        self.lows.append(float(l))
                        self.dates.append(dt)

                    if len(self.closes) >= 2:
                        self.fetch_ok = True
                        self.source_node = node_lbl
                        self.session_label = f"收盤({node_lbl})"
                        if include_prepost:
                            post_p = meta.get("postMarketPrice")
                            pre_p = meta.get("preMarketPrice")
                            reg_p = meta.get("regularMarketPrice")
                            if post_p:
                                self.ext_price = float(post_p)
                                self.session_label = f"盤後({node_lbl})"
                            elif pre_p:
                                self.ext_price = float(pre_p)
                                self.session_label = f"盤前({node_lbl})"
                            elif reg_p:
                                self.ext_price = float(reg_p)
                                self.session_label = f"盤中({node_lbl})"
                        break
            except Exception:
                self.closes.clear()
                self.highs.clear()
                self.lows.clear()
                self.dates.clear()
                continue

        if not self.fetch_ok:
            try:
                stooq_url = f"https://stooq.com/q/d/l/?s={self.symbol.lower()}.us&i=d"
                req = urllib.request.Request(stooq_url, headers=headers)
                with urllib.request.urlopen(req, timeout=7, context=SSL_CTX) as resp:
                    csv_text = resp.read().decode("utf-8", errors="ignore")
                lines = [ln.strip() for ln in csv_text.splitlines() if ln.strip()]
                if len(lines) > 5 and "Date,Open,High,Low,Close" in lines[0]:
                    for ln in lines[1:][-252:]:
                        parts = ln.split(",")
                        if len(parts) >= 5:
                            dt = datetime.datetime.strptime(parts[0], "%Y-%m-%d").date()
                            h = float(parts[2])
                            l = float(parts[3])
                            c = float(parts[4])
                            self.dates.append(dt)
                            self.highs.append(h)
                            self.lows.append(l)
                            self.closes.append(c)
                    if len(self.closes) >= 2:
                        self.fetch_ok = True
                        self.source_node = "Stooq備援"
                        self.session_label = "收盤(Stooq)"
            except Exception:
                self.closes.clear()
                self.highs.clear()
                self.lows.clear()
                self.dates.clear()


class _YFModule:
    Ticker = _YFTicker


yf = _YFModule()


DEFAULT_PORTFOLIO = [
    {
        "Ticker": "NBIS",
        "Name": "Nebius Group",
        "Shares": 550,
        "Avg_Cost": 226.215,
        "Target_Kelly_Pct": 15.0,
        "Hard_Stop": 159.00,
        "Key_Fib_Target": 245.00,
        "Is_Semi_AI": True,
        "Trim_P1": 195.80,
        "Trim_S1": 87,
        "Trim_P2": 200.00,
        "Trim_S2": 80,
        "Trim_P3": 215.50,
        "Trim_S3": 50,
        "Trim_Stop_S": 100,
    },
    {
        "Ticker": "MRVL",
        "Name": "Marvell Tech",
        "Shares": 350,
        "Avg_Cost": 255.965,
        "Target_Kelly_Pct": 15.0,
        "Hard_Stop": 218.00,
        "Key_Fib_Target": 272.50,
        "Is_Semi_AI": True,
        "Trim_P1": 247.77,
        "Trim_S1": 57,
        "Trim_P2": 256.00,
        "Trim_S2": 60,
        "Trim_P3": 272.50,
        "Trim_S3": 53,
        "Trim_Stop_S": 60,
    },
    {"Ticker": "MU", "Name": "Micron Tech", "Shares": 50, "Avg_Cost": 516.017, "Target_Kelly_Pct": 15.0, "Hard_Stop": 465.00, "Key_Fib_Target": 585.00, "Is_Semi_AI": True},
    {"Ticker": "AVGO", "Name": "Broadcom Inc", "Shares": 100, "Avg_Cost": 325.207, "Target_Kelly_Pct": 15.0, "Hard_Stop": 298.00, "Key_Fib_Target": 358.50, "Is_Semi_AI": True},
    {"Ticker": "DRAM", "Name": "Roundhill ETF", "Shares": 350, "Avg_Cost": 68.393, "Target_Kelly_Pct": 5.0, "Hard_Stop": 58.50, "Key_Fib_Target": 76.50, "Is_Semi_AI": True},
    {"Ticker": "PLTR", "Name": "Palantir Tech", "Shares": 50, "Avg_Cost": 178.932, "Target_Kelly_Pct": 10.0, "Hard_Stop": 158.00, "Key_Fib_Target": 200.97, "Is_Semi_AI": True},
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


# --- 零崩潰 UI 元件 ---
def make_btn(text: str, on_click_fn, bg_color: str = "#2563eb", text_color: str = "#ffffff", pad: int = 7, width: int = None, expand: int = None, size: int = 11):
    return ft.Container(
        content=ft.Text(
            text,
            color=text_color,
            size=size,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        ),
        bgcolor=bg_color,
        border_radius=7,
        padding=pad,
        width=width,
        expand=expand,
        on_click=on_click_fn,
    )


def make_tf(label_str: str, val_str: str, expand: int = 1, hint_str: str = None):
    """不綁死 height，避免 Android 上浮動標籤 (Floating Label) 頂部字體被截斷"""
    return ft.TextField(
        label=label_str,
        value=val_str,
        hint_text=hint_str,
        expand=expand,
        text_size=12,
        content_padding=10,
    )


def make_grid_rows(items: list, cols: int = 2, spacing: int = 5) -> list:
    rows = []
    for i in range(0, len(items), cols):
        chunk = items[i : i + cols]
        rows.append(ft.Row(chunk, spacing=spacing))
    return rows


def make_safe_bar(fill_pct: float, fill_color: str = "#48bb78", bg_color: str = "#0e1117", limit_pct: float = None):
    clamped = max(2, min(98, int(round(fill_pct))))
    rem = max(2, 100 - clamped)
    if limit_pct is not None and 0 < limit_pct < 100:
        lim = max(2, min(96, int(round(limit_pct))))
        return ft.Column([
            ft.Container(
                bgcolor=bg_color,
                height=7,
                border_radius=3,
                content=ft.Row([
                    ft.Container(bgcolor=fill_color, expand=clamped, height=7),
                    ft.Container(bgcolor=bg_color, expand=rem, height=7),
                ], spacing=0),
            ),
            ft.Container(
                bgcolor="#0e1117",
                height=3,
                content=ft.Row([
                    ft.Container(bgcolor="#4a5568", expand=lim, height=3),
                    ft.Container(bgcolor="#ecc94b", width=4, height=3),
                    ft.Container(bgcolor="#0e1117", expand=max(2, 100 - lim), height=3),
                ], spacing=0),
            ),
        ], spacing=1)
    return ft.Container(
        bgcolor=bg_color,
        height=7,
        border_radius=3,
        content=ft.Row([
            ft.Container(bgcolor=fill_color, expand=clamped, height=7),
            ft.Container(bgcolor=bg_color, expand=rem, height=7),
        ], spacing=0),
    )


def make_ladder_ruler(cur_p: float, stop_p: float, fib_p: float, is_extended: bool = False):
    if cur_p <= stop_p:
        return ft.Container(
            bgcolor="#9b2c2c",
            border_radius=4,
            padding=4,
            content=ft.Text(
                f"🚨 已跌破停損防線 (現價 ${cur_p:.2f} <= 停損 ${stop_p:.2f})，請立即執行風控減碼！",
                size=10,
                color="#ffffff",
                weight=ft.FontWeight.BOLD,
            ),
        )
    if is_extended or cur_p >= fib_p:
        return ft.Container(
            bgcolor="#22543d",
            border_radius=4,
            padding=4,
            content=ft.Text(
                f"🔥 已達標或進入超漲延伸區 (現價 ${cur_p:.2f} >= ${fib_p:.2f})，改採移動停損 / 階梯減碼！",
                size=10,
                color="#68d391",
                weight=ft.FontWeight.BOLD,
            ),
        )
    span = max(fib_p - stop_p, 0.01)
    pos_pct = max(5, min(95, int(round((cur_p - stop_p) / span * 100.0))))
    right_pct = max(5, 100 - pos_pct)
    return ft.Container(
        bgcolor="#1a2232",
        height=8,
        border_radius=4,
        content=ft.Row([
            ft.Container(bgcolor="#fc8181", expand=pos_pct, height=8),
            ft.Container(bgcolor="#ffffff", width=5, height=8),
            ft.Container(bgcolor="#48bb78", expand=right_pct, height=8),
        ], spacing=0),
    )


def make_table_box(title: str, headers: list, rows: list, header_bg: str = "#1e3a8a"):
    header_cells = [
        ft.Container(content=ft.Text(str(h), size=10, weight=ft.FontWeight.BOLD, color="#90cdf4"), expand=1)
        for h in headers
    ]
    table_rows = [
        ft.Container(bgcolor=header_bg, padding=6, border_radius=5, content=ft.Row(header_cells, spacing=4))
    ]
    for idx, r in enumerate(rows):
        row_bg = "#1a2232" if idx % 2 == 0 else "#131824"
        row_cells = [
            ft.Container(content=ft.Text(str(c), size=10, color="#e2e8f0"), expand=1) for c in r
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
        border_radius=9,
        padding=8,
        content=ft.Column(
            [
                ft.Text(title, size=12, weight=ft.FontWeight.BOLD, color="#f7fafc"),
                ft.Column(table_rows, spacing=3),
            ],
            spacing=5,
        ),
    )


QUOTE_CACHE = {}


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def _pearson_corr(xs: list, ys: list) -> float:
    n = min(len(xs), len(ys))
    if n < 5:
        return 0.65
    x_sub = xs[-n:]
    y_sub = ys[-n:]
    mx = _mean(x_sub)
    my = _mean(y_sub)
    num = sum((x_sub[i] - mx) * (y_sub[i] - my) for i in range(n))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in x_sub))
    den_y = math.sqrt(sum((y - my) ** 2 for y in y_sub))
    if den_x <= 1e-9 or den_y <= 1e-9:
        return 0.65
    return max(-0.95, min(0.99, num / (den_x * den_y)))


def pick_next_fib_target_info(cur_p: float, q: dict):
    ordered_levels = [
        ("Fib 0.500", q.get("Fib_0500", 0)),
        ("Fib 0.618", q.get("Fib_0618", 0)),
        ("前高 1.000", q.get("Swing_High", 0)),
        ("擴散 1.272", q.get("Fib_1272", 0)),
        ("擴散 1.618", q.get("Fib_1618", 0)),
    ]
    for label, lvl in ordered_levels:
        if lvl >= cur_p * 1.01:
            return round(lvl, 2), label, False
    return round(cur_p, 2), "🔥 已延伸 (突破1.618，改採移動停損/減碼)", True


def fetch_quant_metrics(ticker: str, get_extended: bool = True, force_refresh: bool = False):
    tkr = ticker.strip().upper()
    cache_key = f"{tkr}_{get_extended}"
    if not force_refresh and cache_key in QUOTE_CACHE:
        return QUOTE_CACHE[cache_key]
    try:
        tk = yf.Ticker(tkr, include_prepost=get_extended)
        closes, highs, lows, dates = tk.closes, tk.highs, tk.lows, tk.dates
        if not tk.fetch_ok or len(closes) < 2:
            return None
        reg_close = closes[-1]
        prev_close = closes[-2]
        current_price = tk.ext_price if (get_extended and tk.ext_price) else reg_close
        day_chg_pct = ((current_price - prev_close) / prev_close) * 100.0 if prev_close else 0.0

        recent_h = highs[-126:] or closes[-126:]
        recent_l = lows[-126:] or closes[-126:]
        recent_d = dates[-126:] or [datetime.date.today()] * len(recent_h)
        swing_high = max(recent_h)
        swing_low = min(recent_l)
        high_idx = recent_h.index(swing_high)
        low_idx = recent_l.index(swing_low)
        suggested_high_dt = recent_d[high_idx].strftime("%Y-%m-%d")
        suggested_low_dt = recent_d[low_idx].strftime("%Y-%m-%d")

        diff = max(swing_high - swing_low, 0.01)

        trs = []
        for i in range(1, len(closes)):
            h = highs[i] if i < len(highs) else closes[i]
            l = lows[i] if i < len(lows) else closes[i]
            pc = closes[i - 1]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr_14 = _mean(trs[-14:]) if len(trs) >= 14 else reg_close * 0.04

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        daily_returns = [deltas[i] / closes[i] for i in range(len(deltas)) if closes[i] > 0]
        recent_rets = daily_returns[-60:] if len(daily_returns) >= 20 else [0.01, -0.01, 0.015, -0.012, 0.008]
        daily_vol = _stdev(recent_rets) if len(recent_rets) >= 5 else 0.025
        daily_drift = _mean(recent_rets)

        last_d = deltas[-14:] if len(deltas) >= 14 else deltas
        gains = [d for d in last_d if d > 0]
        losses = [-d for d in last_d if d < 0]
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

        ret_236 = round(swing_high - diff * 0.236, 2)
        ret_382 = round(swing_high - diff * 0.382, 2)
        ret_500 = round(swing_high - diff * 0.500, 2)
        ret_618 = round(swing_high - diff * 0.618, 2)
        ret_786 = round(swing_high - diff * 0.786, 2)

        fib_236 = round(swing_low + diff * 0.236, 2)
        fib_382 = round(swing_low + diff * 0.382, 2)
        fib_500 = round(swing_low + diff * 0.500, 2)
        fib_618 = round(swing_low + diff * 0.618, 2)
        ext_1272 = round(swing_low + diff * 1.272, 2)
        ext_1618 = round(swing_low + diff * 1.618, 2)

        if current_price >= ma20 and ma20 >= ma50:
            trend_diag = "多頭排列\n(站穩月/季線)"
        elif current_price >= ma20:
            trend_diag = "短多轉強\n(站上20MA)"
        elif current_price >= ma50:
            trend_diag = "中期震盪\n(月線下/季線上)"
        else:
            trend_diag = "空頭修正\n(月/季線之下)"

        if current_price >= ext_1618:
            fib_zone_diag = "🔥 已延伸\n(>擴散 1.618)"
        elif current_price >= ret_236:
            fib_zone_diag = "強勢區\n(>回撤 0.236)"
        elif current_price >= ret_382:
            fib_zone_diag = "淺回撤支撐\n(0.236~0.382)"
        elif current_price >= ret_500:
            fib_zone_diag = "中度回撤區\n(0.382~0.500)"
        elif current_price >= ret_618:
            fib_zone_diag = "黃金分割支撐\n(0.5~0.618)"
        else:
            fib_zone_diag = "深度回撤超跌\n(<0.618)"

        res = {
            "Price": round(current_price, 2),
            "Reg_Close": round(reg_close, 2),
            "Day_Chg_Pct": round(day_chg_pct, 2),
            "Session": tk.session_label if get_extended else f"日線({tk.source_node})",
            "Is_Fallback": False,
            "Source_Node": tk.source_node,
            "Daily_Vol": daily_vol,
            "Daily_Drift": max(-0.003, min(0.004, daily_drift)),
            "Returns_60d": recent_rets,
            "Swing_High": round(swing_high, 2),
            "Swing_Low": round(swing_low, 2),
            "Suggested_High_Date": suggested_high_dt,
            "Suggested_Low_Date": suggested_low_dt,
            "Ret_0236": ret_236,
            "Ret_0382": ret_382,
            "Ret_0500": ret_500,
            "Ret_0618": ret_618,
            "Ret_0786": ret_786,
            "Fib_0236": fib_236,
            "Fib_0382": fib_382,
            "Fib_0500": fib_500,
            "Fib_0618": fib_618,
            "Fib_1272": ext_1272,
            "Fib_1618": ext_1618,
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


def make_fallback_metrics(raw_price: float, sess_lbl: str = "離線預設"):
    swing_high = round(raw_price * 1.22, 2)
    swing_low = round(raw_price * 0.85, 2)
    diff = max(swing_high - swing_low, 0.01)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    return {
        "Price": round(raw_price, 2),
        "Reg_Close": round(raw_price, 2),
        "Day_Chg_Pct": 0.0,
        "Session": sess_lbl,
        "Is_Fallback": True,
        "Source_Node": "離線預設",
        "Daily_Vol": 0.025,
        "Daily_Drift": 0.0004,
        "Returns_60d": [0.012, -0.009, 0.015, -0.011, 0.007, -0.005, 0.010],
        "Swing_High": swing_high,
        "Swing_Low": swing_low,
        "Suggested_High_Date": today_str,
        "Suggested_Low_Date": today_str,
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
        "Trend_Diag": "離線估算\n(預設模式)",
        "Fib_Zone_Diag": "黃金分割支撐\n(0.5~0.618)",
    }


def compute_dynamic_kelly(price: float, hard_stop: float, fib_target: float, atr: float, rsi: float, trend_str: str, is_extended: bool = False) -> float:
    if price <= 0:
        return 15.0
    if is_extended:
        return 12.0
    eff_target = fib_target if fib_target > price * 1.01 else price + 1.8 * atr
    eff_stop = hard_stop if hard_stop < price * 0.99 else price - 1.2 * atr
    reward = max(eff_target - price, 1.0 * atr)
    risk = max(price - eff_stop, 0.8 * atr)
    b = reward / risk if risk > 0 else 1.5

    p = 0.52
    if "多頭" in trend_str or "轉強" in trend_str:
        p += 0.06
    elif "空頭" in trend_str:
        p -= 0.06

    if rsi < 35:
        p += 0.05
    elif rsi > 72:
        p -= 0.07

    p = max(0.36, min(0.68, p))
    q = 1.0 - p
    f_star = (b * p - q) / b
    kelly_full_pct = max(4.0, f_star * 100.0)
    return round(min(kelly_full_pct, 36.0), 1)


async def main(page: ft.Page):
    page.title = "美股量化風控"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e1117"
    page.padding = 8
    page.scroll = ft.ScrollMode.AUTO

    try:
        await _build(page)
    except Exception as e:
        import traceback
        page.add(ft.Container(height=36))
        page.add(ft.Text(f"啟動錯誤: {e}", color="#fc8181", size=14, selectable=True))
        page.add(ft.Text(traceback.format_exc(), size=11, color="#e2e8f0", selectable=True))
        page.update()


async def _build(page: ft.Page):
    portfolio_data = [dict(item) for item in DEFAULT_PORTFOLIO]
    active_page_idx = [0]        # 6 大主分頁 (0~5)
    kelly_mode = ["half"]        # "half" 或 "full"
    kelly_source = ["min_cap"]   # "min_cap", "dynamic", "manual"
    special_stress = ["none"]    # "none", "top2_atr", "semi_15"

    page0_sub_tab = [0]          # 分頁 1: 0=資金設定, 1=壓力測試, 2=組合MC
    page1_sub_mode = [0]         # 分頁 2: 0=總表, 1=圖表, 2=編輯/新增
    selected_stock_idx = [0]     # 分頁 2 選中個股
    page2_fib_stock_idx = [0]    # 分頁 3 選中個股
    page3_calc_sub_tab = [0]     # 分頁 4: 0=兩批加碼保本, 1=費氏階梯減碼, 2=技術與回撤
    page4_trim_stock_idx = [-1]  # 分頁 5 (持倉減碼專區): -1=全持倉減碼總覽, 0..N=單股減碼掛單與編輯
    page5_sub_tab = [0]          # 分頁 6: 0=技術/費氏, 1=專屬週期, 2=部位試算, 3=單股MC
    mc_drift_mode = ["trend"]    # "trend" 或 "zero"

    last_live_rows = [[]]
    last_equity_info = [314832.0, 9616.50]

    sw_live = ft.Switch(label="自動抓報價", value=True)
    sw_ext = ft.Switch(label="含盤前盤後", value=True)
    sw_trading_days = ft.Switch(label="美股交易日", value=True)
    tf_anchor_date = make_tf("組合 T+0 (YYYY-MM-DD)", "2026-10-16", expand=1, hint_str="例如 2026-10-16")
    tf_cash = make_tf("美元現金池 ($)", "9616.50", expand=1)
    tf_tax = make_tf("累計抵稅虧損 ($)", "-3461.52", expand=1)
    slider_shock = ft.Slider(min=-30, max=10, divisions=40, value=0, label="{value}%", expand=1)
    slider_beta = ft.Slider(min=0.5, max=3.0, divisions=25, value=1.5, label="{value}x", expand=1)
    status_text = ft.Text("✅ 就緒", size=11, color="#68d391", weight=ft.FontWeight.BOLD)

    main_nav_col = ft.Column(spacing=4)
    page0_overview_col = ft.Column(spacing=7, visible=True)
    page1_holdings_col = ft.Column(spacing=7, visible=False)
    page2_fib_col = ft.Column(spacing=7, visible=False)
    page3_calc_col = ft.Column(spacing=7, visible=False)
    page4_trim_col = ft.Column(spacing=7, visible=False)
    page5_research_col = ft.Column(spacing=7, visible=False)

    kpi_grid_col = ft.Column(spacing=5)
    mc_portfolio_result_col = ft.Column(spacing=5)

    # 將「🎯 雙核」改名為「🎯 減碼」，支援所有持股
    page_titles = [
        "📊 總覽",
        "🛡️ 持倉",
        "⏳ 費氏",
        "🧮 加減碼",
        "🎯 減碼",
        "🔍 研究",
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
                    page5_research_col.visible = i == 5
                    render_main_nav()
                    page.update()
                return _sw

            btns.append(
                make_btn(
                    title,
                    make_page_sw(idx),
                    bg_color="#2563eb" if is_act else "#1e293b",
                    text_color="#ffffff" if is_act else "#a0aec0",
                    pad=6,
                    expand=1,
                    size=11,
                )
            )
        main_nav_col.controls.append(ft.Row(btns[:3], spacing=4))
        main_nav_col.controls.append(ft.Row(btns[3:], spacing=4))

    def parse_anchor_date(dt_str: str = None) -> datetime.date:
        raw_str = (dt_str or tf_anchor_date.value or "").strip().replace("/", "-")
        try:
            return datetime.datetime.strptime(raw_str, "%Y-%m-%d").date()
        except Exception:
            return datetime.date(2026, 10, 16)

    # --- 原生日曆選擇器 (支援組合 T+0 與標的研究專屬 T+0) ---
    picker_target = ["portfolio"]  # "portfolio" 或 "research"
    research_t0_tf = make_tf("專屬 T+0 錨點 (YYYY-MM-DD)", "2026-10-23", expand=1, hint_str="例如 2026-10-23")

    def _on_date_picked(e):
        try:
            val = date_picker.value
            if val:
                if isinstance(val, datetime.datetime):
                    d_str = val.date().strftime("%Y-%m-%d")
                elif isinstance(val, datetime.date):
                    d_str = val.strftime("%Y-%m-%d")
                else:
                    d_str = str(val)[:10]
                if picker_target[0] == "portfolio":
                    tf_anchor_date.value = d_str
                    if last_live_rows[0]:
                        build_page2_fib(last_live_rows[0])
                else:
                    research_t0_tf.value = d_str
                    render_research_subviews(last_equity_info[0], last_equity_info[1])
                page.update()
        except Exception:
            pass

    date_picker = None
    try:
        date_picker = ft.DatePicker(
            first_date=datetime.datetime(2024, 1, 1),
            last_date=datetime.datetime(2028, 12, 31),
            on_change=_on_date_picked,
        )
        page.overlay.append(date_picker)
    except Exception:
        date_picker = None

    def open_calendar(target_name: str):
        def _fn(e):
            picker_target[0] = target_name
            if date_picker is not None:
                try:
                    if hasattr(page, "open"):
                        page.open(date_picker)
                    else:
                        date_picker.open = True
                        page.update()
                    return
                except Exception:
                    pass
            status_text.value = "💡 請直接在輸入框填寫 YYYY-MM-DD"
            status_text.color = "#ecc94b"
            page.update()
        return _fn

    def compute_rows(use_network: bool, force_api: bool):
        try:
            cash_pool = float(tf_cash.value)
        except Exception:
            cash_pool = 9616.50
        try:
            realized_loss_tax = float(tf_tax.value)
        except Exception:
            realized_loss_tax = -3461.52

        market_shock = float(slider_shock.value or 0.0)
        beta_mult = float(slider_beta.value or 1.5)
        base_shock_factor = 1.0 + (market_shock / 100.0) * beta_mult

        raw_rows = []
        any_network_success = False
        any_fallback_used = False
        active_node_name = "Q1"

        for item in portfolio_data:
            tkr = str(item["Ticker"]).strip().upper()
            if not tkr:
                continue
            q = None
            if use_network and sw_live.value:
                q = fetch_quant_metrics(tkr, get_extended=sw_ext.value, force_refresh=force_api)
                if q and not q.get("Is_Fallback", False):
                    any_network_success = True
                    active_node_name = q.get("Source_Node", "Q1")
                else:
                    any_fallback_used = True
            elif sw_live.value:
                cache_key = f"{tkr}_{sw_ext.value}"
                q = QUOTE_CACHE.get(cache_key)
                if q and not q.get("Is_Fallback", False):
                    any_network_success = True
                    active_node_name = q.get("Source_Node", "快取")

            if not q:
                fallback_p = float(item.get("Manual_Price", item.get("Avg_Cost", 100.0)))
                q = make_fallback_metrics(fallback_p, "離線預設")
                if use_network and sw_live.value:
                    any_fallback_used = True

            raw_price = q["Price"]
            shares = int(float(item.get("Shares", 0)))
            avg_cost = float(item.get("Avg_Cost", raw_price))
            raw_mkt = shares * raw_price

            dyn_target, dyn_lbl, is_ext = pick_next_fib_target_info(raw_price, q)
            user_target = float(item.get("Key_Fib_Target", dyn_target))

            # 三階減碼預設值：若有自訂則用自訂，否則自動依費氏關卡與 25% 股數產生
            s_qtr = max(1, int(math.floor(shares * 0.25)))
            trim_p1 = float(item.get("Trim_P1", q["Fib_0500"]))
            trim_s1 = int(item.get("Trim_S1", s_qtr))
            trim_p2 = float(item.get("Trim_P2", q["Fib_0618"]))
            trim_s2 = int(item.get("Trim_S2", s_qtr))
            trim_p3 = float(item.get("Trim_P3", q["Fib_1272"]))
            trim_s3 = int(item.get("Trim_S3", s_qtr))
            trim_stop_s = int(item.get("Trim_Stop_S", s_qtr))

            row_dict = dict(q)
            row_dict.update({
                "Ticker": tkr,
                "Name": item.get("Name", tkr),
                "Shares": shares,
                "Avg_Cost": round(avg_cost, 3),
                "Raw_Price": raw_price,
                "Raw_Mkt": raw_mkt,
                "Is_Semi_AI": bool(item.get("Is_Semi_AI", True)),
                "Key_Fib_Target": user_target,
                "Dyn_Fib_Target": dyn_target,
                "Dyn_Fib_Label": dyn_lbl,
                "Is_Extended": is_ext or (raw_price >= user_target and raw_price >= q["Fib_1618"]),
                "Hard_Stop": float(item.get("Hard_Stop", round(raw_price - 2 * q["ATR"], 2))),
                "Manual_Half_Kelly_Pct": float(item.get("Target_Kelly_Pct", 15.0)),
                "Trim_P1": trim_p1,
                "Trim_S1": trim_s1,
                "Trim_P2": trim_p2,
                "Trim_S2": trim_s2,
                "Trim_P3": trim_p3,
                "Trim_S3": trim_s3,
                "Trim_Stop_S": trim_stop_s,
            })
            raw_rows.append(row_dict)

        sorted_by_mkt = sorted(raw_rows, key=lambda x: x["Raw_Mkt"], reverse=True)
        top2_tickers = {x["Ticker"] for x in sorted_by_mkt[:2]}

        live_rows = []
        for r in raw_rows:
            raw_p = r["Raw_Price"]
            sim_p = raw_p * base_shock_factor
            if special_stress[0] == "top2_atr" and r["Ticker"] in top2_tickers:
                sim_p = max(0.01, sim_p - r["ATR"])
            elif special_stress[0] == "semi_15" and r["Is_Semi_AI"]:
                sim_p = max(0.01, sim_p * 0.85)
            sim_price = round(sim_p, 2)

            shares = r["Shares"]
            avg_cost = r["Avg_Cost"]
            mkt_val = round(shares * sim_price, 2)
            cost_val = round(shares * avg_cost, 2)
            pnl = round(mkt_val - cost_val, 2)
            pnl_pct = round((pnl / cost_val) * 100.0, 2) if cost_val > 0 else 0.0

            formula_full_k = compute_dynamic_kelly(
                sim_price, r["Hard_Stop"], r["Key_Fib_Target"], r["ATR"], r["RSI"], r["Trend_Diag"], r["Is_Extended"]
            )
            formula_half_k = round(formula_full_k * 0.5, 1)
            manual_half_k = r["Manual_Half_Kelly_Pct"]
            manual_full_k = round(manual_half_k * 2.0, 1)

            if kelly_source[0] == "min_cap":
                chosen_half_k = min(formula_half_k, manual_half_k)
                chosen_full_k = min(formula_full_k, manual_full_k)
            elif kelly_source[0] == "dynamic":
                chosen_half_k = formula_half_k
                chosen_full_k = formula_full_k
            else:
                chosen_half_k = manual_half_k
                chosen_full_k = manual_full_k

            effective_kelly = chosen_half_k if kelly_mode[0] == "half" else chosen_full_k

            r["Price"] = sim_price
            r["Market_Value"] = mkt_val
            r["Total_Cost"] = cost_val
            r["PnL"] = pnl
            r["PnL_Pct"] = pnl_pct
            r["Formula_Half_K"] = formula_half_k
            r["Formula_Full_K"] = formula_full_k
            r["Manual_Full_K"] = manual_full_k
            r["Chosen_Half_K"] = chosen_half_k
            r["Chosen_Full_K"] = chosen_full_k
            r["Effective_Kelly_Pct"] = effective_kelly
            live_rows.append(r)

        total_stock_val = sum(r["Market_Value"] for r in live_rows)
        total_portfolio_equity = total_stock_val + cash_pool
        total_cost_val = sum(r["Total_Cost"] for r in live_rows)
        total_pnl = total_stock_val - total_cost_val
        total_pnl_pct = (total_pnl / total_cost_val * 100.0) if total_cost_val > 0 else 0.0

        for r in live_rows:
            if total_portfolio_equity > 0 and r["Price"] > 0:
                r["Weight_Pct"] = round((r["Market_Value"] / total_portfolio_equity) * 100.0, 2)
                r["Half_Kelly_Shares"] = int(math.floor((total_portfolio_equity * (r["Chosen_Half_K"] / 100.0)) / r["Price"]))
                r["Full_Kelly_Shares"] = int(math.floor((total_portfolio_equity * (r["Chosen_Full_K"] / 100.0)) / r["Price"]))
                r["Optimal_Shares"] = r["Half_Kelly_Shares"] if kelly_mode[0] == "half" else r["Full_Kelly_Shares"]
                r["Share_Diff"] = r["Optimal_Shares"] - r["Shares"]
            else:
                r["Weight_Pct"] = 0.0
                r["Half_Kelly_Shares"] = 0
                r["Full_Kelly_Shares"] = 0
                r["Optimal_Shares"] = 0
                r["Share_Diff"] = 0

            if r["Price"] <= r["Hard_Stop"]:
                r["Action_Signal"] = "觸底減碼"
            elif r["Is_Extended"] or (r["Price"] >= r["Key_Fib_Target"] and r["Weight_Pct"] > r["Effective_Kelly_Pct"]):
                r["Action_Signal"] = "超漲/達標減碼"
            elif r["Weight_Pct"] > r["Effective_Kelly_Pct"] + 2.0:
                r["Action_Signal"] = "超配禁攤"
            elif r["Price"] >= r["MA20"] and r["Weight_Pct"] < r["Effective_Kelly_Pct"] - 2.0:
                r["Action_Signal"] = "右側加碼"
            else:
                r["Action_Signal"] = "紀律續抱"

        n_pos = len(live_rows)
        indiv_vars = [r["Shares"] * r["ATR"] * 1.645 * 0.75 for r in live_rows]
        if n_pos >= 2:
            cov_sum = 0.0
            pair_corrs = []
            for i in range(n_pos):
                for j in range(n_pos):
                    if i == j:
                        rho = 1.0
                    else:
                        rho = _pearson_corr(live_rows[i]["Returns_60d"], live_rows[j]["Returns_60d"])
                        if i < j:
                            pair_corrs.append(rho)
                    cov_sum += indiv_vars[i] * indiv_vars[j] * rho
            daily_var_95 = math.sqrt(max(0.0, cov_sum))
            avg_corr = _mean(pair_corrs) if pair_corrs else 0.65
        else:
            daily_var_95 = sum(indiv_vars)
            avg_corr = 1.0

        return (
            live_rows,
            total_stock_val,
            total_portfolio_equity,
            total_pnl,
            total_pnl_pct,
            cash_pool,
            realized_loss_tax,
            daily_var_95,
            avg_corr,
            any_network_success,
            any_fallback_used,
            active_node_name,
        )

    def update_ui_from_rows(
        live_rows,
        total_stock_val,
        total_portfolio_equity,
        total_pnl,
        total_pnl_pct,
        cash_pool,
        realized_loss_tax,
        daily_var_95,
        avg_corr,
        any_network_success=True,
        any_fallback_used=False,
        active_node_name="Q1",
    ):
        last_live_rows[0] = live_rows
        last_equity_info[0] = total_portfolio_equity
        last_equity_info[1] = cash_pool

        sorted_w = sorted([r["Weight_Pct"] for r in live_rows], reverse=True)
        top2_conc = sum(sorted_w[:2]) if len(sorted_w) >= 2 else sum(sorted_w)
        weekly_var_95 = daily_var_95 * math.sqrt(5)
        releasable_cash = sum(max(r["Shares"] - r["Optimal_Shares"], 0) * r["Price"] for r in live_rows) + cash_pool

        kpi_grid_col.controls.clear()
        pnl_color = "#48bb78" if total_pnl >= 0 else "#f56565"
        conc_color = "#ecc94b" if top2_conc > 35 else "#48bb78"
        k_mode_str = "半凱利0.5x" if kelly_mode[0] == "half" else "全凱利1.0x⚠️"
        src_map = {"min_cap": "取小min", "dynamic": "模型f*", "manual": "手設"}
        k_src_str = src_map.get(kelly_source[0], "取小min")
        kpi_specs = [
            (f"總淨值 ({k_src_str}/{k_mode_str})", f"${total_portfolio_equity:,.0f}", f"股${total_stock_val:,.0f}/現${cash_pool:,.0f}", "#f7fafc"),
            ("未實現總損益", f"${total_pnl:,.0f} ({total_pnl_pct:+.1f}%)", "持倉浮動損益", pnl_color),
            ("前兩大持股集中度", f"{top2_conc:.1f}%", f"半凱利建議上限 <= 35%", conc_color),
            ("單週 95% VaR (近似估值)", f"-${weekly_var_95:,.0f}", f"單日-${daily_var_95:,.0f} (簡化近似未含完整相關性)", "#f56565"),
            ("可動用現金 + 超配減碼釋出", f"${releasable_cash:,.0f}", f"現金 ${cash_pool:,.0f} | 抵稅 ${realized_loss_tax:,.0f}", "#48bb78"),
        ]
        kpi_cards = []
        for k_title, k_val, k_sub, k_col in kpi_specs:
            kpi_cards.append(
                ft.Container(
                    expand=1,
                    bgcolor="#161b26",
                    border_radius=8,
                    padding=7,
                    content=ft.Column(
                        [
                            ft.Text(k_title, color="#a0aec0", size=10),
                            ft.Text(k_val, color=k_col, size=14, weight=ft.FontWeight.BOLD),
                            ft.Text(k_sub, color="#718096", size=9),
                        ],
                        spacing=2,
                    ),
                )
            )
        kpi_grid_col.controls.extend(make_grid_rows(kpi_cards, cols=2, spacing=5))

        build_page0_subviews(live_rows, total_stock_val, total_portfolio_equity, cash_pool, daily_var_95, avg_corr)
        build_page1_holdings(live_rows)
        build_page2_fib(live_rows)
        build_page3_calc(live_rows, total_portfolio_equity, cash_pool)
        build_page4_trim(live_rows)
        build_page5_research(total_portfolio_equity, cash_pool)
        page.update()

    def refresh_all(force_api: bool = False, use_network: bool = True):
        async def _task():
            status_text.value = "⏳ 同步報價中(Q1/Q2/Stooq)..." if use_network else "⏳ 計算中..."
            status_text.color = "#ecc94b"
            page.update()
            try:
                res = await asyncio.to_thread(compute_rows, use_network, force_api)
                update_ui_from_rows(*res)
                any_net_ok = res[9]
                any_fb = res[10]
                node_lbl = res[11]
                if use_network and sw_live.value:
                    if not any_net_ok:
                        status_text.value = "⚠️ 報價異常，已切換離線值"
                        status_text.color = "#fc8181"
                    elif any_fb:
                        status_text.value = f"⚠️ 部分離線 ({node_lbl})"
                        status_text.color = "#ecc94b"
                    else:
                        status_text.value = f"✅ {node_lbl} 更新 {datetime.datetime.now().strftime('%H:%M:%S')}"
                        status_text.color = "#68d391"
                else:
                    status_text.value = f"✅ 離線重算 {datetime.datetime.now().strftime('%H:%M:%S')}"
                    status_text.color = "#68d391"
            except Exception:
                status_text.value = "⚠️ 報價異常，已切換離線值"
                status_text.color = "#fc8181"
            finally:
                page.update()

        page.run_task(_task)

    # --- 分頁 1：總覽設定 ---
    def build_page0_subviews(live_rows, total_stock_val, total_portfolio_equity, cash_pool, daily_var_95, avg_corr):
        page0_overview_col.controls.clear()

        def sw_kelly_m(m):
            def _fn(e):
                kelly_mode[0] = m
                refresh_all(force_api=False, use_network=False)
            return _fn

        def sw_kelly_src(s):
            def _fn(e):
                kelly_source[0] = s
                refresh_all(force_api=False, use_network=False)
            return _fn

        is_half = kelly_mode[0] == "half"
        cur_src = kelly_source[0]
        kelly_bar = ft.Container(
            bgcolor="#131824",
            border_radius=8,
            padding=6,
            content=ft.Column([
                ft.Row([
                    make_btn("🟢 半凱利 0.5x (穩健預設)", sw_kelly_m("half"), "#2563eb" if is_half else "#1e293b", expand=1, pad=5),
                    make_btn("🔴 全凱利 1.0x (高波動⚠️)", sw_kelly_m("full"), "#dc2626" if not is_half else "#1e293b", expand=1, pad=5),
                ], spacing=5),
                ft.Row([
                    make_btn("🛡️ 取保守值 min(模型,手設)", sw_kelly_src("min_cap"), "#38a169" if cur_src == "min_cap" else "#1e293b", expand=1, pad=5, size=10),
                    make_btn("📐 模型估計凱利", sw_kelly_src("dynamic"), "#38a169" if cur_src == "dynamic" else "#1e293b", expand=1, pad=5, size=10),
                    make_btn("✍️ 手設上限", sw_kelly_src("manual"), "#38a169" if cur_src == "manual" else "#1e293b", expand=1, pad=5, size=10),
                ], spacing=4),
            ], spacing=4),
        )

        def sw_page0_tab(t):
            def _fn(e):
                page0_sub_tab[0] = t
                build_page0_subviews(live_rows, total_stock_val, total_portfolio_equity, cash_pool, daily_var_95, avg_corr)
                page.update()
            return _fn

        sub_tab_bar = ft.Row([
            make_btn("⚙️ 資金參數", sw_page0_tab(0), "#2563eb" if page0_sub_tab[0] == 0 else "#1e293b", expand=1, pad=6),
            make_btn("📉 壓力測試", sw_page0_tab(1), "#2563eb" if page0_sub_tab[0] == 1 else "#1e293b", expand=1, pad=6),
            make_btn("🎲 組合MC", sw_page0_tab(2), "#2563eb" if page0_sub_tab[0] == 2 else "#1e293b", expand=1, pad=6),
        ], spacing=4)

        sub_content = ft.Column(spacing=8)

        if page0_sub_tab[0] == 0:
            def reset_defaults(e):
                portfolio_data.clear()
                for item in DEFAULT_PORTFOLIO:
                    portfolio_data.append(dict(item))
                slider_shock.value = 0
                slider_beta.value = 1.5
                special_stress[0] = "none"
                refresh_all(force_api=True, use_network=True)

            sub_content.controls.extend([
                ft.Row([sw_live, sw_ext], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=2),
                ft.Row([tf_cash, tf_tax], spacing=8),
                ft.Row([
                    make_btn("⚡ 套用重算", lambda e: refresh_all(False, False), "#38a169", pad=7, expand=1),
                    make_btn("🔄 聯網更新報價", lambda e: refresh_all(True, True), "#2563eb", pad=7, expand=1),
                    make_btn("↩️ 重置", reset_defaults, "#4a5568", pad=7, expand=1),
                ], spacing=5),
            ])
        elif page0_sub_tab[0] == 1:
            def apply_scenario(shock_val, beta_val, spec_mode="none"):
                def _fn(e):
                    slider_shock.value = shock_val
                    slider_beta.value = beta_val
                    special_stress[0] = spec_mode
                    refresh_all(force_api=False, use_network=False)
                return _fn

            scenario_row1 = ft.Row([
                make_btn("正常 (0%)", apply_scenario(0, 1.5, "none"), "#2d3748", pad=5, expand=1),
                make_btn("前2大跌1xATR", apply_scenario(0, 1.5, "top2_atr"), "#dd6b20", pad=5, expand=1),
                make_btn("半導體籃-15%", apply_scenario(0, 1.5, "semi_15"), "#c53030", pad=5, expand=1),
            ], spacing=4)
            scenario_row2 = ft.Row([
                make_btn("-5% 小回檔", apply_scenario(-5, 1.5, "none"), "#2b6cb0", pad=5, expand=1),
                make_btn("2022升息(-20%)", apply_scenario(-12, 1.7, "none"), "#9b2c2c", pad=5, expand=1),
                make_btn("AI資本急凍", apply_scenario(-15, 1.8, "semi_15"), "#7b1113", pad=5, expand=1),
            ], spacing=4)

            unshocked_stock = sum(r["Raw_Price"] * r["Shares"] for r in live_rows)
            unshocked_eq = unshocked_stock + cash_pool
            dd_amt = total_portfolio_equity - unshocked_eq
            dd_pct = (dd_amt / unshocked_eq * 100.0) if unshocked_eq > 0 else 0.0
            breached = [r["Ticker"] for r in live_rows if r["Price"] <= r["Hard_Stop"]]
            forced_sell_val = sum(r["Market_Value"] * 0.5 for r in live_rows if r["Price"] <= r["Hard_Stop"])
            cash_cushion_ok = (cash_pool + forced_sell_val) >= abs(dd_amt) * 0.5

            stress_headers = ["系統壓力核心指標", "壓力後數值", "安全墊與風險診斷"]
            stress_rows = [
                ["壓力後組合總淨值", f"${total_portfolio_equity:,.0f}", f"較基準變動 ${dd_amt:+,.0f}"],
                ["近似最大回撤\n(MDD)", f"{dd_pct:+.2f}%", "本估值為簡化近似係數"],
                ["現金安全墊狀態", "安全充裕" if cash_cushion_ok else "⚠️ 跌破安全墊", f"可用現金 ${cash_pool:,.0f}"],
                ["觸及硬停損標的", ", ".join(breached) if breached else "無 (防線完好)", "須強制減碼" if breached else "紀律續抱"],
            ]

            sub_content.controls.extend([
                ft.Text("三層情境壓力測試 (單情景 / 前2大跌ATR / 半導體同跌)：", size=11, color="#cbd5e0"),
                scenario_row1,
                scenario_row2,
                ft.Text(f"大盤衝擊 ({slider_shock.value:+.0f}%) × Beta ({slider_beta.value:.1f}x)", size=10, color="#90cdf4"),
                ft.Row([slider_shock, slider_beta], spacing=4),
                make_btn("🔄 套用滑桿自訂衝擊", lambda e: refresh_all(False, False), "#c53030", pad=6),
                make_table_box("系統性壓力測試三大核心輸出", stress_headers, stress_rows, "#742a2a"),
            ])
        else:
            def run_portfolio_mc(trials: int):
                async def _task():
                    status_text.value = f"⏳ 執行組合 {trials} 次 MC..."
                    status_text.color = "#ecc94b"
                    page.update()

                    def _calc():
                        results = []
                        max_dds = []
                        n_days = 21
                        base_eq = sum(r["Raw_Price"] * r["Shares"] for r in live_rows) + cash_pool
                        for _ in range(trials):
                            prices = [r["Raw_Price"] for r in live_rows]
                            peak_eq = base_eq
                            worst_dd = 0.0
                            for _day in range(n_days):
                                day_market_factor = random.gauss(0.0, 0.012)
                                day_stock_val = 0.0
                                for idx, r in enumerate(live_rows):
                                    idiosyncratic = random.gauss(r["Daily_Drift"], r["Daily_Vol"] * 0.75)
                                    beta_w = 0.75 if r["Is_Semi_AI"] else 0.45
                                    ret = idiosyncratic + day_market_factor * beta_w
                                    prices[idx] = max(0.01, prices[idx] * (1.0 + ret))
                                    day_stock_val += prices[idx] * r["Shares"]
                                cur_eq = day_stock_val + cash_pool
                                if cur_eq > peak_eq:
                                    peak_eq = cur_eq
                                dd = (cur_eq - peak_eq) / peak_eq if peak_eq > 0 else 0.0
                                if dd < worst_dd:
                                    worst_dd = dd
                            end_eq = sum(prices[i] * live_rows[i]["Shares"] for i in range(len(live_rows))) + cash_pool
                            results.append(end_eq)
                            max_dds.append(worst_dd * 100.0)

                        results.sort()
                        max_dds.sort()
                        p5 = results[int(trials * 0.05)]
                        p50 = results[int(trials * 0.50)]
                        p95 = results[int(trials * 0.95)]
                        dd_p50 = max_dds[int(trials * 0.50)]
                        dd_p5 = max_dds[int(trials * 0.05)]
                        under_cushion = sum(1 for x in results if x < base_eq * 0.85) / trials * 100.0
                        return p5, p50, p95, dd_p50, dd_p5, under_cushion

                    p5, p50, p95, dd_p50, dd_p5, under_cushion = await asyncio.to_thread(_calc)
                    mc_portfolio_result_col.controls.clear()
                    mc_headers = ["組合 21 天模擬指標", "估計數值", "實戰含義\n(歷史波動近似)"]
                    mc_rows = [
                        ["P5 悲觀淨值\n(5%分位)", f"${p5:,.0f}", f"{(p5 - total_portfolio_equity) / total_portfolio_equity * 100.0:+.1f}% 尾端風險"],
                        ["P50 中位數淨值", f"${p50:,.0f}", f"{(p50 - total_portfolio_equity) / total_portfolio_equity * 100.0:+.1f}% 期望中樞"],
                        ["P95 樂觀淨值\n(95%分位)", f"${p95:,.0f}", f"{(p95 - total_portfolio_equity) / total_portfolio_equity * 100.0:+.1f}% 順風表現"],
                        ["近似最大回撤分位", f"中位 {dd_p50:.1f}%", f"極端 P5 回撤 {dd_p5:.1f}%"],
                        ["跌破 85% 淨值門檻", f"{under_cushion:.1f}%", "回撤逾 15% 之發生比例"],
                    ]
                    mc_portfolio_result_col.controls.append(
                        make_table_box(f"組合蒙地卡羅參考 ({trials}次 | 每日重抽共同因子)", mc_headers, mc_rows, "#2c5282")
                    )
                    status_text.value = "✅ 組合 MC 完成"
                    status_text.color = "#68d391"
                    page.update()

                page.run_task(_task)

            sub_content.controls.extend([
                ft.Text("歷史波動近似抽樣 (每日重抽共同因子、當日共用)：", size=11, color="#cbd5e0"),
                ft.Row([
                    make_btn("200次", lambda e: run_portfolio_mc(200), "#2b6cb0", pad=6, expand=1),
                    make_btn("500次", lambda e: run_portfolio_mc(500), "#2b6cb0", pad=6, expand=1),
                    make_btn("1000次", lambda e: run_portfolio_mc(1000), "#2b6cb0", pad=6, expand=1),
                    make_btn("2000次", lambda e: run_portfolio_mc(2000), "#1e3a8a", pad=6, expand=1),
                ], spacing=4),
                mc_portfolio_result_col,
            ])

        page0_overview_col.controls.extend([
            kpi_grid_col,
            kelly_bar,
            ft.Container(
                bgcolor="#161b26",
                border_radius=9,
                padding=10,
                content=ft.Column([sub_tab_bar, sub_content], spacing=8),
            ),
        ])

    # --- 分頁 2：風控持倉 ---
    def build_page1_holdings(live_rows: list):
        page1_holdings_col.controls.clear()

        def sw_sub_mode(m):
            def _fn(e):
                page1_sub_mode[0] = m
                build_page1_holdings(live_rows)
                page.update()
            return _fn

        mode_bar = ft.Row([
            make_btn("📋 持倉總表", sw_sub_mode(0), "#38a169" if page1_sub_mode[0] == 0 else "#1e293b", expand=1, pad=6),
            make_btn("📊 權重與量尺圖", sw_sub_mode(1), "#38a169" if page1_sub_mode[0] == 1 else "#1e293b", expand=1, pad=6),
            make_btn("✏️ 編輯/離線價", sw_sub_mode(2), "#38a169" if page1_sub_mode[0] == 2 else "#1e293b", expand=1, pad=6),
        ], spacing=4)
        page1_holdings_col.controls.append(mode_bar)

        if page1_sub_mode[0] == 0:
            headers = ["代號/現價", "股數/均價", "權重/生效限", "模型|手設", "指令"]
            rows = []
            for r in live_rows:
                mod_k = r["Formula_Half_K"] if kelly_mode[0] == "half" else r["Formula_Full_K"]
                man_k = r["Manual_Half_Kelly_Pct"] if kelly_mode[0] == "half" else r["Manual_Full_K"]
                rows.append([
                    f"{r['Ticker']}\n${r['Price']:.2f}",
                    f"{r['Shares']}股\n@${r['Avg_Cost']:.1f}",
                    f"{r['Weight_Pct']:.1f}%\n(限{r['Effective_Kelly_Pct']:.1f}%)",
                    f"模:{mod_k:.1f}%\n手:{man_k:.1f}%",
                    f"{r['Action_Signal']}\n({r['Share_Diff']:+d}股)",
                ])
            page1_holdings_col.controls.append(
                make_table_box("持倉風控總表 (生效上限預設取 min(模型,手設))", headers, rows, "#1e3a8a")
            )
        elif page1_sub_mode[0] == 1:
            weight_bars = []
            ladder_bars = []
            for r in live_rows:
                w_pct = r["Weight_Pct"]
                k_pct = r["Effective_Kelly_Pct"]
                mod_k = r["Formula_Half_K"] if kelly_mode[0] == "half" else r["Formula_Full_K"]
                man_k = r["Manual_Half_Kelly_Pct"] if kelly_mode[0] == "half" else r["Manual_Full_K"]
                is_over = w_pct > k_pct
                w_col = "#fc8181" if is_over else "#48bb78"
                weight_bars.append(
                    ft.Container(
                        bgcolor="#131824",
                        border_radius=6,
                        padding=6,
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"{r['Ticker']} 權重 {w_pct:.1f}%", size=11, weight=ft.FontWeight.BOLD, color=w_col),
                                ft.Text(
                                    f"模型{mod_k:.1f}% | 手設{man_k:.1f}% -> 生效{k_pct:.1f}%",
                                    size=9,
                                    color="#a0aec0",
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            make_safe_bar(w_pct * 2.2, w_col, "#0e1117", limit_pct=k_pct * 2.2),
                        ], spacing=3),
                    )
                )

                cur_p, stop_p, fib_p = r["Price"], r["Hard_Stop"], r["Key_Fib_Target"]
                dist_stop = (cur_p - stop_p) / cur_p * 100.0 if cur_p else 0
                dist_fib = (fib_p - cur_p) / cur_p * 100.0 if cur_p else 0
                ladder_bars.append(
                    ft.Container(
                        bgcolor="#131824",
                        border_radius=6,
                        padding=6,
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"{r['Ticker']} 停損 ${stop_p:.1f} ({dist_stop:+.1f}%)", size=10, color="#fc8181"),
                                ft.Text(f"現價 ${cur_p:.2f}", size=11, weight=ft.FontWeight.BOLD, color="#ffffff"),
                                ft.Text(f"目標 ${fib_p:.1f} ({dist_fib:+.1f}%)", size=10, color="#68d391"),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            make_ladder_ruler(cur_p, stop_p, fib_p, r["Is_Extended"]),
                        ], spacing=3),
                    )
                )

            page1_holdings_col.controls.extend([
                ft.Text("📊 持股權重 vs 生效凱利上限 (黃點為生效上限水位)：", size=11, weight=ft.FontWeight.BOLD, color="#90cdf4"),
                ft.Column(weight_bars, spacing=4),
                ft.Text("📏 各股現價與停損/費氏目標位階量尺 (已正規化)：", size=11, weight=ft.FontWeight.BOLD, color="#90cdf4"),
                ft.Column(ladder_bars, spacing=4),
            ])
        else:
            chips = []
            for idx, r in enumerate(live_rows):
                is_sel = selected_stock_idx[0] == idx

                def make_sel(i):
                    def _fn(e):
                        selected_stock_idx[0] = i
                        build_page1_holdings(live_rows)
                        page.update()
                    return _fn

                chips.append(make_btn(r["Ticker"], make_sel(idx), "#2563eb" if is_sel else "#1e293b", pad=5))

            is_add = selected_stock_idx[0] == len(live_rows)

            def sel_add(e):
                selected_stock_idx[0] = len(live_rows)
                build_page1_holdings(live_rows)
                page.update()

            chips.append(make_btn("+ 新增持股", sel_add, "#dd6b20" if is_add else "#1e293b", pad=5))
            page1_holdings_col.controls.append(ft.Row(chips, wrap=True, spacing=4))

            if not is_add and 0 <= selected_stock_idx[0] < len(live_rows):
                idx = selected_stock_idx[0]
                r = live_rows[idx]
                tf_s = make_tf("股數", str(r["Shares"]), expand=1)
                tf_c = make_tf("持有均價($)", str(r["Avg_Cost"]), expand=1)
                tf_p = make_tf("手動/離線價($)", str(r["Price"]), expand=1)
                tf_k = make_tf("手設半凱利(%)", str(r["Manual_Half_Kelly_Pct"]), expand=1)
                tf_f = make_tf("費氏目標價($)", str(r["Key_Fib_Target"]), expand=1)
                tf_h = make_tf("硬性停損價($)", str(r["Hard_Stop"]), expand=1)

                def _save(e):
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

                def _del(e):
                    if 0 <= idx < len(portfolio_data):
                        portfolio_data.pop(idx)
                        selected_stock_idx[0] = 0
                        page1_sub_mode[0] = 0
                        refresh_all(force_api=False, use_network=False)

                page1_holdings_col.controls.append(
                    ft.Container(
                        bgcolor="#161b26",
                        border_radius=8,
                        padding=10,
                        content=ft.Column([
                            ft.Text(
                                f"編輯 {r['Ticker']} [{r['Session']}] | 模型半凱利 {r['Formula_Half_K']:.1f}% / 手設 {r['Manual_Half_Kelly_Pct']:.1f}%",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color="#ffffff",
                            ),
                            ft.Container(height=2),
                            ft.Row([tf_s, tf_c], spacing=8),
                            ft.Row([tf_p, tf_k], spacing=8),
                            ft.Row([tf_f, tf_h], spacing=8),
                            ft.Row([
                                make_btn("💾 儲存(離線時套用手動價)", _save, "#2563eb", pad=7, expand=1),
                                make_btn("🗑️ 刪除", _del, "#9b2c2c", pad=7, expand=1),
                            ], spacing=6),
                        ], spacing=8),
                    )
                )
            else:
                new_t = make_tf("股票代號", "", expand=1, hint_str="如 NVDA")
                new_s = make_tf("持有股數", "50", expand=1)
                new_c = make_tf("持有均價($)", "100", expand=1)
                new_k = make_tf("手設半凱利(%)", "15", expand=1)

                def _add(e):
                    nt = (new_t.value or "").strip().upper()
                    if nt:
                        def_p = float(new_c.value or 100.0)
                        portfolio_data.append({
                            "Ticker": nt,
                            "Name": nt,
                            "Shares": int(float(new_s.value or 0)),
                            "Avg_Cost": def_p,
                            "Manual_Price": def_p,
                            "Target_Kelly_Pct": float(new_k.value or 15.0),
                            "Hard_Stop": round(def_p * 0.90, 2),
                            "Key_Fib_Target": round(def_p * 1.15, 2),
                            "Is_Semi_AI": True,
                        })
                        selected_stock_idx[0] = len(portfolio_data) - 1
                        page1_sub_mode[0] = 0
                        refresh_all(force_api=True, use_network=True)

                page1_holdings_col.controls.append(
                    ft.Container(
                        bgcolor="#161b26",
                        border_radius=8,
                        padding=10,
                        content=ft.Column([
                            ft.Text("新增美股到持倉 (同時納入減碼與費氏追蹤)：", size=12, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                            ft.Container(height=2),
                            ft.Row([new_t, new_s], spacing=8),
                            ft.Row([new_c, new_k], spacing=8),
                            make_btn("➕ 加入持倉並聯網更新", _add, "#38a169", pad=8),
                        ], spacing=8),
                    )
                )

    # --- 分頁 3：費氏週期與回撤/擴散矩陣 (括號說明全部換行，不再擁擠) ---
    def build_page2_fib(live_rows: list):
        page2_fib_col.controls.clear()
        if not live_rows:
            return
        base_dt = parse_anchor_date()
        use_b_days = sw_trading_days.value

        fib_specs = [
            (5, "T+5 短線確認", "短均線翻揚", "#ed8936"),
            (8, "T+8 第一減碼", "0.236~0.382壓", "#ecc94b"),
            (13, "T+13 波段分水嶺", "20MA扣抵減碼", "#4299e1"),
            (21, "T+21 中期轉折", "0.618黃金分割", "#48bb78"),
            (34, "T+34 季線變盤", "季線定調平衡", "#9f7aea"),
        ]
        today_dt = datetime.date.today()
        tz_cards = []
        for f_num, title, desc, color in fib_specs:
            t_dt = add_us_trading_days(base_dt, f_num) if use_b_days else base_dt + datetime.timedelta(days=f_num)
            d_left = (t_dt - today_dt).days
            day_badge = f"剩{d_left}天" if d_left > 0 else ("今日變盤" if d_left == 0 else f"過{abs(d_left)}天")
            tz_cards.append(
                ft.Container(
                    expand=1,
                    bgcolor="#1e3a8a" if d_left == 0 else "#131824",
                    border_radius=6,
                    padding=6,
                    content=ft.Column([
                        ft.Text(f"{title} ({day_badge})", color=color, size=10, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{t_dt.strftime('%m/%d')} | {desc}", color="#cbd5e0", size=10),
                    ], spacing=2),
                )
            )
        tz_grid = ft.Column(make_grid_rows(tz_cards, cols=2, spacing=5), spacing=5)

        chips = []
        for idx, r in enumerate(live_rows):
            is_sel = page2_fib_stock_idx[0] == idx

            def make_sel_f(i):
                def _fn(e):
                    page2_fib_stock_idx[0] = i
                    build_page2_fib(live_rows)
                    page.update()
                return _fn

            chips.append(make_btn(r["Ticker"], make_sel_f(idx), "#2563eb" if is_sel else "#1e293b", pad=5))

        if page2_fib_stock_idx[0] >= len(live_rows):
            page2_fib_stock_idx[0] = 0
        sr = live_rows[page2_fib_stock_idx[0]]
        cur_p = sr["Price"]

        def _d(lvl):
            pct = ((lvl - cur_p) / cur_p * 100.0) if cur_p else 0
            return f"${lvl:.2f}\n({pct:+.1f}%)"

        # 修正第二張圖紅框：所有括號說明強制換行到下一行，保持寬敞整齊
        fib_headers = [
            "費氏回撤\n(高點回落支撐)",
            "支撐價位\n(距離現價%)",
            "費氏擴散\n(低點推升目標)",
            "目標價位\n(距離現價%)",
        ]
        fib_rows = [
            [
                "波段高點\n(Swing High)",
                f"${sr['Swing_High']:.2f}",
                "波段低點\n(Swing Low)",
                f"${sr['Swing_Low']:.2f}",
            ],
            [
                "回撤 0.236\n(淺回檔)",
                _d(sr["Ret_0236"]),
                "反彈 0.500\n(多空頸線)",
                _d(sr["Fib_0500"]),
            ],
            [
                "回撤 0.382\n(第一支撐)",
                _d(sr["Ret_0382"]),
                "反彈 0.618\n(黃金分割壓)",
                _d(sr["Fib_0618"]),
            ],
            [
                "回撤 0.500\n(多空中軸)",
                _d(sr["Ret_0500"]),
                "前高 1.000\n(突破基準)",
                _d(sr["Swing_High"]),
            ],
            [
                "回撤 0.618\n(黃金分割買點)",
                _d(sr["Ret_0618"]),
                "擴散 1.272\n(延伸一)",
                _d(sr["Fib_1272"]),
            ],
            [
                "回撤 0.786\n(防守底線)",
                _d(sr["Ret_0786"]),
                "擴散 1.618\n(延伸二)",
                _d(sr["Fib_1618"]),
            ],
        ]

        page2_fib_col.controls.extend([
            ft.Container(
                bgcolor="#161b26",
                border_radius=8,
                padding=10,
                content=ft.Column([
                    ft.Container(height=2),
                    ft.Row([
                        tf_anchor_date,
                        make_btn("📅 日曆", open_calendar("portfolio"), "#2563eb", pad=7),
                        make_btn("✅ 套用", lambda e: (build_page2_fib(live_rows), page.update()), "#38a169", pad=7),
                    ], spacing=5),
                    ft.Row([
                        make_btn("10/16錨點", lambda e: (setattr(tf_anchor_date, "value", "2026-10-16"), build_page2_fib(live_rows), page.update()), "#1e293b", pad=5, expand=1),
                        make_btn("今天", lambda e: (setattr(tf_anchor_date, "value", datetime.date.today().strftime("%Y-%m-%d")), build_page2_fib(live_rows), page.update()), "#1e293b", pad=5, expand=1),
                    ], spacing=5),
                    sw_trading_days,
                    tz_grid,
                ], spacing=6),
            ),
            ft.Row(chips, wrap=True, spacing=4),
            make_table_box(
                f"📐 {sr['Ticker']} 現價 ${cur_p:.2f} | 下一關卡: {sr['Dyn_Fib_Label']} (${sr['Dyn_Fib_Target']:.2f})",
                fib_headers,
                fib_rows,
                "#2c5282",
            ),
        ])

    # --- 分頁 4：既有持股加減碼 ---
    t4_ticker_tf = make_tf("持股代號", "NBIS", expand=1)
    t4_shares_tf = make_tf("現有股數", "550", expand=1)
    t4_cost_tf = make_tf("持有均價($)", "226.215", expand=1)
    t4_budget_tf = make_tf("加碼預算($)", "9616.50", expand=1)
    t4_result_col = ft.Column(spacing=6)

    def build_page3_calc(live_rows: list, total_portfolio_equity: float, cash_pool: float):
        page3_calc_col.controls.clear()
        chips = []
        for r in live_rows:
            def make_chip(row_d):
                def _fn(e):
                    t4_ticker_tf.value = row_d["Ticker"]
                    t4_shares_tf.value = str(row_d["Shares"])
                    t4_cost_tf.value = str(row_d["Avg_Cost"])
                    run_calc()
                return _fn
            chips.append(make_btn(r["Ticker"], make_chip(r), "#1e293b", "#90cdf4", pad=5))

        def run_calc(e=None):
            t4_result_col.controls.clear()
            tkr = (t4_ticker_tf.value or "").strip().upper()
            matched = next((x for x in live_rows if x["Ticker"] == tkr), None)
            if not matched and live_rows:
                matched = live_rows[0]
            if not matched:
                return

            try:
                sh = int(float(t4_shares_tf.value or 0))
            except Exception:
                sh = matched["Shares"]
            try:
                cost = float(t4_cost_tf.value or matched["Avg_Cost"])
            except Exception:
                cost = matched["Avg_Cost"]
            try:
                budget = float(t4_budget_tf.value or cash_pool)
            except Exception:
                budget = cash_pool

            live_p = matched["Price"]
            atr = matched["ATR"]
            rsi = matched["RSI"]
            swing_low = matched["Swing_Low"]
            ret_382 = matched["Ret_0382"]
            ret_500 = matched["Ret_0500"]
            ret_618 = matched["Ret_0618"]
            k_pct = matched["Effective_Kelly_Pct"]

            cur_invested = round(sh * cost, 2)
            cur_mkt = round(sh * live_p, 2)
            cur_w = (cur_mkt / total_portfolio_equity * 100.0) if total_portfolio_equity > 0 else 0
            max_k_val = total_portfolio_equity * (k_pct / 100.0)
            rem_k_val = max(0.0, max_k_val - cur_mkt)
            eff_budget = 0.0 if matched["Is_Extended"] else (min(rem_k_val, budget) if rem_k_val > 0 else 0.0)

            buy_p1 = round(live_p, 2)
            buy_p2 = round(max(min(live_p - 1.0 * atr, ret_382), swing_low, live_p * 0.90), 2)

            b1_sh = int(math.floor((eff_budget * 0.40) / buy_p1)) if buy_p1 > 0 else 0
            b1_fund = round(b1_sh * buy_p1, 2)
            after_b1_sh = sh + b1_sh
            after_b1_avg = round((cur_invested + b1_fund) / after_b1_sh, 2) if after_b1_sh > 0 else 0

            rem_b2 = max(0.0, eff_budget - b1_fund)
            b2_sh = int(math.floor(rem_b2 / buy_p2)) if buy_p2 > 0 else 0
            b2_fund = round(b2_sh * buy_p2, 2)

            tot_add = round(b1_fund + b2_fund, 2)
            tot_sh = sh + b1_sh + b2_sh
            final_breakeven = round((cur_invested + tot_add) / tot_sh, 2) if tot_sh > 0 else 0
            hard_stop = matched["Hard_Stop"]

            if matched["Is_Extended"]:
                msg_col = "#ecc94b"
                msg = "🔥 股價已突破 1.618 進入超漲延伸區，停止加碼！請切換至「費氏階梯減碼」鎖利。"
            elif cur_w >= k_pct:
                msg_col = "#fc8181"
                msg = f"權重 {cur_w:.1f}% 已超過生效凱利上限 {k_pct:.1f}%，禁止攤平！請看階梯減碼表。"
            else:
                msg_col = "#68d391"
                msg = f"可加碼額度: ${eff_budget:,.0f} | 兩批補倉後保本均價: ${final_breakeven:.2f}"

            t4_result_col.controls.append(
                ft.Container(
                    bgcolor="#131824",
                    border_radius=7,
                    padding=6,
                    content=ft.Column([
                        ft.Text(
                            f"{tkr} 現價 ${live_p:.2f} | 生效上限 {k_pct:.1f}% (半:{matched['Half_Kelly_Shares']}股 / 全:{matched['Full_Kelly_Shares']}股)",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color="#ffffff",
                        ),
                        ft.Text(msg, size=11, color=msg_col, weight=ft.FontWeight.BOLD),
                    ], spacing=2),
                )
            )

            def sw_c_tab(idx):
                def _fn(e):
                    page3_calc_sub_tab[0] = idx
                    run_calc()
                return _fn

            sub_bar = ft.Row([
                make_btn("➕ 兩批加碼保本", sw_c_tab(0), "#2563eb" if page3_calc_sub_tab[0] == 0 else "#1e293b", expand=1, pad=6),
                make_btn("🎯 費氏階梯減碼", sw_c_tab(1), "#2563eb" if page3_calc_sub_tab[0] == 1 else "#1e293b", expand=1, pad=6),
                make_btn("📊 技術與回撤", sw_c_tab(2), "#2563eb" if page3_calc_sub_tab[0] == 2 else "#1e293b", expand=1, pad=6),
            ], spacing=4)
            t4_result_col.controls.append(sub_bar)

            if page3_calc_sub_tab[0] == 0:
                addon_headers = ["階段", "建議買價", "加碼股數", "動用資金", "補倉後保本均價"]
                addon_rows = [
                    ["原持倉", f"${cost:.2f}", f"{sh}股", f"${cur_invested:,.0f}", f"${cost:.2f}"],
                    ["第一批40%\n(現價)", f"${buy_p1:.2f}", f"+{b1_sh}股", f"${b1_fund:,.0f}", f"${after_b1_avg:.2f}"],
                    ["第二批60%\n(回撤/ATR)", f"${buy_p2:.2f}", f"+{b2_sh}股", f"${b2_fund:,.0f}", f"${final_breakeven:.2f}"],
                    ["合計總結", "-", f"共{tot_sh}股", f"${tot_add:,.0f}", f"保本 ${final_breakeven:.2f}"],
                ]
                t4_result_col.controls.append(make_table_box(f"{tkr} 兩批加碼與補倉保本均價表", addon_headers, addon_rows, "#22543d"))
            elif page3_calc_sub_tab[0] == 1:
                trim_headers = ["費氏減碼區間", "目標價", "比例", "減碼股數", "回收現金"]
                s1 = int(math.floor(tot_sh * 0.25))
                s2 = int(math.floor(tot_sh * 0.25))
                s3 = int(math.floor(tot_sh * 0.25))
                s4 = max(0, tot_sh - s1 - s2 - s3)
                p_500, p_618, p_1272, p_1618 = matched["Fib_0500"], matched["Fib_0618"], matched["Fib_1272"], matched["Fib_1618"]
                trim_rows = [
                    ["Fib 0.500\n(中軸調節)", f"${p_500:.2f}", "25%", f"{s1}股", f"${s1 * p_500:,.0f}"],
                    ["Fib 0.618\n(黃金分割)", f"${p_618:.2f}", "25%", f"{s2}股", f"${s2 * p_618:,.0f}"],
                    ["擴散 1.272\n(波段目標一)", f"${p_1272:.2f}", "25%", f"{s3}股", f"${s3 * p_1272:,.0f}"],
                    ["擴散 1.618\n(波段目標二)", f"${p_1618:.2f}", "25%", f"{s4}股", f"${s4 * p_1618:,.0f}"],
                    ["硬性破位停損線", f"${hard_stop:.2f}", "破位", "強制風控", "跌破無條件減碼"],
                ]
                t4_result_col.controls.append(make_table_box(f"{tkr} 通用費波納契四階減碼表", trim_headers, trim_rows, "#1e3a8a"))
            else:
                tech_headers = ["技術與費氏回撤指標", "數值 / 價位", "實戰量化判讀"]
                tech_rows = [
                    ["均線趨勢結構", f"20MA ${matched['MA20']:.2f}\n50MA ${matched['MA50']:.2f}", matched["Trend_Diag"]],
                    ["動能與波動", f"RSI {rsi:.1f}\nATR ${atr:.2f}", f"模型半凱利 {matched['Formula_Half_K']:.1f}%\n手設 {matched['Manual_Half_Kelly_Pct']:.1f}%"],
                    ["動態下一關卡", f"${matched['Dyn_Fib_Target']:.2f}", matched["Dyn_Fib_Label"]],
                    ["回撤 0.382\n(第一支撐)", f"${ret_382:.2f}", "強勢回檔第一支撐買點"],
                    ["回撤 0.500\n(多空中軸)", f"${ret_500:.2f}", "波段多空分水嶺"],
                    ["回撤 0.618\n(黃金分割)", f"${ret_618:.2f}", "黃金分割防守買點"],
                ]
                t4_result_col.controls.append(make_table_box(f"{tkr} 技術分析與費氏回撤診斷", tech_headers, tech_rows, "#2c5282"))
            page.update()

        page3_calc_col.controls.extend([
            ft.Container(
                bgcolor="#161b26",
                border_radius=8,
                padding=10,
                content=ft.Column([
                    ft.Row(chips, wrap=True, spacing=4),
                    ft.Container(height=2),
                    ft.Row([t4_ticker_tf, t4_shares_tf], spacing=8),
                    ft.Row([t4_cost_tf, t4_budget_tf], spacing=8),
                    make_btn("🧮 重新計算加減碼與通用減碼表", run_calc, "#2563eb", pad=7),
                ], spacing=6),
            ),
            t4_result_col,
        ])
        run_calc()

    # --- 分頁 5：持倉階梯減碼專區 (升級 B：開放支援所有持股 + 新增持股 + 可自訂各階減碼價與股數) ---
    def build_page4_trim(live_rows: list):
        page4_trim_col.controls.clear()
        if not live_rows:
            return

        chips = []
        is_all = page4_trim_stock_idx[0] == -1

        def sel_all(e):
            page4_trim_stock_idx[0] = -1
            build_page4_trim(live_rows)
            page.update()

        chips.append(make_btn("📋 全部持倉總覽", sel_all, "#2563eb" if is_all else "#1e293b", pad=5))

        for idx, r in enumerate(live_rows):
            is_sel = page4_trim_stock_idx[0] == idx

            def make_sel_t(i):
                def _fn(e):
                    page4_trim_stock_idx[0] = i
                    build_page4_trim(live_rows)
                    page.update()
                return _fn

            chips.append(make_btn(r["Ticker"], make_sel_t(idx), "#2563eb" if is_sel else "#1e293b", pad=5))

        def goto_add_stock(e):
            active_page_idx[0] = 1
            page1_sub_mode[0] = 2
            selected_stock_idx[0] = len(live_rows)
            page0_overview_col.visible = False
            page1_holdings_col.visible = True
            page2_fib_col.visible = False
            page3_calc_col.visible = False
            page4_trim_col.visible = False
            page5_research_col.visible = False
            render_main_nav()
            build_page1_holdings(live_rows)
            page.update()

        chips.append(make_btn("+ 新增持股", goto_add_stock, "#dd6b20", pad=5))

        page4_trim_col.controls.append(
            ft.Container(
                bgcolor="#161b26",
                border_radius=8,
                padding=8,
                content=ft.Column([
                    ft.Text("🎯 持倉階梯減碼掛單專區 (點選個股可自訂掛單價與股數)：", size=11, weight=ft.FontWeight.BOLD, color="#90cdf4"),
                    ft.Row(chips, wrap=True, spacing=4),
                ], spacing=5),
            )
        )

        def make_stock_trim_box(r: dict, idx_in_p: int):
            p1, s1 = r["Trim_P1"], r["Trim_S1"]
            p2, s2 = r["Trim_P2"], r["Trim_S2"]
            p3, s3 = r["Trim_P3"], r["Trim_S3"]
            stop_p, stop_s = r["Hard_Stop"], r["Trim_Stop_S"]
            tot_trim_sh = s1 + s2 + s3
            tot_cash = s1 * p1 + s2 * p2 + s3 * p3
            rem_sh = max(0, r["Shares"] - tot_trim_sh)
            return make_table_box(
                f"{r['Ticker']} 三階減碼掛單表 (現有 {r['Shares']}股 | 現價 ${r['Price']:.2f} | 減碼後留 {rem_sh}股)",
                ["階段", "掛單價", "減碼股數", "預計收回現金"],
                [
                    ["第一階\n(初步鎖利)", f"${p1:.2f}", f"{s1}股", f"${s1 * p1:,.0f}"],
                    ["第二階\n(波段調節)", f"${p2:.2f}", f"{s2}股", f"${s2 * p2:,.0f}"],
                    ["第三階\n(主升段目標)", f"${p3:.2f}", f"{s3}股", f"${s3 * p3:,.0f}"],
                    ["三階合計回收", "-", f"共 {tot_trim_sh}股", f"${tot_cash:,.0f}"],
                    ["破位防線\n(硬性停損)", f"${stop_p:.2f}", f"{stop_s}股", f"${stop_s * stop_p:,.0f}"],
                ],
                "#1e3a8a" if idx_in_p % 2 == 0 else "#744210",
            )

        if is_all:
            for idx, r in enumerate(live_rows):
                page4_trim_col.controls.append(make_stock_trim_box(r, idx))
        else:
            if page4_trim_stock_idx[0] >= len(live_rows):
                page4_trim_stock_idx[0] = 0
            idx = page4_trim_stock_idx[0]
            r = live_rows[idx]
            page4_trim_col.controls.append(make_stock_trim_box(r, idx))

            # 單股自訂三階減碼掛單價與股數編輯器
            tf_p1 = make_tf("第一階掛單價($)", str(r["Trim_P1"]), expand=1)
            tf_s1 = make_tf("第一階股數", str(r["Trim_S1"]), expand=1)
            tf_p2 = make_tf("第二階掛單價($)", str(r["Trim_P2"]), expand=1)
            tf_s2 = make_tf("第二階股數", str(r["Trim_S2"]), expand=1)
            tf_p3 = make_tf("第三階掛單價($)", str(r["Trim_P3"]), expand=1)
            tf_s3 = make_tf("第三階股數", str(r["Trim_S3"]), expand=1)
            tf_stp_p = make_tf("破位防線價($)", str(r["Hard_Stop"]), expand=1)
            tf_stp_s = make_tf("破位減碼股數", str(r["Trim_Stop_S"]), expand=1)

            def save_custom_trim(e):
                try:
                    portfolio_data[idx]["Trim_P1"] = float(tf_p1.value)
                    portfolio_data[idx]["Trim_S1"] = int(float(tf_s1.value))
                    portfolio_data[idx]["Trim_P2"] = float(tf_p2.value)
                    portfolio_data[idx]["Trim_S2"] = int(float(tf_s2.value))
                    portfolio_data[idx]["Trim_P3"] = float(tf_p3.value)
                    portfolio_data[idx]["Trim_S3"] = int(float(tf_s3.value))
                    portfolio_data[idx]["Hard_Stop"] = float(tf_stp_p.value)
                    portfolio_data[idx]["Trim_Stop_S"] = int(float(tf_stp_s.value))
                except Exception:
                    pass
                refresh_all(force_api=False, use_network=False)

            def auto_fib_trim(e):
                qtr = max(1, int(math.floor(r["Shares"] * 0.25)))
                portfolio_data[idx]["Trim_P1"] = r["Fib_0500"]
                portfolio_data[idx]["Trim_S1"] = qtr
                portfolio_data[idx]["Trim_P2"] = r["Fib_0618"]
                portfolio_data[idx]["Trim_S2"] = qtr
                portfolio_data[idx]["Trim_P3"] = r["Fib_1272"]
                portfolio_data[idx]["Trim_S3"] = qtr
                portfolio_data[idx]["Trim_Stop_S"] = qtr
                refresh_all(force_api=False, use_network=False)

            page4_trim_col.controls.append(
                ft.Container(
                    bgcolor="#161b26",
                    border_radius=8,
                    padding=10,
                    content=ft.Column([
                        ft.Text(f"✏️ 自訂 {r['Ticker']} 階梯減碼掛單價與股數：", size=12, weight=ft.FontWeight.BOLD, color="#63b3ed"),
                        ft.Container(height=2),
                        ft.Row([tf_p1, tf_s1], spacing=8),
                        ft.Row([tf_p2, tf_s2], spacing=8),
                        ft.Row([tf_p3, tf_s3], spacing=8),
                        ft.Row([tf_stp_p, tf_stp_s], spacing=8),
                        ft.Row([
                            make_btn("💾 儲存自訂掛單", save_custom_trim, "#2563eb", pad=7, expand=1),
                            make_btn("📐 自動套用費氏階梯價", auto_fib_trim, "#38a169", pad=7, expand=1),
                        ], spacing=6),
                    ], spacing=8),
                )
            )

    # --- 分頁 6：標的研究 / 預加碼 (修復第一張圖標籤被切 + 修復第三張圖子分頁切換高亮卡頓與日曆選擇) ---
    research_ticker_tf = make_tf("研究代號", "NVDA", expand=1, hint_str="如 NVDA/AMD/INTC")
    research_budget_tf = make_tf("建倉預算($)", "10000", expand=1)
    research_manual_k_tf = make_tf("手設半凱利(%)", "15.0", expand=1)
    research_sub_tab_row = ft.Row(spacing=4)
    research_result_col = ft.Column(spacing=6)
    research_mc_result_col = ft.Column(spacing=6)

    CURRENT_RESEARCH_INFO = {}

    def render_research_sub_tab_btns(total_portfolio_equity: float, cash_pool: float):
        """動態重繪第6頁的4顆子分頁按鈕，確保點選後立即切換藍色高亮，不卡在第一顆"""
        research_sub_tab_row.controls.clear()
        tab_specs = [
            (0, "📈 技術/費氏"),
            (1, "⏳ 專屬週期"),
            (2, "🧮 部位試算"),
            (3, "🎲 單股MC"),
        ]
        for idx, lbl in tab_specs:
            is_act = page5_sub_tab[0] == idx

            def make_sw(i):
                def _fn(e):
                    page5_sub_tab[0] = i
                    render_research_sub_tab_btns(total_portfolio_equity, cash_pool)
                    render_research_subviews(total_portfolio_equity, cash_pool)
                    page.update()
                return _fn

            research_sub_tab_row.controls.append(
                make_btn(
                    lbl,
                    make_sw(idx),
                    bg_color="#2563eb" if is_act else "#1e293b",
                    text_color="#ffffff" if is_act else "#a0aec0",
                    expand=1,
                    pad=7,
                    size=11,
                )
            )

    def build_page5_research(total_portfolio_equity: float, cash_pool: float):
        page5_research_col.controls.clear()
        render_research_sub_tab_btns(total_portfolio_equity, cash_pool)

        def fetch_and_analyze(e=None):
            tkr = (research_ticker_tf.value or "").strip().upper()
            if not tkr:
                return

            async def _task():
                status_text.value = f"⏳ 正在抓取 {tkr}..."
                status_text.color = "#ecc94b"
                page.update()
                q = await asyncio.to_thread(fetch_quant_metrics, tkr, sw_ext.value, True)
                if not q:
                    q = make_fallback_metrics(100.0, "離線預設")
                    status_text.value = "⚠️ 報價異常，已切換離線值"
                    status_text.color = "#fc8181"
                else:
                    status_text.value = f"✅ {tkr} ${q['Price']:.2f} ({q['Source_Node']})"
                    status_text.color = "#68d391"

                CURRENT_RESEARCH_INFO.clear()
                CURRENT_RESEARCH_INFO.update(q)
                CURRENT_RESEARCH_INFO["Ticker"] = tkr

                research_t0_tf.value = q.get("Suggested_Low_Date") or datetime.date.today().strftime("%Y-%m-%d")
                render_research_sub_tab_btns(total_portfolio_equity, cash_pool)
                render_research_subviews(total_portfolio_equity, cash_pool)
                page.update()

            page.run_task(_task)

        # 修正第一張圖紅框：增加頂部留白、分排寬敞配置、不綁死 height，字體完全不遮擋
        top_ctrl = ft.Container(
            bgcolor="#161b26",
            border_radius=8,
            padding=10,
            content=ft.Column([
                ft.Container(height=2),
                ft.Row([research_ticker_tf, research_budget_tf, research_manual_k_tf], spacing=6),
                make_btn("🔍 聯網抓取最新報價與費氏指標 (Q1/Q2/Stooq)", fetch_and_analyze, "#38a169", pad=8),
                research_sub_tab_row,
            ], spacing=8),
        )

        page5_research_col.controls.extend([top_ctrl, research_result_col])
        if not CURRENT_RESEARCH_INFO:
            fetch_and_analyze()
        else:
            render_research_subviews(total_portfolio_equity, cash_pool)

    def render_research_subviews(total_portfolio_equity: float, cash_pool: float):
        research_result_col.controls.clear()
        q = CURRENT_RESEARCH_INFO
        if not q:
            return
        tkr = q.get("Ticker", "NVDA")
        cur_p = q["Price"]
        atr = q["ATR"]
        rsi = q["RSI"]
        ma20 = q["MA20"]
        ret_382 = q["Ret_0382"]
        ret_618 = q["Ret_0618"]
        hard_stop = round(cur_p - 2.0 * atr, 2)

        active_fib_target, active_fib_lbl, is_ext = pick_next_fib_target_info(cur_p, q)

        formula_full_k = compute_dynamic_kelly(cur_p, hard_stop, active_fib_target, atr, rsi, q["Trend_Diag"], is_ext)
        formula_half_k = round(formula_full_k * 0.5, 1)
        try:
            manual_half_k = float(research_manual_k_tf.value or 15.0)
        except Exception:
            manual_half_k = 15.0
        manual_full_k = round(manual_half_k * 2.0, 1)

        eff_half_k = min(formula_half_k, manual_half_k) if kelly_source[0] == "min_cap" else (formula_half_k if kelly_source[0] == "dynamic" else manual_half_k)
        eff_full_k = min(formula_full_k, manual_full_k) if kelly_source[0] == "min_cap" else (formula_full_k if kelly_source[0] == "dynamic" else manual_full_k)
        eff_k = eff_half_k if kelly_mode[0] == "half" else eff_full_k

        research_result_col.controls.append(
            ft.Container(
                bgcolor="#131824",
                border_radius=6,
                padding=6,
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"{tkr} ${cur_p:.2f} ({q['Day_Chg_Pct']:+.2f}%) [{q['Session']}]", size=11, weight=ft.FontWeight.BOLD, color="#ffffff"),
                        ft.Text(f"RSI {rsi:.1f} | ATR ${atr:.2f}", size=10, color="#90cdf4"),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(
                        f"模型半凱利 {formula_half_k:.1f}% | 手設 {manual_half_k:.1f}% -> 生效上限 {eff_k:.1f}% | 目標: {active_fib_lbl}",
                        size=10,
                        color="#ecc94b" if is_ext else "#68d391",
                        weight=ft.FontWeight.BOLD,
                    ),
                ], spacing=2),
            )
        )

        if page5_sub_tab[0] == 0:
            tech_headers = ["技術與費氏維度", "價位 / 數值", "實戰量化判讀"]
            tech_rows = [
                ["均線趨勢結構", f"20MA ${ma20:.2f}\n50MA ${q['MA50']:.2f}", f"{q['Trend_Diag']}\n(200MA ${q['MA200']:.2f})"],
                ["近半年波段高低", f"高 ${q['Swing_High']:.2f}\n低 ${q['Swing_Low']:.2f}", q["Fib_Zone_Diag"]],
                ["回撤 0.382\n(第一支撐)", f"${ret_382:.2f}", "多頭回檔第一批低接支撐"],
                ["回撤 0.500\n(多空中軸)", f"${q['Ret_0500']:.2f}", "波段多空分水嶺"],
                ["回撤 0.618\n(黃金分割)", f"${ret_618:.2f}", "黃金分割強支撐買點"],
                ["動態目標關卡", f"${active_fib_target:.2f}\n({active_fib_lbl})", "已突破全關卡改採減碼" if is_ext else f"擴散 1.272: ${q['Fib_1272']:.2f}\n擴散 1.618: ${q['Fib_1618']:.2f}"],
                ["硬性停損防線", f"${hard_stop:.2f}\n(-2xATR)", "跌破無條件停損出場"],
            ]
            research_result_col.controls.extend([
                make_ladder_ruler(cur_p, hard_stop, active_fib_target, is_ext),
                make_table_box(f"{tkr} 技術分析與費氏回撤/擴散對照", tech_headers, tech_rows, "#2c5282"),
            ])
        elif page5_sub_tab[0] == 1:
            def set_t0(d_str):
                def _fn(e):
                    research_t0_tf.value = d_str
                    render_research_subviews(total_portfolio_equity, cash_pool)
                    page.update()
                return _fn

            t0_dt = parse_anchor_date(research_t0_tf.value)
            today_dt = datetime.date.today()
            t0_cards = []
            for f_num, title, desc, color in [
                (5, "T+5 確認窗", "短均線翻揚", "#ed8936"),
                (8, "T+8 減碼窗", "0.236~0.382壓", "#ecc94b"),
                (13, "T+13 分水嶺", "20MA扣抵", "#4299e1"),
                (21, "T+21 轉折窗", "0.618強壓", "#48bb78"),
                (34, "T+34 大變盤", "季線定調", "#9f7aea"),
            ]:
                t_dt = add_us_trading_days(t0_dt, f_num) if sw_trading_days.value else t0_dt + datetime.timedelta(days=f_num)
                d_left = (t_dt - today_dt).days
                badge = f"剩{d_left}天" if d_left > 0 else ("今日" if d_left == 0 else f"過{abs(d_left)}天")
                t0_cards.append(
                    ft.Container(
                        expand=1,
                        bgcolor="#1e3a8a" if d_left == 0 else "#131824",
                        border_radius=6,
                        padding=6,
                        content=ft.Column([
                            ft.Text(f"{title} ({badge})", color=color, size=10, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{t_dt.strftime('%m/%d')} | {desc}", color="#cbd5e0", size=10),
                        ], spacing=2),
                    )
                )

            research_result_col.controls.extend([
                ft.Container(
                    bgcolor="#161b26",
                    border_radius=8,
                    padding=8,
                    content=ft.Column([
                        ft.Text("📅 點選「日曆」選擇起始日，或手動輸入 YYYY-MM-DD 後按套用：", size=10, color="#a0aec0"),
                        ft.Row([
                            research_t0_tf,
                            make_btn("📅 日曆", open_calendar("research"), "#2563eb", pad=7),
                            make_btn("✅ 套用", lambda e: (render_research_subviews(total_portfolio_equity, cash_pool), page.update()), "#38a169", pad=7),
                        ], spacing=5),
                        ft.Row([
                            make_btn(f"低點日\n({q.get('Suggested_Low_Date')})", set_t0(q.get("Suggested_Low_Date")), "#1e293b", pad=5, expand=1),
                            make_btn(f"高點日\n({q.get('Suggested_High_Date')})", set_t0(q.get("Suggested_High_Date")), "#1e293b", pad=5, expand=1),
                            make_btn("今天\n(" + today_dt.strftime("%Y-%m-%d") + ")", set_t0(today_dt.strftime("%Y-%m-%d")), "#1e293b", pad=5, expand=1),
                        ], spacing=4),
                    ], spacing=6),
                ),
                ft.Column(make_grid_rows(t0_cards, cols=2, spacing=5), spacing=5),
            ])
        elif page5_sub_tab[0] == 2:
            try:
                budget = float(research_budget_tf.value or 10000.0)
            except Exception:
                budget = 10000.0
            half_max_sh = int(math.floor((total_portfolio_equity * (eff_half_k / 100.0)) / cur_p)) if cur_p > 0 else 0
            full_max_sh = int(math.floor((total_portfolio_equity * (eff_full_k / 100.0)) / cur_p)) if cur_p > 0 else 0
            max_k_val = total_portfolio_equity * (eff_k / 100.0)
            target_budget = 0.0 if is_ext else min(budget, max_k_val)

            buy_p1 = cur_p
            buy_p2 = round(max(min(cur_p - 1.0 * atr, ret_382), q["Swing_Low"], cur_p * 0.90), 2)
            b1_sh = int(math.floor((target_budget * 0.40) / buy_p1)) if buy_p1 > 0 else 0
            b1_fund = round(b1_sh * buy_p1, 2)
            rem_b2 = max(0.0, target_budget - b1_fund)
            b2_sh = int(math.floor(rem_b2 / buy_p2)) if buy_p2 > 0 else 0
            b2_fund = round(b2_sh * buy_p2, 2)
            tot_sh = b1_sh + b2_sh
            tot_fund = round(b1_fund + b2_fund, 2)
            breakeven = round(tot_fund / tot_sh, 2) if tot_sh > 0 else cur_p

            def add_to_portfolio(e):
                sh_to_add = max(tot_sh, 10)
                qtr = max(1, int(math.floor(sh_to_add * 0.25)))
                portfolio_data.append({
                    "Ticker": tkr,
                    "Name": tkr,
                    "Shares": sh_to_add,
                    "Avg_Cost": breakeven,
                    "Manual_Price": cur_p,
                    "Target_Kelly_Pct": manual_half_k,
                    "Hard_Stop": hard_stop,
                    "Key_Fib_Target": active_fib_target if not is_ext else round(cur_p * 1.10, 2),
                    "Is_Semi_AI": True,
                    "Trim_P1": q["Fib_0500"],
                    "Trim_S1": qtr,
                    "Trim_P2": q["Fib_0618"],
                    "Trim_S2": qtr,
                    "Trim_P3": q["Fib_1272"],
                    "Trim_S3": qtr,
                    "Trim_Stop_S": qtr,
                })
                active_page_idx[0] = 1
                page1_sub_mode[0] = 0
                render_main_nav()
                refresh_all(force_api=False, use_network=False)

            plan_headers = ["階段", "建議買價", "股數", "動用資金", "建倉後保本均價"]
            plan_rows = [
                ["生效凱利上限", f"現價 ${cur_p:.2f}", f"半:{half_max_sh}股", f"全:{full_max_sh}股", active_fib_lbl],
                ["第一批40%\n(現價)", f"${buy_p1:.2f}", f"{b1_sh}股", f"${b1_fund:,.0f}", f"${buy_p1:.2f}"],
                ["第二批60%\n(支撐)", f"${buy_p2:.2f}", f"{b2_sh}股", f"${b2_fund:,.0f}", f"${breakeven:.2f}"],
                ["兩批建倉總結", "-", f"共 {tot_sh} 股", f"${tot_fund:,.0f}", f"保本 ${breakeven:.2f}"],
            ]

            research_result_col.controls.extend([
                make_table_box(
                    f"{tkr} 建倉試算 ({'已延伸暫停追價' if is_ext else f'有效額度 ${target_budget:,.0f}'})",
                    plan_headers,
                    plan_rows,
                    "#22543d",
                ),
                make_btn(f"➕ 一鍵將 {tkr} 加入持倉與減碼追蹤", add_to_portfolio, "#38a169", pad=8),
            ])
        else:
            def set_drift(m):
                def _fn(e):
                    mc_drift_mode[0] = m
                    render_research_subviews(total_portfolio_equity, cash_pool)
                    page.update()
                return _fn

            is_trend = mc_drift_mode[0] == "trend"
            drift_bar = ft.Row([
                make_btn("📈 歷史趨勢漂移", set_drift("trend"), "#38a169" if is_trend else "#1e293b", pad=5, expand=1),
                make_btn("⚖️ 0漂移隨機漫步", set_drift("zero"), "#38a169" if not is_trend else "#1e293b", pad=5, expand=1),
            ], spacing=4)

            def run_single_mc(trials: int):
                async def _task():
                    status_text.value = f"⏳ 執行 {tkr} {trials} 次單股 MC..."
                    status_text.color = "#ecc94b"
                    page.update()

                    def _calc():
                        n_days = 21
                        vol = q.get("Daily_Vol", 0.025)
                        mu = q.get("Daily_Drift", 0.0004) if mc_drift_mode[0] == "trend" else 0.0
                        hit_target = 0
                        hit_stop = 0
                        final_prices = []
                        mc_target = active_fib_target if not is_ext else round(cur_p * 1.08, 2)

                        for _ in range(trials):
                            p = cur_p
                            reached_t = False
                            reached_s = False
                            for _ in range(n_days):
                                ret = random.gauss(mu, vol)
                                p = max(0.01, p * (1.0 + ret))
                                if p >= mc_target:
                                    reached_t = True
                                if p <= hard_stop:
                                    reached_s = True
                            if reached_t:
                                hit_target += 1
                            if reached_s:
                                hit_stop += 1
                            final_prices.append(p)

                        final_prices.sort()
                        p5 = final_prices[int(trials * 0.05)]
                        p50 = final_prices[int(trials * 0.50)]
                        p95 = final_prices[int(trials * 0.95)]
                        win_prob = (hit_target / trials) * 100.0
                        loss_prob = (hit_stop / trials) * 100.0
                        return win_prob, loss_prob, p5, p50, p95, mc_target

                    win_prob, loss_prob, p5, p50, p95, mc_target = await asyncio.to_thread(_calc)
                    research_mc_result_col.controls.clear()
                    mc_headers = ["21天波動機率參考", "模擬估計值", "相對現價 / 條件說明"]
                    mc_rows = [
                        ["觸及目標關卡機率", f"{win_prob:.1f}%", f"期間曾觸及 ${mc_target:.2f}"],
                        ["觸及硬性停損機率", f"{loss_prob:.1f}%", f"期間曾跌破停損 ${hard_stop:.2f}"],
                        ["期末中位價\n(P50)", f"${p50:.2f}", f"預期中位變動 {(p50 - cur_p) / cur_p * 100.0:+.1f}%"],
                        ["悲觀分位價\n(P5)", f"${p5:.2f}", f"下檔尾端風險 {(p5 - cur_p) / cur_p * 100.0:+.1f}%"],
                        ["樂觀分位價\n(P95)", f"${p95:.2f}", f"上檔潛在空間 {(p95 - cur_p) / cur_p * 100.0:+.1f}%"],
                    ]
                    research_mc_result_col.controls.append(
                        make_table_box(f"{tkr} 單股蒙地卡羅參考 ({trials}次)", mc_headers, mc_rows, "#2c5282")
                    )
                    status_text.value = f"✅ {tkr} MC 完成"
                    status_text.color = "#68d391"
                    page.update()

                page.run_task(_task)

            research_result_col.controls.extend([
                drift_bar,
                ft.Row([
                    make_btn("200次", lambda e: run_single_mc(200), "#2b6cb0", pad=6, expand=1),
                    make_btn("500次", lambda e: run_single_mc(500), "#2b6cb0", pad=6, expand=1),
                    make_btn("1000次", lambda e: run_single_mc(1000), "#2b6cb0", pad=6, expand=1),
                    make_btn("2000次", lambda e: run_single_mc(2000), "#1e3a8a", pad=6, expand=1),
                ], spacing=4),
                research_mc_result_col,
            ])

    render_main_nav()
    page.controls.clear()
    page.add(
        ft.Container(height=36),
        ft.Container(
            bgcolor="#161b26",
            border_radius=8,
            padding=8,
            content=ft.Column([
                ft.Row([
                    ft.Text("美股量化風控", size=15, weight=ft.FontWeight.BOLD, color="#ffffff"),
                    status_text,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                main_nav_col,
            ], spacing=5),
        ),
        page0_overview_col,
        page1_holdings_col,
        page2_fib_col,
        page3_calc_col,
        page4_trim_col,
        page5_research_col,
        ft.Container(height=28),
    )

    init_res = compute_rows(use_network=False, force_api=False)
    update_ui_from_rows(*init_res)
    refresh_all(force_api=False, use_network=True)


if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)