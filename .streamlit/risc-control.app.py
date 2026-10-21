import os
import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf

# ==========================================
# 1. 頁面與深色專業看盤 CSS 配置 (方案 A + B 旗艦版)
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
        background: linear-gradient(145deg, #161b26, #1e2536);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        height: 100%;
    }
    .kpi-title { color: #a0aec0; font-size: 0.85rem; margin-bottom: 6px; }
    .kpi-val { font-size: 1.65rem; font-weight: 700; margin-bottom: 6px; }
    .kpi-sub { color: #718096; font-size: 0.78rem; }
    .tz-card {
        background-color: #131822;
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 14px;
        height: 100%;
    }
    .tz-highlight {
        border: 1.5px solid #3182ce;
        background-color: #152238;
    }
    .gate-pass {
        background-color: rgba(34, 197, 94, 0.12);
        border-left: 4px solid #22c55e;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .gate-block {
        background-color: rgba(239, 68, 68, 0.12);
        border-left: 4px solid #ef4444;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 初始投資組合配置 (已移除 INTC，NBIS 550 股)
# ==========================================
DEFAULT_PORTFOLIO = [
    {"Ticker": "NBIS", "Name": "Nebius Group", "Shares": 550, "Avg_Cost": 226.215, "Target_Kelly_Pct": 15.0, "Hard_Stop": 159.00, "Key_Fib_Target": 195.80},
    {"Ticker": "MRVL", "Name": "Marvell Tech", "Shares": 350, "Avg_Cost": 255.965, "Target_Kelly_Pct": 15.0, "Hard_Stop": 218.00, "Key_Fib_Target": 247.77},
    {"Ticker": "MU",   "Name": "Micron Tech",  "Shares": 50,  "Avg_Cost": 516.017, "Target_Kelly_Pct": 15.0, "Hard_Stop": 880.00, "Key_Fib_Target": 1003.10},
    {"Ticker": "AVGO", "Name": "Broadcom Inc", "Shares": 100, "Avg_Cost": 325.207, "Target_Kelly_Pct": 15.0, "Hard_Stop": 325.20, "Key_Fib_Target": 358.50},
    {"Ticker": "DRAM", "Name": "Roundhill ETF","Shares": 350, "Avg_Cost": 68.393,  "Target_Kelly_Pct": 5.0,  "Hard_Stop": 44.50,  "Key_Fib_Target": 52.55},
    {"Ticker": "PLTR", "Name": "Palantir Tech","Shares": 50,  "Avg_Cost": 178.932, "Target_Kelly_Pct": 10.0, "Hard_Stop": 185.55, "Key_Fib_Target": 200.97},
]

if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = pd.DataFrame(DEFAULT_PORTFOLIO)

# ==========================================
# 3. 側邊欄：即時報價、盤前交易與資金設定
# ==========================================
with st.sidebar:
    st.markdown("### 📡 即時行情與盤前交易設定")
    enable_live_feed = st.toggle("🌐 自動抓取即時行情 (yfinance)", value=True, help="開啟時自動透過 yfinance 抓取即時報價；關閉時保留主表手動改價")
    include_extended = st.checkbox("🌅 包含盤前/盤後延長交易價格", value=True, help="開啟時在盤前 (台灣 16:00 起) 與盤後優先抓取延長交易撮合價")
    
    if st.button("⚡ 立即強制更新即時報價", use_container_width=True):
        st.cache_data.clear()
        st.success("已清空行情快取，重新連線最新報價！")
        st.rerun()

    st.divider()
    st.markdown("### 💰 資金池與帳戶配置")
    cash_pool = st.number_input(
        "可用美元現金池 (USD Cash)",
        min_value=0.0,
        value=9616.50,
        step=500.0,
        help="整合 INTC 出清 ($1,353.00) + NBIS 減碼 50 股 ($8,263.50) 之現金儲備"
    )
    realized_loss_tax = st.number_input(
        "累計可抵稅已實現虧損 (USD)",
        value=-3461.52,
        step=100.0,
        help="INTC (-$414.27) + NBIS (-$3,047.25) 稅務抵扣池"
    )

    st.divider()
    st.markdown("### 📉 系統性風險壓力測試")
    market_shock = st.slider("大盤漲跌衝擊模擬 (%)", min_value=-30, max_value=20, value=0, step=1)
    beta_mult = st.slider("高 Beta 科技股敏感度倍數", min_value=1.00, max_value=2.50, value=1.50, step=0.05)

    st.divider()
    st.markdown("### ⚙️ 半凱利風控參數")
    default_kelly_cap = st.slider("新股預設半凱利單檔上限 (%)", min_value=5.0, max_value=25.0, value=15.0, step=1.0)
    if st.button("🔄 重置為預設持股狀態"):
        st.session_state.portfolio_df = pd.DataFrame(DEFAULT_PORTFOLIO)
        st.rerun()

# ==========================================
# 4. 行情抓取引擎 (支援常規盤與盤前/盤後延長交易)
# ==========================================
@st.cache_data(ttl=30)
def fetch_ticker_quant_metrics(ticker: str, get_extended: bool = True):
    try:
        tk = yf.Ticker(ticker.strip().upper())
        hist = tk.history(period="1y")
        if hist.empty:
            return None
        
        reg_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else reg_close

        # 嘗試抓取盤前/盤後 1 分鐘延長交易最新報價
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

        # 近 6 個月波段高低點
        recent = hist.tail(126)
        swing_high = float(recent["High"].max())
        swing_low = float(recent["Low"].min())
        diff = max(swing_high - swing_low, 0.01)

        # 費波納契價位
        fib_0236 = swing_low + diff * 0.236
        fib_0382 = swing_low + diff * 0.382
        fib_0618 = swing_low + diff * 0.618
        fib_1272 = swing_low + diff * 1.272
        fib_neg0236 = swing_low - diff * 0.236

        # 14D ATR
        high_low = hist["High"] - hist["Low"]
        high_close = (hist["High"] - hist["Close"].shift()).abs()
        low_close = (hist["Low"] - hist["Close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr_14 = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else reg_close * 0.04

        # 14D RSI
        delta = hist["Close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi_14 = float((100 - (100 / (1 + rs))).iloc[-1]) if not rs.dropna().empty else 50.0

        # 均線系統
        ma20 = float(hist["Close"].rolling(20).mean().iloc[-1]) if len(hist) >= 20 else reg_close
        ma50 = float(hist["Close"].rolling(50).mean().iloc[-1]) if len(hist) >= 50 else reg_close
        ma200 = float(hist["Close"].rolling(200).mean().iloc[-1]) if len(hist) >= 200 else ma50

        return {
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
            "Fib_Neg0236": round(fib_neg0236, 2),
            "ATR": round(atr_14, 2),
            "RSI": round(rsi_14, 1),
            "MA20": round(ma20, 2),
            "MA50": round(ma50, 2),
            "MA200": round(ma200, 2),
        }
    except Exception:
        return None

# 結合持股與即時行情
df_base = st.session_state.portfolio_df.copy()
shock_factor = 1.0 + (market_shock / 100.0) * beta_mult

live_rows = []
for idx, row in df_base.iterrows():
    tkr = str(row["Ticker"]).strip().upper()
    if not tkr:
        continue
    
    if enable_live_feed:
        q = fetch_ticker_quant_metrics(tkr, get_extended=include_extended)
        raw_price = q["Price"] if q else float(row.get("Avg_Cost", 100.0))
        atr_val = q["ATR"] if q else round(raw_price * 0.045, 2)
        fib382 = q["Fib_0382"] if q else round(raw_price * 1.12, 2)
        fib618 = q["Fib_0618"] if q else round(raw_price * 1.22, 2)
        ma20_val = q["MA20"] if q else raw_price
        ma200_val = q["MA200"] if q else raw_price
        session_label = q["Session"] if q else "自訂"
        day_chg = q["Day_Chg_Pct"] if q else 0.0
    else:
        raw_price = float(row.get("Price", row.get("Avg_Cost", 100.0)))
        atr_val = round(raw_price * 0.045, 2)
        fib382 = round(raw_price * 1.12, 2)
        fib618 = round(raw_price * 1.22, 2)
        ma20_val = raw_price
        ma200_val = raw_price
        session_label = "手動離線"
        day_chg = 0.0

    sim_price = round(raw_price * shock_factor, 2)
    shares = float(row["Shares"])
    avg_cost = float(row["Avg_Cost"])
    mkt_val = round(shares * sim_price, 2)
    cost_val = round(shares * avg_cost, 2)
    pnl = round(mkt_val - cost_val, 2)
    pnl_pct = round((pnl / cost_val) * 100.0, 2) if cost_val > 0 else 0.0

    live_rows.append({
        "Ticker": tkr,
        "Name": row.get("Name", tkr),
        "Shares": int(shares),
        "Avg_Cost": round(avg_cost, 3),
        "Price": sim_price,
        "Session": session_label,
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
        "Key_Fib_Target": float(row.get("Key_Fib_Target", fib382)),
        "Hard_Stop": float(row.get("Hard_Stop", round(sim_price - 2 * atr_val, 2))),
        "Target_Kelly_Pct": float(row.get("Target_Kelly_Pct", default_kelly_cap)),
    })

df_calc = pd.DataFrame(live_rows)
total_stock_val = float(df_calc["Market_Value"].sum()) if not df_calc.empty else 0.0
total_portfolio_equity = total_stock_val + cash_pool
total_cost_val = float(df_calc["Total_Cost"].sum()) if not df_calc.empty else 0.0
total_pnl = total_stock_val - total_cost_val
total_pnl_pct = (total_pnl / total_cost_val * 100.0) if total_cost_val > 0 else 0.0

if not df_calc.empty and total_portfolio_equity > 0:
    df_calc["Weight_Pct"] = round((df_calc["Market_Value"] / total_portfolio_equity) * 100.0, 2)
    df_calc["Optimal_Shares"] = np.floor((total_portfolio_equity * (df_calc["Target_Kelly_Pct"] / 100.0)) / df_calc["Price"]).astype(int)
    df_calc["Share_Diff"] = df_calc["Optimal_Shares"] - df_calc["Shares"]
else:
    df_calc["Weight_Pct"] = 0.0
    df_calc["Optimal_Shares"] = 0
    df_calc["Share_Diff"] = 0

# 計算前兩大持股集中度與 VaR
sorted_weights = df_calc["Weight_Pct"].sort_values(ascending=False) if not df_calc.empty else pd.Series([0.0])
top2_conc = float(sorted_weights.iloc[:2].sum()) if len(sorted_weights) >= 2 else float(sorted_weights.sum())
daily_var_95 = float((df_calc["Shares"] * df_calc["ATR"] * 1.645).sum() * 0.65) if not df_calc.empty else 0.0
weekly_var_95 = daily_var_95 * np.sqrt(5)

# 超配部位減碼可釋出資金 + 現金池
excess_shares = np.maximum(df_calc["Shares"] - df_calc["Optimal_Shares"], 0)
releasable_cash = float((excess_shares * df_calc["Price"]).sum()) + cash_pool

# ==========================================
# 5. 頂部標題與 5 大核心 KPI 儀表板
# ==========================================
st.markdown("## 📊 美股量化風控 × 費波納契 × 半凱利操盤系統")
status_feed_txt = "🟢 yfinance 即時/盤前連線中" if enable_live_feed else "🟡 手動改價模式"
st.caption(f"連線狀態：{status_feed_txt} | 結合費波納契時空共振 (0.382 / 0.618 / 1.272)、ATR 動態停損與萬用加減碼建倉模型")

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    sub_k1 = f"股票: ${total_stock_val:,.0f} / 現金池: ${cash_pool:,.0f}"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">股票總市值 + 現金總淨值 (USD)</div>
        <div class="kpi-val" style="color:#f7fafc;">${total_portfolio_equity:,.2f}</div>
        <div class="kpi-sub">{sub_k1}</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    pnl_color = "#48bb78" if total_pnl >= 0 else "#f56565"
    sub_k2 = f"總報酬率: {total_pnl_pct:+.2f}% (壓測: {market_shock*beta_mult:+.1f}%)"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">未實現總損益 (USD / %)</div>
        <div class="kpi-val" style="color:{pnl_color};">${total_pnl:,.2f}</div>
        <div class="kpi-sub" style="color:{pnl_color};">{sub_k2}</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    conc_color = "#ecc94b" if top2_conc > 35 else "#48bb78"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">前兩大持股集中度 (NBIS+MRVL)</div>
        <div class="kpi-val" style="color:{conc_color};">{top2_conc:.2f}%</div>
        <div class="kpi-sub">半凱利建議安全上限: ≤ 35.0%</div>
    </div>
    """, unsafe_allow_html=True)

with k4:
    sub_k4 = f"單日 95% VaR: -${daily_var_95:,.0f} (基於 ATR)"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">單週 95% 風險價值 (5-Day VaR)</div>
        <div class="kpi-val" style="color:#f56565;">-${weekly_var_95:,.0f}</div>
        <div class="kpi-sub">{sub_k4}</div>
    </div>
    """, unsafe_allow_html=True)

with k5:
    sub_k5 = f"現有美金: ${cash_pool:,.0f} / 可抵稅額: ${realized_loss_tax:,.0f}"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">可動用現金 + 減碼釋出資金池</div>
        <div class="kpi-val" style="color:#48bb78;">${releasable_cash:,.0f}</div>
        <div class="kpi-sub">{sub_k5}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ==========================================
# 6. 費波納契時間週期變盤視窗 (無重複版本)
# ==========================================
st.markdown("#### ⏱️ 費波納契時間週期變盤視窗 (Fibonacci Time Zones)")
tz_cols = st.columns(5)
tz_events = [
    ("T+5 短線確認窗", "2026/10/23", "檢視 NBIS $175 / MRVL $247.77 壓力與 5MA 翻揚", "#ed8936", True),
    ("T+8 第一減碼窗", "2026/10/28", "觀察反彈測試 0.236~0.382 壓力區動能", "#ecc94b", False),
    ("T+13 波段分水嶺", "2026/11/04", "日線月線 (20MA) 扣抵，執行第一階段減碼", "#4299e1", False),
    ("T+21 中期轉折窗", "2026/11/16", "挑戰 0.618 黃金分割強壓區與財報指引兌現", "#48bb78", False),
    ("T+34 季線大變盤窗", "2026/12/04", "60MA 季線方向定調與完成組合再平衡", "#9f7aea", False),
]
today_dt = datetime.date.today()
for col, (title, dt_str, desc, color, is_hl) in zip(tz_cols, tz_events):
    target_dt = datetime.datetime.strptime(dt_str, "%Y/%m/%d").date()
    days_left = (target_dt - today_dt).days
    day_badge = f"還有 {days_left} 天" if days_left >= 0 else f"已過 {abs(days_left)} 天"
    card_cls = "tz-card tz-highlight" if is_hl else "tz-card"
    with col:
        st.markdown(f"""
        <div class="{card_cls}">
            <div style="color:{color}; font-weight:700; font-size:0.85rem;">{title} ({day_badge})</div>
            <div style="color:#ffffff; font-size:1.2rem; font-weight:800; margin:6px 0;">{dt_str}</div>
            <div style="color:#a0aec0; font-size:0.78rem;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")

# ==========================================
# 7. 四大核心操作分頁
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 互動式風控追蹤主表 (可改價/增刪股票)",
    "📈 視覺化權重與費氏價位階梯圖",
    "🧮 NBIS & MRVL 三階梯減碼模擬器",
    "🚀 萬用個股加減碼與新股建倉引擎 (既有持股 & 任意新股)"
])

# ------------------------------------------
# Tab 1: 互動式風控追蹤主表
# ------------------------------------------
with tab1:
    st.markdown("##### 💡 可直接點擊表格修改「股數」、「均價」，或滑到表格最下方點擊 `+` 直接新增任何美股代號")
    edited_df = st.data_editor(
        df_calc,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Ticker": st.column_config.TextColumn("代號", required=True),
            "Name": st.column_config.TextColumn("名稱"),
            "Shares": st.column_config.NumberColumn("持有股數", min_value=0, step=1),
            "Avg_Cost": st.column_config.NumberColumn("持有均價 ($)", format="$%.3f"),
            "Price": st.column_config.NumberColumn("即時/盤前價 ($)", format="$%.2f"),
            "Session": st.column_config.TextColumn("時段狀態", disabled=True),
            "Day_Chg_Pct": st.column_config.NumberColumn("當日漲跌 (%)", format="%.2f%%", disabled=True),
            "Market_Value": st.column_config.NumberColumn("總市值 ($)", format="$%.2f", disabled=True),
            "PnL": st.column_config.NumberColumn("未實現損益 ($)", format="$%.2f", disabled=True),
            "PnL_Pct": st.column_config.NumberColumn("報酬率 (%)", format="%.2f%%", disabled=True),
            "Weight_Pct": st.column_config.NumberColumn("目前權重 (%)", format="%.2f%%", disabled=True),
            "Target_Kelly_Pct": st.column_config.NumberColumn("半凱利上限 (%)", format="%.1f%%"),
            "Optimal_Shares": st.column_config.NumberColumn("半凱利建議股數", disabled=True),
            "Share_Diff": st.column_config.NumberColumn("建議加減碼股數 (+加/-減)", disabled=True),
            "Key_Fib_Target": st.column_config.NumberColumn("關鍵費氏目標 ($)", format="$%.2f"),
            "Hard_Stop": st.column_config.NumberColumn("硬性防守底線 ($)", format="$%.2f"),
            "ATR": st.column_config.NumberColumn("14D ATR ($)", format="$%.2f", disabled=True),
        },
        hide_index=True
    )
    if st.button("💾 將表格變更儲存為系統基準"):
        save_cols = ["Ticker", "Name", "Shares", "Avg_Cost", "Target_Kelly_Pct", "Hard_Stop", "Key_Fib_Target"]
        st.session_state.portfolio_df = edited_df[save_cols].copy()
        st.success("✅ 持股清單與參數已更新！")
        st.rerun()

# ------------------------------------------
# Tab 2: 視覺化權重與費氏價位階梯圖
# ------------------------------------------
with tab2:
    c_left, c_right = st.columns(2)
    with c_left:
        fig_w = go.Figure()
        fig_w.add_trace(go.Bar(name="目前實際權重 (%)", x=df_calc["Ticker"], y=df_calc["Weight_Pct"], marker_color="#f56565"))
        fig_w.add_trace(go.Bar(name="半凱利安全上限 (%)", x=df_calc["Ticker"], y=df_calc["Target_Kelly_Pct"], marker_color="#48bb78"))
        fig_w.update_layout(title="目前持股權重 vs. 半凱利安全上限 (%)", barmode="group", template="plotly_dark", height=400)
        st.plotly_chart(fig_w, use_container_width=True)

    with c_right:
        fig_p = go.Figure()
        fig_p.add_trace(go.Bar(name="硬性防守底線 ($)", x=df_calc["Ticker"], y=df_calc["Hard_Stop"], marker_color="#fc8181"))
        fig_p.add_trace(go.Bar(name="目前現價 ($)", x=df_calc["Ticker"], y=df_calc["Price"], marker_color="#63b3ed"))
        fig_p.add_trace(go.Bar(name="費氏減碼/停利目標 ($)", x=df_calc["Ticker"], y=df_calc["Key_Fib_Target"], marker_color="#68d391"))
        fig_p.update_layout(title="各股現價與關鍵防守/費氏目標位階對照", barmode="group", template="plotly_dark", height=400)
        st.plotly_chart(fig_p, use_container_width=True)

# ------------------------------------------
# Tab 3: NBIS & MRVL 三階梯減碼模擬器
# ------------------------------------------
with tab3:
    st.markdown("#### 🧮 核心超配雙雄 (NBIS & MRVL) 專屬減碼回收現金試算")
    col_nbis, col_mrvl = st.columns(2)

    if "NBIS" in df_calc["Ticker"].values:
        nbis_row = df_calc[df_calc["Ticker"] == "NBIS"].iloc[0]
        with col_nbis:
            st.markdown(f"**🔹 NBIS (現有 {int(nbis_row['Shares'])} 股 | 即時/盤前價 ${nbis_row['Price']:.2f} | 目標降至 333 股)**")
            nbis_plan = pd.DataFrame([
                {"階段": "第一階 (0.382 反彈位)", "掛單價 ($)": 195.80, "減碼股數": 87, "預計收回現金 ($)": round(87 * 195.80, 2)},
                {"階段": "第二階 (前波密集壓力)", "掛單價 ($)": 200.00, "減碼股數": 80, "預計收回現金 ($)": round(80 * 200.00, 2)},
                {"階段": "第三階 (0.618 黃金位)", "掛單價 ($)": 215.50, "減碼股數": 50, "預計收回現金 ($)": round(50 * 215.50, 2)},
                {"階段": "⚠️ 破位硬性防禦線", "掛單價 ($)": 159.00, "減碼股數": 100, "預計收回現金 ($)": round(100 * 159.00, 2)},
            ])
            st.dataframe(nbis_plan, use_container_width=True, hide_index=True)

    if "MRVL" in df_calc["Ticker"].values:
        mrvl_row = df_calc[df_calc["Ticker"] == "MRVL"].iloc[0]
        with col_mrvl:
            st.markdown(f"**🔸 MRVL (現有 {int(mrvl_row['Shares'])} 股 | 即時/盤前價 ${mrvl_row['Price']:.2f} | 目標降至 180 股)**")
            mrvl_plan = pd.DataFrame([
                {"階段": "第一階 (0.618 關鍵位 GTC)", "掛單價 ($)": 247.77, "減碼股數": 57, "預計收回現金 ($)": round(57 * 247.77, 2)},
                {"階段": "第二階 (前高成本區)", "掛單價 ($)": 256.00, "減碼股數": 60, "預計收回現金 ($)": round(60 * 256.00, 2)},
                {"階段": "第三階 (1.272 擴展位)", "掛單價 ($)": 272.50, "減碼股數": 53, "預計收回現金 ($)": round(53 * 272.50, 2)},
                {"階段": "⚠️ 破位硬性防禦線", "掛單價 ($)": 218.00, "減碼股數": 60, "預計收回現金 ($)": round(60 * 218.00, 2)},
            ])
            st.dataframe(mrvl_plan, use_container_width=True, hide_index=True)

# ------------------------------------------
# Tab 4: 萬用個股加減碼與新股建倉引擎
# ------------------------------------------
with tab4:
    st.markdown("#### 🚀 萬用個股動態加減碼與新股建倉引擎 (支援現有持股 & 任意新購美股)")
    st.caption("結合「半凱利權重上限」、「20MA/200MA 右側趨勢過濾」與「ATR 金字塔三階梯加減碼模型」，自動計算任何股票的最佳買賣點與股數。")

    sel_col1, sel_col2, sel_col3, sel_col4 = st.columns([1.3, 1.2, 1.2, 1.3])
    existing_tickers = list(df_calc["Ticker"].values)

    with sel_col1:
        mode_choice = st.selectbox(
            "1️⃣ 選擇分析對象",
            options=["既有持股加減碼", "➕ 輸入任意新美股代號 (預備購入)"]
        )

    with sel_col2:
        if mode_choice == "既有持股加減碼" and existing_tickers:
            target_ticker = st.selectbox("2️⃣ 選擇既有持股代號", options=existing_tickers, index=0)
            row_match = df_calc[df_calc["Ticker"] == target_ticker].iloc[0]
            default_cur_shares = int(row_match["Shares"])
            default_cur_cost = float(row_match["Avg_Cost"])
            default_kelly_target = float(row_match["Target_Kelly_Pct"])
        else:
            target_ticker = st.text_input("2️⃣ 輸入美股代號 (如 PLD, COHR, RMBS, NVDA)", value="PLD").strip().upper()
            if target_ticker in existing_tickers:
                row_match = df_calc[df_calc["Ticker"] == target_ticker].iloc[0]
                default_cur_shares = int(row_match["Shares"])
                default_cur_cost = float(row_match["Avg_Cost"])
                default_kelly_target = float(row_match["Target_Kelly_Pct"])
            else:
                default_cur_shares = 0
                default_cur_cost = 0.0
                default_kelly_target = default_kelly_cap

    # 抓取該標的量化指標
    q_data = fetch_ticker_quant_metrics(target_ticker, get_extended=include_extended)
    live_p = q_data["Price"] if q_data else (default_cur_cost if default_cur_cost > 0 else 100.0)
    live_atr = q_data["ATR"] if q_data else round(live_p * 0.04, 2)
    live_ma20 = q_data["MA20"] if q_data else live_p
    live_ma200 = q_data["MA200"] if q_data else live_p
    live_rsi = q_data["RSI"] if q_data else 50.0
    fib_382_lvl = q_data["Fib_0382"] if q_data else round(live_p * 0.96, 2)
    fib_618_lvl = q_data["Fib_0618"] if q_data else round(live_p * 1.08, 2)
    fib_1272_lvl = q_data["Fib_1272"] if q_data else round(live_p * 1.20, 2)
    swing_low_lvl = q_data["Swing_Low"] if q_data else round(live_p * 0.88, 2)

    with sel_col3:
        sim_cur_shares = st.number_input("3️⃣ 目前持有股數 (新股為 0)", min_value=0, value=default_cur_shares, step=10)
        sim_cur_cost = st.number_input("目前持有均價 ($)", min_value=0.0, value=float(default_cur_cost if default_cur_cost > 0 else live_p), step=1.0)

    with sel_col4:
        sim_kelly_pct = st.slider("4️⃣ 該股半凱利目標權重上限 (%)", min_value=2.0, max_value=25.0, value=float(default_kelly_target), step=0.5)
        budget_limit = st.number_input("本次預計最大動用加碼資金 ($)", min_value=500.0, value=float(min(max(cash_pool, 1000.0), 30000.0)), step=500.0)

    # 計算權重空間與守門員檢核
    cur_stock_val = sim_cur_shares * live_p
    cur_weight_pct = (cur_stock_val / total_portfolio_equity * 100.0) if total_portfolio_equity > 0 else 0.0
    max_kelly_val = total_portfolio_equity * (sim_kelly_pct / 100.0)
    max_kelly_shares = int(np.floor(max_kelly_val / live_p)) if live_p > 0 else 0
    remaining_kelly_val = max(0.0, max_kelly_val - cur_stock_val)
    remaining_kelly_shares = max(0, max_kelly_shares - sim_cur_shares)
    excess_trim_shares = max(0, sim_cur_shares - max_kelly_shares)

    effective_add_budget = min(remaining_kelly_val, budget_limit) if remaining_kelly_val > 0 else budget_limit

    st.markdown("---")
    st.markdown(f"##### 🛡️ `{target_ticker}` 即時行情與三道量化風控守門員檢核")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    session_note = f" ({q_data['Session']})" if q_data else ""
    m1.metric("即時報價", f"${live_p:.2f}", f"{q_data['Day_Chg_Pct']:+.2f}%{session_note}" if q_data else "模擬")
    m2.metric("目前權重 / 凱利上限", f"{cur_weight_pct:.1f}% / {sim_kelly_pct:.1f}%", f"{cur_weight_pct - sim_kelly_pct:+.1f}%", delta_color="inverse")
    m3.metric("凱利建議上限股數", f"{max_kelly_shares} 股", f"現有 {sim_cur_shares} 股")
    m4.metric("20MA / 200MA 均線", f"${live_ma20:.2f}", f"年線 ${live_ma200:.2f}")
    m5.metric("14日 ATR 波動值", f"${live_atr:.2f}", f"停損寬度 ${live_atr*2:.2f}")
    m6.metric("14日 RSI 強弱指標", f"{live_rsi:.1f}", "超買 >70 / 超賣 <30")

    is_weight_ok = cur_weight_pct < sim_kelly_pct
    is_trend_ok = live_p >= live_ma20 or live_p >= live_ma200

    if not is_weight_ok:
        st.markdown(f"""
        <div class="gate-block">
            <b>🚫 【風控守門員攔截：權重超標，禁止向下攤平加碼】</b><br>
            • <b>原因</b>：<code>{target_ticker}</code> 目前佔總資產 <b>{cur_weight_pct:.2f}%</b>（持有 {sim_cur_shares} 股），已超過半凱利安全上限 <b>{sim_kelly_pct:.1f}%</b>（上限 {max_kelly_shares} 股）。<br>
            • <b>機械化指令</b>：在股數透過右側反彈減碼降至 <b>{max_kelly_shares} 股</b> 以下之前，嚴格凍結加碼！請直接執行下方右側的<b>「📉 三階梯分批減碼方案」</b>（需減碼 <b>{excess_trim_shares} 股</b>）。
        </div>
        """, unsafe_allow_html=True)
    else:
        trend_status = "✅ 股價站上均線（符合右側順勢加碼條件）" if is_trend_ok else "⚠️ 股價仍處均線下方（建議等待突破 20MA 或於費氏支撐掛單試單，勿重倉接刀）"
        st.markdown(f"""
        <div class="gate-pass">
            <b>✅ 【風控守門員放行：具備加碼 / 新股建倉空間】</b><br>
            • <b>可用額度</b>：距離半凱利 {sim_kelly_pct:.1f}% 上限尚可買入 <b>{remaining_kelly_shares} 股（約 ${remaining_kelly_val:,.2f} 美元）</b>；本次規劃動用預算 <b>${effective_add_budget:,.2f} 美元</b>（目前現金池：${cash_pool:,.2f}）。<br>
            • <b>趨勢位階</b>：{trend_status}
        </div>
        """, unsafe_allow_html=True)

    plan_left, plan_right = st.columns(2)

    with plan_left:
        st.markdown(f"##### 📈 【方案 A】`{target_ticker}` 金字塔三階梯加碼 / 建倉試算表 (40% / 35% / 25%)")
        st.caption("鐵律：第一批建立底倉後，唯有股價順勢上漲脫離成本區，才執行第二、三批右側加碼，絕不向下越跌越買！")

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

        df_pyramid_buy = pd.DataFrame([
            {
                "加碼批次": "第 1 批 (底倉試單 40%)",
                "觸發條件": "現價 / 突破短線轉折",
                "建議買價 ($)": buy_p1,
                "買入股數": b1_shares,
                "動用資金 ($)": round(b1_shares * buy_p1, 2),
                "買後總股數": cum_s1,
                "買後新均價 ($)": round(cum_c1, 2),
                "硬性停損價 (-2 ATR)": round(buy_p1 - 2.0 * live_atr, 2)
            },
            {
                "加碼批次": "第 2 批 (右側確認 35%)",
                "觸發條件": f"站穩 20MA 或漲破 ${buy_p2:.2f}",
                "建議買價 ($)": buy_p2,
                "買入股數": b2_shares,
                "動用資金 ($)": round(b2_shares * buy_p2, 2),
                "買後總股數": cum_s2,
                "買後新均價 ($)": round(cum_c2, 2),
                "硬性停損價 (上移保本)": round(max(cum_c1, buy_p2 - 1.8 * live_atr), 2)
            },
            {
                "加碼批次": "第 3 批 (趨勢滿倉 25%)",
                "觸發條件": f"帶量突破 ${buy_p3:.2f} 順勢加碼",
                "建議買價 ($)": buy_p3,
                "買入股數": b3_shares,
                "動用資金 ($)": round(b3_shares * buy_p3, 2),
                "買後總股數": cum_s3,
                "買後新均價 ($)": round(cum_c3, 2),
                "硬性停損價 (鎖利防守)": round(max(cum_c2, buy_p3 - 1.5 * live_atr), 2)
            }
        ])
        st.dataframe(df_pyramid_buy, use_container_width=True, hide_index=True)

        if target_ticker not in existing_tickers and b1_shares > 0:
            if st.button(f"➕ 將新標的 {target_ticker} (第 1 批 {b1_shares} 股) 加入主表模擬"):
                new_entry = pd.DataFrame([{
                    "Ticker": target_ticker,
                    "Name": target_ticker,
                    "Shares": b1_shares,
                    "Avg_Cost": buy_p1,
                    "Target_Kelly_Pct": sim_kelly_pct,
                    "Hard_Stop": round(buy_p1 - 2.0 * live_atr, 2),
                    "Key_Fib_Target": fib_618_lvl
                }])
                st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new_entry], ignore_index=True)
                st.success(f"已將 {target_ticker} ({b1_shares} 股 @ ${buy_p1}) 加入追蹤主表！")
                st.rerun()

    with plan_right:
        st.markdown(f"##### 📉 【方案 B】`{target_ticker}` 費波納契三階梯減碼 / 停利試算表 (30% / 40% / 30%)")
        st.caption("自動抓取該股費波納契 0.382、0.618 與 1.272 擴展目標位，計算分批減碼或停利回收之現金。")

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

        df_fib_sell = pd.DataFrame([
            {
                "減碼/停利階段": "第一階 (0.382 壓力 / 短線調節 30%)",
                "目標掛單價 ($)": p_t1,
                "賣出股數": s_t1,
                "收回現金 ($)": round(s_t1 * p_t1, 2),
                "單筆實現損益 ($)": round(s_t1 * (p_t1 - ref_cost), 2),
                "距現價漲幅 (%)": f"{((p_t1 - live_p)/live_p)*100:+.2f}%"
            },
            {
                "減碼/停利階段": "第二階 (0.618 黃金分割強壓 40%)",
                "目標掛單價 ($)": p_t2,
                "賣出股數": s_t2,
                "收回現金 ($)": round(s_t2 * p_t2, 2),
                "單筆實現損益 ($)": round(s_t2 * (p_t2 - ref_cost), 2),
                "距現價漲幅 (%)": f"{((p_t2 - live_p)/live_p)*100:+.2f}%"
            },
            {
                "減碼/停利階段": "第三階 (1.272 波段延伸停利 30%)",
                "目標掛單價 ($)": p_t3,
                "賣出股數": s_t3,
                "收回現金 ($)": round(s_t3 * p_t3, 2),
                "單筆實現損益 ($)": round(s_t3 * (p_t3 - ref_cost), 2),
                "距現價漲幅 (%)": f"{((p_t3 - live_p)/live_p)*100:+.2f}%"
            },
            {
                "減碼/停利階段": "⚠️ 左側破位防禦 (跌破 -2 ATR / 波段底)",
                "目標掛單價 ($)": p_stop,
                "賣出股數": s_stop,
                "收回現金 ($)": round(s_stop * p_stop, 2),
                "單筆實現損益 ($)": round(s_stop * (p_stop - ref_cost), 2),
                "距現價漲幅 (%)": f"{((p_stop - live_p)/live_p)*100:+.2f}%"
            }
        ])
        st.dataframe(df_fib_sell, use_container_width=True, hide_index=True)