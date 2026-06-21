# Runtime Pipeline

The gesture runtime stays concurrent because camera capture, hand detection,
window rendering, and TV network commands run at different speeds.

## Pipelines

`GestureRemoteService` is the top-level orchestrator. It creates and owns these
runtime collaborators:

| Pipeline | Responsibility |
| --- | --- |
| `FrameCapturePipeline` | Starts the latest-frame camera source, flips frames, and creates detection/display crops. |
| `DetectionPipeline` | Converts BGR frames to RGB and submits them to MediaPipe live-stream detection. |
| `GestureDecisionPipeline` | Projects hand states back to original frame space, evaluates the domain session, and updates auto-zoom. |
| `CommandDispatchPipeline` | Applies gesture debounce, starts voice capture for `MIC`, and enqueues TV key commands. |
| `DisplayPipeline` | Draws detected hand landmarks and renders the OpenCV preview window. |
| `PipelineMetrics` | Tracks lightweight counters and timings for debug diagnostics. |

## Concurrency Model

Camera capture runs in one dedicated thread. It continuously reads from OpenCV
and stores only the newest frame. The service loop consumes versioned latest
frames; if frame versions jump, older frames are counted as dropped instead of
being processed late.

MediaPipe hand tracking runs in live-stream mode. The runtime submits the
current detection frame and consumes the latest completed result. This lets
MediaPipe skip work when detection is slower than camera capture.

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
- command dispatch queue depth
- command send latency
- dropped/stale frame count
- active TV adapter
- current gesture decision

The metrics are internal counters and timers. The app does not use a heavy
observability framework.
