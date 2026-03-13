<p align="center">
  <img src="logo.svg" alt="HoodLink" width="100" />
</p>

<h1 align="center">HoodLink</h1>

<p align="center">⚡ Local bridge to Robinhood's private API via a Chrome extension and a FastAPI server. ⚡</p>

## Table of Contents

- [📋 Prerequisites](#-prerequisites)
- [⚡ Quick Install (one-liner)](#-quick-install-one-liner)
- [📦 Prebuilt binaries (GitHub Releases)](#-prebuilt-binaries-github-releases)
- [🛠️ Setup](#️-setup)
- [💻 Usage](#-usage)
- [🔍 How It Works](#-how-it-works)
- [📡 API Endpoints](#-api-endpoints)
- [📶 Market Stream (WebSocket)](#-market-stream-websocket)
- [🔒 Security](#-security)
- [⚠️ Disclaimer](#️-disclaimer)

## 📋 Prerequisites

- Google Chrome
- A Robinhood account

## ⚡ Quick Install (one-liner)

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/superagenta110y/hood-link/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
iex ((New-Object Net.WebClient).DownloadString('https://raw.githubusercontent.com/superagenta110y/hood-link/main/install.ps1'))
```

These scripts download the latest repo zip, install dependencies, start the local server, and open HoodLink in your browser.

## 📦 Prebuilt binaries (GitHub Releases)

Download the latest release for your platform from the [GitHub Releases page](https://github.com/superagenta110y/hood-link/releases).

Each bundle includes the server executable, the `extension/` folder, `README.md`, and `LICENSE`.

## 🛠️ Setup

### 1. Server

#### a) From binary

Download a release bundle from the [Releases page](https://github.com/superagenta110y/hood-link/releases), unzip it, and run the executable:

- **Windows:** double-click `hoodlink-server.exe`, or run it from PowerShell
- **macOS / Linux:** `./hoodlink-server`

The dashboard opens automatically at http://127.0.0.1:7878.

#### b) From source

```bash
cd server
uv sync
```

Create a `.env` file (optional — defaults work for local use):

```bash
HOODLINK_API_KEY=changeme    # API key for authenticating requests
HOODLINK_HOST=127.0.0.1      # Bind address
HOODLINK_PORT=7878            # Port
HOODLINK_BRIDGE_TIMEOUT=10.0  # Seconds to wait for extension response
HOODLINK_LOG_LEVEL=info       # Logging level
HOODLINK_OPEN_BROWSER=true    # Auto-open dashboard in browser on server start
```

Start the server:

```bash
uv run uvicorn hoodlink.main:app --host 127.0.0.1 --port 7878
```

The dashboard UI is available at http://localhost:7878.

When the server starts, HoodLink automatically opens a browser tab. If the extension bridge is not connected yet, you'll be routed to `/setup` onboarding. Once the extension is detected on an active Robinhood tab, HoodLink automatically switches to the main dashboard.

### 2. Chrome Extension

Open the dashboard at http://127.0.0.1:7878 — it will walk you through installing the extension.

## 💻 Usage

All API endpoints are under `/api/v1/` and require the `X-API-Key` header.

```bash
# Check status
curl http://localhost:7878/api/v1/status

# Get a quote
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/market/quote/AAPL

# Get multiple quotes
curl -H "X-API-Key: changeme" "http://localhost:7878/api/v1/market/quotes?symbols=AAPL,GOOGL"

# Price history
curl -H "X-API-Key: changeme" "http://localhost:7878/api/v1/market/history/AAPL?interval=day&span=year"

# Fundamentals
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/market/fundamentals/AAPL

# Search instruments
curl -H "X-API-Key: changeme" "http://localhost:7878/api/v1/market/instruments?query=apple"

# Options expirations
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/market/options/expirations/AAPL

# Options chain (with market data stitched in)
curl -H "X-API-Key: changeme" "http://localhost:7878/api/v1/market/options/AAPL?expiration_dates=2026-03-20&type=call"

# Account info
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/account/accounts

# Portfolio
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/account/portfolio

# Positions
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/account/positions

# Options positions
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/account/options/positions

# List orders
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/trading/orders

# List options orders (with filters)
curl -H "X-API-Key: changeme" "http://localhost:7878/api/v1/trading/options/orders?state=filled"
curl -H "X-API-Key: changeme" "http://localhost:7878/api/v1/trading/options/orders?account_number=5PY28838&created_at_gte=2025-11-20T20:09:08.497Z"

# Get specific options order
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/trading/options/orders/{order-uuid}

# Place equity order
curl -X POST -H "X-API-Key: changeme" -H "Content-Type: application/json" \
  http://localhost:7878/api/v1/trading/orders \
  -d '{"symbol":"AAPL","side":"buy","quantity":1,"type":"limit","price":150.00}'

# Place options order
curl -X POST -H "X-API-Key: changeme" -H "Content-Type: application/json" \
  http://localhost:7878/api/v1/trading/options/orders \
  -d '{"option_url":"https://api.robinhood.com/options/instruments/{uuid}/","side":"buy","quantity":1,"price":0.50}'

# Place stop-limit options order
curl -X POST -H "X-API-Key: changeme" -H "Content-Type: application/json" \
  http://localhost:7878/api/v1/trading/options/orders \
  -d '{"option_url":"https://api.robinhood.com/options/instruments/{uuid}/","side":"sell","quantity":1,"price":7.00,"stop_price":7.00,"position_effect":"close","direction":"credit"}'

# Cancel order
curl -X DELETE -H "X-API-Key: changeme" http://localhost:7878/api/v1/trading/orders/{order-uuid}

# Cancel options order
curl -X DELETE -H "X-API-Key: changeme" http://localhost:7878/api/v1/trading/options/orders/{order-uuid}

# Positions
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/account/positions

# Portfolio
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/account/portfolio

# Place a limit order
curl -X POST -H "X-API-Key: changeme" -H "Content-Type: application/json" \
  http://localhost:7878/api/v1/trading/orders \
  -d '{"symbol":"AAPL","side":"buy","quantity":1,"type":"limit","price":150.00}'

# List orders
curl -H "X-API-Key: changeme" http://localhost:7878/api/v1/trading/orders

# Cancel an order
curl -X DELETE -H "X-API-Key: changeme" http://localhost:7878/api/v1/trading/orders/{order_id}
```

You can also use the built-in dashboard at http://localhost:7878 which provides a visual interface for all endpoints.

## 🔍 How It Works

```
                ┌─────────────────┐          ┌──────────────────┐          ┌─────────────────┐
                │                 │  REST /   │                  │          │                 │
                │     Client      │  WebSocket│  HoodLink Server │    WS    │ Chrome Extension│
                │  (your code)    ├──────────►│    (FastAPI)     ├─────────►│  (robinhood.com)│
                │                 │           │                  │          │                 │
                └────────┬────────┘          └────────┬─────────┘          └────────┬────────┘
                         │                            │                             │
                         │                            │                             │  fetch()
                         │                            │                             │  (authenticated)
                         │                            │                             ▼
                         │                            │                    ┌─────────────────┐
                         │         response           │      bridge WS    │                 │
                         └◄───────────────────────────┘◄──────────────────┤  Robinhood API  │
                                                                          │                 │
                                                                          └─────────────────┘
```

1. The **Chrome extension** runs on Robinhood.com and connects to the server via WebSocket
2. The **server** receives REST API requests and forwards them to the extension over the WebSocket bridge
3. The extension executes `fetch()` calls in the page context, inheriting the user's authenticated Robinhood session
4. Responses flow back through the bridge to the API client

The extension never stores or transmits credentials — it simply makes requests using the browser's existing authenticated session.

Because all requests originate from the legitimate authenticated browser tab (with the correct cookies, headers, and session context), they are indistinguishable from normal user activity as far as Robinhood's servers are concerned.

## 📡 API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/market/quote/{symbol}` | Current quote |
| GET | `/api/v1/market/quotes?symbols=X,Y` | Multiple quotes |
| GET | `/api/v1/market/history/{symbol}` | OHLCV price history |
| GET | `/api/v1/market/fundamentals/{symbol}` | Fundamentals |
| GET | `/api/v1/market/instruments?query=X` | Search instruments |
| GET | `/api/v1/market/options/expirations/{symbol}` | Options expiration dates |
| GET | `/api/v1/market/options/{symbol}` | Options chain with market data |
| GET | `/api/v1/market/options/marketdata` | Raw options market data |
| GET | `/api/v1/market/futures/products` | Futures products |
| GET | `/api/v1/market/futures/contracts` | Futures contracts |

### Trading
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/trading/orders` | Place equity order |
| POST | `/api/v1/trading/options/orders` | Place options order |
| GET | `/api/v1/trading/orders` | List orders |
| DELETE | `/api/v1/trading/orders/{id}` | Cancel order |

### Account
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/account/accounts` | Account info |
| GET | `/api/v1/account/positions` | Stock positions |
| GET | `/api/v1/account/portfolio` | Portfolio summary |
| GET | `/api/v1/account/options/positions` | Options positions |
| GET | `/api/v1/account/watchlists` | Watchlists |

### Status
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/status` | Server + bridge status |
| GET | `/api/v1/stream/status` | Stream connection + active subscriptions |
| WS | `/api/v1/stream` | Real-time market data stream |

## 📶 Market Stream (WebSocket)

Connect with your API key as a query param:

```
ws://127.0.0.1:7878/api/v1/stream?api_key=changeme
```

### Client → Server messages

**Subscribe** to one or more event types:

```json
{"action": "subscribe", "subscriptions": [
  {"symbol": "AAPL", "type": "Trade"},
  {"symbol": "AAPL", "type": "Quote"},
  {"symbol": "AAPL", "type": "Candle", "from_time": 1773344400000, "instrument_type": "equity"}
]}
```

**Unsubscribe:**

```json
{"action": "unsubscribe", "subscriptions": [
  {"symbol": "AAPL", "type": "Trade"}
]}
```

### Server → Client messages

#### `rh_status` — bridge/stream connection state

Sent immediately on connect and whenever the connection state changes.

```json
{"type": "rh_status", "connected": true, "subscriptions": [
  {"symbol": "AAPL", "type": "Trade"},
  {"symbol": "AAPL", "type": "Quote"}
]}
```

#### `subscribed` / `unsubscribed` — acknowledgement

```json
{"type": "subscribed",   "symbol": "AAPL", "eventType": "Trade"}
{"type": "unsubscribed", "symbol": "AAPL", "eventType": "Trade"}
```

#### `error`

```json
{"type": "error", "message": "bridge not connected"}
```

#### `Trade` — last sale

```json
{"eventType": "Trade", "eventSymbol": "AAPL", "price": 213.49, "dayVolume": 47832100, "time": 1773344599807}
```

#### `TradeETH` — extended-hours last sale

Same fields as `Trade`, emitted during pre/post-market sessions.

```json
{"eventType": "TradeETH", "eventSymbol": "AAPL", "price": 213.10, "dayVolume": 1204300, "time": 1773344400000}
```

#### `Quote` — NBBO bid/ask

```json
{"eventType": "Quote", "eventSymbol": "AAPL",
 "bidPrice": 213.48, "bidSize": 300, "bidTime": 1773344599700,
 "askPrice": 213.50, "askSize": 100, "askTime": 1773344599700}
```

#### `Candle` — OHLCV bar

Subscribe with `"type": "Candle"` and optionally `"from_time"` (epoch ms) and `"instrument_type"` (`"equity"` or `"option"`).

```json
{"eventType": "Candle", "eventSymbol": "AAPL{=5m}",
 "eventTime": 1773344400000, "eventFlags": 0,
 "open": 212.80, "high": 213.60, "low": 212.75, "close": 213.49,
 "volume": 980200, "impVolatility": 0.2341, "openInterest": 0}
```

#### `Summary` — daily OHLC summary

```json
{"eventType": "Summary", "eventSymbol": "AAPL",
 "dayOpenPrice": 211.50, "dayHighPrice": 214.20,
 "dayLowPrice": 211.10, "dayClosePrice": 213.49,
 "openInterest": 0}
```

#### `Order` — Level 2 order book entry

```json
{"eventType": "Order", "eventSymbol": "AAPL",
 "index": 1, "side": "Buy", "price": 213.48, "size": 300,
 "sequence": 42, "time": 1773344599807, "eventFlags": 0}
```

## 🔒 Security

HoodLink runs a plain **HTTP** server — there is no TLS/HTTPS. This means traffic between your client and the server is unencrypted and should never be exposed to the internet or untrusted networks.

**Recommended usage:**

- Run HoodLink only on `127.0.0.1` (localhost, the default) for single-machine use, or on a **private LAN** you control
- Never bind to `0.0.0.0` or forward port 7878 through a router or firewall
- If you need remote access, put it behind a reverse proxy with TLS (e.g. Caddy, nginx) or use a VPN

**API key:** All non-status endpoints require the `X-API-Key` header. Within a trusted LAN this provides meaningful access control — only clients with the key can invoke trades or read account data. If no key is configured, HoodLink automatically generates a strong random key tied to the machine at startup, so there is no weak default to worry about.

The extension-to-server WebSocket connection is local-only and not exposed to the internet.

## ⚠️ Disclaimer

This project is provided strictly for **educational and demonstrational purposes**.

By using HoodLink, you acknowledge and agree that:

- You are solely responsible for how you use this software.
- Trading can result in financial loss, including losses from automation mistakes.
- The HoodLink developers are **not responsible or liable** for misuse, account issues, service disruptions, losses, or any unintended trades.
- You should review all actions carefully and use this software at your own risk.
