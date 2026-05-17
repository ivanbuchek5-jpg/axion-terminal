"""
CYPHER_TERMINAL — Flask Backend
Проксує запити до публічних API бірж, агрегує та повертає дані фронтенду.
Підтримувані біржі: Binance, Bybit, MEXC, Gate.io, BingX
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os

app = Flask(__name__, static_folder="static")
CORS(app)

# ─── Timeout для зовнішніх запитів ────────────────────────────────────────────
TIMEOUT = 5

# ─── Публічні API ендпоінти бірж ──────────────────────────────────────────────
EXCHANGE_APIS = {
    "binance": {
        "spot":    "https://api.binance.com/api/v3/ticker/24hr",
        "funding": "https://fapi.binance.com/fapi/v1/premiumIndex",
        "book":    "https://api.binance.com/api/v3/ticker/bookTicker",  # bid/ask
        "color":   "#F0B90B",
    },
    "bybit": {
        "spot":    "https://api.bybit.com/v5/market/tickers?category=spot",
        "funding": "https://api.bybit.com/v5/market/tickers?category=linear",
        "color":   "#F7A600",
    },
    "mexc": {
        "spot":    "https://api.mexc.com/api/v3/ticker/24hr",
        "book":    "https://api.mexc.com/api/v3/ticker/bookTicker",
        "color":   "#00B2FF",
    },
    "gate": {
        "spot":    "https://api.gateio.ws/api/v4/spot/tickers",
        "color":   "#EB4D4B",
    },
    "bingx": {
        "spot":    "https://open-api.bingx.com/openApi/spot/v1/ticker/24hr",
        "color":   "#6C5CE7",
    },
}

# ─── Хелпери ──────────────────────────────────────────────────────────────────

def safe_get(url, params=None):
    """Безпечний GET запит з таймаутом."""
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERR] {url}: {e}")
        return None


def fetch_all_parallel(tasks: dict) -> dict:
    """
    Виконує кілька HTTP запитів паралельно.
    tasks = {"key": (url, params), ...}
    Повертає {"key": parsed_json, ...}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(safe_get, url, params): key
                   for key, (url, params) in tasks.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            results[key] = fut.result()
    return results


def normalize_symbol(symbol: str) -> str:
    """BTC/USDT → BTCUSDT"""
    return symbol.replace("/", "").upper()


# ─── Парсери відповідей бірж ───────────────────────────────────────────────────

def parse_binance_spot(data, symbol=None):
    """Повертає список {symbol, price, change24h, volume, bid, ask}."""
    if not data:
        return []
    items = data if isinstance(data, list) else [data]
    out = []
    for d in items:
        s = d.get("symbol", "")
        if symbol and s != symbol:
            continue
        out.append({
            "symbol":    s,
            "price":     float(d.get("lastPrice", 0)),
            "change24h": float(str(d.get("priceChangePercent", 0) or 0).replace("%", "")),
            "volume":    float(d.get("quoteVolume", 0)),
            "bid":       float(d.get("bidPrice", 0) or 0),
            "ask":       float(d.get("askPrice", 0) or 0),
            "high24h":   float(d.get("highPrice", 0)),
            "low24h":    float(d.get("lowPrice", 0)),
        })
    return out


def parse_bybit_spot(data, symbol=None):
    if not data:
        return []
    items = data.get("result", {}).get("list", [])
    out = []
    for d in items:
        s = d.get("symbol", "")
        if symbol and s != symbol:
            continue
        out.append({
            "symbol":    s,
            "price":     float(d.get("lastPrice", 0) or 0),
            "change24h": float(d.get("price24hPcnt", 0) or 0) * 100,
            "volume":    float(d.get("turnover24h", 0) or 0),
            "bid":       float(d.get("bid1Price", 0) or 0),
            "ask":       float(d.get("ask1Price", 0) or 0),
            "high24h":   float(d.get("highPrice24h", 0) or 0),
            "low24h":    float(d.get("lowPrice24h", 0) or 0),
        })
    return out


