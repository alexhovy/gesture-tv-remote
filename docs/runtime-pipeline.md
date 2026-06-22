# Runtime Pipeline

The gesture runtime stays concurrent because camera capture, hand detection,
window rendering, and TV network commands run at different speeds.

## Pipelines

`GestureRemoteService` is the top-level orchestrator. It creates and owns these
runtime collaborators:

| Pipeline | Responsibility |
| --- | --- |
| `FrameCapturePipeline` | Starts the latest-frame camera source, flips frames, and applies the current zoom crop for detection and display. |
| `DetectionPipeline` | Converts BGR frames to RGB and submits them to MediaPipe live-stream detection. |
| `GestureDecisionPipeline` | Projects hand states back from the active detection crop, evaluates the domain session, and updates auto-zoom for the next frame. |
| `CommandDispatchPipeline` | Applies gesture debounce, starts voice capture for `MIC`, and enqueues TV key commands. |
| `DisplayPipeline` | Draws detected hand landmarks and renders the OpenCV preview window. |
| `PipelineMetrics` | Tracks lightweight counters and timings for debug diagnostics. |

Pipeline implementations live in `src/services/pipelines/`. The service module
keeps lifecycle, config reload, and cleanup logic in one place while frame,
detection, gesture, command, and display details stay in focused modules.

## Concurrency Model

Camera capture runs in one dedicated thread. It continuously reads from OpenCV
and stores only the newest frame. The service loop consumes versioned latest
frames; if frame versions jump, older frames are counted as dropped instead of
being processed late.

MediaPipe hand tracking runs in live-stream mode. The runtime submits the
current detection frame and consumes the latest completed result. Detection and
display use the same auto-zoom crop so pointer and volume motion use the same
visual frame that the user sees. Once pointer or volume motion has established
an anchor, auto-zoom crop updates are paused until the anchor clears; this keeps
the visual neutral center fixed during motion and dropout grace.

The preview smooths only the drawn landmark overlay in original-frame
coordinates and holds it briefly through dropped detection frames. Gesture
decisions still use the current MediaPipe result.

TV commands are sent by one bounded async dispatcher task. Slow TV network
calls, reconnects, or adapter retries do not block camera capture, hand
detection, gesture decisions, or display rendering.

Samsung and Roku clients use one thread-bound executor each because their
libraries are synchronous. That keeps each TV connection opened, used, retried,
and closed on one worker thread.

Voice capture runs only when requested by the `MIC` gesture and only when the
selected adapter can provide a voice stream. Its audio queue is bounded and
drops stale chunks.

Shutdown is owned by `GestureRemoteService._cleanup`. It cancels voice capture,
stops frame capture, closes MediaPipe, releases the camera, closes OpenCV
windows, stops command dispatch, and disconnects the TV adapter.

## Diagnostics

Set `GESTURE_TV_VERBOSE_PIPELINE_DIAGNOSTICS=true` to emit periodic pipeline
metrics in debug logs. `GESTURE_TV_METRICS_LOG_SECONDS` controls the log
interval.

Metrics include:

- camera FPS
- detection time per frame
- gesture decision time
- detection crop mode
- command dispatch queue depth
- command send latency
- dropped command count
- dropped/stale frame count
- active TV adapter
- current gesture decision

The metrics are internal counters and timers. The app does not use a heavy
observability framework.
