// Content script — runs on robinhood.com pages
// Manages WebSocket to Hood-link server and message routing to/from inject.js

(function () {
  const RECONNECT_BASE_DELAY = 1000;
  const RECONNECT_MAX_DELAY = 30000;

  let ws = null;
  let reconnectDelay = RECONNECT_BASE_DELAY;
  let reconnectTimer = null;
  let enabled = true;
  let serverUrl = "ws://localhost:7878/bridge";

  // Inject the page-context script
  function injectScript() {
    const script = document.createElement("script");
    script.src = chrome.runtime.getURL("src/inject.js");
    script.onload = () => script.remove();
    (document.head || document.documentElement).appendChild(script);
  }

  // Load settings and start
  chrome.storage.local.get(["serverUrl", "enabled"], (data) => {
    if (data.serverUrl) serverUrl = data.serverUrl;
    if (data.enabled !== undefined) enabled = data.enabled;

    injectScript();
    if (enabled) connect();
  });

  // Listen for enable/disable from popup
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "enabled_changed") {
      enabled = msg.enabled;
      if (enabled) {
        connect();
      } else {
        disconnect();
      }
    }
  });

  function connect() {
    if (ws) return;

    try {
      ws = new WebSocket(serverUrl);
    } catch (e) {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      console.log("[Hood-link] Connected to server");
      reconnectDelay = RECONNECT_BASE_DELAY;
      updateStatus(true);
    };

    ws.onmessage = (event) => {
      // Forward command from server to inject.js via postMessage
      try {
        const msg = JSON.parse(event.data);
        window.postMessage({ source: "hoodlink-content", payload: msg }, "*");
      } catch (e) {
        console.error("[Hood-link] Failed to parse server message:", e);
      }
    };

    ws.onclose = () => {
      console.log("[Hood-link] Disconnected from server");
      ws = null;
      updateStatus(false);
      if (enabled) scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after this
    };
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    updateStatus(false);
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_DELAY);
      connect();
    }, reconnectDelay);
  }

  function updateStatus(connected) {
    chrome.runtime.sendMessage({ type: "status_update", connected });
  }

  // Listen for responses from inject.js
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    if (!event.data || event.data.source !== "hoodlink-inject") return;

    // Forward response back to server
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(event.data.payload));
    }
  });
})();
