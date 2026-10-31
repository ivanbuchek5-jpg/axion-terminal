/* AXION TERMINAL — shared chrome + helpers */
(function () {
  "use strict";
  var AX = (window.AX = window.AX || {});
  var API = window.location.origin;
  AX.API = API;

  /* ── storage (never throws) ── */
  function sget(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function sset(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function ssget(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } }
  function ssset(k, v) { try { sessionStorage.setItem(k, v); } catch (e) {} }
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── theme ── */
  AX.theme = function () { return document.documentElement.getAttribute("data-theme") || "dark"; };
  AX.setTheme = function (t, silent) {
    document.documentElement.setAttribute("data-theme", t);
    sset("axion-theme", t);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute("content", t === "light" ? "#E9EAEC" : "#25272D");
    var b = document.getElementById("themeBtn");
    if (b) { b.setAttribute("aria-label", t === "light" ? "Switch to dark mode" : "Switch to light mode"); b.setAttribute("aria-pressed", t === "dark" ? "true" : "false"); }
    if (!silent) window.dispatchEvent(new CustomEvent("axion:theme", { detail: t }));
  };
  /* "Eclipse": the new theme grows from the toggle as a soft-edged circle (View Transitions API).
     Never locked: a click during a running transition skips it and starts the next one at once. */
  var vtCur = null, vtId = 0, want = null;
  AX.toggleTheme = function () {
    var root = document.documentElement, btn = document.getElementById("themeBtn");
    var next = (want || AX.theme()) === "light" ? "dark" : "light";
    want = next;
    var fast = !document.startViewTransition || reduce || !btn;
    if (vtCur || fast) {
      /* interrupted (or no VT support): flip instantly, never wait for the running animation */
      if (vtCur) { vtId++; try { vtCur.skipTransition(); } catch (e) {} vtCur = null; root.classList.remove("vt-eclipse"); }
      AX.setTheme(next); want = null; return;
    }
    var apply = function () { AX.setTheme(next, true); };
    var r = btn.getBoundingClientRect(), W = innerWidth, H = innerHeight, x = r.left + r.width / 2, y = r.top + r.height / 2;
    var R = Math.hypot(Math.max(x, W - x), Math.max(y, H - y));
    root.style.setProperty("--vt-x", x + "px"); root.style.setProperty("--vt-y", y + "px");
    root.classList.add("vt-eclipse");
    var id = ++vtId, vt = document.startViewTransition(apply);
    vtCur = vt;
    vt.ready.then(function () {
      if (id !== vtId) return;
      var kf = [];
      for (var i = 0; i <= 48; i++) {
        var t = i / 48, e = 1 - Math.pow(1 - t, 3);
        kf.push({ "--l1": (e * (R + 130)) + "px", offset: t });
      }
      root.animate(kf, { duration: 780, easing: "linear", fill: "both", pseudoElement: "::view-transition-new(root)" });
    }, function () {});
    var done = function () {
      if (id !== vtId) return;
      vtCur = null; want = null;
      root.classList.remove("vt-eclipse");
      window.dispatchEvent(new CustomEvent("axion:theme", { detail: AX.theme() }));
    };
    vt.finished.then(done, done);
  };

  /* ── icons ── */
  var P = {
    home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v9.5h13V10"/><path d="M10 19.5v-5h4v5"/>',
    prices: '<circle cx="12" cy="12" r="8.5"/><path d="M14.8 9.2c-.5-.9-1.5-1.4-2.8-1.4-1.6 0-2.7.8-2.7 2 0 1.3 1.1 1.8 2.7 2.1 1.7.3 2.9.8 2.9 2.1 0 1.2-1.2 2-2.9 2-1.4 0-2.5-.6-3-1.6"/><path d="M12 6.5v1.3M12 16.2v1.3"/>',
    spread: '<path d="M7 4v16M7 4 4 7M7 4l3 3"/><path d="M17 20V4M17 20l-3-3M17 20l3-3"/>',
    funding: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    converter: '<path d="M4 8h14l-3-3M20 16H6l3 3"/>',
    chart: '<path d="M4 19V5"/><path d="M4 19h16"/><path d="m7.5 14 3.5-4 3 2.5 4.5-6"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    back: '<path d="M15 5 8 12l7 7"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 5v6h-6"/>',
    copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="3"/><path d="M15.5 8.5V7a3 3 0 0 0-3-3H7a3 3 0 0 0-3 3v5.5a3 3 0 0 0 3 3h1.5"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    chev: '<path d="m9 6 6 6-6 6"/>',
    alert: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5.5M12 16.2v.1"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.1"/>',
    empty: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2M8.5 11h5"/>',
    up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
    down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    filter: '<path d="M4 7h9M18 7h2M4 17h2M11 17h9"/><circle cx="15.5" cy="7" r="2.3"/><circle cx="8.5" cy="17" r="2.3"/>',
    cv: '<path d="m6 9 6 6 6-6"/>',
    swap: '<path d="M8 4v16M8 20l-3.5-3.5M8 20l3.5-3.5"/><path d="M16 20V4M16 4l-3.5 3.5M16 4l3.5 3.5"/>'
  };
  AX.icon = function (n, cls) {
    return '<svg class="i ' + (cls || "") + '" viewBox="0 0 24 24" aria-hidden="true">' + (P[n] || "") + "</svg>";
  };

  /* ── formatters ── */
  AX.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };
  AX.num = function (n, max) {
    return Number(n).toLocaleString("en-US", { maximumFractionDigits: max == null ? 2 : max });
  };
  AX.price = function (p) {
    p = Number(p);
    if (!p) return "—";
    if (p < 0.000001) return "$" + p.toFixed(8);
    if (p < 0.0001) return "$" + p.toFixed(6);
    if (p < 0.01) return "$" + p.toFixed(5);
    if (p < 1) return "$" + p.toFixed(4);
    if (p < 1000) return "$" + p.toFixed(2);
    return "$" + AX.num(p, 2);
  };
  AX.plain = function (n) { /* no $ */
    n = Number(n);
    if (!n) return "—";
    if (n < 0.0001) return n.toFixed(8);
    if (n < 0.01) return n.toFixed(6);
    if (n < 1) return n.toFixed(4);
    if (n < 100) return n.toFixed(3);
    return AX.num(n, 2);
  };
  AX.vol = function (n) { /* compact, truncated: 460.99k · 1.23M · 4.56B */
    n = Number(n);
    if (!n || n < 1) return "—";
    var f = function (v) { return (Math.floor(v * 100) / 100).toFixed(2); };
    if (n >= 1e12) return "$" + f(n / 1e12) + "T";
    if (n >= 1e9) return "$" + f(n / 1e9) + "B";
    if (n >= 1e6) return "$" + f(n / 1e6) + "M";
    if (n >= 1e3) return "$" + f(n / 1e3) + "k";
    return "$" + f(n);
  };
  AX.pct = function (n, d) {
    n = Number(n);
    if (isNaN(n)) return "—";
    return (n > 0 ? "+" : "") + n.toFixed(d == null ? 2 : d) + "%";
  };
  AX.cls = function (n) { return Number(n) >= 0 ? "up" : "dn"; };
  AX.base = function (s) { return String(s || "").toUpperCase().replace("/", "").replace(/USDT$/, ""); };
  AX.go = function (sym) { AX.navigate("token.html?symbol=" + encodeURIComponent(AX.base(sym))); };
  /* ── token logos: CoinMarketCap (id map from /api/logos) → rounded-square tile, text fallback ── */
  var LM = null, ICB = {};
  try { LM = JSON.parse(localStorage.getItem("axion-lm") || "null"); } catch (e) {}
  var lmFresh = LM && LM.t && Date.now() - LM.t < 864e5;
  function lid(s) { var m = LM && LM.m; if (!m) return 0; return m[s] || m[s.replace(/^(1000000|10000|1000|1M)/i, "")] || 0; }
  function lurl(id) { return "https://s2.coinmarketcap.com/static/img/coins/64x64/" + id + ".png"; }
  AX.ico = function (b) {
    var s = AX.base(b).toUpperCase(), id = /^[A-Z0-9]{1,12}$/.test(s) ? lid(s) : 0;
    return '<i class="ti" data-s="' + AX.esc(s) + '">' + AX.esc(s.slice(0, 4)) + "</i>" +
      (id && !ICB[id] ? '<img class="tl" data-id="' + id + '" src="' + lurl(id) + '" alt="" decoding="async" crossorigin="anonymous">' : "");
  };
  function upgrade() {
    if (!LM || !LM.m) return;
    [].forEach.call(document.querySelectorAll("i.ti[data-s]"), function (t) {
      if (t.nextElementSibling && t.nextElementSibling.tagName === "IMG") return;
      var id = lid(t.getAttribute("data-s")); if (!id || ICB[id]) return;
      var im = new Image(); im.className = "tl"; im.setAttribute("data-id", id); im.alt = ""; im.decoding = "async"; im.crossOrigin = "anonymous"; im.src = lurl(id);
      t.parentNode.appendChild(im);
    });
  }
  if (!lmFresh) {
    fetch("/api/logos").then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.map && Object.keys(j.map).length) { LM = { t: Date.now(), m: j.map }; try { localStorage.setItem("axion-lm", JSON.stringify(LM)); } catch (e) {} upgrade(); }
    }).catch(function () {});
  }
  var upT = 0;
  new MutationObserver(function () { clearTimeout(upT); upT = setTimeout(upgrade, 60); }).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("error", function (e) {
    var im = e.target;
    if (!im || im.tagName !== "IMG" || !im.classList.contains("tl")) return;
    ICB[im.getAttribute("data-id")] = 1; im.remove();
  }, true);
  document.addEventListener("load", function (e) {
    var im = e.target;
    if (!im || im.tagName !== "IMG" || !im.classList.contains("tl")) return;
    var box = im.parentNode; if (!box) return;
    box.classList.add("has-logo");
    try {
      var c = document.createElement("canvas"); c.width = c.height = 16;
      var x = c.getContext("2d", { willReadFrequently: true }); x.drawImage(im, 0, 0, 16, 16);
      var p = x.getImageData(8, 1, 1, 1).data;
      box.style.background = p[3] > 200 ? "rgb(" + p[0] + "," + p[1] + "," + p[2] + ")" : "#fff";
    } catch (er) { box.style.background = "#fff"; }
  }, true);

  /* ── exchanges (shared by Spread + Pair pages) ── */
  AX.EX = {
    binance: { n: "Binance", c: "#F0B90B", t: "BN" }, aster: { n: "Aster", c: "#B7791F", t: "AS" },
    okx: { n: "OKX", c: "#3A3D44", t: "OK" }, bingx: { n: "BingX", c: "#2B6BFF", t: "BX" },
    mexc: { n: "MEXC", c: "#1B7BE0", t: "MX" }, gate: { n: "Gate", c: "#E24B4B", t: "GT" }
  };
  AX.exName = function (k) { return (AX.EX[k] || { n: k }).n; };
  var XD = { binance: ["binance.com", 270], aster: ["asterdex.com", 0], okx: ["okx.com", 294], bingx: ["bingx.com", 1064], mexc: ["mexc.com", 544], gate: ["gate.com", 302] };
  /* logo chain: your own file static/ex/<key>.png → site favicon → CoinMarketCap exchange logo → coloured letters tile */
  function xsrc(k, n) {
    var d = XD[k]; if (!d) return null;
    if (n === 0) return "ex/" + k + ".png?v=12";
    if (n === 1) return "https://www.google.com/s2/favicons?domain=" + d[0] + "&sz=128";
    if (n === 2 && d[1]) return "https://s2.coinmarketcap.com/static/img/exchanges/64x64/" + d[1] + ".png";
    return null;
  }
  AX.xt = function (k) {
    var e = AX.EX[k] || { c: "#555", t: "?" }, u = xsrc(k, 0);
    return '<span class="xt" style="--xc:' + e.c + '"><b>' + e.t + "</b>" + (u ? '<img data-k="' + AX.esc(k) + '" data-n="0" src="' + u + '" alt="" referrerpolicy="no-referrer" decoding="async">' : "") + "</span>";
  };
  /* exchange page of this exact token (type: "fut" | "spot") */
  AX.exUrl = function (ex, type, base) {
    var b = AX.base(base), f = type === "fut";
    var U = {
      binance: f ? "https://www.binance.com/en/futures/" + b + "USDT" : "https://www.binance.com/en/trade/" + b + "_USDT?type=spot",
      aster: f ? "https://www.asterdex.com/en/futures/v1/" + b + "USDT" : "https://www.asterdex.com/en/spot/" + b + "USDT",
      okx: f ? "https://www.okx.com/trade-swap/" + b.toLowerCase() + "-usdt-swap" : "https://www.okx.com/trade-spot/" + b.toLowerCase() + "-usdt",
      bingx: f ? "https://bingx.com/en/perpetual/" + b + "-USDT/" : "https://bingx.com/en/spot/" + b + "USDT/",
      mexc: f ? "https://futures.mexc.com/exchange/" + b + "_USDT" : "https://www.mexc.com/exchange/" + b + "_USDT",
      gate: f ? "https://www.gate.io/futures/USDT/" + b + "_USDT" : "https://www.gate.io/trade/" + b + "_USDT"
    };
    return U[ex] || "#";
  };
  document.addEventListener("error", function (e) {
    var im = e.target;
    if (!im || im.tagName !== "IMG" || !im.parentNode || !im.parentNode.classList.contains("xt")) return;
    var k = im.getAttribute("data-k"), n = (+im.getAttribute("data-n") || 0) + 1, u = xsrc(k, n);
    if (u) { im.setAttribute("data-n", n); im.src = u; } else im.remove();
  }, true);
  document.addEventListener("load", function (e) {
    var im = e.target;
    if (im && im.tagName === "IMG" && im.parentNode && im.parentNode.classList.contains("xt")) im.parentNode.classList.add("has");
  }, true);
  /* 3723000 → "01:02:03" */
  AX.hms = function (ms) {
    if (ms == null || isNaN(ms)) return "—";
    var s = Math.max(0, Math.floor(ms / 1000)), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m + ":" + (x < 10 ? "0" : "") + x;
  };

  /* ── count-up ── */
  AX.count = function (el, to, fmt, dur) {
    if (!el) return;
    to = Number(to);
    if (isNaN(to)) { el.textContent = "—"; return; }
    var from = el._v;
    el._v = to;
    if (reduce || from == null || from === to) { el.textContent = fmt(to); return; }
    if (el._raf) cancelAnimationFrame(el._raf);
    var t0 = performance.now(), d = dur || 520;
    (function step(t) {
      var k = Math.min(1, (t - t0) / d), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(from + (to - from) * e);
      if (k < 1) el._raf = requestAnimationFrame(step);
    })(t0);
  };
  /* first paint: count from 0 */
  AX.countIn = function (el, to, fmt, dur) {
    if (!el) return;
    if (el._v == null && !reduce) { el._v = 0; el.textContent = fmt(0); }
    AX.count(el, to, fmt, dur || 700);
  };

  /* ── sparkline ── */
  AX.spark = function (vals, up) {
    if (!vals || vals.length < 2) return '<svg class="spark" viewBox="0 0 300 84" preserveAspectRatio="none"></svg>';
    var w = 300, h = 84, pad = 6;
    var mn = Math.min.apply(0, vals), mx = Math.max.apply(0, vals), rg = mx - mn || 1;
    var pts = vals.map(function (v, i) {
      return [(i / (vals.length - 1)) * w, pad + (1 - (v - mn) / rg) * (h - pad * 2)];
    });
    var d = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
    var id = "sg" + Math.floor(Math.random() * 1e6);
    var col = up === false ? "var(--neg)" : "var(--accent)";
    return '<svg class="spark ' + (up === false ? "dn" : "") + '" viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none">' +
      '<path d="' + d + " L" + w + " " + h + " L0 " + h + 'Z" fill="' + col + '" fill-opacity=".09"/>' +
      '<path class="ln" pathLength="1" d="' + d + '" vector-effect="non-scaling-stroke"/></svg>';
  };

  /* ── live badge ── */
  AX.live = function (el, state, text) {
    if (!el) return;
    el.className = "live " + (state || "");
    el.innerHTML = "<i></i>" + (text || "");
  };
  AX.skel = function (n, cols) {
    var h = "";
    for (var i = 0; i < (n || 6); i++) {
      h += '<div class="skel" style="animation-delay:' + i * 60 + 'ms">';
      for (var j = 0; j < (cols || 3); j++) h += '<i style="flex:' + (j ? 1 : 1.4) + '"></i>';
      h += "</div>";
    }
    return h;
  };
  AX.empty = function (icon, text) {
    return '<div class="empty">' + AX.icon(icon) + "<span>" + AX.esc(text) + "</span></div>";
  };

  /* ── segmented control with sliding pill ── */
  AX.seg = function (el, onChange, initial) {
    var btns = [].slice.call(el.querySelectorAll("button"));
    var pill = document.createElement("span");
    pill.className = "seg-pill";
    el.insertBefore(pill, el.firstChild);
    el.style.setProperty("--n", btns.length);
    function set(i, silent) {
      el.style.setProperty("--i", i);
      btns.forEach(function (b, k) { b.classList.toggle("on", k === i); });
      if (!silent && onChange) onChange(btns[i].getAttribute("data-v"), i);
    }
    btns.forEach(function (b, i) { b.addEventListener("click", function () { set(i); }); });
    var start = 0;
    btns.forEach(function (b, i) { if (b.getAttribute("data-v") === initial || b.classList.contains("on")) start = i; });
    set(start, true);
    return { set: function (v) { btns.forEach(function (b, i) { if (b.getAttribute("data-v") === v) set(i, true); }); } };
  };

  /* ── toast ── */
  var toastBox;
  AX.toast = function (text, ok) {
    if (!toastBox) {
      toastBox = document.createElement("div");
      toastBox.className = "toasts";
      toastBox.setAttribute("role", "status");
      document.body.appendChild(toastBox);
    }
    var t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = (ok === false ? AX.icon("alert") : AX.icon("check")) + "<span>" + AX.esc(text) + "</span>";
    toastBox.appendChild(t);
    setTimeout(function () {
      t.classList.add("out");
      setTimeout(function () { t.remove(); }, 240);
    }, 2200);
  };

  /* ── bottom sheet ── */
  AX.sheet = function (opts) {
    var scrim = document.createElement("div");
    scrim.className = "scrim";
    var sh = document.createElement("div");
    sh.className = "sheet";
    sh.setAttribute("role", "dialog");
    sh.setAttribute("aria-modal", "true");
    sh.innerHTML = '<div class="sheet-grab"><i></i></div><div class="sheet-h"><b>' + AX.esc(opts.title || "") +
      '</b><button class="icon-btn" style="width:38px;height:38px;border-radius:13px" aria-label="Close">' + AX.icon("close") + '</button></div><div class="sheet-body"></div>';
    var body = sh.querySelector(".sheet-body");
    if (typeof opts.content === "string") body.innerHTML = opts.content; else if (opts.content) body.appendChild(opts.content);
    document.body.appendChild(scrim);
    document.body.appendChild(sh);
    document.body.style.overflow = "hidden";
    var closed = false;
    function close() {
      if (closed) return;
      closed = true;
      scrim.classList.add("out");
      sh.classList.add("out");
      sh.style.transform = "";
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      setTimeout(function () { scrim.remove(); sh.remove(); if (opts.onClose) opts.onClose(); }, 300);
    }
    function onKey(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    scrim.addEventListener("click", close);
    sh.querySelector(".icon-btn").addEventListener("click", close);
    /* drag to dismiss — velocity aware */
    var grab = sh.querySelector(".sheet-grab"), y0 = 0, t0 = 0, dy = 0, drag = false;
    grab.addEventListener("pointerdown", function (e) {
      drag = true; y0 = e.clientY; t0 = performance.now(); dy = 0;
      grab.setPointerCapture(e.pointerId);
      sh.style.transition = "none";
    });
    grab.addEventListener("pointermove", function (e) {
      if (!drag) return;
      dy = Math.max(0, e.clientY - y0);
      sh.style.transform = "translate(-50%," + dy + "px)";
    });
    function end() {
      if (!drag) return;
      drag = false;
      var v = dy / Math.max(1, performance.now() - t0);
      sh.style.transition = "";
      if (dy > 110 || v > 0.11) close(); else sh.style.transform = "";
    }
    grab.addEventListener("pointerup", end);
    grab.addEventListener("pointercancel", end);
    if (opts.onOpen) opts.onOpen(sh, body);
    return { close: close, el: sh, body: body };
  };


  /* ── branded page transition ── */
  var root = document.documentElement, leaving = false, target = null, leaveTimer = null;
  var warmed = {};
  AX.warm = function (href) {
    try {
      var u = new URL(href, location.href);
      if (u.origin !== location.origin || warmed[u.href] || u.href === location.href) return;
      warmed[u.href] = 1;
      fetch(u.href, { credentials: "same-origin" }).catch(function () {});
    } catch (e) {}
  };
  ["pointerover", "touchstart"].forEach(function (ev) {
    document.addEventListener(ev, function (e) {
      var a = e.target.closest && e.target.closest("a[href]");
      if (a && !a.target && a.getAttribute("href").charAt(0) !== "#") AX.warm(a.href);
    }, { passive: true });
  });
  AX.navigate = function (url) {
    var abs;
    try { abs = new URL(url, location.href); } catch (e) { location.href = url; return; }
    if (reduce || abs.origin !== location.origin || (abs.pathname === location.pathname && abs.search === location.search)) { location.href = abs.href; return; }
    target = abs.href;
    AX.warm(target);
    if (leaving) return;                      /* rapid clicks: just retarget */
    leaving = true;
    root.classList.remove("pt-in", "pt-reveal");
    root.classList.add("pt-out");
    leaveTimer = setTimeout(function () {
      try { sessionStorage.setItem("axion-pt", String(Date.now())); } catch (e) {}
      location.assign(target);
      /* navigation failed or was cancelled: restore the page */
      setTimeout(function () { leaving = false; root.classList.remove("pt-out"); }, 6000);
    }, 340);
  };
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
    var h = a.getAttribute("href");
    if (!h || h.charAt(0) === "#" || /^(mailto:|tel:|javascript:)/i.test(h)) return;
    e.preventDefault();
    AX.navigate(a.href);
  });
  window.addEventListener("pageshow", function (e) {   /* back/forward cache */
    leaving = false; clearTimeout(leaveTimer);
    root.classList.remove("pt-out", "pt-in");
  });
  /* arrival: keep the branded screen until the page and its first data are ready */
  if (root.classList.contains("pt-in")) {
    var loaded = document.readyState === "complete", revealed = false, t0 = performance.now(), fontsOk = !(document.fonts && document.fonts.ready);
    function reveal() {
      if (revealed) return; revealed = true;
      root.classList.add("pt-reveal");
      root.classList.remove("pt-in");
      setTimeout(function () { root.classList.remove("pt-reveal"); }, 900);
    }
    AX._ready = function () {
      if (revealed || !loaded || !fontsOk || AX._pend > 0) return;
      setTimeout(reveal, Math.max(0, 380 - (performance.now() - t0)));
    };
    if (!fontsOk) document.fonts.ready.then(function () { fontsOk = true; AX._ready(); });
    if (!loaded) window.addEventListener("load", function () { loaded = true; AX._ready(); });
    setTimeout(AX._ready, 120);
    setTimeout(reveal, 2800);                          /* never stay stuck */
  }


  /* ── custom scrollbar ── */
  AX.scrollbar = function () {
    if (AX._sb) return; AX._sb = true;
    var root = document.documentElement;
    var sb = document.createElement("div");
    sb.className = "sb"; sb.setAttribute("aria-hidden", "true");
    sb.innerHTML = '<div class="sb-track"><div class="sb-thumb"></div></div>';
    document.body.appendChild(sb);
    var thumb = sb.querySelector(".sb-thumb");
    root.classList.add("has-sb");
    var trackH = 240, thumbH = 40, maxScroll = 0, cur = 0, tgt = 0, raf = 0, dragging = false, grab = 0, idle = 0;
    function metrics() {
      var vh = window.innerHeight, dh = Math.max(root.scrollHeight, document.body.scrollHeight);
      maxScroll = Math.max(0, dh - vh);
      trackH = Math.round(Math.min(300, Math.max(150, vh * 0.36)));
      thumbH = Math.round(Math.min(trackH * 0.3, Math.max(28, trackH * vh / Math.max(dh, 1))));
      sb.style.setProperty("--sb-h", trackH + "px");
      thumb.style.height = thumbH + "px";
      sb.classList.toggle("on", maxScroll > 2);
      target();
    }
    function target() {
      var r = maxScroll ? Math.min(1, Math.max(0, (window.scrollY || root.scrollTop) / maxScroll)) : 0;
      tgt = r * (trackH - thumbH);
      if (!raf) raf = requestAnimationFrame(tick);
    }
    function tick() {
      raf = 0;
      var d = tgt - cur;
      cur = dragging || reduce || Math.abs(d) < 0.15 ? tgt : cur + d * 0.22;
      thumb.style.transform = "translate3d(0," + cur.toFixed(2) + "px,0)";
      if (cur !== tgt) raf = requestAnimationFrame(tick);
    }
    function wake() { sb.classList.add("act"); clearTimeout(idle); idle = setTimeout(function () { sb.classList.remove("act"); }, 900); }
    window.addEventListener("scroll", function () { target(); wake(); }, { passive: true });
    window.addEventListener("resize", metrics);
    window.addEventListener("load", metrics);
    if (window.ResizeObserver) { var ro = new ResizeObserver(metrics); ro.observe(document.body); ro.observe(root); }
    else setInterval(metrics, 1000);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(metrics);
    window.addEventListener("pageshow", metrics);

    function ratioFrom(y, off) {
      var r = sb.getBoundingClientRect(), top = r.top;
      return Math.min(1, Math.max(0, (y - top - off) / Math.max(1, trackH - thumbH)));
    }
    sb.addEventListener("pointerdown", function (e) {
      if (e.button) return;
      e.preventDefault();
      var tr = thumb.getBoundingClientRect();
      if (e.clientY >= tr.top && e.clientY <= tr.bottom) grab = e.clientY - tr.top;
      else { grab = thumbH / 2; window.scrollTo({ top: ratioFrom(e.clientY, grab) * maxScroll, behavior: reduce ? "auto" : "smooth" }); }
      dragging = true; sb.classList.add("drag"); sb.setPointerCapture(e.pointerId);
      document.body.style.userSelect = "none";
    });
    sb.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      window.scrollTo(0, ratioFrom(e.clientY, grab) * maxScroll);
    });
    function end() { if (!dragging) return; dragging = false; sb.classList.remove("drag"); document.body.style.userSelect = ""; target(); }
    sb.addEventListener("pointerup", end); sb.addEventListener("pointercancel", end);
    metrics(); wake();
  };

  /* ── chrome ── */
  var NAV = [
    ["home", "index.html", "Home"],
    ["prices", "prices.html", "Prices"],
    ["spread", "spread.html", "Spread"],
    ["funding", "funding.html", "Funding"],
    ["converter", "converter.html", "Convert"],
    ["chart", "chart.html", "Chart"]
  ];

  AX.init = function (page, opts) {
    opts = opts || {};
    var shell = document.querySelector(".shell");
    var NI = 0;
    NAV.forEach(function (n, i) { if (n[0] === page) NI = i; });
    var top = document.createElement("div");
    top.innerHTML =
      '<header class="nav" id="nav"><div class="nav-in">' +
      '<a class="brand" href="index.html" aria-label="AXION TERMINAL"><span class="logo"><img src="logo.png?v=12" alt="" decoding="sync"></span>' +
      '<span class="brand-t"><b>AXION</b><i>TERMINAL</i></span></a>' +
      '<nav class="nav-links" id="navLinks" aria-label="Main">' +
      NAV.map(function (n) { return '<a href="' + n[1] + '"' + (n[0] === page ? ' aria-current="page"' : "") + ">" + n[2] + "</a>"; }).join("") + "</nav>" +
      '<div class="nav-r"><button type="button" class="nav-search" id="navSearchBtn" aria-label="Search" aria-expanded="false">' + AX.icon("search") + '<span>Search</span></button><button type="button" class="theme-toggle" id="themeBtn" aria-pressed="true">' + AX.icon("moon", "icon-moon") + AX.icon("sun", "icon-sun") + "</button></div>" +
      "</div></header>" +
      '<div class="spal-s" id="spalS" hidden></div><div class="spal" id="spal" hidden><label class="search">' + AX.icon("search") + '<input id="navSearch" placeholder="Search token — BTC, ETH, SOL…" autocomplete="off" spellcheck="false"></label></div>' +
      (opts.ticker === false ? "" : '<div class="ticker rise" style="--d:2"><div class="tk-track" id="tkTrack"><div class="tk-load">Loading market data…</div></div></div>');
    while (top.lastChild) shell.insertBefore(top.lastChild, shell.firstChild);

    /* theme toggle */
    var tb = document.getElementById("themeBtn");
    tb.setAttribute("aria-label", AX.theme() === "light" ? "Switch to dark mode" : "Switch to light mode");
    tb.setAttribute("aria-pressed", AX.theme() === "dark" ? "true" : "false");
    tb.addEventListener("click", AX.toggleTheme);

    /* navbar: morph on scroll */
    var nav = document.getElementById("nav"), ticking = false;
    function onScroll() {
      if (ticking) return; ticking = true;
      requestAnimationFrame(function () {
        var y = window.scrollY || 0, c = nav.classList.contains("compact");
        if (!c && y > 56) nav.classList.add("compact"); else if (c && y < 18) nav.classList.remove("compact");
        ticking = false;
      });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    /* dock */
    var idx = 0;
    NAV.forEach(function (n, i) { if (n[0] === page) idx = i; });
    var prev = parseInt(ssget("axion-dock"), 10);
    if (isNaN(prev)) prev = idx;
    var dock = document.createElement("nav");
    dock.className = "dock";
    dock.setAttribute("aria-label", "Main");
    dock.innerHTML = '<div class="dock-in"><span class="dock-pill" style="--i:' + prev + '"></span>' +
      NAV.map(function (n) {
        return '<a href="' + n[1] + '"' + (n[0] === page ? ' aria-current="page"' : "") + ">" + AX.icon(n[0]) + "<span>" + n[2] + "</span></a>";
      }).join("") + "</div>";
    document.body.appendChild(dock);
    var pill = dock.querySelector(".dock-pill");
    requestAnimationFrame(function () { requestAnimationFrame(function () { pill.style.setProperty("--i", idx); }); });
    ssset("axion-dock", idx);
    dock.addEventListener("click", function (e) {
      var a = e.target.closest("a");
      if (!a) return;
      var k = NAV.map(function (n) { return n[1]; }).indexOf(a.getAttribute("href"));
      if (k > -1) { pill.style.setProperty("--i", k); ssset("axion-dock", k); }
    });

    /* search palette in the navbar */
    var sbtn = document.getElementById("navSearchBtn"), spal = document.getElementById("spal"), spS = document.getElementById("spalS");
    function sOpen() { spal.hidden = false; spS.hidden = false; sbtn.setAttribute("aria-expanded", "true"); document.getElementById("navSearch").focus(); }
    function sClose() { spal.hidden = true; spS.hidden = true; sbtn.setAttribute("aria-expanded", "false"); }
    sbtn.addEventListener("click", function () { spal.hidden ? sOpen() : sClose(); });
    spS.addEventListener("click", sClose);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !spal.hidden) sClose(); });
    document.getElementById("navSearch").addEventListener("input", function () { sbtn.classList.toggle("has-q", !!this.value.trim()); });
    AX.openSearch = sOpen;

    /* search autocomplete → token page */
    var si = document.getElementById("navSearch");
    if (window.initAutocomplete) window.initAutocomplete(si, function (sym, base) { AX.go(base); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "")) { e.preventDefault(); sOpen(); }
    });

    if (opts.ticker !== false) AX.ticker();
    AX.scrollbar();
    document.documentElement.classList.add("ready");
  };

  /* ── ticker ── */
  var tkFirst = true;
  AX.ticker = function () {
    var track = document.getElementById("tkTrack");
    if (!track) return;
    function build(j) {
      var items = [], i;
      (j.tokens || []).forEach(function (t) {
        items.push('<a class="tk" href="token.html?symbol=' + encodeURIComponent(AX.base(t.symbol)) + '"><span class="m">' + AX.esc(t.label || t.symbol) + "</span><b>" + AX.price(t.price) +
          '</b><span class="' + (t.up ? "up" : "dn") + '">' + (t.up ? "▲" : "▼") + " " + (t.up ? "+" : "") + AX.esc(t.change_8h) + "%</span></a>");
      });
      (j.spreads || []).forEach(function (s) {
        items.push('<a class="tk" href="token.html?symbol=' + encodeURIComponent(AX.base(s.symbol)) + '"><span class="tag">S</span><span class="m">' + AX.esc(AX.base(s.symbol)) + '</span><b class="up">+' + Number(s.spread).toFixed(3) + "%</b></a>");
      });
      (j.funding || []).forEach(function (f) {
        items.push('<a class="tk" href="token.html?symbol=' + encodeURIComponent(AX.base(f.symbol)) + '"><span class="tag">F</span><span class="m">' + AX.esc(AX.base(f.symbol)) + '</span><b class="' + (f.positive ? "up" : "dn") + '">' + (f.positive ? "+" : "") + Number(f.rate).toFixed(4) + "%</b></a>");
      });
      if (!items.length) return;
      var prev = track.getAnimations ? track.getAnimations()[0] : null;
      var t = prev ? prev.currentTime : null;
      var h = items.join("");
      track.innerHTML = h + h;
      var half = track.scrollWidth / 2;
      track.style.setProperty("--tk-dur", Math.max(30, half / 42) + "s");
      if (t != null && track.getAnimations) {
        var a = track.getAnimations()[0];
        if (a) a.currentTime = t;
      }
    }
    function load() {
      fetch(API + "/api/ticker").then(function (r) { return r.json(); }).then(build).catch(function () {});
    }
    load();
    setInterval(load, 15000);
  };

  /* ── data helper with simple error surface ── */
  AX._pend = 0;
  AX.get = function (path) {
    AX._pend++;
    function done() { AX._pend--; if (AX._ready) AX._ready(); }
    return fetch(API + path).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (j) { done(); return j; }, function (e) { done(); throw e; });
  };

  /* ── TradingView theme colors ── */
  AX.tvColors = function () {
    return AX.theme() === "light"
      ? { theme: "light", bg: "#FDFDFD", grid: "#ECEDEF" }
      : { theme: "dark", bg: "#0E0F11", grid: "#1D1F24" };
  };
})();
