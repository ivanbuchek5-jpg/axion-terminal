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

# ── Performance: gzip + cache headers (no extra dependencies) ────────────────
import gzip as _gzip
CACHE_GEN = "8"  # bump to force every browser to drop its cached copy once

@app.after_request
def _optimize(resp):
    try:
        p = request.path
        if resp.status_code == 200 and not p.startswith("/api/"):
            if request.args.get("v"):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif p.endswith((".png", ".ico", ".jpg", ".svg")):
                resp.headers["Cache-Control"] = "no-cache"  # revalidate (ETag/304): a replaced logo shows up immediately
            else:
                resp.headers["Cache-Control"] = "no-cache"  # html/js/css without ?v= → always revalidate (ETag/304)
            if (resp.mimetype == "text/html" and request.cookies.get("axion_cv") != CACHE_GEN):
                # one-time purge of stale cached copies in the visitor's browser after a release
                resp.headers["Clear-Site-Data"] = '"cache"'
                resp.set_cookie("axion_cv", CACHE_GEN, max_age=31536000, samesite="Lax")
        ctype = resp.headers.get("Content-Type", "")
        if (resp.status_code == 200
                and "gzip" in request.headers.get("Accept-Encoding", "")
                and "Content-Encoding" not in resp.headers
                and any(t in ctype for t in ("text/", "javascript", "json"))):
            resp.direct_passthrough = False
            data = resp.get_data()
            if len(data) > 600:
                resp.set_data(_gzip.compress(data, 5))
                resp.headers["Content-Encoding"] = "gzip"
                resp.headers["Vary"] = "Accept-Encoding"
                resp.headers["Content-Length"] = str(len(resp.get_data()))
    except Exception:
        pass
    return resp

# ─── Timeout для зовнішніх запитів ────────────────────────────────────────────
TIMEOUT = 5

# ─── Публічні API ендпоінти бірж ──────────────────────────────────────────────
EXCHANGE_APIS = {
    "binance": {
        # data-api.binance.vision — публічне дзеркало ринкових даних, не блокується на cloud (api.binance.com дає 451)
        "spot":    ["https://data-api.binance.vision/api/v3/ticker/24hr", "https://api.binance.com/api/v3/ticker/24hr"],
        "funding": ["https://fapi.binance.com/fapi/v1/premiumIndex"],
        "color":   "#F0B90B",
    },
    "aster": {
        "spot":    ["https://sapi.asterdex.com/api/v3/ticker/24hr"],
        "funding": ["https://fapi.asterdex.com/fapi/v1/premiumIndex"],
        "color":   "#E6A23C",
    },
    "okx": {
        "spot":    ["https://www.okx.com/api/v5/market/tickers?instType=SPOT"],
        "color":   "#B8BCC4",
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
        "funding": "https://open-api.bingx.com/openApi/swap/v2/quote/premiumIndex",
        "color":   "#6C5CE7",
    },
}

# ─── Хелпери ──────────────────────────────────────────────────────────────────