def parse_mexc_spot(data, symbol=None):
    if not data:
        return []
    items = data if isinstance(data, list) else [data]
    out = []
    for d in items:
        s = d.get("symbol", "")
        if symbol and s != symbol:
            continue
        out.append({
            "symbol":    s,
            "price":     float(d.get("lastPrice", 0) or 0),
            "change24h": float(str(d.get("priceChangePercent", 0) or 0).replace("%", "")),
            "volume":    float(d.get("quoteVolume", 0) or 0),
            "bid":       float(d.get("bidPrice", 0) or 0),
            "ask":       float(d.get("askPrice", 0) or 0),
            "high24h":   float(d.get("highPrice", 0) or 0),
            "low24h":    float(d.get("lowPrice", 0) or 0),
        })
    return out


def parse_gate_spot(data, symbol=None):
    if not data:
        return []
    out = []
    for d in data:
        raw = d.get("currency_pair", "")
        s = raw.replace("_", "")
        if symbol and s != symbol:
            continue
        out.append({
            "symbol":    s,
            "price":     float(d.get("last", 0) or 0),
            "change24h": float(d.get("change_percentage", 0) or 0),
            "volume":    float(d.get("quote_volume", 0) or 0),
            "bid":       float(d.get("highest_bid", 0) or 0),
            "ask":       float(d.get("lowest_ask", 0) or 0),
            "high24h":   float(d.get("high_24h", 0) or 0),
            "low24h":    float(d.get("low_24h", 0) or 0),
        })
    return out


def parse_bingx_spot(data, symbol=None):
    if not data:
        return []
    items = data.get("data", {})
    if isinstance(items, dict):
        items = items.get("tickers", [])
    if not items:
        return []
    out = []
    for d in items:
        s = d.get("symbol", "").replace("-", "")
        if symbol and s != symbol:
            continue
        out.append({
            "symbol":    s,
            "price":     float(d.get("lastPrice", 0) or 0),
            "change24h": float(str(d.get("priceChangePercent", 0) or 0).replace("%", "")),
            "volume":    float(d.get("quoteVolume", 0) or 0),
            "bid":       0,
            "ask":       0,
            "high24h":   float(d.get("highPrice", 0) or 0),
            "low24h":    float(d.get("lowPrice", 0) or 0),
        })
    return out


PARSERS = {
    "binance": parse_binance_spot,
    "bybit":   parse_bybit_spot,
    "mexc":    parse_mexc_spot,
    "gate":    parse_gate_spot,
    "bingx":  parse_bingx_spot,
}


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Статичні файли ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


# ─── /api/prices?symbol=BTCUSDT ───────────────────────────────────────────────
@app.route("/api/prices")
def api_prices():
    """
    Повертає ціни одного символу з усіх бірж.
    ?symbol=BTCUSDT (default: BTCUSDT)
    """
    symbol = normalize_symbol(request.args.get("symbol", "BTCUSDT"))

    tasks = {
        "binance": (EXCHANGE_APIS["binance"]["spot"], {"symbol": symbol}),
        "bybit":   (f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}", None),
        "mexc":    (EXCHANGE_APIS["mexc"]["spot"], {"symbol": symbol}),
        "gate":    (EXCHANGE_APIS["gate"]["spot"], None),
        "bingx":  (f"https://open-api.bingx.com/openApi/spot/v1/ticker/24hr?symbol={symbol[:3]}-{symbol[3:]}", None),
    }
    raw = fetch_all_parallel(tasks)

    result = []
    for ex_name, data in raw.items():
        parser = PARSERS[ex_name]
        parsed = parser(data, symbol=symbol)
        if parsed:
            item = parsed[0]
            item["exchange"] = ex_name
            item["color"] = EXCHANGE_APIS[ex_name]["color"]
            result.append(item)

    # Сортуємо за ціною
    result.sort(key=lambda x: x["price"], reverse=True)

    return jsonify({"symbol": symbol, "data": result, "ts": int(time.time() * 1000)})


