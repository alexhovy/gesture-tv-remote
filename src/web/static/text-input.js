const tvKeyboardOverlay = document.getElementById("tv-keyboard-overlay");
const tvKeyboardCapture = document.getElementById("tv-keyboard-capture");
const TV_SYNC_DELAY_MS = 650;

let tvTextCapabilities = {};
let tvTextActive = false;
let tvManualTextEnabled = false;
let tvTextQueue = Promise.resolve();
let tvTextEvents = null;
let tvTextPoll = null;
let tvSyncTimer = null;
let tvSyncInFlight = false;
let tvPendingSyncValue = null;
let tvLastSyncValue = "";

initTvKeyboardCapture();

async function initTvKeyboardCapture() {
  if (!tvKeyboardOverlay || !tvKeyboardCapture) {
    return;
  }
  tvKeyboardCapture.addEventListener("input", handleTvCaptureInput);
  tvKeyboardCapture.addEventListener("keydown", handleTvCaptureKeydown);
  tvKeyboardCapture.addEventListener("focus", () => {
    showTvKeyboardOverlay();
    postTvTextClientLog("debug", "keyboard capture focused", {
      active: tvTextActive,
      manual: tvManualTextEnabled,
      valueLength: tvKeyboardCapture.value.length,
    });
  });
  tvKeyboardCapture.addEventListener("blur", (event) => {
    postTvTextClientLog("debug", "keyboard capture blurred", {
      active: tvTextActive,
      manual: tvManualTextEnabled,
      relatedTarget: elementLogName(event.relatedTarget),
      valueLength: tvKeyboardCapture.value.length,
    });
  });
  document.addEventListener("focusout", handleTvDocumentFocusOut);
  document.addEventListener("visibilitychange", handleTvVisibilityChange);
  document.addEventListener("keydown", handleTvDocumentKeydown);
  document.addEventListener("pointerup", handleTvDocumentPointerUp);
  document.addEventListener("click", handleTvDocumentClick);
  window.focusTvKeyboardCapture = focusTvKeyboardCapture;
  window.isTvTextCaptureEnabled = isTvTextCaptureEnabled;
  window.dismissTvKeyboardCapture = deactivateTvKeyboardCapture;
  await loadTvTextCapabilities();
  await loadTvTextStatus();
  await resetTvTextSession();
  connectTvTextEvents();
}

async function loadTvTextCapabilities() {
  try {
    const response = await fetch("/api/remote/capabilities");
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    tvTextCapabilities = payload.textInput || {};
    tvManualTextEnabled = shouldEnableManualTextCapture();
    postTvTextClientLog("debug", "keyboard capture capabilities loaded", {
      browserCapture: tvTextCapabilities.browserCapture || "",
      deleteText: tvTextCapabilities.deleteText || "",
      focusDetection: tvTextCapabilities.focusDetection || "",
      manual: tvManualTextEnabled,
      replaceText: tvTextCapabilities.replaceText || "",
      sendText: tvTextCapabilities.sendText || "",
    });
  } catch {
    tvTextCapabilities = {};
    tvManualTextEnabled = false;
  }
}

async function loadTvTextStatus() {
  try {
    const response = await fetch("/api/remote/text/status");
    if (!response.ok) {
      return;
    }
    applyTvTextStatus(await response.json());
  } catch {
    deactivateTvKeyboardCapture();
  }
}

function connectTvTextEvents() {
  if (!window.EventSource) {
    tvTextPoll = window.setInterval(loadTvTextStatus, 2500);
    return;
  }
  tvTextEvents = new EventSource("/api/remote/text/events");
  tvTextEvents.onmessage = (event) => {
    applyTvTextStatus(JSON.parse(event.data));
  };
  tvTextEvents.onerror = () => {
    if (!tvTextPoll) {
      tvTextPoll = window.setInterval(loadTvTextStatus, 2500);
    }
  };
}

function applyTvTextStatus(payload) {
  const active = Boolean(payload.active);
  tvTextActive = active;
  if (!active) {
    if (tvManualTextEnabled) {
      return;
    }
    deactivateTvKeyboardCapture();
    return;
  }
  setTvCaptureValue(payload.value || "");
  if (tvTextCapabilities.browserCapture === "auto_focus") {
    focusTvKeyboardCapture();
  } else {
    showTvKeyboardOverlay();
  }
}

function handleTvCaptureInput(event) {
  if (!isTvTextCaptureEnabled()) {
    resetTvCapture();
    return;
  }
  handleTvCaptureValueChanged({
    inputType: event.inputType || "",
    source: "input",
  });
}

