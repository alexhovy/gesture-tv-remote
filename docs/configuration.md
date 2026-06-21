# Configuration

Runtime defaults live in `src/shared/config.py` as `AppConfig`. The application
loads those defaults, applies saved configuration from the local config database
when present, and then applies environment-variable overrides at startup.

The current defaults preserve the MVP behavior:

- TV adapter: `samsung`
- TV host: `192.168.8.7`
- config database file: `data/gesture_tv_remote.sqlite3`
- webcam index: `0`
- model file: `models/hand_landmarker.task`
- Android TV cert file: `certs/android/cert.pem`
- Android TV key file: `certs/android/key.pem`

## Pairing Credentials

Pairing credentials are stored in `certs/`. They are ignored by git because
they identify paired TV sessions.

On first Android TV pairing, `androidtvremote2` generates:

- `certs/android/cert.pem`
- `certs/android/key.pem`

Samsung tokens are stored in `certs/samsung/token.txt` by default. webOS client
keys are stored in `certs/webos/client_key.txt` by default.

Do not commit those files.

## TV Adapters

Set `GESTURE_TV_ADAPTER` to select the TV integration:

| Value | Library | Notes |
| --- | --- | --- |
| `androidtv` | `androidtvremote2` | Supports pairing, key commands, and voice capture. |
| `samsung` | `samsungtvws` | Supports key commands. Accept the pairing prompt on the TV when required. |
| `webos` | `aiowebostv` | Supports key commands. Accept the pairing prompt on the TV when required. |
| `roku` | `rokuecp` | Supports ECP key commands. |

The `MIC` gesture starts voice capture only when the selected adapter returns a
voice stream. Unsupported adapters log that microphone capture is skipped.

## Model File

On first run, the app downloads Google's `hand_landmarker.task` model into
`models/`. The file is ignored by git. Downloads use a bounded timeout and
retry count, write to a temporary file first, and atomically replace the final
model file only after a complete download.

## Config Database

The SQLite configuration database defaults to
`data/gesture_tv_remote.sqlite3`. The `data/` directory is ignored by git
because it contains local runtime state.

Startup config precedence is:

1. `AppConfig` defaults
2. saved config from the local database, when present
3. environment variables

`GESTURE_TV_CONFIG_DB` is read during bootstrap to decide which database file to
open, so it can point the app at a different saved configuration store.

## Environment Variables

| Variable | Default |
| --- | --- |
| `GESTURE_TV_APP_NAME` | `Gesture TV Remote` |
| `GESTURE_TV_CONFIG_DB` | `data/gesture_tv_remote.sqlite3` |
| `GESTURE_TV_ADAPTER` | `samsung` |
| `GESTURE_TV_HOST` | `192.168.8.7` |
| `GESTURE_TV_ANDROID_CERT_FILE` | `certs/android/cert.pem` |
| `GESTURE_TV_ANDROID_KEY_FILE` | `certs/android/key.pem` |
| `GESTURE_TV_SAMSUNG_TOKEN_FILE` | `certs/samsung/token.txt` |
| `GESTURE_TV_SAMSUNG_PORT` | `8002` |
| `GESTURE_TV_WEBOS_CLIENT_KEY_FILE` | `certs/webos/client_key.txt` |
| `GESTURE_TV_ROKU_PORT` | `8060` |
| `GESTURE_TV_MODEL_FILE` | `models/hand_landmarker.task` |
| `GESTURE_TV_MODEL_URL` | MediaPipe hand landmarker URL |
| `GESTURE_TV_MODEL_DOWNLOAD_TIMEOUT_SECONDS` | `20.0` |
| `GESTURE_TV_MODEL_DOWNLOAD_RETRIES` | `2` |
| `GESTURE_TV_WEBCAM_INDEX` | `0` |
| `GESTURE_TV_CAMERA_ZOOM` | `1.0` |
| `GESTURE_TV_AUTO_ZOOM_ENABLED` | `True` |
| `GESTURE_TV_AUTO_ZOOM_MIN` | `1.0` |
| `GESTURE_TV_AUTO_ZOOM_MAX` | `10.0` |
| `GESTURE_TV_AUTO_ZOOM_PADDING` | `0.5` |
| `GESTURE_TV_AUTO_ZOOM_SMOOTHING` | `0.1` |
| `GESTURE_TV_AUTO_ZOOM_POSITION_DEADBAND` | `0.08` |
| `GESTURE_TV_AUTO_ZOOM_SCALE_DEADBAND` | `0.12` |
| `GESTURE_TV_AUTO_ZOOM_CROP_RESET_THRESHOLD` | `0.08` |
| `GESTURE_TV_MAX_HANDS` | `2` |
| `GESTURE_TV_DEBOUNCE_SECONDS` | `0.3` |
| `GESTURE_TV_HOME_CHORD_SECONDS` | `0.35` |
| `GESTURE_TV_POINTER_DISTANCE_RATIO` | `0.25` |
| `GESTURE_TV_POINTER_MIN_DISTANCE` | `0.02` |
| `GESTURE_TV_POINTER_MAX_DISTANCE` | `0.08` |
| `GESTURE_TV_POINTER_DOMINANCE` | `1.0` |
| `GESTURE_TV_VOLUME_DISTANCE_RATIO` | `0.25` |
| `GESTURE_TV_VOLUME_MIN_DISTANCE` | `0.02` |
| `GESTURE_TV_VOLUME_MAX_DISTANCE` | `0.08` |
| `GESTURE_TV_PINCH_DISTANCE_RATIO` | `0.22` |
| `GESTURE_TV_REQUIRE_UPRIGHT_HANDS` | `True` |
| `GESTURE_TV_HAND_UPRIGHT_MAX_TILT_RATIO` | `0.75` |
| `GESTURE_TV_VOICE_CAPTURE_SECONDS` | `5.0` |
| `GESTURE_TV_DEBUG_LOG_SECONDS` | `0.5` |
| `GESTURE_TV_PRIMARY_LOST_GRACE_SECONDS` | `0.35` |
| `GESTURE_TV_MIN_HAND_DETECTION_CONFIDENCE` | `0.6` |
| `GESTURE_TV_MIN_HAND_PRESENCE_CONFIDENCE` | `0.6` |
| `GESTURE_TV_MIN_TRACKING_CONFIDENCE` | `0.6` |

Example:

```bash
GESTURE_TV_ADAPTER=samsung GESTURE_TV_HOST=10.0.0.25 GESTURE_TV_WEBCAM_INDEX=1 python main.py
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

Numeric settings are validated at startup. Zoom values must be at least `1.0`,
confidence values must be between `0.0` and `1.0`, max values must not be lower
than their matching min values, and durations or distances cannot be negative.
Boolean settings accept `1`, `true`, `yes`, `on`, `0`, `false`, `no`, and `off`.

`GESTURE_TV_REQUIRE_UPRIGHT_HANDS` and
`GESTURE_TV_HAND_UPRIGHT_MAX_TILT_RATIO` apply to both primary and secondary
hands. This prevents sideways or upside-down hands from activating controls or
being misclassified as command gestures.

`GESTURE_TV_PRIMARY_LOST_GRACE_SECONDS` keeps an active gesture session alive
through brief primary-hand detection dropouts. This helps when a hand is close
to a frame or crop edge and MediaPipe occasionally reports zero hands for a
frame or two. Once the primary hand is missing longer than the grace interval,
the session deactivates normally.
