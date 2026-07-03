const preview = document.getElementById("preview");
const overlay = document.getElementById("overlay");
const overlayContext = overlay.getContext("2d");
const empty = document.getElementById("empty");
const statusLabel = document.getElementById("status");
const connectButton = document.getElementById("connect");
const disconnectButton = document.getElementById("disconnect");

let stream = null;
let peerConnection = null;
let debugEvents = null;
let latestDebug = null;
let debugStreamLoggedOpen = false;
let debugStreamLoggedError = false;

connectButton.addEventListener("click", connect);
disconnectButton.addEventListener("click", disconnect);
window.addEventListener("resize", drawDebugOverlay);
preview.addEventListener("loadedmetadata", drawDebugOverlay);

async function connect() {
  setStatus("Requesting devices");
  connectButton.disabled = true;
  try {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      const details = {
        href: window.location.href,
        isSecureContext: window.isSecureContext,
        hasMediaDevices: Boolean(navigator.mediaDevices),
        userAgent: navigator.userAgent,
      };
      await postClientLog(
        "error",
        "media devices unavailable",
        details
      );
      throw new Error(
        "Camera and microphone require HTTPS, localhost, and a supported browser."
      );
    }

    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
      video: {
        facingMode: "user",
        frameRate: { ideal: 30, max: 30 },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });

    preview.srcObject = stream;
    empty.classList.add("hidden");
    startDebugEvents();

    peerConnection = new RTCPeerConnection({ iceServers: [] });
    for (const track of stream.getTracks()) {
      peerConnection.addTrack(track, stream);
    }

    peerConnection.addEventListener("connectionstatechange", () => {
      setStatus(peerConnection.connectionState);
      if (
        peerConnection.connectionState === "failed" ||
        peerConnection.connectionState === "closed" ||
        peerConnection.connectionState === "disconnected"
      ) {
        disconnect();
      }
    });

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    await waitForIceGathering(peerConnection);

    const response = await fetch("/api/control/offer", {
      body: JSON.stringify(peerConnection.localDescription),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`Signaling failed: ${response.status}`);
    }

    const answer = await response.json();
    await peerConnection.setRemoteDescription(answer);
    disconnectButton.disabled = false;
    setStatus("connected");
    await postClientLog("info", "browser control connected", {
      tracks: stream.getTracks().map((track) => track.kind),
    });
  } catch (error) {
    await postClientLog("error", "browser control connection failed", {
      message: error.message || String(error),
    });
    setStatus(error.message || "Connection failed");
    disconnect();
  }
}

function disconnect() {
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }
  if (stream) {
    for (const track of stream.getTracks()) {
      track.stop();
    }
    stream = null;
  }
  stopDebugEvents();
  preview.srcObject = null;
  empty.classList.remove("hidden");
  latestDebug = null;
  clearOverlay();
  connectButton.disabled = false;
  disconnectButton.disabled = true;
  if (statusLabel.textContent !== "connected") {
    return;
  }
  setStatus("Disconnected");
}

function waitForIceGathering(pc) {
  if (pc.iceGatheringState === "complete") {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    function checkState() {
      if (pc.iceGatheringState === "complete") {
        pc.removeEventListener("icegatheringstatechange", checkState);
        resolve();
      }
    }
    pc.addEventListener("icegatheringstatechange", checkState);
  });
}

function setStatus(value) {
  statusLabel.textContent = value;
}

function startDebugEvents() {
  stopDebugEvents();
  debugStreamLoggedOpen = false;
  debugStreamLoggedError = false;
  debugEvents = new EventSource("/api/control/debug");
  debugEvents.onopen = async () => {
    if (debugStreamLoggedOpen) {
      return;
    }
    debugStreamLoggedOpen = true;
    await postClientLog("info", "debug stream connected", {
      readyState: debugEvents.readyState,
    });
  };
  debugEvents.onmessage = (event) => {
    latestDebug = JSON.parse(event.data);
    drawDebugOverlay();
  };
  debugEvents.onerror = async () => {
    if (debugStreamLoggedError || !debugEvents) {
      return;
    }
    debugStreamLoggedError = true;
    await postClientLog("error", "debug stream error", {
      readyState: debugEvents.readyState,
    });
  };
}

function stopDebugEvents() {
  if (debugEvents) {
    debugEvents.close();
    debugEvents = null;
  }
}

function drawDebugOverlay() {
  const area = layoutPreviewFrame();
  resizeOverlayCanvas();
  clearOverlay();
  if (!latestDebug || !area || !overlayContext) {
    return;
  }

  const ratio = window.devicePixelRatio || 1;
  overlayContext.save();
  try {
    overlayContext.setTransform(ratio, 0, 0, ratio, 0, 0);
    overlayContext.translate(area.x, area.y);
    overlayContext.lineWidth = 2;
    drawHands(latestDebug.hands || [], area.width, area.height);
    drawPointer(latestDebug.pointer, displayCrop(), area.width, area.height);
    drawVolume(latestDebug.volume, displayCrop(), area.width, area.height);
    drawDebugText(latestDebug, area.width, area.height);
  } finally {
    overlayContext.restore();
  }
}