function handleTvCaptureKeydown(event) {
  if (!isTvTextCaptureEnabled()) {
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    commitTvCaptureValue();
    queueTvSubmit();
    resetTvCapture();
    hideTvKeyboardOverlay();
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    deactivateTvKeyboardCapture();
  }
}

function handleTvDocumentKeydown(event) {
  if (!isTvTextCaptureEnabled() || document.activeElement === tvKeyboardCapture) {
    return;
  }
  if (event.ctrlKey || event.metaKey || event.altKey) {
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    commitTvCaptureValue();
    queueTvSubmit();
    resetTvCapture();
    hideTvKeyboardOverlay();
    return;
  }
  if (event.key === "Backspace") {
    event.preventDefault();
    setTvCaptureValue(tvKeyboardCapture.value.slice(0, -1), { sync: true });
    return;
  }
  if (event.key.length === 1) {
    event.preventDefault();
    showTvKeyboardOverlay();
    setTvCaptureValue(tvKeyboardCapture.value + event.key, { sync: true });
  }
}

function handleTvDocumentPointerUp(event) {
  if (!isTvTextCaptureEnabled()) {
    return;
  }
  if (event.target === tvKeyboardCapture) {
    return;
  }
  if (isTvKeyboardDismissTarget(event.target)) {
    return;
  }
  focusTvKeyboardCapture({ force: true, source: "pointerup" });
}

function handleTvDocumentClick(event) {
  if (!isTvTextCaptureEnabled()) {
    return;
  }
  if (event.target === tvKeyboardCapture) {
    return;
  }
  if (isTvKeyboardDismissTarget(event.target)) {
    return;
  }
  focusTvKeyboardCapture({ force: true, source: "click" });
}

function handleTvDocumentFocusOut(event) {
  if (event.target !== tvKeyboardCapture) {
    return;
  }
  postTvTextClientLog("debug", "keyboard capture focusout", {
    active: tvTextActive,
    manual: tvManualTextEnabled,
    relatedTarget: elementLogName(event.relatedTarget),
    valueLength: tvKeyboardCapture.value.length,
  });
}

function handleTvVisibilityChange() {
  postTvTextClientLog("debug", "keyboard capture visibility changed", {
    active: tvTextActive,
    focused: document.activeElement === tvKeyboardCapture,
    manual: tvManualTextEnabled,
    valueLength: tvKeyboardCapture.value.length,
    visibilityState: document.visibilityState,
  });
}

function setTvCaptureValue(value, options = {}) {
  tvKeyboardCapture.value = value;
  if (options.sync) {
    handleTvCaptureValueChanged({ source: "programmatic" });
  } else {
    tvLastSyncValue = value;
  }
}

function handleTvCaptureValueChanged(details) {
  scheduleTvSync(tvKeyboardCapture.value, details);
}

function commitTvCaptureValue() {
  tvPendingSyncValue = tvKeyboardCapture.value;
  flushTvSyncNow();
}

function scheduleTvSync(value, details) {
  if (value === tvLastSyncValue && !tvSyncInFlight) {
    return;
  }
  tvPendingSyncValue = value;
  if (tvSyncTimer) {
    window.clearTimeout(tvSyncTimer);
  }
  postTvTextClientLog("debug", "keyboard text sync queued", {
    ...details,
    valueLength: value.length,
  });
  tvSyncTimer = window.setTimeout(flushTvSyncNow, TV_SYNC_DELAY_MS);
}

function flushTvSyncNow() {
  if (tvSyncTimer) {
    window.clearTimeout(tvSyncTimer);
    tvSyncTimer = null;
  }
  if (tvPendingSyncValue === null || tvSyncInFlight) {
    return;
  }
  void sendNextTvSync();
}

async function sendNextTvSync() {
  if (tvPendingSyncValue === null || tvSyncInFlight) {
    return;
  }
  tvSyncInFlight = true;
  const value = tvPendingSyncValue;
  tvPendingSyncValue = null;
  try {
    await sendTvTextAction(
      "/api/remote/text/sync",
      { text: value },
      "sync",
      value.length,
    );
    tvLastSyncValue = value;
  } catch (error) {
    tvPendingSyncValue = value;
    postTvTextClientLog("error", "keyboard text sync failed", {
      message: error.message || String(error),
      valueLength: value.length,
    });
  } finally {
    tvSyncInFlight = false;
  }
  if (tvPendingSyncValue !== null && tvPendingSyncValue !== tvLastSyncValue) {
    void sendNextTvSync();
  }
}

async function resetTvTextSession() {
  resetTvCapture();
  try {
    await sendTvTextAction("/api/remote/text/sync", { text: "" }, "reset", 0);
    tvLastSyncValue = "";
  } catch (error) {
    postTvTextClientLog("error", "keyboard text reset failed", {
      message: error.message || String(error),
    });
  }
}

