from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "Gesture TV Remote"
    tv_ip: str = "192.168.0.5"
    cert_file: Path = Path("certs/cert.pem")
    key_file: Path = Path("certs/key.pem")
    model_file: Path = Path("models/hand_landmarker.task")
    model_url: str = (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task"
    )
    debounce_seconds: float = 1.0
    home_chord_seconds: float = 0.35
    pointer_distance: float = 0.08
    pointer_dominance: float = 1.15
    volume_distance: float = 0.16
    pinch_distance_ratio: float = 0.22
    voice_capture_seconds: float = 5.0
    debug_log_seconds: float = 0.5
    webcam_index: int = 0
    max_hands: int = 2
    min_hand_detection_confidence: float = 0.7
    min_hand_presence_confidence: float = 0.7
    min_tracking_confidence: float = 0.7


DEFAULT_CONFIG = AppConfig()


def load_config_from_env(environ: dict[str, str] | None = None) -> AppConfig:
    values = os.environ if environ is None else environ
    defaults = AppConfig()

    return AppConfig(
        app_name=values.get("GESTURE_TV_APP_NAME", defaults.app_name),
        tv_ip=values.get("GESTURE_TV_IP", defaults.tv_ip),
        cert_file=_path(values, "GESTURE_TV_CERT_FILE", defaults.cert_file),
        key_file=_path(values, "GESTURE_TV_KEY_FILE", defaults.key_file),
        model_file=_path(values, "GESTURE_TV_MODEL_FILE", defaults.model_file),
        model_url=values.get("GESTURE_TV_MODEL_URL", defaults.model_url),
        debounce_seconds=_float(values, "GESTURE_TV_DEBOUNCE_SECONDS", defaults.debounce_seconds),
        home_chord_seconds=_float(
            values,
            "GESTURE_TV_HOME_CHORD_SECONDS",
            defaults.home_chord_seconds,
        ),
        pointer_distance=_float(
            values,
            "GESTURE_TV_POINTER_DISTANCE",
            defaults.pointer_distance,
        ),
        pointer_dominance=_float(
            values,
            "GESTURE_TV_POINTER_DOMINANCE",
            defaults.pointer_dominance,
        ),
        volume_distance=_float(
            values,
            "GESTURE_TV_VOLUME_DISTANCE",
            defaults.volume_distance,
        ),
        pinch_distance_ratio=_float(
            values,
            "GESTURE_TV_PINCH_DISTANCE_RATIO",
            defaults.pinch_distance_ratio,
        ),
        voice_capture_seconds=_float(
            values,
            "GESTURE_TV_VOICE_CAPTURE_SECONDS",
            defaults.voice_capture_seconds,
        ),
        debug_log_seconds=_float(
            values,
            "GESTURE_TV_DEBUG_LOG_SECONDS",
            defaults.debug_log_seconds,
        ),
        webcam_index=_int(values, "GESTURE_TV_WEBCAM_INDEX", defaults.webcam_index),
        max_hands=_int(values, "GESTURE_TV_MAX_HANDS", defaults.max_hands),
        min_hand_detection_confidence=_float(
            values,
            "GESTURE_TV_MIN_HAND_DETECTION_CONFIDENCE",
            defaults.min_hand_detection_confidence,
        ),
        min_hand_presence_confidence=_float(
            values,
            "GESTURE_TV_MIN_HAND_PRESENCE_CONFIDENCE",
            defaults.min_hand_presence_confidence,
        ),
        min_tracking_confidence=_float(
            values,
            "GESTURE_TV_MIN_TRACKING_CONFIDENCE",
            defaults.min_tracking_confidence,
        ),
    )


def _path(values: dict[str, str], name: str, default: Path) -> Path:
    raw_value = values.get(name)
    return Path(raw_value) if raw_value else default


def _float(values: dict[str, str], name: str, default: float) -> float:
    raw_value = values.get(name)
    return float(raw_value) if raw_value else default


def _int(values: dict[str, str], name: str, default: int) -> int:
    raw_value = values.get(name)
    return int(raw_value) if raw_value else default