def safe_get(url, params=None):
    """Безпечний GET запит з таймаутом. `url` може бути списком дзеркал — пробуємо по черзі."""
    urls = list(url) if isinstance(url, (list, tuple)) else [url]
    for u in urls:
        try:
            r = requests.get(u, params=params, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0 AxionTerminal"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"[ERR] {u}: {e}")
    return None


def _ts():
    return int(time.time() * 1000)


def fetch_all_parallel(tasks: dict) -> dict:
    """
    Виконує кілька HTTP запитів паралельно.
    tasks = {"key": (url, params), ...}
    Повертає {"key": parsed_json, ...}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
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


def parse_okx_spot(data, symbol=None):
    """OKX v5 tickers: {"data":[{instId:"BTC-USDT", last, open24h, volCcy24h, bidPx, askPx, high24h, low24h}]}"""
    if not data or not isinstance(data, dict):
        return []
    out = []
    for d in (data.get("data") or []):
        inst = d.get("instId", "")
        if not inst.endswith("-USDT"):
            continue
        s = inst.replace("-", "")
        if symbol and s != symbol:
            continue
        try:
            last = float(d.get("last") or 0)
            op = float(d.get("open24h") or 0)
            out.append({
                "symbol":    s,
                "price":     last,
                "change24h": ((last - op) / op * 100) if op > 0 else 0.0,
                "volume":    float(d.get("volCcy24h") or 0),
                "bid":       float(d.get("bidPx") or 0),
                "ask":       float(d.get("askPx") or 0),
                "high24h":   float(d.get("high24h") or 0),
                "low24h":    float(d.get("low24h") or 0),
            })
        except (TypeError, ValueError):
            continue
    return out


def okx_inst(symbol):
    """BTCUSDT → BTC-USDT"""
    return symbol[:-4] + "-USDT" if symbol.endswith("USDT") else symbol


def bingx_params():
    return {"timestamp": _ts()}


PARSERS = {
    "aster":   parse_binance_spot,   # Aster API сумісне з Binance
    "okx":     parse_okx_spot,
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
        "aster":   (EXCHANGE_APIS["aster"]["spot"], {"symbol": symbol}),
        # bybit: blocked on cloud
        "mexc":    (EXCHANGE_APIS["mexc"]["spot"], {"symbol": symbol}),
        "gate":    (EXCHANGE_APIS["gate"]["spot"], None),
        "bingx":  (EXCHANGE_APIS["bingx"]["spot"], {"symbol": f"{symbol[:-4]}-USDT", "timestamp": _ts()}),
        "okx":     (["https://www.okx.com/api/v5/market/ticker"], {"instId": okx_inst(symbol)}),
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
        # bybit blocked on cloud: ("https://api.bybit.com/v5/market/tickers?category=spot", None),
        "aster":   (EXCHANGE_APIS["aster"]["spot"], None),
        "bingx":   (EXCHANGE_APIS["bingx"]["spot"], bingx_params()),
        "okx":     (EXCHANGE_APIS["okx"]["spot"], None),
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
        # bybit blocked on cloud
        "gate":    ("https://api.gateio.ws/api/v4/futures/usdt/tickers", None),
        "mexc":    ("https://contract.mexc.com/api/v1/contract/ticker", None),
        "binance": (EXCHANGE_APIS["binance"]["funding"], None),
        "binance_i": (["https://fapi.binance.com/fapi/v1/fundingInfo"], None),
        "aster":   (EXCHANGE_APIS["aster"]["funding"], None),
        "aster_i": (["https://fapi.asterdex.com/fapi/v1/fundingInfo"], None),
        "bingx":   (EXCHANGE_APIS["bingx"]["funding"], bingx_params()),
        "okx":     (["https://www.okx.com/api/v5/public/funding-rate"], {"instId": "ANY"}),
        "okx_mark": (["https://www.okx.com/api/v5/public/mark-price"], {"instType": "SWAP"}),
    }
    raw = fetch_all_parallel(tasks)
    result = []

    def add_row(name, sym, rate, color, mark, hours):
        hours = hours if hours and hours > 0 else 8
        result.append({"exchange": name, "symbol": sym, "rate": round(rate, 4),
                       "annualized": round(rate * (24 / hours) * 365, 2), "color": color,
                       "mark_price": mark, "positive": rate >= 0, "interval": f"{int(hours)}H"})

    # Binance-сумісні (Binance, Aster): premiumIndex + fundingInfo (інтервали)
    for key, label in (("binance", "Binance"), ("aster", "Aster")):
        info = {}
        for it in (raw.get(key + "_i") or []):
            try: info[it.get("symbol")] = float(it.get("fundingIntervalHours") or 8)
            except (TypeError, ValueError): pass
        for d in (raw.get(key) if isinstance(raw.get(key), list) else []):
            sym = d.get("symbol", "")
            if not sym.endswith("USDT"): continue
            try:
                add_row(label, sym, float(d.get("lastFundingRate") or 0) * 100, EXCHANGE_APIS[key]["color"],
                        float(d.get("markPrice") or 0), info.get(sym, 8))
            except (TypeError, ValueError):
                continue

    # BingX swap premiumIndex
    bx = raw.get("bingx") or {}
    bx = bx.get("data") if isinstance(bx, dict) else None
    for d in (bx if isinstance(bx, list) else ([bx] if isinstance(bx, dict) else [])):
        sym = str(d.get("symbol", "")).replace("-", "")
        if not sym.endswith("USDT"): continue
        try:
            add_row("BingX", sym, float(d.get("lastFundingRate") or 0) * 100, EXCHANGE_APIS["bingx"]["color"],
                    float(d.get("markPrice") or 0), 8)
        except (TypeError, ValueError):
            continue

    # OKX swaps
    okx_mark = {}
    for d in ((raw.get("okx_mark") or {}).get("data") or []):
        try: okx_mark[d.get("instId")] = float(d.get("markPx") or 0)
        except (TypeError, ValueError): pass
    for d in ((raw.get("okx") or {}).get("data") or []):
        inst = d.get("instId", "")
        if not inst.endswith("-USDT-SWAP"): continue
        try:
            hrs = (int(d.get("nextFundingTime")) - int(d.get("fundingTime"))) / 3600000.0
            add_row("OKX", inst.replace("-SWAP", "").replace("-", ""), float(d.get("fundingRate") or 0) * 100,
                    EXCHANGE_APIS["okx"]["color"], okx_mark.get(inst, 0), round(hrs) or 8)
        except (TypeError, ValueError):
            continue

    # Інтервали Gate.io (секунди → години)
    gate_intervals = {}
    gate_contracts = safe_get("https://api.gateio.ws/api/v4/futures/usdt/contracts")
    if gate_contracts and isinstance(gate_contracts, list):
        for gc in gate_contracts:
            name = gc.get("name","").replace("_","")
            secs = int(gc.get("funding_interval", 28800) or 28800)
            gate_intervals[name] = f"{secs//3600}H"

    # Bybit blocked on Railway cloud servers

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
        "mexc_spot":  (EXCHANGE_APIS["mexc"]["spot"], None),
        "gate_spot":  (EXCHANGE_APIS["gate"]["spot"], None),
        "mexc_fund":  ("https://contract.mexc.com/api/v1/contract/ticker", None),
    }
    raw = fetch_all_parallel(tasks)

    # MEXC spot — основне джерело
    mexc_items = parse_mexc_spot(raw.get("mexc_spot"))
    mexc_map   = {d["symbol"]: d for d in mexc_items}

    # Gate.io — запасне
    gate_items = parse_gate_spot(raw.get("gate_spot"))
    gate_map   = {d["symbol"]: d for d in gate_items}

    # Funding з MEXC futures
    funding_map = {}
    mexc_fund_raw = (raw.get("mexc_fund") or {}).get("data", [])
    for d in (mexc_fund_raw if isinstance(mexc_fund_raw, list) else []):
        sym  = d.get("symbol", "").replace("_", "")
        rate = float(d.get("fundingRate", 0) or 0) * 100
        if rate != 0:
            funding_map[sym] = round(rate, 4)

    tokens = []
    for sym in TOP_SYMBOLS:
        d = mexc_map.get(sym) or gate_map.get(sym)
        if not d or d["price"] == 0:
            continue
        tokens.append({
            "symbol":    sym.replace("USDT", ""),
            "full":      sym,
            "name":      NAMES.get(sym, sym),
            "price":     d["price"],
            "change24h": round(d["change24h"], 2),
            "volume":    d["volume"],
            "funding":   funding_map.get(sym, 0),
            "up":        d["change24h"] >= 0,
        })

    total_vol = sum(d["volume"] for d in mexc_items)

    return jsonify({
        "tokens":    tokens,
        "global":    {"total_volume_usdt": total_vol},
        "ts":        int(time.time() * 1000),
    })


# ─── /api/logos → {symbol: coinmarketcap_id} (logo = s2.coinmarketcap.com/static/img/coins/64x64/<id>.png) ──
_LOGO_CACHE = {"t": 0, "map": {}}

@app.route("/api/logos")
def api_logos():
    now = time.time()
    if _LOGO_CACHE["map"] and now - _LOGO_CACHE["t"] < 6 * 3600:
        resp = jsonify({"map": _LOGO_CACHE["map"]})
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
    best = {}  # symbol -> (rank, id)
    key = os.environ.get("CMC_API_KEY")
    rows = []
    if key:
        try:
            r = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/map",
                             params={"listing_status": "active", "limit": 5000, "sort": "cmc_rank"},
                             headers={"X-CMC_PRO_API_KEY": key, "Accept": "application/json"}, timeout=10)
            rows = [(d.get("symbol"), d.get("id"), d.get("rank") or 10**9) for d in r.json().get("data", [])]
        except Exception as e:
            print("[ERR] cmc pro map:", e)
    if not rows:
        d = safe_get("https://api.coinmarketcap.com/data-api/v3/map/all",
                     {"listing_status": "active", "start": 1, "limit": 5000})
        try:
            data = (d or {}).get("data", {}).get("cryptoCurrencyMap", [])
            rows = [(x.get("symbol"), x.get("id"), x.get("rank") or 10**9) for x in data]
        except Exception:
            rows = []
    for sym, cid, rank in rows:
        if sym and cid and (sym.upper() not in best or rank < best[sym.upper()][0]):
            best[sym.upper()] = (rank, cid)
    m = {s: v[1] for s, v in best.items()}
    if m:
        _LOGO_CACHE.update(t=now, map=m)
    elif _LOGO_CACHE["map"]:
        m = _LOGO_CACHE["map"]
    resp = jsonify({"map": m})
    resp.headers["Cache-Control"] = "public, max-age=3600" if m else "no-store"
    return resp


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
    tasks = {sym: (f"{EXCHANGE_APIS['mexc']['spot']}?symbol={sym}", None) for sym in crypto_symbols}
    tasks["fiat"] = ("https://open.er-api.com/v6/latest/USD", None)

    raw = fetch_all_parallel(tasks)

    # Криптовалюти (ціна в USD)
    rates = {"USDT": 1.0, "USD": 1.0}
    for sym in crypto_symbols:
        data = raw.get(sym)
        if data:
            key = sym.replace("USDT", "")
            items = data if isinstance(data, list) else []
            if items:
                val = float(items[0].get("lastPrice",0) or 0)
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

    data = safe_get(EXCHANGE_APIS["mexc"]["spot"]) or []
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
            f"https://api.mexc.com/api/v3/klines?symbol={sym}&interval=8h&limit=2", None
        )
    tasks["funding"] = ("https://contract.mexc.com/api/v1/contract/ticker", None)
    tasks["tickers_mexc"] = (EXCHANGE_APIS["mexc"]["spot"], None)
    # tasks["tickers_bybit"] blocked on cloud
    tasks["tickers_mexc"]    = (EXCHANGE_APIS["mexc"]["spot"], None)
    tasks["tickers_gate"]    = (EXCHANGE_APIS["gate"]["spot"], None)
    tasks["tickers_binance"] = (EXCHANGE_APIS["binance"]["spot"], None)
    tasks["tickers_aster"]   = (EXCHANGE_APIS["aster"]["spot"], None)
    tasks["tickers_bingx"]   = (EXCHANGE_APIS["bingx"]["spot"], bingx_params())
    tasks["tickers_okx"]     = (EXCHANGE_APIS["okx"]["spot"], None)

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
        # MEXC kline format same as Binance: [[time,open,high,low,close,vol,...]]
        kline_list = klines if isinstance(klines, list) else []
        if not kline_list: continue
        try:
            last  = kline_list[-1]  # newest last
            open_ = float(last[1])
            close = float(last[4])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
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
        "tickers_mexc":      ("mexc",    parse_mexc_spot),
        "tickers_bybit":   ("bybit",   parse_bybit_spot),
        "tickers_mexc":    ("mexc",    parse_mexc_spot),
        "tickers_gate":    ("gate",    parse_gate_spot),
        "tickers_binance": ("binance", parse_binance_spot),
        "tickers_aster":   ("aster",   parse_binance_spot),
        "tickers_bingx":   ("bingx",   parse_bingx_spot),
        "tickers_okx":     ("okx",     parse_okx_spot),
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
    fund_raw_data = (raw.get("funding") or {}).get("data", [])
    funding_items = []
    for d in (fund_raw_data if isinstance(fund_raw_data, list) else []):
        sym = d.get("symbol","").replace("_","")
        if not sym.endswith("USDT"):
            continue
        rate = float(d.get("fundingRate", 0) or 0) * 100
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