# ─── /api/spread?symbol=BTCUSDT ───────────────────────────────────────────────
@app.route("/api/spread")
def api_spread():
    """
    Розраховує спред між біржами для списку символів.
    ?symbols=BTCUSDT,ETHUSDT,SOLUSDT (default: топ пари)
    """
    default_symbols = "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,ADAUSDT,AVAXUSDT,DOGEUSDT,LINKUSDT"
    raw_symbols = request.args.get("symbols", default_symbols)
    symbols = [s.strip() for s in raw_symbols.split(",")]

    # Завантажуємо всі тікери паралельно
    tasks = {
        "binance": (EXCHANGE_APIS["binance"]["spot"], None),
        "bybit":   ("https://api.bybit.com/v5/market/tickers?category=spot", None),
        "mexc":    (EXCHANGE_APIS["mexc"]["spot"], None),
        "gate":    (EXCHANGE_APIS["gate"]["spot"], None),
    }
    raw = fetch_all_parallel(tasks)

    # Будуємо словник: {exchange: {symbol: {bid, ask, price}}}
    exchange_data = {}
    for ex_name, data in raw.items():
        parser = PARSERS[ex_name]
        items = parser(data)
        exchange_data[ex_name] = {item["symbol"]: item for item in items}

    # Рахуємо спреди
    spreads = []
    for symbol in symbols:
        prices_per_ex = {}
        for ex_name, ex_map in exchange_data.items():
            if symbol in ex_map:
                prices_per_ex[ex_name] = ex_map[symbol]

        if len(prices_per_ex) < 2:
            continue

        # Знаходимо пари з максимальним спредом
        ex_list = list(prices_per_ex.items())
        for i in range(len(ex_list)):
            for j in range(i + 1, len(ex_list)):
                ex_a, data_a = ex_list[i]
                ex_b, data_b = ex_list[j]

                price_a = data_a["price"]
                price_b = data_b["price"]

                if price_a <= 0 or price_b <= 0:
                    continue

                # Спред = (max - min) / min * 100
                high = max(price_a, price_b)
                low  = min(price_a, price_b)
                spread_pct = (high - low) / low * 100

                if spread_pct < 0.01:  # Фільтруємо мікро-спреди
                    continue

                ex_high = ex_a if price_a >= price_b else ex_b
                ex_low  = ex_b if price_a >= price_b else ex_a

                spreads.append({
                    "symbol":      symbol,
                    "exchange_a":  ex_high,
                    "price_a":     round(high, 8),
                    "color_a":     EXCHANGE_APIS[ex_high]["color"],
                    "exchange_b":  ex_low,
                    "price_b":     round(low, 8),
                    "color_b":     EXCHANGE_APIS[ex_low]["color"],
                    "spread_pct":  round(spread_pct, 4),
                    "hot":         spread_pct >= 0.5,
                })

    spreads.sort(key=lambda x: x["spread_pct"], reverse=True)

    return jsonify({"data": spreads[:50], "ts": int(time.time() * 1000)})


