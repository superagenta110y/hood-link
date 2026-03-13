// Injected into page context — has access to Robinhood's auth context
// Intercepts RH's auth token and executes fetch() calls on behalf of the server

(function () {
  let authToken = null;

  // Intercept RH's own fetch calls to capture the Authorization header
  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    const [resource, init] = args;
    const url = typeof resource === "string" ? resource : resource?.url || "";

    if (url.includes("robinhood.com") && init?.headers) {
      // Extract auth token from headers (could be Headers object, plain object, or array)
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

  // Listen for commands from content.js
  window.addEventListener("message", async (event) => {
    if (event.source !== window) return;
    if (!event.data || event.data.source !== "hoodlink-content") return;

    const command = event.data.payload;
    if (command.action !== "fetch") return;

    try {
      const headers = {
        Accept: "application/json",
        ...command.headers,
      };

      // Attach captured auth token
      if (authToken && !headers["Authorization"]) {
        headers["Authorization"] = authToken;
      }

      const fetchOpts = {
        method: command.method || "GET",
        credentials: "include",
        headers,
      };

      if (command.body && command.method !== "GET") {
        headers["Content-Type"] = "application/json";
        fetchOpts.body = JSON.stringify(command.body);
      }

      const response = await originalFetch(command.url, fetchOpts);

      let data;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      window.postMessage(
        {
          source: "hoodlink-inject",
          payload: {
            id: command.id,
            status: response.status,
            data: data,
            error: null,
          },
        },
        "*"
      );
    } catch (err) {
      window.postMessage(
        {
          source: "hoodlink-inject",
          payload: {
            id: command.id,
            status: 0,
            data: null,
            error: err.message || String(err),
          },
        },
        "*"
      );
    }
  });

  console.log("[HoodLink] Inject script loaded — intercepting auth tokens");
})();
