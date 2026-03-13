// Injected into page context — has access to Robinhood's auth context
// Intercepts RH's auth token and executes fetch() calls on behalf of the server

(function () {
  let authToken = null;

  // ── Auth token capture ──────────────────────────────────────────────────

  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    const [resource, init] = args;
    const url = typeof resource === "string" ? resource : resource?.url || "";

    if (url.includes("robinhood.com") && init?.headers) {
      let authHeader = null;
      if (init.headers instanceof Headers) {
        authHeader = init.headers.get("Authorization") || init.headers.get("authorization");
      } else if (Array.isArray(init.headers)) {
        const entry = init.headers.find(([k]) => k.toLowerCase() === "authorization");
        if (entry) authHeader = entry[1];
      } else if (typeof init.headers === "object") {
        authHeader = init.headers["Authorization"] || init.headers["authorization"];
      }
      if (authHeader && authHeader.startsWith("Bearer ")) {
        authToken = authHeader;
      }
    }

    return originalFetch.apply(this, args);
  };

  // ── Robinhood dxFeed connection (one persistent WS, managed here) ───────

  const RH_STREAM_URL = "wss://api.robinhood.com/marketdata/streaming/legend/v2/";

  const EVENT_FIELDS = {
    Trade:    ["price", "dayVolume", "eventSymbol", "eventType", "time"],
    TradeETH: ["price", "dayVolume", "eventSymbol", "eventType", "time"],
    Quote:    ["askPrice", "askSize", "askTime", "bidPrice", "bidSize", "bidTime", "eventSymbol", "eventType"],
    Candle:   ["close", "eventFlags", "eventSymbol", "eventType", "eventTime", "high",
               "impVolatility", "low", "open", "openInterest", "volume"],
    Order:    ["eventFlags", "eventSymbol", "eventType", "index", "side", "sequence", "price", "size", "time"],
    Summary:  ["dayHighPrice", "dayLowPrice", "dayOpenPrice", "dayClosePrice", "eventSymbol", "eventType", "openInterest"],
  };

  const _rh = {
    ws: null,
    connectId: null,        // correlation id of pending rh_connect command
    authorized: false,
    channelReady: {},       // event_type → Promise<channel_number>
    nextChannel: 1,
    subs: {},               // "symbol|type" → sub object
    keepaliveTimer: null,
    authTimer: null,
  };

  function _rhSend(msg) {
    if (_rh.ws && _rh.ws.readyState === WebSocket.OPEN) {
      _rh.ws.send(JSON.stringify(msg));
    }
  }

  function _rhPostBack(id, data, error) {
    window.postMessage({
      source: "hoodlink-inject",
      payload: { id, status: error ? 0 : 200, data: data || {}, error: error || null },
    }, "*");
  }

  function _rhPostEvent(data) {
    window.postMessage({
      source: "hoodlink-inject",
      payload: { channel: "rh_event", data },
    }, "*");
  }

  function _rhPostStatus(connected, error) {
    window.postMessage({
      source: "hoodlink-inject",
      payload: { channel: "rh_status", data: { connected, error: error || null } },
    }, "*");
  }

  function _rhSubEntry(sub) {
    const entry = { symbol: sub.symbol, type: sub.type };
    if (sub.from_time != null) entry.fromTime = sub.from_time;
    if (sub.instrument_type)  entry.instrumentType = sub.instrument_type;
    if (sub.type === "Order") entry.source = sub.source || "NTV";
    return entry;
  }

  // Returns a Promise<channel_number>; creates the channel the first time
  function _rhEnsureChannel(eventType) {
    if (_rh.channelReady[eventType]) return _rh.channelReady[eventType];

    const ch = _rh.nextChannel;
    _rh.nextChannel += 2;

    const promise = new Promise((resolve, reject) => {
      // Resolve when CHANNEL_OPENED arrives
      _rh.channelPending = _rh.channelPending || {};
      _rh.channelPending[ch] = resolve;
      _rhSend({ type: "CHANNEL_REQUEST", channel: ch, service: "FEED", parameters: { contract: "AUTO" } });
    }).then(() => {
      _rhSend({ type: "FEED_SETUP", channel: ch, acceptAggregationPeriod: 0.25 });
      if (EVENT_FIELDS[eventType]) {
        _rhSend({
          type: "FEED_SETUP", channel: ch, acceptAggregationPeriod: 0.25,
          acceptEventFields: { [eventType]: EVENT_FIELDS[eventType] },
        });
      }
      return ch;
    });

    _rh.channelReady[eventType] = promise;
    return promise;
  }

  async function _rhResubscribeAll() {
    const byType = {};
    for (const sub of Object.values(_rh.subs)) {
      (byType[sub.type] = byType[sub.type] || []).push(sub);
    }
    for (const [eventType, subs] of Object.entries(byType)) {
      const ch = await _rhEnsureChannel(eventType);
      _rhSend({
        type: "FEED_SUBSCRIPTION", channel: ch, reset: true,
        add: subs.map(_rhSubEntry),
      });
    }
  }

  function _rhDisconnect() {
    if (_rh.keepaliveTimer) { clearInterval(_rh.keepaliveTimer); _rh.keepaliveTimer = null; }
    if (_rh.authTimer)      { clearTimeout(_rh.authTimer);      _rh.authTimer = null; }
    if (_rh.ws) { try { _rh.ws.close(); } catch {} _rh.ws = null; }
    _rh.authorized = false;
    _rh.channelReady = {};
    _rh.channelPending = {};
    _rh.nextChannel = 1;
    _rh.subs = {};
  }

  function _rhHandleMessage(msg) {
    const t = msg.type;
    if (t === "AUTH_STATE") {
      if (msg.state === "AUTHORIZED") {
        _rh.authorized = true;
        _rhPostStatus(true, null);
        _rhResubscribeAll().catch(e => console.error("[HoodLink] resubscribe error:", e));
      } else if (msg.state === "UNAUTHORIZED") {
        if (_rh.authorized) {
          // Auth was revoked after a successful session — treat as disconnect
          _rh.authorized = false;
          _rhPostStatus(false, "Robinhood auth revoked");
        }
        // else: initial UNAUTHORIZED is always sent before AUTHORIZED — ignore it
      }
    } else if (t === "CHANNEL_OPENED") {
      const resolver = (_rh.channelPending || {})[msg.channel];
      if (resolver) { resolver(); delete _rh.channelPending[msg.channel]; }
    } else if (t === "FEED_DATA") {
      for (const event of (msg.data || [])) _rhPostEvent(event);
    }
  }

  // ── Message handler ─────────────────────────────────────────────────────

  window.addEventListener("message", async (event) => {
    if (event.source !== window) return;
    if (!event.data || event.data.source !== "hoodlink-content") return;

    const command = event.data.payload;
    console.log("[HoodLink] command received:", command?.action, command?.id?.slice(0, 8));

    // ── get_token ──
    if (command.action === "get_token") {
      window.postMessage({
        source: "hoodlink-inject",
        payload: {
          id: command.id, status: 200,
          data: { token: authToken },
          error: authToken ? null : "No auth token captured yet — browse Robinhood first",
        },
      }, "*");
      return;
    }

    // ── rh_connect: open (or reopen) the single Robinhood dxFeed WebSocket ──
    if (command.action === "rh_connect") {
      _rhDisconnect();

      if (!authToken) {
        _rhPostBack(command.id, null, "No auth token captured — browse Robinhood first");
        return;
      }

      _rh.connectId = command.id;
      // sec-websocket-protocol: "bearer, <jwt>" requires two separate protocol strings
      const [scheme, jwt] = authToken.split(" ");
      let ws;
      try {
        console.log("[HoodLink] opening RH WebSocket, scheme:", scheme.toLowerCase());
        ws = new WebSocket(RH_STREAM_URL, [scheme.toLowerCase(), jwt]);
        console.log("[HoodLink] WebSocket created, readyState:", ws.readyState);
      } catch (err) {
        console.error("[HoodLink] WebSocket constructor threw:", err);
        _rhPostBack(command.id, null, "Failed to open WebSocket: " + (err.message || String(err)));
        _rh.connectId = null;
        return;
      }
      _rh.ws = ws;

      // Respond to rh_connect as soon as the socket opens (≤5s), not waiting for full auth.
      // Auth state is reported asynchronously via rh_status channel.
      _rh.authTimer = setTimeout(() => {
        if (_rh.connectId) {
          _rhPostBack(_rh.connectId, null, "WebSocket failed to open within 5s");
          _rh.connectId = null;
        }
        _rhPostStatus(false, "open timeout");
      }, 5000);

      ws.onopen = () => {
        // ACK rh_connect immediately — the server can proceed
        if (_rh.authTimer) { clearTimeout(_rh.authTimer); _rh.authTimer = null; }
        if (_rh.connectId) { _rhPostBack(_rh.connectId, { opened: true }, null); _rh.connectId = null; }
        _rhSend({ acceptKeepaliveTimeout: 60, channel: 0, keepaliveTimeout: 60, type: "SETUP", version: "0.1-DXF-JS/0.5.1" });
        _rhSend({ channel: 0, token: command.stream_token, type: "AUTH" });
        _rhSend({ enable_heartbeat_timestamp: true, enable_logging_raw_incoming_message: false, enable_subscription_debugging: false, type: "MD_SETUP" });
        _rh.keepaliveTimer = setInterval(() => _rhSend({ type: "KEEPALIVE", channel: 0 }), 30000);
      };

      ws.onmessage = (evt) => {
        try { _rhHandleMessage(JSON.parse(evt.data)); } catch {}
      };

      ws.onclose = (evt) => {
        _rh.ws = null;
        _rh.authorized = false;
        if (_rh.keepaliveTimer) { clearInterval(_rh.keepaliveTimer); _rh.keepaliveTimer = null; }
        if (_rh.authTimer)      { clearTimeout(_rh.authTimer);      _rh.authTimer = null; }
        if (_rh.connectId) {
          _rhPostBack(_rh.connectId, null, `WebSocket closed before auth: ${evt.code} ${evt.reason}`);
          _rh.connectId = null;
        }
        _rhPostStatus(false, `closed: ${evt.code}`);
      };

      ws.onerror = () => {
        _rhPostStatus(false, "WebSocket error");
      }; // onclose also fires after onerror
      return;
    }

    // ── rh_get_subs: return current active subscriptions ──
    if (command.action === "rh_get_subs") {
      _rhPostBack(command.id, { subscriptions: Object.values(_rh.subs) }, null);
      return;
    }

    // ── rh_subscribe ──
    if (command.action === "rh_subscribe") {
      for (const sub of (command.subscriptions || [])) {
        _rh.subs[sub.symbol + "|" + sub.type] = sub;
        if (_rh.authorized) {
          _rhEnsureChannel(sub.type).then(ch => {
            _rhSend({ type: "FEED_SUBSCRIPTION", channel: ch, reset: false, add: [_rhSubEntry(sub)] });
          }).catch(e => console.error("[HoodLink] subscribe channel error:", e));
        }
      }
      _rhPostBack(command.id, { subscribed: (command.subscriptions || []).length }, null);
      return;
    }

    // ── rh_unsubscribe ──
    if (command.action === "rh_unsubscribe") {
      for (const sub of (command.subscriptions || [])) {
        const key = sub.symbol + "|" + sub.type;
        const existing = _rh.subs[key];
        if (existing) {
          delete _rh.subs[key];
          if (_rh.authorized) {
            _rhEnsureChannel(sub.type).then(ch => {
              _rhSend({ type: "FEED_SUBSCRIPTION", channel: ch, reset: false, remove: [_rhSubEntry(existing)] });
            }).catch(() => {});
          }
        }
      }
      _rhPostBack(command.id, { unsubscribed: (command.subscriptions || []).length }, null);
      return;
    }

    // ── rh_disconnect ──
    if (command.action === "rh_disconnect") {
      _rhDisconnect();
      _rhPostBack(command.id, { disconnected: true }, null);
      return;
    }

    // ── fetch (existing REST proxy) ──
    if (command.action !== "fetch") return;

    try {
      const headers = { Accept: "application/json", ...command.headers };
      if (authToken && !headers["Authorization"]) headers["Authorization"] = authToken;

      const fetchOpts = { method: command.method || "GET", credentials: "include", headers };
      if (command.body && command.method !== "GET") {
        headers["Content-Type"] = "application/json";
        fetchOpts.body = JSON.stringify(command.body);
      }

      const response = await originalFetch(command.url, fetchOpts);
      const contentType = response.headers.get("content-type") || "";
      const data = contentType.includes("application/json") ? await response.json() : await response.text();

      window.postMessage({
        source: "hoodlink-inject",
        payload: { id: command.id, status: response.status, data, error: null },
      }, "*");
    } catch (err) {
      window.postMessage({
        source: "hoodlink-inject",
        payload: { id: command.id, status: 0, data: null, error: err.message || String(err) },
      }, "*");
    }
  });

  console.log("[HoodLink] Inject script loaded — intercepting auth tokens");
})();