# ─── /api/funding ─────────────────────────────────────────────────────────────
@app.route("/api/funding")
def api_funding():
    tasks = {
        "binance": ("https://fapi.binance.com/fapi/v1/premiumIndex", None),
        "bybit":   ("https://api.bybit.com/v5/market/tickers?category=linear", None),
        "gate":    ("https://api.gateio.ws/api/v4/futures/usdt/tickers", None),
        "mexc":    ("https://contract.mexc.com/api/v1/contract/ticker", None),
    }
    raw = fetch_all_parallel(tasks)
    result = []

    # Інтервали Gate.io (секунди → години)
    gate_intervals = {}
    gate_contracts = safe_get("https://api.gateio.ws/api/v4/futures/usdt/contracts")
    if gate_contracts and isinstance(gate_contracts, list):
        for gc in gate_contracts:
            name = gc.get("name","").replace("_","")
            secs = int(gc.get("funding_interval", 28800) or 28800)
            gate_intervals[name] = f"{secs//3600}H"

    for d in (raw.get("binance") or []):
        sym = d.get("symbol", "")
        if not sym.endswith("USDT"): continue
        rate = float(d.get("lastFundingRate", 0) or 0) * 100
        result.append({"exchange":"Binance","symbol":sym,"rate":round(rate,4),"annualized":round(rate*3*365,2),"color":"#F0B90B","mark_price":float(d.get("markPrice",0) or 0),"positive":rate>=0,"interval":"8H"})

    for d in (raw.get("bybit") or {}).get("result",{}).get("list",[]):
        sym = d.get("symbol", "")
        if not sym.endswith("USDT"): continue
        rate = float(d.get("fundingRate", 0) or 0) * 100
        result.append({"exchange":"Bybit","symbol":sym,"rate":round(rate,4),"annualized":round(rate*3*365,2),"color":"#F7A600","mark_price":float(d.get("markPrice",0) or 0),"positive":rate>=0,"interval":"8H"})

    for d in (raw.get("gate") or []):
        raw_name = d.get("contract", "")
        if not raw_name.endswith("_USDT"): continue
        sym = raw_name.replace("_", "")
        rate = float(d.get("funding_rate", 0) or 0) * 100
        interval = gate_intervals.get(sym, "8H")
        result.append({"exchange":"Gate.io","symbol":sym,"rate":round(rate,4),"annualized":round(rate*3*365,2),"color":"#EB4D4B","mark_price":float(d.get("mark_price",0) or 0),"positive":rate>=0,"interval":interval})

    mexc_list = (raw.get("mexc") or {}).get("data", [])
    for d in (mexc_list if isinstance(mexc_list, list) else []):
        sym = d.get("symbol", "").replace("_", "")
        if not sym.endswith("USDT"): continue
        rate = float(d.get("fundingRate", 0) or 0) * 100
        result.append({"exchange":"MEXC","symbol":sym,"rate":round(rate,4),"annualized":round(rate*3*365,2),"color":"#00B2FF","mark_price":float(d.get("lastPrice",0) or 0),"positive":rate>=0,"interval":"8H"})

    seen, deduped = set(), []
    for r in result:
        k = (r["exchange"], r["symbol"])
        if k not in seen:
            seen.add(k)
            deduped.append(r)

    deduped.sort(key=lambda x: abs(x["rate"]), reverse=True)
    return jsonify({"data": deduped, "ts": int(time.time() * 1000)})


# ─── /api/market ──────────────────────────────────────────────────────────────
@app.route("/api/market")
def api_market():
    """
    Топ-10 монет для головної сторінки + глобальна статистика.
    Використовує тільки Binance як найнадійніше джерело.
    """
    TOP_SYMBOLS = [
        "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
        "DOGEUSDT","ADAUSDT","AVAXUSDT","SHIBUSDT","DOTUSDT"
    ]
    NAMES = {
        "BTCUSDT":"Bitcoin","ETHUSDT":"Ethereum","SOLUSDT":"Solana",
        "BNBUSDT":"Binance Coin","XRPUSDT":"Ripple","DOGEUSDT":"Dogecoin",
        "ADAUSDT":"Cardano","AVAXUSDT":"Avalanche","SHIBUSDT":"Shiba Inu","DOTUSDT":"Polkadot"
    }

    tasks = {
        "all_tickers":  (EXCHANGE_APIS["binance"]["spot"], None),
        "funding_rates": ("https://fapi.binance.com/fapi/v1/premiumIndex", None),
    }
    raw = fetch_all_parallel(tasks)

    all_tickers = raw.get("all_tickers") or []
    funding_map = {}
    for f in (raw.get("funding_rates") or []):
        funding_map[f.get("symbol", "")] = float(f.get("lastFundingRate", 0) or 0) * 100

    ticker_map = {d.get("symbol"): d for d in all_tickers}

    tokens = []
    for sym in TOP_SYMBOLS:
        d = ticker_map.get(sym)
        if not d:
            continue
        price  = float(d.get("lastPrice", 0))
        change = float(str(d.get("priceChangePercent", 0) or 0).replace("%", ""))
        vol    = float(d.get("quoteVolume", 0))
        tokens.append({
            "symbol":    sym.replace("USDT", ""),
            "full":      sym,
            "name":      NAMES.get(sym, sym),
            "price":     price,
            "change24h": round(change, 2),
            "volume":    vol,
            "funding":   round(funding_map.get(sym, 0), 4),
            "up":        change >= 0,
        })

    # Глобальна статистика (проста агрегація)
    total_vol = sum(float(d.get("quoteVolume", 0)) for d in all_tickers)

    return jsonify({
        "tokens":    tokens,
        "global":    {"total_volume_usdt": total_vol},
        "ts":        int(time.time() * 1000),
    })


