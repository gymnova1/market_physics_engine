# Market Physics Engine

Mobilbarát Streamlit webalkalmazás BTC/USDT és más Binance USDⓈ-M perpetual piacok elemzésére.

## Mit tud?

- Binance Futures publikus gyertyaadatok lekérése (OHLCV + taker-buy volumen)
- Árfolyam, Physics Score és komponensgrafikonok
- Sebesség, gyorsulás, order-flow erő, tehetetlenség, súrlódásproxy, potenciális energia proxy, entrópia
- Reszponzív felület, telefonos böngészőben is használható

## Telefonon történő megnyitás – javasolt módszer

A telefonon nem kell Pythont telepíteni. Az alkalmazást internetes Streamlit-oldalként kell futtatni.

1. Számítógépen hozz létre egy GitHub-fiókot, ha még nincs.
2. Hozz létre egy új, például `market-physics-engine` nevű **Public** repositoryt.
3. Töltsd fel a ZIP kibontása után a fájlokat és mappákat a repository gyökerébe (`app.py`, `requirements.txt`, `.streamlit/config.toml`, `README.md`).
4. Nyisd meg a https://share.streamlit.io oldalt, és jelentkezz be GitHub-fiókkal.
5. Válaszd a **Create app** lehetőséget, majd add meg a repositoryt, a branch-et (`main`) és a fő fájlt (`app.py`).
6. Kattints a Deploy gombra. A telepítés után kapsz egy `https://....streamlit.app` címet.
7. Nyisd meg ezt a címet Androidon vagy iPhone-on. Chrome-ban a menü → **Hozzáadás a kezdőképernyőhöz** lehetőséggel alkalmazásszerű parancsikont készíthetsz.

A Streamlit Cloud aktuális regisztrációs és használati feltételei változhatnak; a szolgáltatás elérhetőségét és korlátait a telepítéskor ellenőrizd.

## Helyi indítás Windows 11-en

A projekt mappájában CMD-ben:

```cmd
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

A telefon és a számítógép ugyanazon Wi-Fi hálózatán helyi hálózati eléréssel is megnyitható, de a felhős telepítés kényelmesebb.

## Adatforrás és korlátok

Az app a Binance USDⓈ-M Futures publikus `/fapi/v1/klines` végpontját használja. Nem kér API-kulcsot, nem küld megbízást, és nem fér hozzá privát számlaadatokhoz.

A fizikai fogalmak piaci analógiák, nem szó szerinti fizikai mennyiségek:
- sebesség: loghozam
- gyorsulás: sebességváltozás
- erő: taker-buy volumenből képzett order-flow proxy
- tehetetlenség: trendirányú perzisztencia
- súrlódás: gyertyakanóc és volumen alapú proxy
- potenciális energia: volatilitás-kompresszió proxy
- entrópia: hozameloszlás Shannon-entrópiája

A Physics Score kutatási indikátor, nem bizonyított előrejelző és nem befektetési tanács. Éles használat előtt backtest, walk-forward teszt, tranzakciós költségek és slippage modellezése szükséges.
