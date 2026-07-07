const statusLabel = document.getElementById("status");
const commandButtons = Array.from(
  document.querySelectorAll("[data-command], [data-command-options]"),
);
const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));
const modePanels = Array.from(document.querySelectorAll("[data-panel]"));
const touchpad = document.getElementById("touchpad");
const keyboardDismissCommands = new Set([
  "BACK",
  "HOME",
  "POWER_TOGGLE",
  "POWER_OFF",
  "POWER_ON",
]);

let supportedCommands = new Set();
let pointerStart = null;

loadCapabilities();

for (const button of commandButtons) {
  button.addEventListener("click", async () => {
    await sendCommand(commandForButton(button));
  });
}

for (const button of modeButtons) {
  button.addEventListener("click", () => {
    activateMode(button.dataset.mode);
    restoreKeyboardCaptureFocus();
  });
}

if (touchpad) {
  touchpad.addEventListener("pointerdown", (event) => {
    pointerStart = { x: event.clientX, y: event.clientY };
    touchpad.setPointerCapture(event.pointerId);
  });
  touchpad.addEventListener("pointerup", async (event) => {
    if (!pointerStart) {
      return;
    }
    const command = commandFromTouch(pointerStart, {
      x: event.clientX,
      y: event.clientY,
    });
    pointerStart = null;
    if (command) {
      await sendCommand(command);
    }
  });
  touchpad.addEventListener("keydown", async (event) => {
    const commandsByKey = {
      ArrowDown: "DPAD_DOWN",
      ArrowLeft: "DPAD_LEFT",
      ArrowRight: "DPAD_RIGHT",
      ArrowUp: "DPAD_UP",
      Enter: "DPAD_CENTER",
      " ": "DPAD_CENTER",
    };
    const command = commandsByKey[event.key];
    if (command) {
      event.preventDefault();
      await sendCommand(command);
    }
  });
}

async function loadCapabilities() {
  try {
    const response = await fetch("/api/remote/capabilities");
    if (!response.ok) {
      throw new Error(`Capabilities failed: ${response.status}`);
    }
    const payload = await response.json();
    supportedCommands = new Set(payload.supportedCommands || []);
    for (const button of commandButtons) {
      button.disabled = !commandForButton(button);
    }
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message || "Capabilities unavailable");
  }
}

async function sendCommand(command) {
  if (!supportedCommands.has(command)) {
    setStatus("Unsupported");
    return;
  }
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
  } finally {
    if (keyboardDismissCommands.has(command)) {
      dismissKeyboardCapture();
    } else {
      restoreKeyboardCaptureFocus();
    }
  }
}

function activateMode(mode) {
  for (const button of modeButtons) {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const panel of modePanels) {
    panel.classList.toggle("active", panel.dataset.panel === mode);
  }
}

function commandFromTouch(start, end) {
  const deltaX = end.x - start.x;
  const deltaY = end.y - start.y;
  const distance = Math.hypot(deltaX, deltaY);
  if (distance < 24) {
    return "DPAD_CENTER";
  }
  if (Math.abs(deltaX) > Math.abs(deltaY)) {
    return deltaX > 0 ? "DPAD_RIGHT" : "DPAD_LEFT";
  }
  return deltaY > 0 ? "DPAD_DOWN" : "DPAD_UP";
}

function commandForButton(button) {
  const commands = button.dataset.commandOptions
    ? button.dataset.commandOptions.split(" ")
    : [button.dataset.command];
  return commands.find((command) => supportedCommands.has(command)) || "";
}

function setStatus(value) {
  statusLabel.textContent = value;
}

function restoreKeyboardCaptureFocus() {
  if (
    typeof window.isTvTextCaptureEnabled !== "function" ||
    typeof window.focusTvKeyboardCapture !== "function" ||
    !window.isTvTextCaptureEnabled()
  ) {
    return;
  }
  window.focusTvKeyboardCapture({ force: true, source: "remote_restore" });
}

function dismissKeyboardCapture() {
  if (typeof window.dismissTvKeyboardCapture === "function") {
    window.dismissTvKeyboardCapture();
  }
}
