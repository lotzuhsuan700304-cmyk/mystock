import os
import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf

# ==========================================
# 1. 頁面與深色專業看盤 CSS 配置 (移植自方案 A)
# ==========================================
st.set_page_config(
    page_title="美股量化風控 × 費波納契 × 半凱利操盤系統",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .kpi-card {
        background-color: #151c2c;
        border: 1px solid #263147;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }
    .kpi-title { font-size: 0.78rem; color: #94a3b8; font-weight: 500; }
    .kpi-value { font-size: 1.55rem; font-weight: 700; color: #f8fafc; margin-top: 4px; }
    .kpi-sub { font-size: 0.75rem; color: #64748b; margin-top: 4px; }
    .fib-box {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 12px;
        height: 100%;
    }
    .fib-box-highlight {
        background-color: #0f172a;
        border: 1px solid #3b82f6;
        border-radius: 10px;
        padding: 12px;
        height: 100%;
    }
</style>
""", unsafe_allow_html=True)

SAVE_FILE = "portfolio_saved.csv"

# 初始庫存數據 (依據複委託帳戶截圖基準)
DEFAULT_PORTFOLIO = [
    {"Ticker": "NBIS", "YahooTicker": "NBIS", "Name": "尼比厄斯", "Shares": 600, "AvgCost": 226.215, "Price": 176.9999, "ATR": 9.50, "RSI": 33.5, "WinRate": 0.48, "Stop": 165.39, "TargetCap": 0.15, "TargetShares": 333},
    {"Ticker": "MRVL", "YahooTicker": "MRVL", "Name": "Marvell", "Shares": 350, "AvgCost": 255.965, "Price": 234.5100, "ATR": 7.20, "RSI": 45.2, "WinRate": 0.58, "Stop": 225.00, "TargetCap": 0.18, "TargetShares": 233},
    {"Ticker": "MU",   "YahooTicker": "MU",   "Name": "美光科技", "Shares": 50,  "AvgCost": 516.017, "Price": 898.9400, "ATR": 32.00, "RSI": 68.4, "WinRate": 0.55, "Stop": 845.00, "TargetCap": 0.15, "TargetShares": 35},
    {"Ticker": "AVGO", "YahooTicker": "AVGO", "Name": "Broadcom", "Shares": 100, "AvgCost": 325.207, "Price": 338.2400, "ATR": 8.50, "RSI": 56.1, "WinRate": 0.62, "Stop": 328.00, "TargetCap": 0.15, "TargetShares": 100},
    {"Ticker": "MEME", "YahooTicker": "MEME", "Name": "Memory ETF", "Shares": 350, "AvgCost": 68.393, "Price": 47.6500, "ATR": 1.90, "RSI": 31.0, "WinRate": 0.40, "Stop": 44.50, "TargetCap": 0.00, "TargetShares": 0},
    {"Ticker": "PLTR", "YahooTicker": "PLTR", "Name": "帕蘭提爾", "Shares": 50,  "AvgCost": 178.932, "Price": 196.2550, "ATR": 6.80, "RSI": 61.2, "WinRate": 0.56, "Stop": 185.55, "TargetCap": 0.05, "TargetShares": 50},
    {"Ticker": "INTC", "YahooTicker": "INTC", "Name": "英特爾",   "Shares": 15,  "AvgCost": 117.818, "Price": 92.9300,  "ATR": 3.10, "RSI": 38.5, "WinRate": 0.35, "Stop": 88.00,  "TargetCap": 0.00, "TargetShares": 0},
]

# 初始化 Session State
if "portfolio_df" not in st.session_state:
    if os.path.exists(SAVE_FILE):
        try:
            st.session_state.portfolio_df = pd.read_csv(SAVE_FILE)
        except Exception:
            st.session_state.portfolio_df = pd.DataFrame(DEFAULT_PORTFOLIO)
    else:
        st.session_state.portfolio_df = pd.DataFrame(DEFAULT_PORTFOLIO)


# ==========================================
# 2. 輔助運算函數 (費氏交易日、Yahoo 抓價 + ATR/RSI)
# ==========================================
US_HOLIDAYS = {
    datetime.date(2026, 11, 26),
    datetime.date(2026, 12, 25),
    datetime.date(2027, 1, 1),
    datetime.date(2027, 1, 18),
}

def add_us_trading_days(start_date: datetime.date, n_days: int) -> datetime.date:
    curr = start_date
    count = 0
    while count < n_days:
        curr += datetime.timedelta(days=1)
        if curr.weekday() < 5 and curr not in US_HOLIDAYS:
            count += 1
    return curr

def fetch_live_market_data(df: pd.DataFrame) -> pd.DataFrame:
    updated = df.copy()
    for idx, row in updated.iterrows():
        ytk = str(row.get("YahooTicker", row["Ticker"])).strip()
        try:
            ticker_obj = yf.Ticker(ytk)
            hist = ticker_obj.history(period="3mo")
            if not hist.empty and len(hist) >= 15:
                # 最新收盤價
                latest_close = float(hist["Close"].iloc[-1])
                updated.at[idx, "Price"] = round(latest_close, 4)

                # 計算真實 14 日 ATR
                high_low = hist["High"] - hist["Low"]
                high_close = (hist["High"] - hist["Close"].shift(1)).abs()
                low_close = (hist["Low"] - hist["Close"].shift(1)).abs()
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr_14 = float(tr.rolling(window=14).mean().iloc[-1])
                if not np.isnan(atr_14) and atr_14 > 0:
                    updated.at[idx, "ATR"] = round(atr_14, 2)

                # 計算 14 日 RSI
                delta = hist["Close"].diff()
                gain = delta.clip(lower=0).rolling(window=14).mean()
                loss = (-delta.clip(upper=0)).rolling(window=14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi_14 = float((100 - (100 / (1 + rs))).iloc[-1])
                if not np.isnan(rsi_14):
                    updated.at[idx, "RSI"] = round(rsi_14, 1)
        except Exception:
            continue
    return updated

def compute_quant_table(df: pd.DataFrame, shock_pct: float, beta_mult: float) -> pd.DataFrame:
    calc = df.copy()
    # 壓力測試模擬價格
    impact = (shock_pct / 100.0) * beta_mult
    calc["SimPrice"] = (calc["Price"] * (1.0 + impact)).round(4)
    calc["MarketValue"] = calc["Shares"] * calc["SimPrice"]
    calc["TotalCost"] = calc["Shares"] * calc["AvgCost"]
    calc["PnL"] = calc["MarketValue"] - calc["TotalCost"]
    calc["Return(%)"] = np.where(calc["TotalCost"] > 0, (calc["PnL"] / calc["TotalCost"]) * 100, 0.0)

    total_mkt = calc["MarketValue"].sum()
    calc["Weight(%)"] = np.where(total_mkt > 0, (calc["MarketValue"] / total_mkt) * 100, 0.0)
    calc["TargetWeight(%)"] = calc["TargetCap"] * 100.0

    # 費波納契價位計算 (區分套牢反彈 vs. 獲利回撤與擴展)
    diff = (calc["SimPrice"] - calc["AvgCost"]).abs()
    underwater = calc["SimPrice"] < calc["AvgCost"]

    calc["Fib_0236"] = np.where(underwater, calc["SimPrice"] + diff * 0.236, calc["SimPrice"] - diff * 0.236)
    calc["Fib_0382"] = np.where(underwater, calc["SimPrice"] + diff * 0.382, calc["SimPrice"] - diff * 0.382)
    calc["Fib_0500"] = np.where(underwater, calc["SimPrice"] + diff * 0.500, calc["SimPrice"] - diff * 0.500)
    calc["Fib_0618"] = np.where(underwater, calc["SimPrice"] + diff * 0.618, calc["SimPrice"] - diff * 0.618)
    calc["Fib_1272"] = np.where(underwater, calc["SimPrice"] + diff * 1.272, calc["AvgCost"] + diff * 1.272)
    calc["Fib_1618"] = np.where(underwater, calc["SimPrice"] + diff * 1.618, calc["AvgCost"] + diff * 1.618)

    # 計算賠率 (Odds b)、波段期望值 E[R] 與 半凱利倉位 (0.5f*)
    upside_target = np.where(underwater, calc["Fib_0618"], calc["Fib_1272"])
    up_pct = np.maximum(0.005, (upside_target - calc["SimPrice"]) / calc["SimPrice"])
    down_pct = np.maximum(0.005, (calc["SimPrice"] - calc["Stop"]) / calc["SimPrice"])

    calc["Odds(b)"] = (up_pct / down_pct).round(2)
    p = calc["WinRate"]
    q = 1.0 - p
    calc["ExpReturn(%)"] = ((p * up_pct - q * down_pct) * 100).round(2)
    calc["HalfKelly(%)"] = (np.maximum(0.0, 0.5 * (p - q / calc["Odds(b)"])) * 100).round(1)

    # 自動生成即時量化操盤訊號 (整合自方案 A)
    signals = []
    for _, r in calc.iterrows():
        if r["SimPrice"] <= r["Stop"]:
            signals.append("🚨 觸及停損/鎖利防線！立即減碼")
        elif r["Ticker"] in ["INTC", "MEME"]:
            signals.append("🔴 非核心/重疊曝險：逢彈出清")
        elif r["SimPrice"] < r["AvgCost"] and r["SimPrice"] >= r["Fib_0382"]:
            signals.append("🎯 進入費氏減碼區：執行分批調節")
        elif r["SimPrice"] >= r["Fib_1272"]:
            signals.append("💰 達 1.272 擴展目標：右側分批停利")
        elif r["Shares"] > r["TargetShares"]:
            trim_n = int(r["Shares"] - r["TargetShares"])
            signals.append(f"⚠️ 權重超配：待反彈減碼 {trim_n} 股")
        else:
            signals.append("✅ 守穩防線：核心部位續抱")
    calc["即時量化指令"] = signals
    return calc


# ==========================================
# 3. 側邊欄控制中心 (整合方案 A 存取與方案 B 抓價/壓測)
# ==========================================
with st.sidebar:
    st.header("⚙️ 量化控制與數據同步")

    if st.button("🔄 一鍵同步 Yahoo 即時價 + 14D ATR/RSI", use_container_width=True, type="primary"):
        with st.spinner("正在從 Yahoo Finance 同步最新報價與計算 14 日 ATR / RSI..."):
            st.session_state.portfolio_df = fetch_live_market_data(st.session_state.portfolio_df)
        st.success("✅ 已完成最新市價、ATR 與 RSI 更新！")

    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        if st.button("💾 儲存參數", use_container_width=True):
            st.session_state.portfolio_df.to_csv(SAVE_FILE, index=False)
            st.toast("✅ 已儲存至本機 portfolio_saved.csv！")
    with col_sb2:
        if st.button("🔄 重置初始", use_container_width=True):
            st.session_state.portfolio_df = pd.DataFrame(DEFAULT_PORTFOLIO)
            if os.path.exists(SAVE_FILE):
                os.remove(SAVE_FILE)
            st.rerun()

    st.divider()
    st.subheader("⏱️ 費氏時間週期起算錨點 ($T_0$)")
    anchor_date = st.date_input("選擇波段基準日 ($T_0$)", value=datetime.date(2026, 10, 16))

    st.divider()
    st.subheader("📉 系統性風險壓力測試")
    shock_pct = st.slider("大盤漲跌衝擊模擬 (%)", min_value=-30, max_value=20, value=0, step=5)
    beta_mult = st.slider("高 Beta 科技股敏感度倍數", min_value=1.0, max_value=2.0, value=1.5, step=0.1)

    st.divider()
    st.subheader("📤 匯入自訂 CSV 風控表")
    uploaded_csv = st.file_uploader("上傳 CSV 覆蓋當前表格", type=["csv"])
    if uploaded_csv is not None:
        try:
            user_df = pd.read_csv(uploaded_csv)
            st.session_state.portfolio_df = user_df
            st.success("✅ 已成功載入自訂 CSV！")
        except Exception as e:
            st.error(f"讀取失敗: {e}")


# ==========================================
# 4. 頂部標題與 5 大核心量化 KPI 卡片 (方案 A 介面)
# ==========================================
st.markdown("## 📊 美股量化風控 × 費波納契 × 半凱利操盤系統")
st.caption("結合 Python `yfinance` 自動化行情抓取、費波納契時空共振（0.382 / 0.618 / 1.272 + 時間轉折窗）、ATR 動態停損與半凱利 ($0.5f^*$) 部位優化模型")

# 先以當前 session_state 計算初始展示指標
calc_df = compute_quant_table(st.session_state.portfolio_df, shock_pct, beta_mult)

sum_mkt = calc_df["MarketValue"].sum()
sum_cost = calc_df["TotalCost"].sum()
sum_pnl = calc_df["PnL"].sum()
total_ret = (sum_pnl / sum_cost * 100) if sum_cost > 0 else 0.0

sorted_weights = calc_df.sort_values("Weight(%)", ascending=False)["Weight(%)"]
top2_weight = sorted_weights.iloc[:2].sum() if len(sorted_weights) >= 2 else 0.0

# 計算單週 95% VaR (考量高相关性科技股投組效應)
daily_var_95 = (calc_df["Shares"] * calc_df["ATR"] * 1.65).sum() * 0.55
weekly_var_95 = daily_var_95 * np.sqrt(5)

# 計算依目標股數減碼後可釋出之防禦資金池
excess_shares = np.maximum(0, calc_df["Shares"] - calc_df["TargetShares"])
released_cash = (excess_shares * calc_df["SimPrice"]).sum()
released_pct = (released_cash / sum_mkt * 100) if sum_mkt > 0 else 0.0

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">股票總市值 (USD)</div>
        <div class="kpi-value">${sum_mkt:,.2f}</div>
        <div class="kpi-sub">總投入成本: ${sum_cost:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    pnl_color = "#34d399" if sum_pnl >= 0 else "#fb7185"
    sign = "+" if sum_pnl >= 0 else ""
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">未實現總損益 (USD / %)</div>
        <div class="kpi-value" style="color: {pnl_color};">{sign}${sum_pnl:,.2f}</div>
        <div class="kpi-sub" style="color: {pnl_color};">總報酬率: {sign}{total_ret:.2f}% (壓測: {shock_pct*beta_mult:+.1f}%)</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    top2_color = "#fbbf24" if top2_weight > 35 else "#34d399"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">前兩大持股集中度 (NBIS+MRVL)</div>
        <div class="kpi-value" style="color: {top2_color};">{top2_weight:.2f}%</div>
        <div class="kpi-sub">半凱利建議安全上限: ≤ 35.0%</div>
    </div>
    """, unsafe_allow_html=True)

with k4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">單週 95% 風險價值 (5-Day VaR)</div>
        <div class="kpi-value" style="color: #fb7185;">-${weekly_var_95:,.0f}</div>
        <div class="kpi-sub">單日 95% VaR: -${daily_var_95:,.0f} (基於 ATR)</div>
    </div>
    """, unsafe_allow_html=True)

with k5:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">減碼可釋出防禦資金池</div>
        <div class="kpi-value" style="color: #34d399;">${released_cash:,.0f}</div>
        <div class="kpi-sub">佔總市值 {released_pct:.1f}% (目標防禦配置 ~30%)</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ==========================================
# 5. 費波納契時間週期變盤視窗 (移植自方案 A 並加入倒數計時)
# ==========================================
st.markdown("#### ⏱️ 費波納契時間週期變盤視窗（Fibonacci Time Zones）")
fib_windows = [
    ("T+5 短線確認窗", 5, "檢視 NBIS $175 / MRVL $233 支撐與 5MA 翻揚", "#f59e0b"),
    ("T+8 第一減碼窗", 8, "觀察反彈測試 0.236~0.382 壓力區動能", "#f59e0b"),
    ("T+13 波段分水嶺", 13, "日線月線 (20MA) 扣抵，執行第一階段減碼", "#3b82f6"),
    ("T+21 中期轉折窗", 21, "挑戰 0.618 黃金分割強壓區與財報指引兌現", "#10b981"),
    ("T+34 季線大變盤窗", 34, "60MA 季線方向定調與完成組合再平衡", "#a855f7"),
]

f_cols = st.columns(5)
today_date = datetime.date.today()
for idx, (label, days_n, desc, color_hex) in enumerate(fib_windows):
    target_dt = add_us_trading_days(anchor_date, days_n)
    delta_days = (target_dt - today_date).days
    countdown_str = f"還有 {delta_days} 天" if delta_days > 0 else ("🔥 今日變盤！" if delta_days == 0 else f"已過 {-delta_days} 天")
    box_class = "fib-box-highlight" if 0 <= delta_days <= 4 else "fib-box"
    with f_cols[idx]:
        st.markdown(f"""
        <div class="{box_class}">
            <div style="color: {color_hex}; font-weight: 700; font-size: 0.82rem;">{label} ({countdown_str})</div>
            <div style="color: #ffffff; font-weight: 700; font-size: 1.05rem; margin-top: 4px;">{target_dt.strftime('%Y/%m/%d')}</div>
            <div style="color: #94a3b8; font-size: 0.75rem; margin-top: 4px;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")

# ==========================================
# 6. 核心操作分頁 (Tab 1: 互動風控總表 | Tab 2: 圖表分析 | Tab 3: 分批減碼模擬器)
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "📋 互動式風控追蹤主表 (可即時改價)",
    "📈 視覺化權重與費氏價位階梯圖",
    "🧮 NBIS & MRVL 三階梯減碼模擬器"
])

with tab1:
    st.markdown("##### ✏️ 第 1 步：直接雙擊下方表格修改【股數、目前市價、ATR、勝率、左側停損價或目標保留股數】")
    edited_raw = st.data_editor(
        st.session_state.portfolio_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Ticker": st.column_config.TextColumn("代碼", width="small"),
            "YahooTicker": st.column_config.TextColumn("Yahoo代碼", width="small"),
            "Name": st.column_config.TextColumn("名稱", width="small"),
            "Shares": st.column_config.NumberColumn("持有股數", step=1, format="%d"),
            "AvgCost": st.column_config.NumberColumn("持有均價($)", format="$%.3f"),
            "Price": st.column_config.NumberColumn("目前市價($)", format="$%.4f"),
            "ATR": st.column_config.NumberColumn("14D ATR($)", format="$%.2f"),
            "RSI": st.column_config.NumberColumn("14D RSI", format="%.1f"),
            "WinRate": st.column_config.NumberColumn("預估勝率(p)", min_value=0.05, max_value=0.95, step=0.01, format="%.2f"),
            "Stop": st.column_config.NumberColumn("左側停損/鎖利($)", format="$%.2f"),
            "TargetCap": st.column_config.NumberColumn("目標權重上限", min_value=0.0, max_value=1.0, step=0.01, format="%.2f"),
            "TargetShares": st.column_config.NumberColumn("目標保留股數", step=1, format="%d"),
        },
        key="main_editor"
    )

    # 若用戶編輯了表格，立即同步並重算
    st.session_state.portfolio_df = edited_raw
    calc_df = compute_quant_table(edited_raw, shock_pct, beta_mult)

    st.markdown("##### 🎯 第 2 步：即時自動重算之【費波納契價位 × 半凱利最佳倉位 × 量化指令總表】")
    display_cols = [
        "Ticker", "Name", "Shares", "AvgCost", "SimPrice", "MarketValue",
        "PnL", "Return(%)", "Weight(%)", "HalfKelly(%)", "TargetShares",
        "Stop", "Fib_0382", "Fib_0500", "Fib_0618", "Fib_1272", "即時量化指令"
    ]

    st.dataframe(
        calc_df[display_cols].style.format({
            "AvgCost": "${:,.2f}",
            "SimPrice": "${:,.2f}",
            "MarketValue": "${:,.2f}",
            "PnL": "{:+,.2f}",
            "Return(%)": "{:+.2f}%",
            "Weight(%)": "{:.2f}%",
            "HalfKelly(%)": "{:.1f}%",
            "Stop": "${:,.2f}",
            "Fib_0382": "${:,.2f}",
            "Fib_0500": "${:,.2f}",
            "Fib_0618": "${:,.2f}",
            "Fib_1272": "${:,.2f}",
        }),
        use_container_width=True,
        height=320
    )

    # 匯出 CSV 按鈕 (方案 A 功能)
    csv_bytes = calc_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 匯出完整量化風控追蹤報表 (us_portfolio_risk_tracker.csv)",
        data=csv_bytes,
        file_name="us_portfolio_risk_tracker.csv",
        mime="text/csv",
    )

