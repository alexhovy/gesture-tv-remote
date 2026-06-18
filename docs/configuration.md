# Configuration

Runtime defaults live in `src/shared/config.py` as `AppConfig`. The application
loads those defaults and applies environment-variable overrides at startup.

The current defaults preserve the MVP behavior:

- TV IP: `192.168.0.5`
- webcam index: `0`
- model file: `models/hand_landmarker.task`
- cert file: `certs/cert.pem`
- key file: `certs/key.pem`

## Certificates

Pairing certificates are stored in `certs/`. They are ignored by git because
they identify a paired TV session.

On first pairing, `androidtvremote2` generates:

- `certs/cert.pem`
- `certs/key.pem`

Do not commit those files.

## Model File

On first run, the app downloads Google's `hand_landmarker.task` model into
`models/`. The file is ignored by git.

## Environment Variables

| Variable | Default |
| --- | --- |
| `GESTURE_TV_APP_NAME` | `Gesture TV Remote` |
| `GESTURE_TV_IP` | `192.168.0.5` |
| `GESTURE_TV_CERT_FILE` | `certs/cert.pem` |
| `GESTURE_TV_KEY_FILE` | `certs/key.pem` |
| `GESTURE_TV_MODEL_FILE` | `models/hand_landmarker.task` |
| `GESTURE_TV_MODEL_URL` | MediaPipe hand landmarker URL |
| `GESTURE_TV_WEBCAM_INDEX` | `0` |
| `GESTURE_TV_CAMERA_ZOOM` | `1.0` |
| `GESTURE_TV_AUTO_ZOOM_ENABLED` | `False` |
| `GESTURE_TV_AUTO_ZOOM_MIN` | `1.0` |
| `GESTURE_TV_AUTO_ZOOM_MAX` | `2.0` |
| `GESTURE_TV_AUTO_ZOOM_PADDING` | `0.45` |
| `GESTURE_TV_AUTO_ZOOM_SMOOTHING` | `0.15` |
| `GESTURE_TV_MAX_HANDS` | `2` |
| `GESTURE_TV_DEBOUNCE_SECONDS` | `1.0` |
| `GESTURE_TV_HOME_CHORD_SECONDS` | `0.35` |
| `GESTURE_TV_POINTER_DISTANCE_RATIO` | `0.45` |
| `GESTURE_TV_POINTER_MIN_DISTANCE` | `0.04` |
| `GESTURE_TV_POINTER_MAX_DISTANCE` | `0.14` |
| `GESTURE_TV_POINTER_DOMINANCE` | `1.15` |
| `GESTURE_TV_VOLUME_DISTANCE_RATIO` | `0.9` |
| `GESTURE_TV_VOLUME_MIN_DISTANCE` | `0.08` |
| `GESTURE_TV_VOLUME_MAX_DISTANCE` | `0.28` |
| `GESTURE_TV_PINCH_DISTANCE_RATIO` | `0.22` |
| `GESTURE_TV_VOICE_CAPTURE_SECONDS` | `5.0` |
| `GESTURE_TV_DEBUG_LOG_SECONDS` | `0.5` |
| `GESTURE_TV_PRIMARY_LOST_GRACE_SECONDS` | `0.35` |
| `GESTURE_TV_MIN_HAND_DETECTION_CONFIDENCE` | `0.7` |
| `GESTURE_TV_MIN_HAND_PRESENCE_CONFIDENCE` | `0.7` |
| `GESTURE_TV_MIN_TRACKING_CONFIDENCE` | `0.7` |

Example:

```bash
GESTURE_TV_IP=10.0.0.25 GESTURE_TV_WEBCAM_INDEX=1 python main.py
```

Pointer and volume movement thresholds are scaled from the detected secondary
hand size, then clamped by their min/max distance settings. This keeps gestures
more consistent when the user moves closer to or farther from the camera.

`GESTURE_TV_CAMERA_ZOOM` applies digital center-crop zoom before MediaPipe hand
tracking. Values above `1.0` make hands larger in the tracking input, which can
help finger landmark reliability when the camera is far away. Start with `1.5`;
larger values reduce the field of view and can crop out two-hand gestures.

Set `GESTURE_TV_AUTO_ZOOM_ENABLED=true` to let the displayed crop follow the
last detected hand area. Auto zoom does not change the MediaPipe tracking input;
tracking uses the stable `GESTURE_TV_CAMERA_ZOOM` crop. This prevents display
zoom from cropping hands out of the detector input while it follows movement.

`GESTURE_TV_PRIMARY_LOST_GRACE_SECONDS` keeps an active gesture session alive
through brief primary-hand detection dropouts. This helps when a hand is close
to a frame or crop edge and MediaPipe occasionally reports zero hands for a
frame or two. Once the primary hand is missing longer than the grace interval,
the session deactivates normally.
