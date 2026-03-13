// Service worker — manages extension lifecycle

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    serverUrl: "ws://localhost:7878/bridge",
    enabled: true,
  });
});

// Relay connection status from content script to popup
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "get_status") {
    chrome.storage.local.get(["connected", "enabled", "serverUrl"], (data) => {
      sendResponse(data);
    });
    return true;
  }

  if (msg.type === "status_update") {
    chrome.storage.local.set({ connected: msg.connected });
  }

  if (msg.type === "set_enabled") {
    chrome.storage.local.set({ enabled: msg.enabled });
    // Notify content scripts
    chrome.tabs.query({ url: "*://*.robinhood.com/*" }, (tabs) => {
      for (const tab of tabs) {
        chrome.tabs.sendMessage(tab.id, {
          type: "enabled_changed",
          enabled: msg.enabled,
        });
      }
    });
  }

  if (msg.type === "set_server_url") {
    chrome.storage.local.set({ serverUrl: msg.serverUrl });
  }
});