with tab2:
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        fig_w = go.Figure()
        fig_w.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["Weight(%)"], name="目前實際市值權重 (%)", marker_color="#3b82f6"))
        fig_w.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["HalfKelly(%)"], name="理論半凱利倉位 (0.5f* %)", marker_color="#f59e0b"))
        fig_w.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["TargetWeight(%)"], name="相關性調整後目標權重 (%)", marker_color="#10b981"))
        fig_w.update_layout(
            title="📊 投組權重對比：目前實際 vs. 理論半凱利 vs. 目標權重 (%)",
            barmode="group",
            template="plotly_dark",
            paper_bgcolor="#151c2c",
            plot_bgcolor="#151c2c",
            height=400,
            legend=dict(orientation="h", y=1.12)
        )
        st.plotly_chart(fig_w, use_container_width=True)

    with col_c2:
        fig_fib = go.Figure()
        fig_fib.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["Stop"], name="左側停損/鎖利防線 ($)", marker_color="#f43f5e"))
        fig_fib.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["SimPrice"], name="目前市價 ($)", marker_color="#38bdf8"))
        fig_fib.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["Fib_0382"], name="費氏 0.382 位 ($)", marker_color="#fbbf24"))
        fig_fib.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["Fib_0618"], name="費氏 0.618 黃金分割位 ($)", marker_color="#a855f7"))
        fig_fib.add_trace(go.Bar(x=calc_df["Ticker"], y=calc_df["Fib_1272"], name="費氏 1.272 擴展目標 ($)", marker_color="#10b981"))
        fig_fib.update_layout(
            title="🎯 個股現價與費波納契關鍵價位階梯對照圖 (USD)",
            barmode="group",
            template="plotly_dark",
            paper_bgcolor="#151c2c",
            plot_bgcolor="#151c2c",
            height=400,
            legend=dict(orientation="h", y=1.12)
        )
        st.plotly_chart(fig_fib, use_container_width=True)

    col_c3, col_c4 = st.columns(2)
    with col_c3:
        fig_pie1 = px.pie(
            calc_df, values="MarketValue", names="Ticker", hole=0.42,
            title="目前投資組合市值分佈 (100% 科技股暴露)",
            template="plotly_dark"
        )
        fig_pie1.update_layout(paper_bgcolor="#151c2c", height=360)
        st.plotly_chart(fig_pie1, use_container_width=True)

    with col_c4:
        target_vals = calc_df["TargetShares"] * calc_df["SimPrice"]
        rebal_df = pd.DataFrame({
            "Asset": list(calc_df["Ticker"]) + ["防禦收息資產/美元現金池 (PLD/SGOV)"],
            "Value": list(target_vals) + [released_cash]
        })
        rebal_df = rebal_df[rebal_df["Value"] > 0]
        fig_pie2 = px.pie(
            rebal_df, values="Value", names="Asset", hole=0.42,
            title="執行半凱利與費氏減碼後之目標資產配置",
            template="plotly_dark"
        )
        fig_pie2.update_layout(paper_bgcolor="#151c2c", height=360)
        st.plotly_chart(fig_pie2, use_container_width=True)