# ─── /api/rates ───────────────────────────────────────────────────────────────
@app.route("/api/rates")
def api_rates():
    """
    Курси для конвертера: топ криптовалюти + 20 фіатних валют.
    """
    crypto_symbols = [
        "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
        "DOGEUSDT","ADAUSDT","AVAXUSDT","DOTUSDT","LINKUSDT",
        "UNIUSDT","ATOMUSDT","LTCUSDT","BCHUSDT","NEARUSDT",
        "APTUSDT","OPUSDT","ARBUSDT","INJUSDT","SUIUSDT",
        "TRXUSDT","TONUSDT","SHIBUSDT","MATICUSDT","FTMUSDT",
    ]
    tasks = {sym: (EXCHANGE_APIS["binance"]["spot"], {"symbol": sym}) for sym in crypto_symbols}
    tasks["fiat"] = ("https://open.er-api.com/v6/latest/USD", None)

    raw = fetch_all_parallel(tasks)

    # Криптовалюти (ціна в USD)
    rates = {"USDT": 1.0, "USD": 1.0}
    for sym in crypto_symbols:
        data = raw.get(sym)
        if data and isinstance(data, dict):
            key = sym.replace("USDT", "")
            val = float(data.get("lastPrice", 0) or 0)
            if val > 0:
                rates[key] = val

    # Фіат — зберігаємо як кількість одиниць за 1 USD
    FIAT_KEYS = [
        "EUR","UAH","GBP","JPY","CHF","CAD","AUD","SGD",
        "HKD","KRW","BRL","MXN","PLN","CZK","SEK","NOK",
        "DKK","TRY","INR","CNY",
    ]
    fiat_data  = raw.get("fiat") or {}
    fiat_rates = fiat_data.get("rates", {})
    if fiat_rates:
        for key in FIAT_KEYS:
            if key in fiat_rates:
                rates[key] = round(float(fiat_rates[key]), 6)

    # Метадані для фронтенду
    FIAT_NAMES = {
        "USD":"US Dollar","EUR":"Euro","UAH":"Ukrainian Hryvnia",
        "GBP":"British Pound","JPY":"Japanese Yen","CHF":"Swiss Franc",
        "CAD":"Canadian Dollar","AUD":"Australian Dollar","SGD":"Singapore Dollar",
        "HKD":"Hong Kong Dollar","KRW":"South Korean Won","BRL":"Brazilian Real",
        "MXN":"Mexican Peso","PLN":"Polish Zloty","CZK":"Czech Koruna",
        "SEK":"Swedish Krona","NOK":"Norwegian Krone","DKK":"Danish Krone",
        "TRY":"Turkish Lira","INR":"Indian Rupee","CNY":"Chinese Yuan",
    }
    FIAT_SYMBOLS = {
        "USD":"$","EUR":"€","UAH":"₴","GBP":"£","JPY":"¥","CHF":"Fr",
        "CAD":"C$","AUD":"A$","SGD":"S$","HKD":"HK$","KRW":"₩",
        "BRL":"R$","MXN":"MX$","PLN":"zł","CZK":"Kč","SEK":"kr",
        "NOK":"kr","DKK":"kr","TRY":"₺","INR":"₹","CNY":"¥",
    }

    fiat_list = [
        {"code": k, "name": FIAT_NAMES.get(k, k), "symbol": FIAT_SYMBOLS.get(k, k)}
        for k in FIAT_KEYS if k in rates
    ]

    return jsonify({
        "rates":      rates,
        "fiat_list":  fiat_list,
        "base":       "USD",
        "ts":         int(time.time() * 1000),
    })




