"""
app.py — TradeSim v2  (candle-by-candle trading simulator)
Design: Dark Blue Analytics | #0F172A bg | #3B82F6 primary | #F59E0B accent
Stack:  Streamlit 1.54 + streamlit-lightweight-charts 0.7 + yfinance + SQLite
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as _st_comp
from streamlit_lightweight_charts import renderLightweightCharts

import data as dt
import db
import engine as eng

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="TradeSim",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ─────────────────────────────────────────────────────────── #
C_BG      = "#0F172A"
C_SURF    = "#1E293B"
C_SURF2   = "#273549"
C_BORDER  = "#334155"
C_PRIMARY = "#3B82F6"
C_ACCENT  = "#F59E0B"
C_GREEN   = "#22C55E"
C_RED     = "#EF4444"
C_TEXT    = "#F1F5F9"
C_MUTED   = "#94A3B8"
C_DIM     = "#475569"

_SESSION_FILE = Path(__file__).parent / ".tradesim_session.json"


def _pos_to_dict(p) -> Optional[dict]:
    if p is None:
        return None
    return {"side": p.side, "entry_time": p.entry_time, "entry": p.entry,
            "stop": p.stop, "target": p.target, "setup": p.setup,
            "trigger": p.trigger, "emotag": p.emotag,
            "emo_intensity": p.emo_intensity,
            "rule_adherence": p.rule_adherence, "notes": p.notes}


def _pending_to_dict(p) -> Optional[dict]:
    if p is None:
        return None
    return {"side": p.side, "stop": p.stop, "target": p.target,
            "setup": p.setup, "trigger": p.trigger, "emotag": p.emotag,
            "emo_intensity": p.emo_intensity,
            "rule_adherence": p.rule_adherence, "notes": p.notes}


def _save_session(sym: str, ivl: str) -> None:
    """Persist cursor + open position/pending so the user can fully resume."""
    try:
        _SESSION_FILE.write_text(json.dumps({
            "symbol": sym, "interval": ivl,
            "cursor": st.session_state.cursor,
            "pos":     _pos_to_dict(st.session_state.pos),
            "pending": _pending_to_dict(st.session_state.pending),
        }))
    except Exception:
        pass


st.markdown(f"""<style>
/* ── Base ── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="block-container"] {{
    background: {C_BG};
    color: {C_TEXT};
    font-family: Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;
}}
/* ── Sidebar ── */
[data-testid="stSidebar"] {{ background: {C_SURF}; border-right: 1px solid {C_BORDER}; }}
[data-testid="stSidebar"] * {{ color: {C_TEXT}; }}
/* ── Labels ── */
label, .stTextInput label, .stNumberInput label, .stTextArea label,
.stSelectbox label, .stSlider label, .stRadio label {{
    color: {C_MUTED} !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: .05em;
}}
/* ── Inputs – explicit dark background so they're always readable ── */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {{
    background: {C_SURF2} !important;
    border: 1px solid {C_BORDER} !important;
    color: {C_TEXT} !important;
    border-radius: 6px !important;
    font-size: 14px !important;
}}
.stSelectbox > div > div,
.stSelectbox > div > div > div {{
    background: {C_SURF2} !important;
    border: 1px solid {C_BORDER} !important;
    color: {C_TEXT} !important;
    border-radius: 6px !important;
}}
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
    border-color: {C_PRIMARY} !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,.25) !important;
    outline: none !important;
}}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {{ color: {C_DIM}; opacity: 1; }}
/* ── Default button ── */
.stButton > button {{
    background: {C_SURF2};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 700;
    transition: filter .15s;
}}
.stButton > button:hover {{ filter: brightness(1.15); }}
/* ── Primary button ── */
.stButton > button[kind="primary"] {{
    background: {C_PRIMARY} !important;
    border-color: {C_PRIMARY} !important;
    color: white !important;
}}
/* ── Buy / Sell button classes ── */
button.ts-buy  {{ background: {C_GREEN} !important; border-color: {C_GREEN} !important; color: #000 !important; font-size:17px !important; font-weight:800 !important; letter-spacing:.02em; padding:10px !important; border-radius:10px !important; }}
button.ts-sell {{ background: {C_RED}   !important; border-color: {C_RED}   !important; color: #fff !important; font-size:17px !important; font-weight:800 !important; letter-spacing:.02em; padding:10px !important; border-radius:10px !important; }}
button.ts-dir-active-long  {{ background: {C_GREEN} !important; border: 2px solid {C_GREEN} !important; color: #000 !important; font-weight:900 !important; }}
button.ts-dir-active-short {{ background: {C_RED}   !important; border: 2px solid {C_RED}   !important; color: #fff !important; font-weight:900 !important; }}
/* ── Metric ── */
[data-testid="stMetricLabel"] {{ color: {C_MUTED}; font-size:11px; font-weight:600; text-transform:uppercase; }}
[data-testid="stMetricValue"] {{ color: {C_TEXT}; font-size:20px; font-weight:700; }}
/* ── Tabs ── */
[data-testid="stTabs"] button {{ color: {C_MUTED}; font-weight:600; }}
[data-testid="stTabs"] button[aria-selected="true"] {{ color: {C_PRIMARY}; border-bottom: 2px solid {C_PRIMARY}; background: transparent; }}
/* ── Misc ── */
[data-testid="stDataFrame"] {{ background: transparent; border-radius: 8px; color: {C_TEXT}; }}
hr {{ border-color: {C_BORDER} !important; margin: 8px 0 !important; }}
.stat-card {{ background: {C_SURF2}; border: 1px solid {C_BORDER}; border-radius: 10px; padding: 12px 16px; color: {C_TEXT}; }}
.bdg {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size:11px; font-weight:700; color: {C_TEXT}; background: rgba(255,255,255,0.06); border:1px solid {C_BORDER}; }}
.bdg-long  {{ background: rgba(34,197,94,.18); border-color: {C_GREEN}; color:{C_GREEN}; }}
.bdg-short {{ background: rgba(239,68,68,.18); border-color: {C_RED};   color:{C_RED};   }}
.bdg-pend  {{ background: rgba(245,158,11,.18); border-color: {C_ACCENT}; color:{C_ACCENT}; }}
.bdg-none  {{ opacity:.6; }}
.ohlc-row {{ font-family: 'JetBrains Mono', monospace; font-size:13px; letter-spacing:.01em; color: {C_TEXT}; }}
/* number input spinner buttons */
.stNumberInput button {{ background: {C_SURF2} !important; border-color: {C_BORDER} !important; color: {C_TEXT} !important; }}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DB INIT + SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
db.init()

_DEFAULTS = {
    "cursor": 0,
    "pending": None,
    "pos": None,
    "lookback": 150,
    "show_ema20": True,
    "show_ema50": True,
    "show_sma200": False,
    "session_goal": "",
    "autoplay": False,
    "autoplay_speed": 1.0,
    "autoplay_stop_on_trade": False,
    "last_sym": "SPY",
    "last_interval": "1d",
    "trade_side": "LONG",
    "q_risk_pct": 1.0,
    "q_acct": 10000,
    "q_setup": "",
    "q_trigger": "",
    "q_emotag": "",
    "q_emo_int": 0,
    "q_rule_ad": 1,
    "q_notes": "",
    "q_stop_ovr": None,
    "q_target_ovr": None,
    "_ap_skip": False,
    "_ap_last_render": 0.0,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📈 TradeSim")
    st.caption("Candle-by-candle practice")

    # ── Session restore banner ─────────────────────────────────────── #
    _sess_data: dict = {}
    if _SESSION_FILE.exists():
        try:
            _sess_data = json.loads(_SESSION_FILE.read_text())
        except Exception:
            pass
    if _sess_data.get("cursor", 0) > 0:
        _rs_sym = _sess_data.get("symbol", "")
        _rs_ivl = _sess_data.get("interval", "")
        _rs_cur = _sess_data.get("cursor", 0)
        st.markdown(
            f'<div style="background:{C_SURF2};border:1px solid {C_BORDER};border-radius:8px;'
            f'padding:8px 10px;font-size:12px;color:{C_MUTED}">Last session:<br>'
            f'<b style="color:{C_TEXT}">{_rs_sym} {_rs_ivl}</b> @ bar {_rs_cur + 1}</div>',
            unsafe_allow_html=True,
        )
        if st.button("↩ Resume last session", use_container_width=True, key="resume_btn"):
            st.session_state.last_sym      = _rs_sym
            st.session_state.last_interval = _rs_ivl
            st.session_state.cursor        = _rs_cur
            st.rerun()

    st.divider()

    # ── Quick-symbol presets ───────────────────────────────────────── #
    _qs_list = ["SPY", "QQQ", "AAPL", "TSLA", "GLD", "BTC-USD"]
    _qs_cols = st.columns(len(_qs_list))
    for _qi, (_qsc, _qss) in enumerate(zip(_qs_cols, _qs_list)):
        with _qsc:
            if st.button(_qss, key=f"qs_{_qi}", use_container_width=True, help=f"Load {_qss}"):
                st.session_state.last_sym = _qss
                st.rerun()

    symbol = st.text_input("Symbol", value=st.session_state.last_sym,
                            help="e.g. SPY AAPL BTC-USD").strip().upper()
    st.session_state.last_sym = symbol

    _interval_opts = ["1m", "5m", "15m", "1h", "1d", "1wk"]
    _int_default   = (_interval_opts.index(st.session_state.last_interval)
                      if st.session_state.last_interval in _interval_opts else 4)
    interval = st.selectbox("Interval", _interval_opts, index=_int_default)
    st.session_state.last_interval = interval

    today = date.today()
    if interval in dt.INTRADAY_INTERVALS:
        _default_start = today - timedelta(days=55)
    else:
        _default_start = today - timedelta(days=365 * 2)

    col_s, col_e = st.columns(2)
    with col_s: start_d = st.date_input("Start", value=_default_start)
    with col_e: end_d   = st.date_input("End",   value=today)

    if st.button("🔄 Reload data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**Chart overlays**")
    col_i1, col_i2, col_i3 = st.columns(3)
    with col_i1: st.session_state.show_ema20  = st.checkbox("EMA 20",  value=st.session_state.show_ema20)
    with col_i2: st.session_state.show_ema50  = st.checkbox("EMA 50",  value=st.session_state.show_ema50)
    with col_i3: st.session_state.show_sma200 = st.checkbox("SMA 200", value=st.session_state.show_sma200)

    lookback = st.slider("Visible bars", 50, 500, st.session_state.lookback, 25)
    st.session_state.lookback = lookback

    st.divider()
    st.markdown("**Auto-play**")
    st.caption("Space/\u2192 = +1 \u00b7 Shift+\u2192 = +5 \u00b7 Ctrl+\u2192 = +10 \u00b7 R = Reset \u00b7 P = Play/Pause")
    _ap_c1, _ap_c2 = st.columns([1.6, 1])
    with _ap_c1:
        _ap_lbl = "\u23f8 Running\u2026" if st.session_state.autoplay else "\u25b6 Auto-play"
        if st.button(_ap_lbl, key="ap_toggle_btn", use_container_width=True,
                     type="primary" if st.session_state.autoplay else "secondary"):
            st.session_state.autoplay = not st.session_state.autoplay
            st.session_state._ap_last_render = 0.0   # reset timer on toggle
            st.rerun()
    with _ap_c2:
        st.session_state.autoplay_speed = st.number_input(
            "s/bar", min_value=0.1, max_value=10.0,
            value=float(st.session_state.autoplay_speed), step=0.1, format="%.1f",
            key="ap_speed_in", help="Seconds per bar",
        )
    # Speed presets
    _sp_cols = st.columns(5)
    for _spc, _spv, _spl in zip(_sp_cols, [0.1, 0.25, 0.5, 1.0, 2.0], ["0.1", "0.25", "0.5", "1s", "2s"]):
        with _spc:
            _sp_active = abs(st.session_state.autoplay_speed - _spv) < 0.01
            if st.button(_spl, key=f"spd_{_spl}",
                         type="primary" if _sp_active else "secondary",
                         use_container_width=True):
                st.session_state.autoplay_speed  = _spv
                st.session_state._ap_last_render = 0.0
                st.rerun()
    st.session_state.autoplay_stop_on_trade = st.checkbox(
        "⏸ עצור כשיש עסקה פתוחה / Pause on open trade",
        value=st.session_state.autoplay_stop_on_trade,
        help="אם מסומן — האוטופליי יפסיק כשיש פוזיציה פתוחה או פקודה ממתינה.",
    )

    st.divider()
    st.markdown("**Session goal**")
    st.session_state.session_goal = st.text_area(
        "Goal", value=st.session_state.session_goal,
        placeholder="e.g. Practice ORB setups only.",
        height=70, label_visibility="collapsed",
    )

    if interval in dt.INTRADAY_INTERVALS:
        st.caption("⚠️ Intraday: max 60 days")


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOAD
# ══════════════════════════════════════════════════════════════════════════════
err = dt.validate_date_range(interval, start_d, end_d)
if err:
    st.error(err)
    st.stop()

df = dt.load(symbol, interval, start_d, end_d + timedelta(days=1))

if df.empty:
    st.error(f"No data for `{symbol}` `{interval}`. Check symbol / date range.")
    st.stop()

N = len(df)

# Guard cursor
if st.session_state.cursor >= N:
    st.session_state.cursor = min(N - 1, lookback)
if st.session_state.cursor < 1:
    st.session_state.cursor = min(1, N - 1)

# Pre-compute indicators on full df (correct EMA history)
if st.session_state.show_ema20:
    df["_ema20"]  = dt.ema(df, 20)
if st.session_state.show_ema50:
    df["_ema50"]  = dt.ema(df, 50)
if st.session_state.show_sma200:
    df["_sma200"] = dt.sma(df, 200)

# ── Sidebar live summary ──────────────────────────────────────────────────── #
_trades_all = db.read_trades(symbol, interval)
if not _trades_all.empty:
    _r_all = _trades_all["r_multiple"].dropna().astype(float)
    _eq = _r_all.sum()
    _wr = (_r_all > 0).mean() * 100
    _n  = len(_r_all)
    _streak_val, _streak_dir = 0, ""
    for _rv in reversed(_r_all.tolist()):
        if _streak_val == 0:
            _streak_dir = "W" if _rv > 0 else "L"
            _streak_val = 1
        elif (_rv > 0 and _streak_dir == "W") or (_rv <= 0 and _streak_dir == "L"):
            _streak_val += 1
        else:
            break
    with st.sidebar:
        st.divider()
        st.markdown("**Session summary**")
        _sc1, _sc2 = st.columns(2)
        with _sc1:
            st.metric("Total R", f"{_eq:+.2f}R")
            st.metric("Trades",  str(_n))
        with _sc2:
            st.metric("Win %", f"{_wr:.0f}%")
            _streak_color = C_GREEN if _streak_dir == "W" else C_RED
            st.markdown(
                f'<div class="stat-card">'
                f'<div style="color:{C_MUTED};font-size:11px;font-weight:600;text-transform:uppercase">Streak</div>'
                f'<div style="color:{_streak_color};font-size:20px;font-weight:700">'
                f'{_streak_val}{_streak_dir}</div></div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_sim, tab_stats, tab_mc = st.tabs(["📈 Simulator", "📊 Stats & Log", "🎲 Monte Carlo"])


# ════════════════════════════════════════════════════════════════════════════ #
# TAB 1 — SIMULATOR
# ════════════════════════════════════════════════════════════════════════════ #
with tab_sim:
    cursor       = st.session_state.cursor
    pos_state: Optional[eng.Position]         = st.session_state.pos
    pending_state: Optional[eng.PendingOrder] = st.session_state.pending
    last         = df.iloc[cursor]

    # ── Keyboard shortcuts (Space/→/R/P) ──────────────────────────── #
    _st_comp.html("""
    <script>
    (function(){
      var pd = window.parent.document;
      if (pd._tsKbLoaded) return;
      pd._tsKbLoaded = true;
      function clk(prefix){
        var btns = Array.from(pd.querySelectorAll('button'));
        var b = btns.find(function(b){ return b.innerText.trim().replace(/\\s+/g,' ').indexOf(prefix)===0; });
        if (b) b.click();
      }
      pd.addEventListener('keydown', function(e){
        var t = e.target.tagName;
        if (t==='INPUT'||t==='TEXTAREA'||t==='SELECT') return;
        if ((e.code==='Space')||(e.code==='ArrowRight'&&!e.shiftKey&&!e.ctrlKey&&!e.metaKey&&!e.altKey)){
          e.preventDefault(); clk('\u25b6 +1');
        } else if (e.code==='ArrowRight' && e.shiftKey){
          e.preventDefault(); clk('\u25b6\u25b6 +5');
        } else if (e.code==='ArrowRight' && e.ctrlKey){
          e.preventDefault(); clk('\u25b6\u25b6\u25b6 +10');
        } else if (e.code==='ArrowRight' && e.altKey){
          e.preventDefault(); clk('\u23e9 +50');
        } else if ((e.key==='r'||e.key==='R') && !e.ctrlKey && !e.metaKey){
          e.preventDefault(); clk('\u23ee Reset');
        } else if ((e.key==='p'||e.key==='P') && !e.ctrlKey && !e.metaKey){
          e.preventDefault();
          var apb = Array.from(pd.querySelectorAll('button')).find(function(b){
            return b.innerText.includes('Auto-play') || b.innerText.includes('Running');
          });
          if (apb) apb.click();
        }
      }, false);
    })();
    </script>
    """, height=0)

    # ── Advance helper ────────────────────────────────────────────────── #
    def _advance(steps: int) -> None:
        for _ in range(steps):
            if st.session_state.cursor >= N - 1:
                break
            st.session_state.cursor += 1
            _idx = st.session_state.cursor
            _bar = df.iloc[_idx]

            if st.session_state.pending is not None and st.session_state.pos is None:
                _po = st.session_state.pending
                st.session_state.pos = eng.Position(
                    side=_po.side, entry_time=int(_bar["time"]),
                    entry=float(_bar["open"]),
                    stop=_po.stop, target=_po.target,
                    setup=_po.setup, trigger=_po.trigger,
                    emotag=_po.emotag, emo_intensity=_po.emo_intensity,
                    rule_adherence=_po.rule_adherence, notes=_po.notes,
                )
                st.session_state.pending = None

            if st.session_state.pos is not None:
                _hit = eng.check_bar(st.session_state.pos, _bar)
                if _hit is not None:
                    _p   = st.session_state.pos
                    _rmult = _p.r_multiple(_hit.exit_price)
                    db.insert_trade({
                        "symbol": symbol, "interval": interval,
                        "side": _p.side,
                        "entry_time": _p.entry_time, "exit_time": int(_bar["time"]),
                        "entry": _p.entry, "exit": _hit.exit_price,
                        "stop": _p.stop,   "target": _p.target,
                        "r_multiple": float(_rmult) if np.isfinite(_rmult) else None,
                        "exit_reason": _hit.exit_reason,
                        "setup": _p.setup, "trigger": _p.trigger,
                        "emotag": _p.emotag, "emo_intensity": int(_p.emo_intensity),
                        "rule_adherence": int(_p.rule_adherence), "notes": _p.notes,
                    })
                    st.session_state.pos = None
        # Auto-save cursor after each advance
        _save_session(symbol, interval)

    # ── Control bar ───────────────────────────────────────────────────── #
    cb1, cb2, cb3, cb4, cb5, cb6, cb7 = st.columns([1.2, 1, 1, 1, 1, 1.4, 3.4])

    with cb1:
        if st.button("⏮ Reset", use_container_width=True):
            st.session_state.cursor  = min(N - 1, lookback)
            st.session_state.pending = None
            st.session_state.pos     = None
            st.rerun()
    with cb2:
        if st.button("▶ +1",     use_container_width=True, type="primary"): st.session_state._ap_skip = True; _advance(1);  st.rerun()
    with cb3:
        if st.button("▶▶ +5",   use_container_width=True): st.session_state._ap_skip = True; _advance(5);  st.rerun()
    with cb4:
        if st.button("▶▶▶ +10", use_container_width=True): st.session_state._ap_skip = True; _advance(10); st.rerun()
    with cb5:
        if st.button("⏩ +50",   use_container_width=True): st.session_state._ap_skip = True; _advance(50); st.rerun()
    with cb6:
        _jump = st.number_input("Jump", min_value=1, max_value=N,
                                value=cursor + 1, label_visibility="collapsed", key="jump_input")
        if st.button("Go →", use_container_width=True, key="jump_btn"):
            st.session_state.cursor = max(0, int(_jump) - 1)
            st.rerun()

    with cb7:
        if pos_state:
            _live_r = pos_state.r_multiple(float(last["close"]))
            _lr_col = C_GREEN if _live_r >= 0 else C_RED
            _sbadge = "bdg-long" if pos_state.side == "LONG" else "bdg-short"
            _status_html = (
                f'<span class="bdg {_sbadge}">● {pos_state.side}</span>'
                f'&nbsp;<span style="color:{_lr_col};font-weight:700;font-size:15px">{_live_r:+.2f}R</span>'
                f'&nbsp; E <code>{pos_state.entry:.3f}</code>'
                f' S <code style="color:{C_RED}">{pos_state.stop:.3f}</code>'
                f' T <code style="color:{C_GREEN}">{pos_state.target:.3f}</code>'
            )
        elif pending_state:
            _status_html = f'<span class="bdg bdg-pend">⏳ PENDING {pending_state.side}</span>&nbsp; fills next open'
        else:
            _status_html = f'<span class="bdg bdg-none">— idle</span>'

        st.markdown(
            f'<div style="padding:6px 0;line-height:2.2">'
            f'<b style="color:{C_MUTED}">Bar {cursor+1}/{N}</b>&nbsp;'
            f'<code style="color:{C_ACCENT}">{symbol}</code>&nbsp;'
            f'<code style="color:{C_DIM}">{interval}</code>'
            f'&nbsp;&nbsp;{_status_html}</div>',
            unsafe_allow_html=True,
        )

    # ── Chart + Panel ──────────────────────────────────────────────────── #
    col_chart, col_panel = st.columns([3, 2], gap="medium")

    with col_chart:
        lb        = st.session_state.lookback
        start_idx = max(0, cursor - lb + 1)
        vis       = df.iloc[start_idx : cursor + 1].copy()

        candles = dt.to_candles(vis)
        vol     = dt.to_volume(vis)

        # Price-line overlays (proper LWC priceLine — no extra data needed)
        price_lines = []
        if pos_state:
            price_lines = [
                {"price": pos_state.entry,  "color": C_ACCENT, "lineWidth": 1, "lineStyle": 2,
                 "title": "Entry",  "axisLabelVisible": True},
                {"price": pos_state.stop,   "color": C_RED,    "lineWidth": 2, "lineStyle": 0,
                 "title": "Stop",   "axisLabelVisible": True},
                {"price": pos_state.target, "color": C_GREEN,  "lineWidth": 2, "lineStyle": 0,
                 "title": "Target", "axisLabelVisible": True},
            ]

        # MA series
        indicator_series = []
        for _col, _color, _label in [
            ("_ema20",  "#60A5FA", "EMA20"),
            ("_ema50",  "#A78BFA", "EMA50"),
            ("_sma200", "#FB923C", "SMA200"),
        ]:
            if _col in df.columns:
                _vis_ind = vis[vis[_col].notna()]
                if not _vis_ind.empty:
                    indicator_series.append({
                        "type": "Line",
                        "data": [{"time": int(t), "value": round(float(v), 6)}
                                 for t, v in zip(_vis_ind["time"], _vis_ind[_col])],
                        "options": {
                            "color": _color, "lineWidth": 1,
                            "priceLineVisible": False, "lastValueVisible": True,
                            "title": _label, "crosshairMarkerVisible": False,
                        },
                    })

        # ── Trade markers from historical trades in visible window ──────
        _all_trades = db.read_trades(symbol, interval)
        _trade_markers: list = []
        if not _all_trades.empty:
            _vis_times = set(int(t) for t in vis["time"])
            for _, _tr in _all_trades.iterrows():
                _et   = int(_tr["entry_time"])
                _xt   = int(_tr["exit_time"])
                _side = str(_tr.get("side", "LONG"))
                _rm   = _tr.get("r_multiple", None)
                _rm_s = f"{float(_rm):+.1f}R" if _rm is not None and pd.notna(_rm) else ""
                # Entry marker — find nearest candle time in visible range
                _et_snapped = min(_vis_times, key=lambda t: abs(t - _et)) if _vis_times else None
                if _et_snapped and abs(_et_snapped - _et) < 86400 * 5:
                    _trade_markers.append({
                        "time": _et_snapped,
                        "position": "belowBar" if _side == "LONG" else "aboveBar",
                        "color": C_GREEN if _side == "LONG" else C_RED,
                        "shape": "arrowUp" if _side == "LONG" else "arrowDown",
                        "text": f"{'B' if _side=='LONG' else 'S'}",
                        "size": 1,
                    })
                # Exit marker
                _xt_snapped = min(_vis_times, key=lambda t: abs(t - _xt)) if _vis_times else None
                if _xt_snapped and abs(_xt_snapped - _xt) < 86400 * 5 and _xt_snapped != _et_snapped:
                    _exit_reason = str(_tr.get("exit_reason", ""))
                    _ex_col = C_GREEN if (_rm is not None and pd.notna(_rm) and float(_rm) > 0) else C_RED
                    _trade_markers.append({
                        "time": _xt_snapped,
                        "position": "aboveBar" if _side == "LONG" else "belowBar",
                        "color": _ex_col,
                        "shape": "circle",
                        "text": _rm_s,
                        "size": 1,
                    })
            # Sort markers by time (required by LWC)
            _trade_markers.sort(key=lambda m: m["time"])

        bar_spacing = max(3, min(18, 900 // max(len(candles), 1)))

        renderLightweightCharts(
            [
                {
                    "chart": {
                        "height": 420,
                        "layout": {
                            "background": {"type": "solid", "color": C_BG},
                            "textColor": C_MUTED,
                            "fontFamily": "Inter,system-ui,sans-serif",
                        },
                        "grid": {
                            "vertLines": {"color": C_BORDER, "style": 1},
                            "horzLines": {"color": C_BORDER, "style": 1},
                        },
                        "crosshair": {"mode": 1},
                        "rightPriceScale": {"borderColor": C_BORDER},
                        "timeScale": {
                            "borderColor": C_BORDER,
                            "barSpacing": bar_spacing,
                            "rightOffset": 3,
                            "timeVisible": True,
                            "secondsVisible": False,
                        },
                    },
                    "series": [
                        {
                            "type": "Candlestick",
                            "data": candles,
                            "options": {
                                "upColor": C_GREEN, "downColor": C_RED,
                                "borderUpColor": C_GREEN, "borderDownColor": C_RED,
                                "wickUpColor": C_GREEN, "wickDownColor": C_RED,
                            },
                            "priceLines": price_lines,
                            "markers": _trade_markers,
                        }
                    ] + indicator_series,
                },
                {
                    "chart": {
                        "height": 90,
                        "layout": {
                            "background": {"type": "solid", "color": C_BG},
                            "textColor": C_MUTED,
                        },
                        "grid": {
                            "vertLines": {"visible": False},
                            "horzLines": {"visible": False},
                        },
                        "timeScale": {"visible": False},
                        "rightPriceScale": {
                            "scaleMargins": {"top": 0.1, "bottom": 0.0},
                            "borderVisible": False,
                        },
                    },
                    "series": [{
                        "type": "Histogram",
                        "data": vol,
                        "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""},
                        "priceScale": {"scaleMargins": {"top": 0, "bottom": 0}, "alignLabels": False},
                    }],
                },
            ],
            key=f"lwc_{symbol}_{interval}"
                f"_{int(st.session_state.show_ema20)}"
                f"{int(st.session_state.show_ema50)}"
                f"{int(st.session_state.show_sma200)}",
        )

        # OHLCV strip
        _chg = float(last["close"]) - float(last["open"])
        _chg_pct = _chg / float(last["open"]) * 100 if float(last["open"]) > 0 else 0
        _cc = C_GREEN if _chg >= 0 else C_RED
        st.markdown(
            f'<div class="ohlc-row" style="color:{C_MUTED};padding:4px 0">'
            f'O <b style="color:{C_TEXT}">{last["open"]:.4f}</b> &nbsp;'
            f'H <b style="color:{C_GREEN}">{last["high"]:.4f}</b> &nbsp;'
            f'L <b style="color:{C_RED}">{last["low"]:.4f}</b> &nbsp;'
            f'C <b style="color:{C_TEXT}">{last["close"]:.4f}</b> &nbsp;'
            f'<span style="color:{_cc}">({_chg:+.4f} / {_chg_pct:+.2f}%)</span> &nbsp;'
            f'Vol <b style="color:{C_DIM}">{last["volume"]:,.0f}</b>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Indicator values legend
        _leg = []
        for _col, _color, _lbl in [("_ema20","#60A5FA","EMA20"),("_ema50","#A78BFA","EMA50"),("_sma200","#FB923C","SMA200")]:
            if _col in df.columns:
                _v = df[_col].iloc[cursor]
                if pd.notna(_v):
                    _leg.append(f'<span style="color:{_color};font-size:12px">{_lbl} {_v:.2f}</span>')
        if _leg:
            st.markdown(" &nbsp;·&nbsp; ".join(_leg), unsafe_allow_html=True)

    # ── Decision panel ─────────────────────────────────────────────────── #
    with col_panel:
        pos     = st.session_state.pos
        pending = st.session_state.pending

        # CASE A — idle ─────────────────────────────────────────────────
        if pos is None and pending is None:

            # ── Pre-compute ATR defaults ─────────────────────────────────
            _c = float(last["close"])
            _atr_slice = df.iloc[max(0, cursor - 14): cursor + 1]
            _atr = float((_atr_slice["high"] - _atr_slice["low"]).mean()) if len(_atr_slice) > 2 else _c * 0.01

            _q_stop_val   = st.session_state.q_stop_ovr
            _q_target_val = st.session_state.q_target_ovr

            def _resolve(side: str):
                _s_def = round(_c - _atr, 4) if side == "LONG" else round(_c + _atr, 4)
                _t_def = round(_c + _atr * 2, 4) if side == "LONG" else round(_c - _atr * 2, 4)
                _s = float(_q_stop_val)   if _q_stop_val   is not None else _s_def
                _t = float(_q_target_val) if _q_target_val is not None else _t_def
                return _s, _t, _s_def, _t_def

            # ── Account + Risk row ───────────────────────────────────────
            _acct  = float(st.session_state.q_acct)
            _riskp = float(st.session_state.q_risk_pct)

            _ra1, _ra2 = st.columns(2)
            with _ra1:
                _new_acct = st.number_input(
                    "Account ($)", value=int(_acct), step=1000,
                    key="acct_top", label_visibility="visible",
                )
                st.session_state.q_acct = int(_new_acct)
                _acct = float(_new_acct)
            with _ra2:
                st.markdown(
                    f'<div style="color:{C_MUTED};font-size:11px;font-weight:600;'
                    f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Risk %</div>',
                    unsafe_allow_html=True,
                )
                _rp2 = st.columns(4)
                for _rpc, _rpv in zip(_rp2, [0.5, 1.0, 2.0, 3.0]):
                    with _rpc:
                        _act = abs(_riskp - _rpv) < 0.01
                        if st.button(
                            f"{_rpv}%", key=f"rp_{_rpv}",
                            type="primary" if _act else "secondary",
                            use_container_width=True,
                        ):
                            st.session_state.q_risk_pct = _rpv
                            st.rerun()

            # ── Live quantities preview ──────────────────────────────────
            _s_long,  _t_long,  _, _ = _resolve("LONG")
            _s_short, _t_short, _, _ = _resolve("SHORT")
            _r0_long  = abs(_c - _s_long)
            _r0_short = abs(_c - _s_short)
            _units_long  = int(_acct * _riskp / 100 / _r0_long)  if _r0_long  > 1e-10 else 0
            _units_short = int(_acct * _riskp / 100 / _r0_short) if _r0_short > 1e-10 else 0
            _rr_long  = abs(_t_long  - _c) / _r0_long  if _r0_long  > 1e-10 else 0
            _rr_short = abs(_t_short - _c) / _r0_short if _r0_short > 1e-10 else 0
            _rr_lc = C_GREEN if _rr_long  >= 2 else (C_ACCENT if _rr_long  >= 1 else C_RED)
            _rr_sc = C_GREEN if _rr_short >= 2 else (C_ACCENT if _rr_short >= 1 else C_RED)
            _dollar_risk = _acct * _riskp / 100

            st.markdown(
                f'<div style="background:{C_SURF2};border:1px solid {C_BORDER};border-radius:8px;'
                f'padding:7px 12px;font-size:12px;color:{C_MUTED};margin:6px 0 10px 0;display:flex;gap:12px">'
                f'Risk&nbsp;<b style="color:{C_ACCENT}">${_dollar_risk:.0f}</b>'
                f'&nbsp;·&nbsp;1R={_r0_long:.4f}'
                f'&nbsp;·&nbsp;Stop<b style="color:{C_RED}">&nbsp;{_s_long:.4f}</b>'
                f'&nbsp;·&nbsp;Tgt<b style="color:{C_GREEN}">&nbsp;{_t_long:.4f}</b>'
                f'&nbsp;·&nbsp;R:R&nbsp;<b style="color:{_rr_lc}">{_rr_long:.2f}</b>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── BUY / SELL big buttons (instant fill at close) ───────────
            _bb1, _bb2 = st.columns(2)
            with _bb1:
                st.markdown(
                    f'<div style="text-align:center;background:#16a34a22;border:2px solid {C_GREEN};'
                    f'border-radius:12px;padding:6px 0 4px 0;margin-bottom:4px">'
                    f'<div style="font-size:28px;font-weight:900;color:{C_GREEN};'
                    f'line-height:1">{_units_long:,}</div>'
                    f'<div style="font-size:10px;color:{C_GREEN};opacity:.8;'
                    f'font-weight:600;text-transform:uppercase">units</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "▲  BUY  LONG", use_container_width=True,
                    type="primary", key="instant_buy",
                ):
                    _s, _t, _, _ = _resolve("LONG")
                    st.session_state.pos = eng.Position(
                        side="LONG",
                        entry_time=int(last["time"]),
                        entry=_c,
                        stop=_s, target=_t,
                        setup=st.session_state.q_setup,
                        trigger=st.session_state.q_trigger,
                        emotag=st.session_state.q_emotag,
                        emo_intensity=int(st.session_state.q_emo_int),
                        rule_adherence=int(st.session_state.q_rule_ad),
                        notes=st.session_state.q_notes,
                    )
                    st.session_state.q_stop_ovr   = None
                    st.session_state.q_target_ovr = None
                    st.session_state.trade_side   = "LONG"
                    st.session_state._ap_skip     = True
                    st.rerun()
            with _bb2:
                st.markdown(
                    f'<div style="text-align:center;background:#dc262622;border:2px solid {C_RED};'
                    f'border-radius:12px;padding:6px 0 4px 0;margin-bottom:4px">'
                    f'<div style="font-size:28px;font-weight:900;color:{C_RED};'
                    f'line-height:1">{_units_short:,}</div>'
                    f'<div style="font-size:10px;color:{C_RED};opacity:.8;'
                    f'font-weight:600;text-transform:uppercase">units</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "▼  SELL  SHORT", use_container_width=True,
                    type="secondary", key="instant_sell",
                ):
                    _s, _t, _, _ = _resolve("SHORT")
                    st.session_state.pos = eng.Position(
                        side="SHORT",
                        entry_time=int(last["time"]),
                        entry=_c,
                        stop=_s, target=_t,
                        setup=st.session_state.q_setup,
                        trigger=st.session_state.q_trigger,
                        emotag=st.session_state.q_emotag,
                        emo_intensity=int(st.session_state.q_emo_int),
                        rule_adherence=int(st.session_state.q_rule_ad),
                        notes=st.session_state.q_notes,
                    )
                    st.session_state.q_stop_ovr   = None
                    st.session_state.q_target_ovr = None
                    st.session_state.trade_side   = "SHORT"
                    st.session_state._ap_skip     = True
                    st.rerun()

            # ── Custom overrides banner ───────────────────────────────────
            if _q_stop_val is not None:
                st.markdown(
                    f'<div style="background:#F59E0B18;border:1px solid {C_ACCENT};border-radius:6px;'
                    f'padding:4px 10px;font-size:11px;color:{C_ACCENT}">'
                    f'⚙ Custom Stop {_q_stop_val:.4f} · Target {_q_target_val:.4f}'
                    f'&nbsp;<span style="opacity:.7">— click BUY/SELL to apply</span></div>',
                    unsafe_allow_html=True,
                )

            # ── Advanced settings expander ───────────────────────────────
            with st.expander("⚙ Advanced — stop / target / tags", expanded=False):
                _, _s_def_l, _, _ = (lambda s,t,sd,td: (s,sd,t,td))(*_resolve("LONG"))  # noqa
                _s_def_l = round(_c - _atr, 4)
                _t_def_l = round(_c + _atr * 2, 4)
                _cs1, _cs2 = st.columns(2)
                with _cs1:
                    _q_s = st.number_input("Stop",   value=float(_q_stop_val   or _s_def_l), format="%.4f", key="q_stop_in")
                with _cs2:
                    _q_t = st.number_input("Target", value=float(_q_target_val or _t_def_l), format="%.4f", key="q_target_in")

                _q_setup   = st.text_input("Setup",   value=st.session_state.q_setup,   placeholder="ORB / Break&Retest", key="q_set_in")
                _q_trigger = st.text_input("Trigger", value=st.session_state.q_trigger, placeholder="Candle close above level", key="q_trg_in")
                _q_emotag  = st.text_input("EmoTag",  value=st.session_state.q_emotag,  placeholder="#Neutral #FOMO", key="q_emo_in")
                _qj1, _qj2 = st.columns(2)
                with _qj1:
                    _q_ei = st.slider("Emo", 0, 10, int(st.session_state.q_emo_int), key="q_ei_in")
                with _qj2:
                    _q_ra = st.radio("Rules", [1, 0],
                        index=0 if st.session_state.q_rule_ad == 1 else 1,
                        format_func=lambda x: "✓ OK" if x == 1 else "✗ Broke",
                        horizontal=True, key="q_ra_in")
                _q_notes = st.text_area("Notes", value=st.session_state.q_notes, height=50,
                    placeholder="What do you see?", key="q_nt_in")

                _sv1, _sv2 = st.columns(2)
                with _sv1:
                    if st.button("💾 Apply overrides", use_container_width=True, key="q_save_btn"):
                        st.session_state.q_stop_ovr   = float(_q_s)
                        st.session_state.q_target_ovr = float(_q_t)
                        st.session_state.q_setup      = _q_setup
                        st.session_state.q_trigger    = _q_trigger
                        st.session_state.q_emotag     = _q_emotag
                        st.session_state.q_emo_int    = int(_q_ei)
                        st.session_state.q_rule_ad    = int(_q_ra)
                        st.session_state.q_notes      = _q_notes
                        st.rerun()
                with _sv2:
                    if st.button("✕ Clear overrides", use_container_width=True, key="q_clr_btn"):
                        st.session_state.q_stop_ovr   = None
                        st.session_state.q_target_ovr = None
                        st.session_state.q_setup      = ""
                        st.session_state.q_trigger    = ""
                        st.session_state.q_emotag     = ""
                        st.session_state.q_emo_int    = 0
                        st.session_state.q_rule_ad    = 1
                        st.session_state.q_notes      = ""
                        st.rerun()

        # CASE B — pending ──────────────────────────────────────────────
        elif pending is not None and pos is None:
            st.markdown("### ⏳ Pending Order")
            _rr_p = (abs(pending.target - float(last["close"])) /
                     abs(pending.stop   - float(last["close"]))) if abs(pending.stop - float(last["close"])) > 1e-10 else 0
            st.markdown(
                f'<div class="stat-card" style="margin-bottom:12px">'
                f'<div style="font-size:22px;font-weight:700;color:{C_GREEN if pending.side=="LONG" else C_RED}">{pending.side}</div>'
                f'<div style="color:{C_MUTED};font-size:12px;margin-top:6px">'
                f'Stop <b style="color:{C_RED}">{pending.stop:.4f}</b>&nbsp;│&nbsp;'
                f'Target <b style="color:{C_GREEN}">{pending.target:.4f}</b>&nbsp;│&nbsp;'
                f'R:R <b style="color:{C_ACCENT}">{_rr_p:.2f}</b></div>'
                f'<div style="color:{C_DIM};font-size:11px;margin-top:4px">'
                f'{pending.setup or "—"} &nbsp;·&nbsp; {pending.trigger or "—"}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.info("Fills at the **open** of the next candle. Press ▶ +1.")
            if st.button("✕ Cancel Order", use_container_width=True):
                st.session_state.pending = None
                st.rerun()

        # CASE C — open position ────────────────────────────────────────
        elif pos is not None:
            lc     = float(last["close"])
            live_r = pos.r_multiple(lc)
            rr     = pos.rr_ratio()
            r0     = pos.initial_r()
            lrc    = C_GREEN if live_r >= 0 else C_RED

            st.markdown("### 🔴 Open Position")

            st.markdown(
                f'<div style="background:{C_SURF2};border:1px solid {lrc};border-radius:10px;'
                f'padding:14px;text-align:center;margin-bottom:12px">'
                f'<div style="font-size:11px;color:{C_MUTED};font-weight:600;'
                f'text-transform:uppercase;letter-spacing:.06em">Live R (mark→close)</div>'
                f'<div style="font-size:38px;font-weight:800;color:{lrc}">{live_r:+.2f}R</div>'
                f'<div style="font-size:11px;color:{C_MUTED}">'
                f'Close {lc:.4f} &nbsp;·&nbsp; R:R {rr:.2f} &nbsp;·&nbsp; 1R = {r0:.4f}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Entry",  f"{pos.entry:.4f}")
            with m2: st.metric("Stop",   f"{pos.stop:.4f}")
            with m3: st.metric("Target", f"{pos.target:.4f}")

            if pos.setup or pos.trigger:
                st.caption(f"📋 {pos.setup}  •  {pos.trigger}")

            st.divider()

            _x1, _x2, _x3 = st.columns(3)
            with _x1:
                if st.button("Exit @ Close", use_container_width=True):
                    _rm = pos.r_multiple(lc)
                    db.insert_trade({"symbol": symbol, "interval": interval,
                        "side": pos.side, "entry_time": pos.entry_time,
                        "exit_time": int(last["time"]), "entry": pos.entry,
                        "exit": lc, "stop": pos.stop, "target": pos.target,
                        "r_multiple": float(_rm) if np.isfinite(_rm) else None,
                        "exit_reason": "MANUAL@CLOSE", "setup": pos.setup,
                        "trigger": pos.trigger, "emotag": pos.emotag,
                        "emo_intensity": int(pos.emo_intensity),
                        "rule_adherence": int(pos.rule_adherence), "notes": pos.notes,
                    })
                    st.session_state.pos = None
                    st.session_state._ap_skip = True
                    st.rerun()
            with _x2:
                if st.button("🔒 Move to BE", use_container_width=True):
                    st.session_state.pos.stop = st.session_state.pos.entry
                    st.rerun()
            with _x3:
                if st.button("½ Partial exit", use_container_width=True):
                    _rm = pos.r_multiple(lc) * 0.5
                    db.insert_trade({"symbol": symbol, "interval": interval,
                        "side": pos.side, "entry_time": pos.entry_time,
                        "exit_time": int(last["time"]), "entry": pos.entry,
                        "exit": lc, "stop": pos.stop, "target": pos.target,
                        "r_multiple": float(_rm) if np.isfinite(_rm) else None,
                        "exit_reason": "PARTIAL_50%@CLOSE", "setup": pos.setup,
                        "trigger": pos.trigger, "emotag": pos.emotag,
                        "emo_intensity": int(pos.emo_intensity),
                        "rule_adherence": int(pos.rule_adherence), "notes": pos.notes,
                    })
                    st.rerun()

            with st.expander("Custom exit / partial"):
                _ex_px  = st.number_input("Exit price", value=lc, format="%.4f", key="cex_px")
                _ex_pct = st.slider("% of position", 10, 100, 100, 10, key="cex_pct")
                if st.button("Execute", use_container_width=True, key="cex_go"):
                    _rm = pos.r_multiple(float(_ex_px)) * _ex_pct / 100
                    db.insert_trade({"symbol": symbol, "interval": interval,
                        "side": pos.side, "entry_time": pos.entry_time,
                        "exit_time": int(last["time"]), "entry": pos.entry,
                        "exit": float(_ex_px), "stop": pos.stop, "target": pos.target,
                        "r_multiple": float(_rm) if np.isfinite(_rm) else None,
                        "exit_reason": f"CUSTOM_{_ex_pct}%@{_ex_px:.4f}",
                        "setup": pos.setup, "trigger": pos.trigger, "emotag": pos.emotag,
                        "emo_intensity": int(pos.emo_intensity),
                        "rule_adherence": int(pos.rule_adherence), "notes": pos.notes,
                    })
                    if _ex_pct == 100:
                        st.session_state.pos = None
                    st.rerun()

            with st.expander("Trail stop"):
                _new_stop = st.number_input("New stop", value=pos.stop, format="%.4f", key="ts_val")
                if st.button("Update stop", use_container_width=True, key="ts_go"):
                    st.session_state.pos.stop = float(_new_stop)
                    st.rerun()

    # ── Persist state every render (catches BUY/SELL/exit that don't call _advance) ── #
    _save_session(symbol, interval)

    # ── Auto-play loop ──────────────────────────────────────────────────────── #
    # Always advances exactly 1 bar per render.
    # Sleep = max(0, speed - render_overhead) so fast speeds (≤0.2s) run full-speed.
    if st.session_state.autoplay:
        _stop_on_trade = st.session_state.get("autoplay_stop_on_trade", False)
        _trade_active  = (st.session_state.pos is not None
                          or st.session_state.pending is not None)
        if _stop_on_trade and _trade_active:
            st.session_state.autoplay = False
            st.toast("Auto-play paused — open/pending trade.", icon="⏸")
            st.rerun()
        elif st.session_state.cursor < N - 1:
            _speed = float(st.session_state.autoplay_speed)
            _now   = time.time()
            _last  = float(st.session_state._ap_last_render)
            # Render overhead is typically 150-250ms; sleep only the remainder
            _render_overhead = 0.18
            _sleep = max(0.0, _speed - _render_overhead)
            # Skip sleep on first tick or after a manual user action
            if _last > 0.0 and not st.session_state._ap_skip and _sleep > 0.0:
                time.sleep(_sleep)
            st.session_state._ap_skip        = False
            st.session_state._ap_last_render = time.time()
            _advance(1)
            st.rerun()
        else:
            st.session_state.autoplay        = False
            st.session_state._ap_last_render = 0.0
            st.toast("Auto-play finished — reached end of data.", icon="✅")
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════ #
# TAB 2 — STATS & LOG
# ════════════════════════════════════════════════════════════════════════════ #
with tab_stats:
    trades_df = db.read_trades(symbol, interval)

    if trades_df.empty:
        st.info(f"No trades yet for **{symbol} {interval}**.")
    else:
        r_series = trades_df["r_multiple"].dropna().astype(float)
        stats    = eng.compute_stats(r_series)

        # ── KPI strip ─────────────────────────────────────────────────── #
        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        _pf     = stats.get("profit_factor", float("nan"))
        _pf_str = f"{_pf:.2f}" if np.isfinite(_pf) else "∞"
        with k1: st.metric("Trades",         stats.get("trades", "—"))
        with k2: st.metric("Win Rate",        f"{stats.get('win_rate',0)*100:.1f}%")
        with k3: st.metric("Total R",         f"{r_series.sum():+.2f}R")
        with k4: st.metric("Expectancy",      f"{stats.get('expectancy_R',0):+.3f}R")
        with k5: st.metric("Avg Win",         f"{stats.get('avg_win_R', float('nan')):+.2f}R"  if np.isfinite(stats.get('avg_win_R',  float('nan'))) else "—")
        with k6: st.metric("Avg Loss",        f"{stats.get('avg_loss_R', float('nan')):+.2f}R" if np.isfinite(stats.get('avg_loss_R', float('nan'))) else "—")
        with k7: st.metric("Profit Factor",   _pf_str)

        st.divider()

        # ── Charts row ────────────────────────────────────────────────── #
        ch1, ch2, ch3 = st.columns(3)

        with ch1:
            st.markdown("**Equity curve (R)**")
            if "equity_curve" in stats and stats["equity_curve"]:
                _eq_df = pd.DataFrame({
                    "Trade": range(1, len(stats["equity_curve"]) + 1),
                    "Equity R": stats["equity_curve"],
                })
                st.line_chart(_eq_df.set_index("Trade"), color=C_PRIMARY)

        with ch2:
            st.markdown("**R-multiple distribution**")
            _bins = pd.cut(r_series, bins=12)
            _hist = r_series.groupby(_bins, observed=True).count()
            _hist_df = pd.DataFrame({"R bucket": [str(x) for x in _hist.index], "Count": _hist.values})
            st.bar_chart(_hist_df.set_index("R bucket"), color=C_PRIMARY)

        with ch3:
            st.markdown("**Exit reasons**")
            _reasons = trades_df["exit_reason"].value_counts()
            st.bar_chart(_reasons, color=C_ACCENT)

        st.divider()

        # ── Breakdown ─────────────────────────────────────────────────── #
        tbl1, tbl2 = st.columns(2)

        with tbl1:
            if "setup" in trades_df.columns and trades_df["setup"].str.strip().astype(bool).any():
                st.markdown("**Setup performance**")
                _sg = (trades_df[trades_df["setup"].str.strip().astype(bool)]
                       .groupby("setup")["r_multiple"]
                       .agg(Trades="count", Mean_R="mean", Total_R="sum",
                            Win_pct=lambda x: round((x > 0).mean() * 100, 1))
                       .round(3).reset_index())
                st.dataframe(_sg, use_container_width=True, hide_index=True)

        with tbl2:
            if "emotag" in trades_df.columns:
                st.markdown("**EmoTag performance**")
                _ed = trades_df.copy()
                _ed["emotag"] = _ed["emotag"].replace("", "Untagged").fillna("Untagged")
                _eg = (_ed.groupby("emotag")["r_multiple"]
                          .agg(Trades="count", Mean_R="mean", Total_R="sum")
                          .round(3).reset_index())
                st.dataframe(_eg, use_container_width=True, hide_index=True)

        st.divider()

        # ── Trade log ──────────────────────────────────────────────────── #
        st.markdown("**Trade log**")
        _show = [c for c in ["id","side","entry","exit","stop","target",
                              "r_multiple","exit_reason","setup","trigger",
                              "emotag","rule_adherence","notes"]
                 if c in trades_df.columns]

        def _row_bg(row):
            r = row.get("r_multiple", None)
            if r is None or (isinstance(r, float) and not np.isfinite(r)):
                return [""] * len(row)
            return [f"background-color: {'#22C55E15' if r > 0 else '#EF444415'}"] * len(row)

        st.dataframe(trades_df[_show].style.apply(_row_bg, axis=1),
                     use_container_width=True, hide_index=True)

        _dl_col, _clr_col = st.columns(2)
        with _dl_col:
            _csv = trades_df[_show].to_csv(index=False).encode()
            st.download_button("⬇ Export CSV", _csv,
                               f"tradesim_{symbol}_{interval}.csv",
                               mime="text/csv", use_container_width=True)
        with _clr_col:
            if st.button("🗑 Clear history", use_container_width=True, type="secondary"):
                db.clear_trades(symbol, interval)
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════ #
# TAB 3 — MONTE CARLO
# ════════════════════════════════════════════════════════════════════════════ #
with tab_mc:
    _mc_t  = db.read_trades(symbol, interval)
    _mc_n  = 0 if _mc_t.empty else int(_mc_t["r_multiple"].dropna().shape[0])

    if _mc_n < 5:
        st.info(f"Need at least **5 trades** with an R-multiple. You have **{_mc_n}**.")
    else:
        r_mc = _mc_t["r_multiple"].dropna().astype(float)

        mc1, mc2, mc3 = st.columns(3)
        with mc1: n_sims   = st.slider("Simulations",       100, 2000,  500, 100)
        with mc2: n_trades = st.slider("Trades per sim",     20,  500,  100,  10)
        with mc3: ruin_thr = st.slider("Ruin threshold (R)",-100,   -5, -20,   5)

        if st.button("▶ Run Monte Carlo", type="primary"):
            with st.spinner("Simulating…"):
                mc = eng.monte_carlo(r_mc, n_sims=n_sims, n_trades=n_trades)

            if not mc:
                st.error("Not enough data.")
            else:
                p1, p2, p3, p4, p5, p6 = st.columns(6)
                with p1: st.metric("5th pct",  f"{mc['p5']:+.1f}R",  delta_color="inverse")
                with p2: st.metric("25th pct", f"{mc['p25']:+.1f}R")
                with p3: st.metric("Median",   f"{mc['p50']:+.1f}R")
                with p4: st.metric("75th pct", f"{mc['p75']:+.1f}R")
                with p5: st.metric("95th pct", f"{mc['p95']:+.1f}R")
                _ruin_c = C_RED if mc["ruin_pct"] > 0.05 else C_GREEN
                with p6: st.metric("Ruin risk", f"{mc['ruin_pct']*100:.1f}%")

                st.divider()

                # Percentile fan
                _sims_arr = np.array(mc["curves_sample"])
                _t_axis   = list(range(1, n_trades + 1))
                _band_df  = pd.DataFrame({
                    "Trade":  _t_axis,
                    "5th":    np.percentile(_sims_arr, 5,  axis=0),
                    "Median": np.percentile(_sims_arr, 50, axis=0),
                    "95th":   np.percentile(_sims_arr, 95, axis=0),
                })
                mc_c1, mc_c2 = st.columns(2)
                with mc_c1:
                    st.markdown("**Percentile fan (5 / median / 95)**")
                    st.line_chart(_band_df.set_index("Trade"),
                                  color=[C_RED, C_PRIMARY, C_GREEN])
                with mc_c2:
                    st.markdown("**50 sample paths**")
                    _paths = pd.DataFrame(
                        _sims_arr[:50].T,
                        columns=[f"s{i}" for i in range(min(50, len(_sims_arr)))],
                    )
                    st.line_chart(_paths)

                st.caption(
                    f"{n_sims} bootstrap sims × {n_trades} trades from "
                    f"{len(r_mc)} historical R-multiples. Ruin = below {ruin_thr}R."
                )
