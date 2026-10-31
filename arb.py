"""Arbitrage scanner + live pair data for AXION TERMINAL.

/api/arb   – list of long/short bundles (futures-futures or spot-futures), ranked by funding or spread
/api/pair  – live order books, funding, 24h volume for one bundle (polled ~1/s by pair.html)
Public exchange endpoints only. Registered from app.py via init().
"""
import time
import threading
from datetime import datetime, timezone
from flask import jsonify, request

EXCH = ["binance", "aster", "okx", "bingx", "mexc", "gate"]
# taker fees, % per side (approximate public tiers: shown as an estimate in the UI)
FEES = {
    "binance": {"fut": 0.05, "spot": 0.10},
    "aster":   {"fut": 0.035, "spot": 0.10},
    "okx":     {"fut": 0.05, "spot": 0.10},
    "bingx":   {"fut": 0.05, "spot": 0.10},
    "mexc":    {"fut": 0.02, "spot": 0.05},
    "gate":    {"fut": 0.05, "spot": 0.20},
}
MAX_ABS_SPREAD = 50.0  # %: bigger "spreads" are almost always two different coins sharing a ticker

_S = {}  # injected helpers
_cache = {}
_lock = threading.Lock()


def init(app, safe_get, fetch_all_parallel, apis, bingx_params, parsers):
    _S.update(get=safe_get, many=fetch_all_parallel, apis=apis, bx=bingx_params, parsers=parsers)
    app.add_url_rule("/api/arb", "api_arb", api_arb)
    app.add_url_rule("/api/pair", "api_pair", api_pair)


def _f(x, d=0.0):
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def _cached(key, ttl, fn):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    val = fn()
    if val:
        with _lock:
            _cache[key] = (now, val)
        return val
    return hit[1] if hit else val  # stale beats empty