# ─── /api/health ──────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "ts": int(time.time() * 1000)})


# ─── /api/symbols ─────────────────────────────────────────────────────────────
_symbols_cache = {"data": [], "ts": 0}

@app.route("/api/symbols")
def api_symbols():
    now = time.time()
    if now - _symbols_cache["ts"] < 3600 and _symbols_cache["data"]:
        return jsonify({"data": _symbols_cache["data"], "cached": True})

    data = safe_get("https://api.binance.com/api/v3/ticker/24hr")
    if not data:
        return jsonify({"data": _symbols_cache["data"], "cached": True})

    TOKEN_NAMES = {
        "BTC":"Bitcoin","ETH":"Ethereum","SOL":"Solana","BNB":"Binance Coin",
        "XRP":"Ripple","DOGE":"Dogecoin","ADA":"Cardano","AVAX":"Avalanche",
        "SHIB":"Shiba Inu","DOT":"Polkadot","LINK":"Chainlink","MATIC":"Polygon",
        "UNI":"Uniswap","ATOM":"Cosmos","LTC":"Litecoin","BCH":"Bitcoin Cash",
        "NEAR":"NEAR Protocol","APT":"Aptos","OP":"Optimism","ARB":"Arbitrum",
        "PEPE":"Pepe","WIF":"dogwifhat","FLOKI":"Floki","TRX":"TRON",
        "TON":"Toncoin","SUI":"Sui","FIL":"Filecoin","ICP":"Internet Computer",
        "ALGO":"Algorand","MANA":"Decentraland","STORJ":"Storj","SAND":"The Sandbox",
        "AAVE":"Aave","CRV":"Curve","ENJ":"Enjin","CHZ":"Chiliz",
        "VET":"VeChain","THETA":"Theta","FTM":"Fantom","AXS":"Axie Infinity",
        "GALA":"Gala","IMX":"Immutable X","LDO":"Lido DAO","INJ":"Injective",
        "SEI":"Sei","TIA":"Celestia","RUNE":"THORChain","STX":"Stacks",
    }

    symbols = []
    for d in data:
        sym = d.get("symbol", "")
        if not sym.endswith("USDT") or "_" in sym:
            continue
        base   = sym.replace("USDT", "")
        price  = float(d.get("lastPrice", 0) or 0)
        change = float(str(d.get("priceChangePercent", 0) or 0).replace("%",""))
        vol    = float(d.get("quoteVolume", 0) or 0)
        symbols.append({
            "symbol": sym,
            "base":   base,
            "name":   TOKEN_NAMES.get(base, ""),
            "price":  price,
            "change": round(change, 2),
            "vol":    vol,
            "up":     change >= 0,
        })

    symbols.sort(key=lambda x: x["vol"], reverse=True)
    _symbols_cache["data"] = symbols
    _symbols_cache["ts"]   = now
    return jsonify({"data": symbols, "cached": False, "ts": int(now * 1000)})