function clearOverlay() {
  if (!overlayContext) {
    return;
  }
  overlayContext.save();
  try {
    overlayContext.setTransform(1, 0, 0, 1, 0, 0);
    overlayContext.clearRect(0, 0, overlay.width, overlay.height);
  } finally {
    overlayContext.restore();
  }
}

function resizeOverlayCanvas() {
  const rect = overlay.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(rect.width * ratio));
  const height = Math.max(1, Math.round(rect.height * ratio));
  if (overlay.width !== width) {
    overlay.width = width;
  }
  if (overlay.height !== height) {
    overlay.height = height;
  }
}

function layoutPreviewFrame() {
  const area = containedPreviewArea();
  if (!area) {
    return null;
  }

  const crop = displayCrop();
  const videoWidth = area.width / crop.width;
  const videoHeight = area.height / crop.height;
  preview.style.left = `${area.x - crop.x * videoWidth}px`;
  preview.style.top = `${area.y - crop.y * videoHeight}px`;
  preview.style.width = `${videoWidth}px`;
  preview.style.height = `${videoHeight}px`;
  return area;
}

function containedPreviewArea() {
  if (!preview.videoWidth || !preview.videoHeight) {
    return null;
  }
  const stage = preview.parentElement.getBoundingClientRect();
  const videoRatio = preview.videoWidth / preview.videoHeight;
  const stageRatio = stage.width / stage.height;
  let width = stage.width;
  let height = stage.height;
  let x = 0;
  let y = 0;
  if (stageRatio > videoRatio) {
    width = height * videoRatio;
    x = (stage.width - width) / 2;
  } else {
    height = width / videoRatio;
    y = (stage.height - height) / 2;
  }
  return { x, y, width, height };
}

function displayCrop() {
  return normalizedCrop(latestDebug?.displayCrop);
}

function normalizedCrop(crop) {
  const x = clamp(crop?.x ?? 0, 0, 0.99);
  const y = clamp(crop?.y ?? 0, 0, 0.99);
  const maxWidth = 1 - x;
  const maxHeight = 1 - y;
  return {
    x,
    y,
    width: Math.max(0.01, Math.min(crop?.width ?? 1, maxWidth)),
    height: Math.max(0.01, Math.min(crop?.height ?? 1, maxHeight)),
  };
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(Number(value) || 0, maximum));
}

function drawHands(hands, width, height) {
  for (const landmarks of hands) {
    overlayContext.strokeStyle = "#00dc55";
    overlayContext.fillStyle = "#f04b4b";
    for (const [start, end] of HAND_CONNECTIONS) {
      const a = landmarks[start];
      const b = landmarks[end];
      if (!a || !b) {
        continue;
      }
      drawLine(point(a, width, height), point(b, width, height));
    }
    for (const landmark of landmarks) {
      const p = point(landmark, width, height);
      circle(p.x, p.y, 4, "#f04b4b", true);
    }
  }
}

function drawPointer(pointer, crop, width, height) {
  if (!pointer?.anchor) {
    return;
  }
  const anchor = pointToCropPixels(pointer.anchor, crop, width, height);
  const current = pointer.current
    ? pointToCropPixels(pointer.current, crop, width, height)
    : null;
  const neutral = distanceToCropPixels(pointer.neutralDistance, crop, width, height);
  const activationX = xDistanceToCropPixels(pointer.activationDistance, crop, width);
  const activationY = yDistanceToCropPixels(pointer.activationDistance, crop, height);
  const color = debugColor(pointer);

  circle(anchor.x, anchor.y, neutral, "#ffe05d", false);
  drawLine({ x: anchor.x - activationX, y: 0 }, { x: anchor.x - activationX, y: height }, "#ffb347", 1);
  drawLine({ x: anchor.x + activationX, y: 0 }, { x: anchor.x + activationX, y: height }, "#ffb347", 1);
  drawLine({ x: 0, y: anchor.y - activationY }, { x: width, y: anchor.y - activationY }, "#ffb347", 1);
  drawLine({ x: 0, y: anchor.y + activationY }, { x: width, y: anchor.y + activationY }, "#ffb347", 1);
  drawLine({ x: 0, y: anchor.y }, { x: width, y: anchor.y }, "#909090", 1);
  drawLine({ x: anchor.x, y: 0 }, { x: anchor.x, y: height }, "#909090", 1);
  circle(anchor.x, anchor.y, 5, color, true);
  if (current) {
    drawLine(anchor, current, color, 2);
    circle(current.x, current.y, 6, "#ffffff", false);
  }
  label(pointer.activeGesture || pointer.candidateGesture || pointer.phase, 8, height - 12, color);
}

