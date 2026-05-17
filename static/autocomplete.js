/**
 * CYPHER_TERMINAL — Universal Token Autocomplete
 * Підключається на всіх сторінках. Ініціалізується через:
 *   initAutocomplete(inputEl, onSelect, options?)
 *
 * onSelect(symbol, base) — callback коли юзер обирає токен
 * options.maxResults     — макс. кількість результатів (default: 8)
 * options.minChars       — мін. символів для пошуку (default: 1)
 */

(function() {

// ── Стилі dropdown ──────────────────────────────────────────────────────────
const STYLES = `
.ct-dropdown {
  position: absolute;
  z-index: 9999;
  background: #1d1f26;
  border: 1px solid #3b4a44;
  min-width: 260px;
  max-height: 320px;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0,0,0,.5);
  scrollbar-width: none;
}
.ct-dropdown::-webkit-scrollbar { display: none; }
.ct-dropdown-item {
  display: grid;
  grid-template-columns: 1fr 1fr 80px;
  align-items: center;
  padding: 7px 12px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  border-bottom: 1px solid #282a30;
  transition: background .1s;
  gap: 8px;
}
.ct-dropdown-item:last-child { border-bottom: none; }
.ct-dropdown-item:hover,
.ct-dropdown-item.selected {
  background: #282a30;
}
.ct-dropdown-item .sym  { color: #e2e2ea; font-weight: 600; }
.ct-dropdown-item .name { color: #bacac2; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ct-dropdown-item .prc  { text-align: right; color: #46f1c5; }
.ct-dropdown-item .chg  { text-align: right; font-size: 11px; }
.ct-dropdown-item .chg.up   { color: #4ae176; }
.ct-dropdown-item .chg.down { color: #ffb4ab; }
.ct-dropdown-empty {
  padding: 14px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #bacac2;
  text-align: center;
}
`;

// Вставляємо стилі один раз
if (!document.getElementById('ct-ac-styles')) {
  const el = document.createElement('style');
  el.id = 'ct-ac-styles';
  el.textContent = STYLES;
  document.head.appendChild(el);
}

// ── Глобальний кеш символів ─────────────────────────────────────────────────
let _cache = null;
let _loading = false;
let _callbacks = [];

async function getSymbols() {
  if (_cache) return _cache;
  if (_loading) {
    return new Promise(r => _callbacks.push(r));
  }
  _loading = true;
  try {
    const res  = await fetch(window.location.origin + '/api/symbols');
    const json = await res.json();
    _cache = json.data || [];
  } catch(e) {
    _cache = [];
  }
  _loading = false;
  _callbacks.forEach(r => r(_cache));
  _callbacks = [];
  return _cache;
}

// Форматування ціни
function fmtPrice(n) {
  if (!n) return '—';
  if (n < 0.0001) return n.toFixed(6);
  if (n < 0.01)   return n.toFixed(5);
  if (n < 1)      return n.toFixed(4);
  if (n < 1000)   return n.toFixed(3);
  return n.toLocaleString('en-US', {maximumFractionDigits: 2});
}

// ── Головна функція ──────────────────────────────────────────────────────────
window.initAutocomplete = function(inputEl, onSelect, opts = {}) {
  const maxResults = opts.maxResults || 8;
  const minChars   = opts.minChars   || 1;

  let dropdown = null;
  let activeIdx = -1;
  let allSymbols = [];

  // Завантажуємо символи одразу
  getSymbols().then(s => { allSymbols = s; });

  // Позиціонуємо dropdown під input
  function positionDropdown() {
    if (!dropdown) return;
    const rect = inputEl.getBoundingClientRect();
    dropdown.style.top    = (rect.bottom + window.scrollY + 2) + 'px';
    dropdown.style.left   = rect.left + 'px';
    dropdown.style.width  = Math.max(rect.width, 280) + 'px';
  }

  function showDropdown(results) {
    hideDropdown();
    if (!results.length) {
      dropdown = document.createElement('div');
      dropdown.className = 'ct-dropdown';
      dropdown.innerHTML = `<div class="ct-dropdown-empty">No results for "${inputEl.value}"</div>`;
      document.body.appendChild(dropdown);
      positionDropdown();
      return;
    }

    dropdown = document.createElement('div');
    dropdown.className = 'ct-dropdown';
    activeIdx = -1;

    results.forEach((s, i) => {
      const chgClass = s.up ? 'up' : 'down';
      const sign     = s.up ? '+' : '';
      const name     = s.name || s.base;

      const item = document.createElement('div');
      item.className = 'ct-dropdown-item';
      item.dataset.idx = i;
      item.innerHTML = `
        <div>
          <div class="sym">${s.base}<span style="color:#bacac2;font-weight:400">/USDT</span></div>
          <div class="name">${name}</div>
        </div>
        <div class="prc">$${fmtPrice(s.price)}</div>
        <div class="chg ${chgClass}">${sign}${s.change.toFixed(2)}%</div>
      `;
      item.addEventListener('mousedown', e => {
        e.preventDefault();
        select(s);
      });
      dropdown.appendChild(item);
    });

    document.body.appendChild(dropdown);
    positionDropdown();
  }

  function hideDropdown() {
    if (dropdown) { dropdown.remove(); dropdown = null; }
    activeIdx = -1;
  }

  function setActive(idx) {
    if (!dropdown) return;
    const items = dropdown.querySelectorAll('.ct-dropdown-item');
    items.forEach(el => el.classList.remove('selected'));
    if (idx >= 0 && idx < items.length) {
      items[idx].classList.add('selected');
      items[idx].scrollIntoView({block:'nearest'});
    }
    activeIdx = idx;
  }

  function select(s) {
    inputEl.value = s.base;
    hideDropdown();
    onSelect(s.symbol, s.base, s);
  }

  function search(query) {
    if (!query || query.length < minChars) { hideDropdown(); return; }
    const q = query.toUpperCase().replace('USDT','').replace('/','');
    const results = allSymbols
      .filter(s =>
        s.base.startsWith(q) ||
        s.symbol.startsWith(q) ||
        (s.name && s.name.toUpperCase().includes(q))
      )
      .slice(0, maxResults);
    showDropdown(results);
  }

  // ── Events ──────────────────────────────────────────────────────────────────
  inputEl.addEventListener('input', () => search(inputEl.value));
  inputEl.addEventListener('focus', () => {
    if (inputEl.value.length >= minChars) search(inputEl.value);
  });

  inputEl.addEventListener('keydown', e => {
    if (!dropdown) {
      if (e.key === 'Enter') {
        const q = inputEl.value.trim().toUpperCase().replace('USDT','').replace('/','');
        if (q) onSelect(q + 'USDT', q, null);
      }
      return;
    }

    const items = dropdown.querySelectorAll('.ct-dropdown-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive(Math.min(activeIdx + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive(Math.max(activeIdx - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) {
        items[activeIdx].dispatchEvent(new Event('mousedown'));
      } else {
        const q = inputEl.value.trim().toUpperCase().replace('USDT','').replace('/','');
        if (q) { hideDropdown(); onSelect(q + 'USDT', q, null); }
      }
    } else if (e.key === 'Escape') {
      hideDropdown();
      inputEl.blur();
    }
  });

  // Закрити при кліку поза dropdown
  document.addEventListener('click', e => {
    if (!inputEl.contains(e.target) && !(dropdown && dropdown.contains(e.target))) {
      hideDropdown();
    }
  });

  window.addEventListener('resize', positionDropdown);
  window.addEventListener('scroll', positionDropdown);
};

})();
