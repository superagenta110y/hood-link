const dot = document.getElementById("dot");
const statusText = document.getElementById("status-text");
const serverUrlInput = document.getElementById("server-url");
const toggleEnabled = document.getElementById("toggle-enabled");

function updateUI(data) {
  const connected = data.connected || false;
  dot.className = "dot " + (connected ? "connected" : "disconnected");
  statusText.textContent = connected ? "Connected" : "Disconnected";
  if (data.serverUrl) serverUrlInput.value = data.serverUrl;
  if (data.enabled !== undefined) toggleEnabled.checked = data.enabled;
}

// Load current status
chrome.runtime.sendMessage({ type: "get_status" }, updateUI);

// Toggle enabled
toggleEnabled.addEventListener("change", () => {
  chrome.runtime.sendMessage({
    type: "set_enabled",
    enabled: toggleEnabled.checked,
  });
});

// Update server URL on blur
serverUrlInput.addEventListener("change", () => {
  chrome.runtime.sendMessage({
    type: "set_server_url",
    serverUrl: serverUrlInput.value,
  });
});