function drawVolume(volume, crop, width, height) {
  if (!volume || volume.anchorY === null || volume.anchorY === undefined) {
    return;
  }
  const anchorY = yToCropPixels(volume.anchorY, crop, height);
  const visualAnchor = volume.anchor
    ? pointToCropPixels(volume.anchor, crop, width, height)
    : null;
  const anchorX = visualAnchor ? visualAnchor.x : width / 2;
  const anchor = { x: anchorX, y: anchorY };
  const current = volume.current
    ? pointToCropPixels(volume.current, crop, width, height)
    : null;
  const neutral = yDistanceToCropPixels(volume.neutralDistance, crop, height);
  const activation = yDistanceToCropPixels(volume.activationDistance, crop, height);
  const color = debugColor(volume);

  drawLine({ x: 0, y: anchorY - neutral }, { x: width, y: anchorY - neutral }, "#ffe05d", 2);
  drawLine({ x: 0, y: anchorY + neutral }, { x: width, y: anchorY + neutral }, "#ffe05d", 2);
  drawLine({ x: 0, y: anchorY - activation }, { x: width, y: anchorY - activation }, "#ffb347", 1);
  drawLine({ x: 0, y: anchorY + activation }, { x: width, y: anchorY + activation }, "#ffb347", 1);
  drawLine({ x: 0, y: anchorY }, { x: width, y: anchorY }, "#909090", 1);
  circle(anchor.x, anchor.y, 5, color, true);
  if (current) {
    drawLine(anchor, current, color, 2);
    circle(current.x, current.y, 6, "#ffffff", false);
  }
  label(volume.activeGesture || volume.candidateGesture || volume.phase, 8, height - 12, color);
}

function drawDebugText(snapshot, width) {
  overlayContext.font = "13px system-ui, sans-serif";
  overlayContext.textBaseline = "top";
  const text = snapshot.debugMessage || "";
  const metrics = overlayContext.measureText(text);
  overlayContext.fillStyle = "rgba(0, 0, 0, 0.62)";
  overlayContext.fillRect(8, 8, Math.min(metrics.width + 16, width - 16), 26);
  overlayContext.fillStyle = "#eef4f0";
  overlayContext.fillText(text, 16, 14, width - 32);
}

function point(value, width, height) {
  return {
    x: value.x * width,
    y: value.y * height,
  };
}

function pointToCropPixels(value, crop, width, height) {
  return {
    x: ((value.x - crop.x) / crop.width) * width,
    y: ((value.y - crop.y) / crop.height) * height,
  };
}

function yToCropPixels(value, crop, height) {
  return ((value - crop.y) / crop.height) * height;
}

function distanceToCropPixels(distance, crop, width, height) {
  return Math.max(
    0,
    Math.min(
      xDistanceToCropPixels(distance, crop, width),
      yDistanceToCropPixels(distance, crop, height)
    )
  );
}

function xDistanceToCropPixels(distance, crop, width) {
  return Math.max(0, (distance / crop.width) * width);
}

function yDistanceToCropPixels(distance, crop, height) {
  return Math.max(0, (distance / crop.height) * height);
}

function drawLine(start, end, color = overlayContext.strokeStyle, width = 2) {
  overlayContext.strokeStyle = color;
  overlayContext.lineWidth = width;
  overlayContext.beginPath();
  overlayContext.moveTo(start.x, start.y);
  overlayContext.lineTo(end.x, end.y);
  overlayContext.stroke();
}

function circle(x, y, radius, color, filled) {
  overlayContext.beginPath();
  overlayContext.arc(x, y, radius, 0, Math.PI * 2);
  if (filled) {
    overlayContext.fillStyle = color;
    overlayContext.fill();
    return;
  }
  overlayContext.strokeStyle = color;
  overlayContext.stroke();
}

function label(text, x, y, color) {
  overlayContext.font = "13px system-ui, sans-serif";
  overlayContext.fillStyle = color;
  overlayContext.fillText(text || "", x, y);
}

function debugColor(debug) {
  if (debug.activeGesture) {
    return "#ffa500";
  }
  if (debug.blockedReason === "rearmed") {
    return "#ffe05d";
  }
  if (debug.blockedReason) {
    return "#f04b4b";
  }
  if (debug.armed) {
    return "#00dc55";
  }
  return "#a0a0a0";
}

async function postClientLog(level, message, details = {}) {
  try {
    await fetch("/api/log/client", {
      body: JSON.stringify({ level, message, details }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
  } catch (error) {
    console.debug("client log failed", error);
  }
}

const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];
