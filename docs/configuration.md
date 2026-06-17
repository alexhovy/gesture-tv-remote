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
| `GESTURE_TV_MAX_HANDS` | `2` |
| `GESTURE_TV_DEBOUNCE_SECONDS` | `1.0` |
| `GESTURE_TV_HOME_CHORD_SECONDS` | `0.35` |
| `GESTURE_TV_POINTER_DISTANCE` | `0.08` |
| `GESTURE_TV_POINTER_DOMINANCE` | `1.15` |
| `GESTURE_TV_VOLUME_DISTANCE` | `0.16` |
| `GESTURE_TV_PINCH_DISTANCE_RATIO` | `0.22` |
| `GESTURE_TV_VOICE_CAPTURE_SECONDS` | `5.0` |
| `GESTURE_TV_DEBUG_LOG_SECONDS` | `0.5` |
| `GESTURE_TV_MIN_HAND_DETECTION_CONFIDENCE` | `0.7` |
| `GESTURE_TV_MIN_HAND_PRESENCE_CONFIDENCE` | `0.7` |
| `GESTURE_TV_MIN_TRACKING_CONFIDENCE` | `0.7` |

Example:

```bash
GESTURE_TV_IP=10.0.0.25 GESTURE_TV_WEBCAM_INDEX=1 python main.py
```
