const statusLabel = document.getElementById("status");
const commandButtons = Array.from(document.querySelectorAll("[data-command]"));

loadCapabilities();

for (const button of commandButtons) {
  button.addEventListener("click", async () => {
    await sendCommand(button.dataset.command);
  });
}

async function loadCapabilities() {
  try {
    const response = await fetch("/api/remote/capabilities");
    if (!response.ok) {
      throw new Error(`Capabilities failed: ${response.status}`);
    }
    const payload = await response.json();
    const supported = new Set(payload.supportedCommands || []);
    for (const button of commandButtons) {
      button.disabled = !supported.has(button.dataset.command);
    }
  } catch (error) {
    setStatus(error.message || "Capabilities unavailable");
  }
}

async function sendCommand(command) {
  setStatus(command);
  try {
    const response = await fetch("/api/remote/commands", {
      body: JSON.stringify({ command }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
    const payload = await response.json();
    if (!response.ok || !payload.accepted) {
      throw new Error(payload.reason || `Command failed: ${response.status}`);
    }
    setStatus("Sent");
  } catch (error) {
    setStatus(error.message || "Command failed");
  }
}

function setStatus(value) {
  statusLabel.textContent = value;
}