def _next_aligned(hours):
    h = max(1, int(hours or 8))
    now = datetime.now(timezone.utc)
    ms = int(now.timestamp() * 1000)
    step = h * 3600000
    return (ms // step + 1) * step


# ── futures snapshot: {ex: {BASE: {price, bid, ask, rate, hours, next}}}  (rate = % per interval) ──────────────────
def _futures():
    A = _S["apis"]
    tasks = {
        "binance": (A["binance"]["funding"], None),
        "binance_i": (["https://fapi.binance.com/fapi/v1/fundingInfo"], None),
        "aster": (A["aster"]["funding"], None),
        "aster_i": (["https://fapi.asterdex.com/fapi/v1/fundingInfo"], None),
        "okx": (["https://www.okx.com/api/v5/public/funding-rate"], {"instId": "ANY"}),
        "okx_mark": (["https://www.okx.com/api/v5/public/mark-price"], {"instType": "SWAP"}),
        "bingx": (A["bingx"]["funding"], _S["bx"]()),
        "gate": ("https://api.gateio.ws/api/v4/futures/usdt/tickers", None),
        "gate_c": ("https://api.gateio.ws/api/v4/futures/usdt/contracts", None),
        "mexc": ("https://contract.mexc.com/api/v1/contract/ticker", None),
    }
    raw = _S["many"](tasks)
    out = {e: {} for e in EXCH}

    def put(ex, base, price, rate, hours, nxt, bid=0.0, ask=0.0):
        if price > 0 and base:
            out[ex][base] = {"price": price, "bid": bid, "ask": ask, "rate": rate,
                             "hours": hours or 8, "next": nxt or _next_aligned(hours or 8)}

    for ex in ("binance", "aster"):
        info = {}
        for it in (raw.get(ex + "_i") or []):
            info[it.get("symbol")] = _f(it.get("fundingIntervalHours"), 8)
        data = raw.get(ex)
        for d in (data if isinstance(data, list) else []):
            s = d.get("symbol", "")
            if s.endswith("USDT"):
                put(ex, s[:-4], _f(d.get("markPrice")), _f(d.get("lastFundingRate")) * 100,
                    info.get(s, 8), int(_f(d.get("nextFundingTime"))) or None)

    mk = {d.get("instId"): _f(d.get("markPx")) for d in ((raw.get("okx_mark") or {}).get("data") or [])}
    for d in ((raw.get("okx") or {}).get("data") or []):
        inst = d.get("instId", "")
        if inst.endswith("-USDT-SWAP"):
            try:
                hrs = round((int(d["nextFundingTime"]) - int(d["fundingTime"])) / 3600000.0) or 8
            except (KeyError, TypeError, ValueError):
                hrs = 8
            put("okx", inst[:-10], mk.get(inst, 0), _f(d.get("fundingRate")) * 100, hrs,
                int(_f(d.get("nextFundingTime"))) or None)

    bx = raw.get("bingx") or {}
    bx = bx.get("data") if isinstance(bx, dict) else None
    for d in (bx if isinstance(bx, list) else ([bx] if isinstance(bx, dict) else [])):
        s = str(d.get("symbol", "")).replace("-", "")
        if s.endswith("USDT"):
            put("bingx", s[:-4], _f(d.get("markPrice")), _f(d.get("lastFundingRate")) * 100, 8,
                int(_f(d.get("nextFundingTime"))) or None)

    gi = {}
    for c in (raw.get("gate_c") if isinstance(raw.get("gate_c"), list) else []):
        gi[c.get("name")] = max(1, int(_f(c.get("funding_interval"), 28800) // 3600))
    for d in (raw.get("gate") if isinstance(raw.get("gate"), list) else []):
        n = d.get("contract", "")
        if n.endswith("_USDT"):
            put("gate", n[:-5], _f(d.get("mark_price")) or _f(d.get("last")), _f(d.get("funding_rate")) * 100,
                gi.get(n, 8), int(_f(d.get("funding_next_apply")) * 1000) or None,
                _f(d.get("highest_bid")), _f(d.get("lowest_ask")))

    mx = (raw.get("mexc") or {}).get("data", [])
    for d in (mx if isinstance(mx, list) else []):
        s = d.get("symbol", "")
        if s.endswith("_USDT"):
            put("mexc", s[:-5], _f(d.get("lastPrice")), _f(d.get("fundingRate")) * 100, 8, None,
                _f(d.get("bid1")), _f(d.get("ask1")))
    return out


# ── spot snapshot: {ex: {BASE: {price, bid, ask, vol}}} ─────────────────────────────────────────────────────────
def _spot():
    PARSERS = _S["parsers"]
    A = _S["apis"]
    tasks = {
        "binance": (A["binance"]["spot"], None),
        "aster": (A["aster"]["spot"], None),
        "okx": (A["okx"]["spot"], None),
        "bingx": (A["bingx"]["spot"], _S["bx"]()),
        "mexc": (A["mexc"]["spot"], None),
        "gate": (A["gate"]["spot"], None),
    }
    raw = _S["many"](tasks)
    out = {}
    for ex in EXCH:
        m = {}
        for it in PARSERS[ex](raw.get(ex)):
            s = it["symbol"]
            if s.endswith("USDT") and it["price"] > 0:
                m[s[:-4]] = {"price": it["price"], "bid": it.get("bid", 0), "ask": it.get("ask", 0), "vol": it.get("volume", 0)}
        out[ex] = m
    return out


def _leg_out(ex, typ, d):
    o = {"ex": ex, "type": typ, "price": d["price"]}
    if typ == "fut":
        o.update(rate=round(d["rate"], 5), hours=d["hours"], next=d["next"])
    return o


MODES = {"ff_funding", "ff_spread", "sf_funding", "sf_spread", "sf_spread_neg"}


def api_arb():
    mode = request.args.get("mode", "ff_funding")
    if mode not in MODES:
        mode = "ff_funding"
    exs = [e for e in (request.args.get("ex") or "").split(",") if e in EXCH] or EXCH
    mins = _f(request.args.get("mins"), -1e9)
    minf = _f(request.args.get("minf"), -1e9)
    q = (request.args.get("q") or "").upper().replace("/", "").replace("USDT", "")
    limit = max(10, min(500, int(_f(request.args.get("limit"), 150))))

    fut = _cached("fut", 4, _futures) or {}
    spot = _cached("spot", 6, _spot) if mode.startswith("sf") else {}
    rows = []
    bases = set()
    for e in exs:
        bases.update(fut.get(e, {}).keys())
    if q:
        bases = {b for b in bases if q in b}

    def per8(d):
        return d["rate"] / d["hours"] * 8.0

    for b in bases:
        if mode.startswith("ff"):
            legs = [(e, fut[e][b]) for e in exs if b in fut.get(e, {})]
            for le, ld in legs:
                for se, sd in legs:
                    if le == se:
                        continue
                    spread = (sd["price"] - ld["price"]) / ld["price"] * 100
                    if abs(spread) > MAX_ABS_SPREAD:
                        continue
                    fnet = per8(sd) - per8(ld)
                    if mode == "ff_funding" and fnet <= 0:
                        continue
                    if mode == "ff_spread" and spread <= 0:
                        continue
                    rows.append((b, _leg_out(le, "fut", ld), _leg_out(se, "fut", sd), spread, fnet))
        else:
            sps = [(e, spot[e][b]) for e in exs if b in spot.get(e, {})]
            futs = [(e, fut[e][b]) for e in exs if b in fut.get(e, {})]
            for xe, xd in sps:
                for ye, yd in futs:
                    spread = (yd["price"] - xd["price"]) / xd["price"] * 100
                    if abs(spread) > MAX_ABS_SPREAD:
                        continue
                    fnet = per8(yd)
                    if mode == "sf_funding" and fnet <= 0:
                        continue
                    if mode == "sf_spread" and spread <= 0:
                        continue
                    if mode == "sf_spread_neg" and spread >= 0:
                        continue
                    rows.append((b, _leg_out(xe, "spot", xd), _leg_out(ye, "fut", yd), spread, fnet))

    rows = [r for r in rows if r[3] >= mins and r[4] >= minf]
    if mode.endswith("funding"):
        rows.sort(key=lambda r: r[4], reverse=True)
    elif mode.endswith("neg"):
        rows.sort(key=lambda r: r[3])
    else:
        rows.sort(key=lambda r: r[3], reverse=True)
    data = [{"symbol": b, "long": l, "short": s, "spread": round(sp, 4), "fund": round(fn, 4)}
            for b, l, s, sp, fn in rows[:limit]]
    return jsonify({"data": data, "total": len(rows), "mode": mode, "ts": int(time.time() * 1000)})


# ── order books ─────────────────────────────────────────────────────────────────────────────────────────────────
def _ct_sizes(ex):
    """contract size in coins for okx / mexc / gate swaps: {BASE: size}"""
    def load():
        m = {}
        if ex == "okx":
            d = _S["get"](["https://www.okx.com/api/v5/public/instruments"], {"instType": "SWAP"})
            for i in ((d or {}).get("data") or []):
                if i.get("instId", "").endswith("-USDT-SWAP"):
                    m[i["instId"][:-10]] = _f(i.get("ctVal"), 1)
        elif ex == "mexc":
            d = _S["get"]("https://contract.mexc.com/api/v1/contract/detail")
            for i in ((d or {}).get("data") or []):
                if str(i.get("symbol", "")).endswith("_USDT"):
                    m[i["symbol"][:-5]] = _f(i.get("contractSize"), 1)
        elif ex == "gate":
            d = _S["get"]("https://api.gateio.ws/api/v4/futures/usdt/contracts")
            for i in (d if isinstance(d, list) else []):
                if str(i.get("name", "")).endswith("_USDT"):
                    m[i["name"][:-5]] = _f(i.get("quanto_multiplier"), 1)
        return m
    return _cached("ct_" + ex, 6 * 3600, load) or {}


def _norm_book(bids, asks, k=1.0, depth=14):
    bids = sorted(([_f(p), _f(q) * k] for p, q in bids if _f(p) > 0), key=lambda x: -x[0])[:depth]
    asks = sorted(([_f(p), _f(q) * k] for p, q in asks if _f(p) > 0), key=lambda x: x[0])[:depth]
    return bids, asks


def _fetch_book(ex, typ, b):
    g = _S["get"]
    S = b + "USDT"
    if typ == "fut":
        if ex in ("binance", "aster"):
            host = "fapi.binance.com" if ex == "binance" else "fapi.asterdex.com"
            d = g(f"https://{host}/fapi/v1/depth", {"symbol": S, "limit": 20}) or {}
            return _norm_book(d.get("bids", []), d.get("asks", []))
        if ex == "okx":
            d = g("https://www.okx.com/api/v5/market/books", {"instId": f"{b}-USDT-SWAP", "sz": 20}) or {}
            x = ((d.get("data") or [{}])[0]) or {}
            k = _ct_sizes("okx").get(b, 1)
            return _norm_book([r[:2] for r in x.get("bids", [])], [r[:2] for r in x.get("asks", [])], k)
        if ex == "bingx":
            d = g("https://open-api.bingx.com/openApi/swap/v2/quote/depth",
                  {"symbol": f"{b}-USDT", "limit": 20, **_S["bx"]()}) or {}
            x = d.get("data") or {}
            return _norm_book(x.get("bids", []), x.get("asks", []))
        if ex == "mexc":
            d = g(f"https://contract.mexc.com/api/v1/contract/depth/{b}_USDT", {"limit": 20}) or {}
            x = d.get("data") or {}
            k = _ct_sizes("mexc").get(b, 1)
            return _norm_book([r[:2] for r in x.get("bids", [])], [r[:2] for r in x.get("asks", [])], k)
        if ex == "gate":
            d = g("https://api.gateio.ws/api/v4/futures/usdt/order_book", {"contract": f"{b}_USDT", "limit": 20}) or {}
            k = _ct_sizes("gate").get(b, 1)
            return _norm_book([(r.get("p"), r.get("s")) for r in d.get("bids", [])],
                              [(r.get("p"), r.get("s")) for r in d.get("asks", [])], k)
    else:
        if ex in ("binance", "aster"):
            host = "https://data-api.binance.vision/api/v3/depth" if ex == "binance" else "https://sapi.asterdex.com/api/v3/depth"
            d = g([host] + (["https://api.binance.com/api/v3/depth"] if ex == "binance" else []), {"symbol": S, "limit": 20}) or {}
            return _norm_book(d.get("bids", []), d.get("asks", []))
        if ex == "okx":
            d = g("https://www.okx.com/api/v5/market/books", {"instId": f"{b}-USDT", "sz": 20}) or {}
            x = ((d.get("data") or [{}])[0]) or {}
            return _norm_book([r[:2] for r in x.get("bids", [])], [r[:2] for r in x.get("asks", [])])
        if ex == "bingx":
            d = g("https://open-api.bingx.com/openApi/spot/v1/market/depth",
                  {"symbol": f"{b}-USDT", "limit": 20, **_S["bx"]()}) or {}
            x = d.get("data") or {}
            return _norm_book(x.get("bids", []), x.get("asks", []))
        if ex == "mexc":
            d = g("https://api.mexc.com/api/v3/depth", {"symbol": S, "limit": 20}) or {}
            return _norm_book(d.get("bids", []), d.get("asks", []))
        if ex == "gate":
            d = g("https://api.gateio.ws/api/v4/spot/order_book", {"currency_pair": f"{b}_USDT", "limit": 20}) or {}
            return _norm_book(d.get("bids", []), d.get("asks", []))
    return [], []


def _fetch_vol(ex, typ, b):
    g = _S["get"]
    S = b + "USDT"
    try:
        if typ == "spot":
            s = _cached("spot", 6, _spot) or {}
            return _f(((s.get(ex) or {}).get(b) or {}).get("vol"))
        if ex in ("binance", "aster"):
            host = "fapi.binance.com" if ex == "binance" else "fapi.asterdex.com"
            return _f((g(f"https://{host}/fapi/v1/ticker/24hr", {"symbol": S}) or {}).get("quoteVolume"))
        if ex == "okx":
            x = (((g("https://www.okx.com/api/v5/market/ticker", {"instId": f"{b}-USDT-SWAP"}) or {}).get("data")) or [{}])[0]
            return _f(x.get("volCcy24h")) * _f(x.get("last"))
        if ex == "bingx":
            d = (g("https://open-api.bingx.com/openApi/swap/v2/quote/ticker", {"symbol": f"{b}-USDT", **_S["bx"]()}) or {}).get("data") or {}
            d = d[0] if isinstance(d, list) and d else d
            return _f(d.get("quoteVolume"))
        if ex == "mexc":
            return _f(((g("https://contract.mexc.com/api/v1/contract/ticker", {"symbol": f"{b}_USDT"}) or {}).get("data") or {}).get("amount24"))
        if ex == "gate":
            d = g("https://api.gateio.ws/api/v4/futures/usdt/tickers", {"contract": f"{b}_USDT"})
            return _f((d[0] if isinstance(d, list) and d else {}).get("volume_24h_quote"))
    except Exception:
        pass
    return 0.0


def _parse_leg(s):
    try:
        ex, typ = s.split(":")
    except ValueError:
        return None
    return (ex, typ) if ex in EXCH and typ in ("fut", "spot") else None


def api_pair():
    b = (request.args.get("symbol") or "").upper().replace("/", "").replace("USDT", "")
    legs = [_parse_leg(request.args.get("long", "")), _parse_leg(request.args.get("short", ""))]
    if not b or not all(legs):
        return jsonify({"error": "bad params"}), 400
    out = []
    fut = _cached("fut", 4, _futures) or {}
    spot = _cached("spot", 6, _spot) or {}
    for ex, typ in legs:
        bids, asks = _cached(f"bk_{ex}_{typ}_{b}", 0.7, lambda: _fetch_book(ex, typ, b)) or ([], [])
        vol = _cached(f"vol_{ex}_{typ}_{b}", 30, lambda: _fetch_vol(ex, typ, b))
        d = (fut if typ == "fut" else spot).get(ex, {}).get(b) or {}
        leg = {"ex": ex, "type": typ, "bids": bids, "asks": asks, "vol24h": vol,
               "price": d.get("price", 0), "fee": FEES[ex][typ],
               "spot": (spot.get(ex, {}).get(b) or {}).get("price") if typ == "fut" else None}
        if typ == "fut":
            leg.update(rate=round(d.get("rate", 0), 5), hours=d.get("hours", 8), next=d.get("next"))
        out.append(leg)
    return jsonify({"symbol": b, "long": out[0], "short": out[1], "ts": int(time.time() * 1000)})