function queueTvSubmit() {
  tvPendingSyncValue = null;
  void sendTvTextAction("/api/remote/text/submit", {}, "submit", 0).catch(
    (error) => {
      postTvTextClientLog("error", "keyboard text submit failed", {
        message: error.message || String(error),
      });
    },
  );
}

async function sendTvTextAction(url, payload, action, size) {
  tvTextQueue = tvTextQueue.catch(() => {}).then(() =>
    performTvTextAction(url, payload, action, size),
  );
  return tvTextQueue;
}

async function performTvTextAction(url, payload, action, size) {
  postTvTextClientLog("debug", "keyboard text action queued", { action, size });
  const response = await fetch(url, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Text failed: ${response.status}`);
  }
  const result = await response.json();
  if (!result.accepted) {
    throw new Error(result.reason || "Text failed");
  }
  postTvTextClientLog("debug", "keyboard text action sent", { action, size });
}

function focusTvKeyboardCapture(options = {}) {
  if (tvTextCapabilities.sendText !== "implemented") {
    postTvTextClientLog("debug", "keyboard capture focus skipped", {
      reason: "send_text_unsupported",
    });
    return;
  }
  if (!options.force && tvTextCapabilities.browserCapture !== "auto_focus") {
    postTvTextClientLog("debug", "keyboard capture focus skipped", {
      browserCapture: tvTextCapabilities.browserCapture || "",
      reason: "manual_capture_requires_user_gesture",
    });
    return;
  }
  showTvKeyboardOverlay();
  tvKeyboardCapture.removeAttribute("tabindex");
  tvKeyboardCapture.focus({ preventScroll: true });
  postTvTextClientLog("debug", "keyboard capture focus requested", {
    active: tvTextActive,
    browserCapture: tvTextCapabilities.browserCapture || "",
    focused: document.activeElement === tvKeyboardCapture,
    forced: Boolean(options.force),
    manual: tvManualTextEnabled,
    source: options.source || "",
    valueLength: tvKeyboardCapture.value.length,
  });
}

function deactivateTvKeyboardCapture() {
  tvTextActive = false;
  resetTvCapture();
  hideTvKeyboardOverlay();
  if (document.activeElement === tvKeyboardCapture) {
    tvKeyboardCapture.blur();
  }
  tvKeyboardCapture.setAttribute("tabindex", "-1");
}

function resetTvCapture() {
  tvKeyboardCapture.value = "";
  tvLastSyncValue = "";
  tvPendingSyncValue = null;
  if (tvSyncTimer) {
    window.clearTimeout(tvSyncTimer);
    tvSyncTimer = null;
  }
}

function showTvKeyboardOverlay() {
  tvKeyboardOverlay.classList.add("active");
  postTvTextClientLog("debug", "keyboard overlay shown", {
    activeClass: tvKeyboardOverlay.classList.contains("active"),
    valueLength: tvKeyboardCapture.value.length,
  });
}

function hideTvKeyboardOverlay() {
  tvKeyboardOverlay.classList.remove("active");
  postTvTextClientLog("debug", "keyboard overlay hidden", {
    activeClass: tvKeyboardOverlay.classList.contains("active"),
    valueLength: tvKeyboardCapture.value.length,
  });
}

function isTvTextCaptureEnabled() {
  return tvTextActive || tvManualTextEnabled;
}

function shouldEnableManualTextCapture() {
  if (tvTextCapabilities.sendText !== "implemented") {
    return false;
  }
  return (
    tvTextCapabilities.focusDetection !== "implemented" ||
    tvTextCapabilities.browserCapture === "hardware_keys"
  );
}

function elementLogName(element) {
  if (!(element instanceof Element)) {
    return "";
  }
  const id = element.id ? `#${element.id}` : "";
  const command = element.dataset?.command || element.dataset?.commandOptions || "";
  const commandSuffix = command ? `[${command}]` : "";
  return `${element.tagName.toLowerCase()}${id}${commandSuffix}`;
}

function isTvKeyboardDismissTarget(target) {
  if (!(target instanceof Element)) {
    return false;
  }
  const commandElement = target.closest("[data-command], [data-command-options]");
  if (!commandElement) {
    return false;
  }
  const commands = commandElement.dataset.commandOptions
    ? commandElement.dataset.commandOptions.split(" ")
    : [commandElement.dataset.command || ""];
  return commands.some((command) =>
    ["BACK", "HOME", "POWER_TOGGLE", "POWER_OFF", "POWER_ON"].includes(command),
  );
}

function postTvTextClientLog(level, message, details) {
  fetch("/api/log/client", {
    body: JSON.stringify({ level, message, details }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  }).catch(() => {});
}