with tab3:
    st.markdown("##### 🧮 核心超配股（NBIS & MRVL）費波納契分批減碼執行模擬器")
    st.caption("自動模擬在費氏 0.382、0.500、0.618 階梯掛單減碼後，實際收回之現金、已實現損益與剩餘核心部位表現：")

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        st.markdown("###### 🔴 NBIS（尼比厄斯｜現有 600 股，目標保留 333 股，共減碼 267 股）")
        nbis_row = calc_df[calc_df["Ticker"] == "NBIS"].iloc[0]
        nbis_plan = pd.DataFrame([
            {"執行階段": "第一批 (0.382 反彈位)", "目標委賣價 ($)": round(nbis_row["Fib_0382"], 2), "減碼股數": 87, "收回現金 ($)": round(87 * nbis_row["Fib_0382"], 2), "階段實現損益 ($)": round(87 * (nbis_row["Fib_0382"] - nbis_row["AvgCost"]), 2)},
            {"執行階段": "第二批 (0.500 分水嶺)", "目標委賣價 ($)": round(nbis_row["Fib_0500"], 2), "減碼股數": 90, "收回現金 ($)": round(90 * nbis_row["Fib_0500"], 2), "階段實現損益 ($)": round(90 * (nbis_row["Fib_0500"] - nbis_row["AvgCost"]), 2)},
            {"執行階段": "第三批 (0.618 強壓區)", "目標委賣價 ($)": round(nbis_row["Fib_0618"], 2), "減碼股數": 90, "收回現金 ($)": round(90 * nbis_row["Fib_0618"], 2), "階段實現損益 ($)": round(90 * (nbis_row["Fib_0618"] - nbis_row["AvgCost"]), 2)},
        ])
        st.dataframe(nbis_plan, use_container_width=True, hide_index=True)
        st.info(f"💡 **NBIS 三批減碼合計收回現金**：**${nbis_plan['收回現金 ($)'].sum():,.2f}** ｜ 剩餘 **333 股** 續抱等待重返成本區 **${nbis_row['AvgCost']:.2f}**。")

    with sim_col2:
        st.markdown("###### 🟡 MRVL（Marvell｜現有 350 股，目標保留 233 股，共減碼 117 股）")
        mrvl_row = calc_df[calc_df["Ticker"] == "MRVL"].iloc[0]
        mrvl_plan = pd.DataFrame([
            {"執行階段": "第一批 (0.618 黃金分割位)", "目標委賣價 ($)": round(mrvl_row["Fib_0618"], 2), "減碼股數": 57, "收回現金 ($)": round(57 * mrvl_row["Fib_0618"], 2), "階段實現損益 ($)": round(57 * (mrvl_row["Fib_0618"] - mrvl_row["AvgCost"]), 2)},
            {"執行階段": "第二批 (1.000 成本解套區)", "目標委賣價 ($)": round(mrvl_row["AvgCost"], 2), "減碼股數": 60, "收回現金 ($)": round(60 * mrvl_row["AvgCost"], 2), "階段實現損益 ($)": 0.00},
        ])
        st.dataframe(mrvl_plan, use_container_width=True, hide_index=True)
        st.info(f"💡 **MRVL 兩批減碼合計收回現金**：**${mrvl_plan['收回現金 ($)'].sum():,.2f}** ｜ 剩餘 **233 股** 上看 1.272 擴展目標 **${mrvl_row['Fib_1272']:.2f}**。")
