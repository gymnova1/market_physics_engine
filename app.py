import time
import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="Market Physics Engine",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Compact, phone-friendly layout
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px;}
    [data-testid="stMetric"] {background: rgba(128,128,128,.08); padding: 12px; border-radius: 12px;}
    .small-note {font-size: .85rem; opacity: .78;}
    h1 {font-size: clamp(1.65rem, 4vw, 2.35rem) !important;}
    @media (max-width: 640px) {
      .block-container {padding-left: .8rem; padding-right: .8rem;}
      [data-testid="stMetric"] {padding: 8px;}
    }
</style>
""", unsafe_allow_html=True)

BASE = "https://fapi.binance.com"

@st.cache_data(ttl=45, show_spinner=False)
def get_klines(symbol: str, interval: str, limit: int):
    url = f"{BASE}/fapi/v1/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
    r.raise_for_status()
    raw = r.json()
    cols = ["open_time","open","high","low","close","volume","close_time",
            "quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"]
    df = pd.DataFrame(raw, columns=cols)
    for c in ["open","high","low","close","volume","quote_volume","taker_buy_base","taker_buy_quote"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_convert("Europe/Budapest")
    return df

def rolling_z(s, window=50):
    mean = s.rolling(window, min_periods=max(8, window//4)).mean()
    std = s.rolling(window, min_periods=max(8, window//4)).std().replace(0, np.nan)
    return ((s - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0)

def calculate_physics(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    close = x["close"]
    logret = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).fillna(0)

    # Kinematics: normalized velocity and acceleration
    x["velocity"] = logret * 10000
    x["acceleration"] = x["velocity"].diff().fillna(0)
    x["velocity_z"] = rolling_z(x["velocity"], 50).clip(-4, 4)
    x["acceleration_z"] = rolling_z(x["acceleration"], 50).clip(-4, 4)

    # Directional order-flow proxy from Binance taker-buy volume
    total = x["volume"].replace(0, np.nan)
    x["buy_pressure"] = ((2 * x["taker_buy_base"] / total) - 1).fillna(0).clip(-1, 1)
    x["force"] = (x["buy_pressure"] * rolling_z(x["volume"], 50)).clip(-4, 4)

    # Inertia: persistence of signed returns, scaled to 0..100
    sign = np.sign(x["velocity"])
    persistence = sign.rolling(20, min_periods=5).mean().abs().fillna(0)
    trend_alignment = (np.sign(x["velocity"].rolling(5, min_periods=2).mean()) == sign).astype(float)
    x["inertia"] = (50 + 50 * persistence * trend_alignment).clip(0, 100)

    # Friction proxy: wickiness + weak price response relative to volume
    candle_range = (x["high"] - x["low"]).replace(0, np.nan)
    body_ratio = ((x["close"] - x["open"]).abs() / candle_range).fillna(0)
    wickiness = (1 - body_ratio).clip(0, 1)
    vol_z = rolling_z(x["volume"], 50).clip(-2, 3)
    x["friction"] = (100 * (0.65 * wickiness + 0.35 / (1 + np.exp(vol_z)))).clip(0, 100)

    # Potential energy proxy: low recent range/ATR relative to longer-term volatility
    tr = pd.concat([
        x["high"] - x["low"],
        (x["high"] - close.shift()).abs(),
        (x["low"] - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr_fast = tr.rolling(10, min_periods=5).mean()
    atr_slow = tr.rolling(40, min_periods=15).mean()
    compression = (1 - atr_fast / atr_slow.replace(0, np.nan)).clip(0, 1).fillna(0)
    volume_build = rolling_z(x["volume"], 40).clip(0, 3) / 3
    x["potential"] = (100 * (0.75 * compression + 0.25 * volume_build)).clip(0, 100)

    # Entropy: Shannon entropy of recent return distribution, normalized 0..100
    def entropy_window(a):
        a = np.asarray(a)
        if len(a) < 8:
            return np.nan
        hist, _ = np.histogram(a, bins=10)
        p = hist[hist > 0] / len(a)
        return float(-(p * np.log(p)).sum() / np.log(10) * 100)
    x["entropy"] = logret.rolling(30, min_periods=15).apply(entropy_window, raw=True).fillna(50).clip(0, 100)

    # Composite directional score; positive = bullish, negative = bearish
    directional = (
        0.35 * x["velocity_z"] +
        0.25 * x["acceleration_z"] +
        0.25 * x["force"] +
        0.15 * ((x["buy_pressure"] * 2).clip(-1, 1))
    )
    quality = (1 - x["entropy"] / 150).clip(0.25, 1)
    x["physics_score"] = (50 + 50 * np.tanh(directional / 2) * quality).clip(0, 100)
    x["directional_strength"] = (x["physics_score"] - 50).abs() * 2
    x["regime"] = np.select(
        [x["entropy"] > 78, x["potential"] > 65, x["inertia"] > 70],
        ["High entropy / noisy", "Compression / energy build-up", "Directional / persistent"],
        default="Mixed / transitional"
    )
    return x

def fmt_num(v, digits=2):
    try:
        return f"{float(v):,.{digits}f}"
    except Exception:
        return "—"

st.title("⚛️ Market Physics Engine")
st.caption("Kísérleti, fizikai analógiákra épülő piaci állapot- és dinamikaelemző")

with st.sidebar:
    st.subheader("Piaci beállítások")
    symbol = st.selectbox("Instrumentum", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"])
    interval = st.selectbox("Idősík", ["5m", "15m", "30m", "1h", "4h", "1d"], index=2)
    limit = st.slider("Betöltött gyertyák", 150, 1000, 500, 50)
    refresh = st.button("Adatok frissítése", use_container_width=True)
    st.caption("Forrás: Binance USDⓈ-M Futures publikus piaci adatok.")

if refresh:
    get_klines.clear()

try:
    with st.spinner("Binance-adatok betöltése és modellek számítása…"):
        raw = get_klines(symbol, interval, limit)
        data = calculate_physics(raw)
except Exception as e:
    st.error("Nem sikerült lekérni a Binance Futures adatokat.")
    st.code(str(e))
    st.info("Ellenőrizd az internetkapcsolatot, vagy próbáld újra később. A Binance API időszakosan korlátozhatja a kéréseket.")
    st.stop()

last = data.iloc[-1]
prev = data.iloc[-2]
score = float(last["physics_score"])
direction = "BULLISH" if score >= 58 else "BEARISH" if score <= 42 else "NEUTRAL"
delta = score - float(prev["physics_score"])

st.markdown(f"**{symbol} · {interval} · {last['time'].strftime('%Y-%m-%d %H:%M')} (Budapest)**")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Ár", fmt_num(last["close"], 2))
m2.metric("Physics Score", f"{score:.1f}/100", f"{delta:+.1f}")
m3.metric("Piaci irány", direction)
m4.metric("Állapot", str(last["regime"]))

st.markdown("### Fizikai modellkomponensek")
cols = st.columns(3)
metrics = [
    ("Sebesség", last["velocity"], "loghozam-alapú, skálázott"),
    ("Gyorsulás", last["acceleration"], "a sebesség változása"),
    ("Erő / order flow", last["force"], "taker vételi-eladási nyomás"),
    ("Tehetetlenség", last["inertia"], "trendirányú perzisztencia 0–100"),
    ("Súrlódás", last["friction"], "kanócosság + volumenproxy 0–100"),
    ("Potenciális energia", last["potential"], "volatilitás-kompresszió proxy 0–100"),
    ("Entrópia", last["entropy"], "hozameloszlás rendezetlensége 0–100"),
]
for i, (name, value, desc) in enumerate(metrics):
    with cols[i % 3]:
        st.metric(name, fmt_num(value, 1))
        st.caption(desc)

st.markdown("### Árfolyam és fizikai pontszám")
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                    row_heights=[0.68, 0.32], subplot_titles=("Árfolyam", "Physics Score"))
fig.add_trace(go.Candlestick(x=data["time"], open=data["open"], high=data["high"],
                             low=data["low"], close=data["close"], name="Ár"), row=1, col=1)
fig.add_trace(go.Scatter(x=data["time"], y=data["physics_score"], name="Physics Score",
                         line=dict(width=2)), row=2, col=1)
fig.add_hline(y=58, line_dash="dot", row=2, col=1)
fig.add_hline(y=42, line_dash="dot", row=2, col=1)
fig.update_layout(height=600, margin=dict(l=10,r=10,t=55,b=10), xaxis_rangeslider_visible=False,
                  legend=dict(orientation="h", y=1.02), hovermode="x unified")
fig.update_yaxes(title_text="Ár", row=1, col=1)
fig.update_yaxes(title_text="0–100", range=[0,100], row=2, col=1)
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Modellkomponensek időbeli alakulása")
component = st.selectbox("Megjelenített komponens", ["velocity_z", "acceleration_z", "force",
    "inertia", "friction", "potential", "entropy"])
labels = {"velocity_z":"Sebesség (z-score)", "acceleration_z":"Gyorsulás (z-score)",
          "force":"Erő / order flow", "inertia":"Tehetetlenség", "friction":"Súrlódás",
          "potential":"Potenciális energia", "entropy":"Entrópia"}
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=data["time"], y=data[component], mode="lines", name=labels[component]))
fig2.update_layout(height=300, margin=dict(l=10,r=10,t=25,b=10), hovermode="x unified")
st.plotly_chart(fig2, use_container_width=True)

st.markdown("### Legutóbbi gyertyák")
view = data[["time","open","high","low","close","volume","buy_pressure",
             "physics_score","inertia","friction","potential","entropy"]].tail(15).copy()
view["time"] = view["time"].dt.strftime("%m-%d %H:%M")
view = view.rename(columns={"time":"Idő","open":"Open","high":"High","low":"Low","close":"Close",
    "volume":"Volume","buy_pressure":"Vételi nyomás","physics_score":"Physics Score",
    "inertia":"Tehetetlenség","friction":"Súrlódás","potential":"Potenciális energia","entropy":"Entrópia"})
st.dataframe(view.iloc[::-1], use_container_width=True, hide_index=True)

st.markdown("### Hogyan értelmezd?")
st.write("""
- **Physics Score 58 felett:** pozitív irányú dinamika; önmagában nem vételi jel.
- **Physics Score 42 alatt:** negatív irányú dinamika; önmagában nem eladási jel.
- **42–58 között:** semleges vagy bizonytalan állapot.
- **Magas potenciális energia:** szűkülő volatilitásra és lehetséges aktivitásnövekedésre utaló proxy, nem előrejelzés.
- **Magas entrópia:** rendezetlenebb, nehezebben modellezhető hozamfolyamat.
- **Magas súrlódás:** a gyertyaszerkezet és volumen alapján becsült akadályozottság, nem valódi order-book ellenállás.
""")
st.warning("Fontos: ez kutatási prototípus, nem befektetési tanács és nem kész kereskedési stratégia. A „potenciális energia”, „súrlódás” és „tehetetlenség” piaci proxyk, nem szó szerinti fizikai mennyiségek. A pontszámot éles kereskedés előtt díjakkal, csúszással és out-of-sample adatokon is tesztelni kell.")

with st.expander("Módszertani megjegyzések"):
    st.write("""
    **Sebesség:** egymást követő záróárak loghozama, 10 000-rel skálázva.

    **Gyorsulás:** a sebesség első differenciája.

    **Erő:** a Binance gyertyák taker-buy volumenéből becsült nettó agresszív vételi nyomás, volumen-z-score-ral súlyozva.

    **Tehetetlenség:** a közelmúltbeli hozamirányok következetessége.

    **Súrlódás:** gyertyakanócok és volumen alapján képzett közelítő mutató.

    **Potenciális energia:** rövid és hosszabb ATR arányából becsült volatilitás-kompresszió, volumen-kiegészítéssel.

    **Entrópia:** a 30 gyertyás loghozam-eloszlás normalizált Shannon-entrópiája.

    **Physics Score:** a sebesség, gyorsulás és order-flow irányított kombinációja, entrópiával mérsékelve.

    Ezek hipotézisek és mérnöki proxyk. A fizikai analógiák nem bizonyítják, hogy a piac Newton törvényei szerint működik.
    """)
