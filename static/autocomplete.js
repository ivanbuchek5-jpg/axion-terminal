/**
 * AXION TERMINAL — Universal Token Autocomplete
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
  background: var(--surface, #171a13);
  border: 1px solid var(--line, #2b3223);
  border-radius: 20px;
  padding: 6px;
  min-width: 280px;
  max-height: 340px;
  overflow-y: auto;
  box-shadow: var(--shadow, 0 10px 30px rgba(0,0,0,.35));
  scrollbar-width: none;
  transform-origin: top center;
  opacity: 1;
  transform: none;
  transition: opacity 160ms cubic-bezier(.23,1,.32,1), transform 200ms cubic-bezier(.23,1,.32,1);
}
@starting-style { .ct-dropdown { opacity: 0; transform: translateY(-6px) scale(.98); } }
.ct-dropdown::-webkit-scrollbar { display: none; }
.ct-dropdown-item {
  display: grid;
  grid-template-columns: 1fr auto 70px;
  align-items: center;
  padding: 9px 10px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  border-radius: 14px;
  transition: background-color .12s;
  gap: 10px;
}
.ct-dropdown-item:hover,
.ct-dropdown-item.selected { background: var(--surface2, #21261b); }
.ct-dropdown-item.selected { box-shadow: inset 0 0 0 1px var(--accent-text, #c6ff00); }
.ct-dropdown-item .sym  { color: var(--fg, #f3f6ea); font-weight: 700; font-family: 'Inter', sans-serif; font-size: 14px; display: block; }
.ct-dropdown-item .name { color: var(--muted, #9aa38c); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ct-dropdown-item .prc  { text-align: right; color: var(--fg, #f3f6ea); font-weight: 600; }
.ct-dropdown-item .chg  { text-align: right; font-size: 11px; font-weight: 600; }
.ct-dropdown-item .chg.up   { color: var(--accent-text, #c6ff00); }
.ct-dropdown-item .chg.down { color: var(--neg, #ff6b5e); }
.ct-dropdown-empty {
  padding: 18px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--muted, #9aa38c);
  text-align: center;
}
@media (prefers-reduced-motion: reduce) { .ct-dropdown { transition: none; } }
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

function esc(x){return String(x==null?'':x).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
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
      dropdown.innerHTML = `<div class="ct-dropdown-empty">No results for "${esc(inputEl.value)}"</div>`;
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
          <span class="sym">${s.base}</span>
          <div class="name">${esc(name)}</div>
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
