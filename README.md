# CYPHER_TERMINAL

Веб-термінал для аналізу криптовалютних спредів, funding rates та цін по біржах.

## Структура

```
cypher_terminal/
├── app.py              — Flask бекенд (API проксі)
├── requirements.txt    — Python залежності
├── static/
│   ├── index.html      — Головна (топ монети)
│   ├── prices.html     — Ціни по біржах
│   ├── spread.html     — Спред сканер ★
│   ├── funding.html    — Funding rates
│   ├── converter.html  — Конвертер
│   └── chart.html      — TradingView графік
```

## Запуск

### 1. Встановити залежності
```bash
pip install -r requirements.txt
```

### 2. Запустити Flask сервер
```bash
python app.py
```
Сервер стартує на `http://localhost:5000`

### 3. Відкрити сайт
Відкрий у браузері: `http://localhost:5000`

---

## API Endpoints

| Endpoint | Опис |
|----------|------|
| `GET /api/market` | Топ-10 монет + глобальна статистика |
| `GET /api/prices?symbol=BTCUSDT` | Ціни символу з усіх бірж |
| `GET /api/spread` | Розрахунок спредів між біржами |
| `GET /api/funding` | Funding rates (Binance + Bybit) |
| `GET /api/rates` | Курси для конвертера |
| `GET /api/health` | Статус сервера |

## Біржі

- **Binance** — spot + futures funding
- **Bybit** — spot + linear perps funding
- **MEXC** — spot
- **Gate.io** — spot

## Технології

- **Backend**: Python 3, Flask, requests (паралельні запити через ThreadPoolExecutor)
- **Frontend**: HTML5, TailwindCSS, Vanilla JS
- **Графіки**: TradingView Widget
- **Шрифти**: Geist, JetBrains Mono
