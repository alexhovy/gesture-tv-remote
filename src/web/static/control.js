const preview = document.getElementById("preview");
const empty = document.getElementById("empty");
const statusLabel = document.getElementById("status");
const connectButton = document.getElementById("connect");
const disconnectButton = document.getElementById("disconnect");

let stream = null;
let peerConnection = null;

connectButton.addEventListener("click", connect);
disconnectButton.addEventListener("click", disconnect);

async function connect() {
  setStatus("Requesting devices");
  connectButton.disabled = true;
  try {
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
  } catch (error) {
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
  preview.srcObject = null;
  empty.classList.remove("hidden");
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
