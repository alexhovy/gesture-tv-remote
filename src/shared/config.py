from dataclasses import dataclass
import os
from pathlib import Path


class EnvVar:
    APP_NAME = "GESTURE_TV_APP_NAME"
    TV_IP = "GESTURE_TV_IP"
    CERT_FILE = "GESTURE_TV_CERT_FILE"
    KEY_FILE = "GESTURE_TV_KEY_FILE"
    MODEL_FILE = "GESTURE_TV_MODEL_FILE"
    MODEL_URL = "GESTURE_TV_MODEL_URL"
    DEBOUNCE_SECONDS = "GESTURE_TV_DEBOUNCE_SECONDS"
    HOME_CHORD_SECONDS = "GESTURE_TV_HOME_CHORD_SECONDS"
    POINTER_DISTANCE_RATIO = "GESTURE_TV_POINTER_DISTANCE_RATIO"
    POINTER_MIN_DISTANCE = "GESTURE_TV_POINTER_MIN_DISTANCE"
    POINTER_MAX_DISTANCE = "GESTURE_TV_POINTER_MAX_DISTANCE"
    POINTER_DOMINANCE = "GESTURE_TV_POINTER_DOMINANCE"
    VOLUME_DISTANCE_RATIO = "GESTURE_TV_VOLUME_DISTANCE_RATIO"
    VOLUME_MIN_DISTANCE = "GESTURE_TV_VOLUME_MIN_DISTANCE"
    VOLUME_MAX_DISTANCE = "GESTURE_TV_VOLUME_MAX_DISTANCE"
    PINCH_DISTANCE_RATIO = "GESTURE_TV_PINCH_DISTANCE_RATIO"
    VOICE_CAPTURE_SECONDS = "GESTURE_TV_VOICE_CAPTURE_SECONDS"
    DEBUG_LOG_SECONDS = "GESTURE_TV_DEBUG_LOG_SECONDS"
    WEBCAM_INDEX = "GESTURE_TV_WEBCAM_INDEX"
    CAMERA_ZOOM = "GESTURE_TV_CAMERA_ZOOM"
    AUTO_ZOOM_ENABLED = "GESTURE_TV_AUTO_ZOOM_ENABLED"
    AUTO_ZOOM_MIN = "GESTURE_TV_AUTO_ZOOM_MIN"
    AUTO_ZOOM_MAX = "GESTURE_TV_AUTO_ZOOM_MAX"
    AUTO_ZOOM_PADDING = "GESTURE_TV_AUTO_ZOOM_PADDING"
    AUTO_ZOOM_SMOOTHING = "GESTURE_TV_AUTO_ZOOM_SMOOTHING"
    MAX_HANDS = "GESTURE_TV_MAX_HANDS"
    MIN_HAND_DETECTION_CONFIDENCE = "GESTURE_TV_MIN_HAND_DETECTION_CONFIDENCE"
    MIN_HAND_PRESENCE_CONFIDENCE = "GESTURE_TV_MIN_HAND_PRESENCE_CONFIDENCE"
    MIN_TRACKING_CONFIDENCE = "GESTURE_TV_MIN_TRACKING_CONFIDENCE"


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
    pointer_distance_ratio: float = 0.45
    pointer_min_distance: float = 0.04
    pointer_max_distance: float = 0.14
    pointer_dominance: float = 1.15
    volume_distance_ratio: float = 0.9
    volume_min_distance: float = 0.08
    volume_max_distance: float = 0.28
    pinch_distance_ratio: float = 0.22
    voice_capture_seconds: float = 5.0
    debug_log_seconds: float = 0.5
    webcam_index: int = 0
    camera_zoom: float = 1.0
    auto_zoom_enabled: bool = True
    auto_zoom_min: float = 1.0
    auto_zoom_max: float = 5.0
    auto_zoom_padding: float = 0.45
    auto_zoom_smoothing: float = 0.15
    max_hands: int = 2
    min_hand_detection_confidence: float = 0.7
    min_hand_presence_confidence: float = 0.7
    min_tracking_confidence: float = 0.7


DEFAULT_CONFIG = AppConfig()