# ─── /api/ticker ──────────────────────────────────────────────────────────────
@app.route("/api/ticker")
def api_ticker():
    """
    Дані для бігаючої стрічки на головній:
    - Ціни топ-токенів з 8H зміною (через klines)
    - Топ-5 спредів
    - Топ-5 екстремальних funding rates
    """
    TOP_TOKENS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT"]

    # 8H klines + funding + spreads паралельно
    tasks = {}
    for sym in TOP_TOKENS:
        tasks[f"kline_{sym}"] = (
            f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=8h&limit=2", None
        )
    tasks["funding"] = ("https://fapi.binance.com/fapi/v1/premiumIndex", None)
    tasks["tickers_binance"] = (EXCHANGE_APIS["binance"]["spot"], None)
    tasks["tickers_bybit"]   = ("https://api.bybit.com/v5/market/tickers?category=spot", None)
    tasks["tickers_mexc"]    = (EXCHANGE_APIS["mexc"]["spot"], None)
    tasks["tickers_gate"]    = (EXCHANGE_APIS["gate"]["spot"], None)

    raw = fetch_all_parallel(tasks)

    # ── Токени з 8H зміною ─────────────────────────────────────────────────────
    TOKEN_LABELS = {
        "BTCUSDT":"BTC","ETHUSDT":"ETH","SOLUSDT":"SOL",
        "BNBUSDT":"BNB","XRPUSDT":"XRP","DOGEUSDT":"DOGE",
        "ADAUSDT":"ADA","AVAXUSDT":"AVAX",
    }
    tokens = []
    for sym in TOP_TOKENS:
        klines = raw.get(f"kline_{sym}")
        if not klines or len(klines) < 1:
            continue
        # Остання свічка: [openTime, open, high, low, close, ...]
        last  = klines[-1]
        open_ = float(last[1])
        close = float(last[4])
        change_8h = ((close - open_) / open_ * 100) if open_ > 0 else 0
        tokens.append({
            "symbol":    sym,
            "label":     TOKEN_LABELS.get(sym, sym.replace("USDT","")),
            "price":     close,
            "change_8h": round(change_8h, 2),
            "up":        change_8h >= 0,
        })

    # ── Спреди ─────────────────────────────────────────────────────────────────
    ex_data = {}
    parse_map = {
        "tickers_binance": ("binance", parse_binance_spot),
        "tickers_bybit":   ("bybit",   parse_bybit_spot),
        "tickers_mexc":    ("mexc",    parse_mexc_spot),
        "tickers_gate":    ("gate",    parse_gate_spot),
    }
    for key, (ex_name, parser) in parse_map.items():
        items = parser(raw.get(key))
        ex_data[ex_name] = {item["symbol"]: item for item in items}

    SPREAD_SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
                      "ADAUSDT","LINKUSDT","AVAXUSDT","DOGEUSDT","DOTUSDT",
                      "ALGOUSDT","MANAUSDT","STORJUSDT","BNBUSDT"]
    spreads = []
    ex_list = list(ex_data.items())
    for symbol in SPREAD_SYMBOLS:
        for i in range(len(ex_list)):
            for j in range(i+1, len(ex_list)):
                ex_a, map_a = ex_list[i]
                ex_b, map_b = ex_list[j]
                if symbol not in map_a or symbol not in map_b:
                    continue
                pa = map_a[symbol]["price"]
                pb = map_b[symbol]["price"]
                if pa <= 0 or pb <= 0:
                    continue
                sp = abs(pa - pb) / min(pa, pb) * 100
                if sp < 0.05:
                    continue
                spreads.append({
                    "symbol": symbol.replace("USDT",""),
                    "spread": round(sp, 3),
                    "ex_a":   ex_a,
                    "ex_b":   ex_b,
                })

    spreads.sort(key=lambda x: x["spread"], reverse=True)
    top_spreads = spreads[:5]

    # ── Funding extremes ───────────────────────────────────────────────────────
    funding_raw = raw.get("funding") or []
    funding_items = []
    for d in funding_raw:
        sym = d.get("symbol","")
        if not sym.endswith("USDT"):
            continue
        rate = float(d.get("lastFundingRate", 0) or 0) * 100
        if abs(rate) < 0.02:
            continue
        funding_items.append({
            "symbol":   sym.replace("USDT",""),
            "rate":     round(rate, 4),
            "positive": rate >= 0,
        })
    funding_items.sort(key=lambda x: abs(x["rate"]), reverse=True)
    top_funding = funding_items[:5]

    return jsonify({
        "tokens":   tokens,
        "spreads":  top_spreads,
        "funding":  top_funding,
        "ts":       int(time.time() * 1000),
    })


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🚀 CYPHER_TERMINAL backend running at http://localhost:8888")
    app.run(debug=True, host="0.0.0.0", port=8888)