def load_config_from_env(environ: dict[str, str] | None = None) -> AppConfig:
    values = os.environ if environ is None else environ
    defaults = AppConfig()

    return AppConfig(
        app_name=values.get(EnvVar.APP_NAME, defaults.app_name),
        tv_ip=values.get(EnvVar.TV_IP, defaults.tv_ip),
        cert_file=_path(values, EnvVar.CERT_FILE, defaults.cert_file),
        key_file=_path(values, EnvVar.KEY_FILE, defaults.key_file),
        model_file=_path(values, EnvVar.MODEL_FILE, defaults.model_file),
        model_url=values.get(EnvVar.MODEL_URL, defaults.model_url),
        debounce_seconds=_float(
            values,
            EnvVar.DEBOUNCE_SECONDS,
            defaults.debounce_seconds,
        ),
        home_chord_seconds=_float(
            values,
            EnvVar.HOME_CHORD_SECONDS,
            defaults.home_chord_seconds,
        ),
        pointer_distance_ratio=_float(
            values,
            EnvVar.POINTER_DISTANCE_RATIO,
            defaults.pointer_distance_ratio,
        ),
        pointer_min_distance=_float(
            values,
            EnvVar.POINTER_MIN_DISTANCE,
            defaults.pointer_min_distance,
        ),
        pointer_max_distance=_float(
            values,
            EnvVar.POINTER_MAX_DISTANCE,
            defaults.pointer_max_distance,
        ),
        pointer_dominance=_float(
            values,
            EnvVar.POINTER_DOMINANCE,
            defaults.pointer_dominance,
        ),
        volume_distance_ratio=_float(
            values,
            EnvVar.VOLUME_DISTANCE_RATIO,
            defaults.volume_distance_ratio,
        ),
        volume_min_distance=_float(
            values,
            EnvVar.VOLUME_MIN_DISTANCE,
            defaults.volume_min_distance,
        ),
        volume_max_distance=_float(
            values,
            EnvVar.VOLUME_MAX_DISTANCE,
            defaults.volume_max_distance,
        ),
        pinch_distance_ratio=_float(
            values,
            EnvVar.PINCH_DISTANCE_RATIO,
            defaults.pinch_distance_ratio,
        ),
        voice_capture_seconds=_float(
            values,
            EnvVar.VOICE_CAPTURE_SECONDS,
            defaults.voice_capture_seconds,
        ),
        debug_log_seconds=_float(
            values,
            EnvVar.DEBUG_LOG_SECONDS,
            defaults.debug_log_seconds,
        ),
        webcam_index=_int(values, EnvVar.WEBCAM_INDEX, defaults.webcam_index),
        camera_zoom=_float(values, EnvVar.CAMERA_ZOOM, defaults.camera_zoom),
        auto_zoom_enabled=_bool(
            values,
            EnvVar.AUTO_ZOOM_ENABLED,
            defaults.auto_zoom_enabled,
        ),
        auto_zoom_min=_float(values, EnvVar.AUTO_ZOOM_MIN, defaults.auto_zoom_min),
        auto_zoom_max=_float(values, EnvVar.AUTO_ZOOM_MAX, defaults.auto_zoom_max),
        auto_zoom_padding=_float(
            values,
            EnvVar.AUTO_ZOOM_PADDING,
            defaults.auto_zoom_padding,
        ),
        auto_zoom_smoothing=_float(
            values,
            EnvVar.AUTO_ZOOM_SMOOTHING,
            defaults.auto_zoom_smoothing,
        ),
        max_hands=_int(values, EnvVar.MAX_HANDS, defaults.max_hands),
        min_hand_detection_confidence=_float(
            values,
            EnvVar.MIN_HAND_DETECTION_CONFIDENCE,
            defaults.min_hand_detection_confidence,
        ),
        min_hand_presence_confidence=_float(
            values,
            EnvVar.MIN_HAND_PRESENCE_CONFIDENCE,
            defaults.min_hand_presence_confidence,
        ),
        min_tracking_confidence=_float(
            values,
            EnvVar.MIN_TRACKING_CONFIDENCE,
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


def _bool(values: dict[str, str], name: str, default: bool) -> bool:
    raw_value = values.get(name)
    if raw_value is None:
        return default

    return raw_value.lower() in {"1", "true", "yes", "on"}
