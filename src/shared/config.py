from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable


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
    REQUIRE_UPRIGHT_HANDS = "GESTURE_TV_REQUIRE_UPRIGHT_HANDS"
    HAND_UPRIGHT_MAX_TILT_RATIO = "GESTURE_TV_HAND_UPRIGHT_MAX_TILT_RATIO"
    VOICE_CAPTURE_SECONDS = "GESTURE_TV_VOICE_CAPTURE_SECONDS"
    DEBUG_LOG_SECONDS = "GESTURE_TV_DEBUG_LOG_SECONDS"
    WEBCAM_INDEX = "GESTURE_TV_WEBCAM_INDEX"
    CAMERA_ZOOM = "GESTURE_TV_CAMERA_ZOOM"
    AUTO_ZOOM_ENABLED = "GESTURE_TV_AUTO_ZOOM_ENABLED"
    AUTO_ZOOM_MIN = "GESTURE_TV_AUTO_ZOOM_MIN"
    AUTO_ZOOM_MAX = "GESTURE_TV_AUTO_ZOOM_MAX"
    AUTO_ZOOM_PADDING = "GESTURE_TV_AUTO_ZOOM_PADDING"
    AUTO_ZOOM_SMOOTHING = "GESTURE_TV_AUTO_ZOOM_SMOOTHING"
    AUTO_ZOOM_POSITION_DEADBAND = "GESTURE_TV_AUTO_ZOOM_POSITION_DEADBAND"
    AUTO_ZOOM_SCALE_DEADBAND = "GESTURE_TV_AUTO_ZOOM_SCALE_DEADBAND"
    AUTO_ZOOM_CROP_RESET_THRESHOLD = "GESTURE_TV_AUTO_ZOOM_CROP_RESET_THRESHOLD"
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
    debounce_seconds: float = 0.3
    home_chord_seconds: float = 0.35
    pointer_distance_ratio: float = 0.25
    pointer_min_distance: float = 0.02
    pointer_max_distance: float = 0.08
    pointer_dominance: float = 1.0
    volume_distance_ratio: float = 0.25
    volume_min_distance: float = 0.02
    volume_max_distance: float = 0.08
    pinch_distance_ratio: float = 0.22
    require_upright_hands: bool = True
    hand_upright_max_tilt_ratio: float = 0.75
    voice_capture_seconds: float = 5.0
    debug_log_seconds: float = 0.5
    webcam_index: int = 0
    camera_zoom: float = 1.0
    auto_zoom_enabled: bool = True
    auto_zoom_min: float = 1.0
    auto_zoom_max: float = 10.0
    auto_zoom_padding: float = 0.5
    auto_zoom_smoothing: float = 0.1
    auto_zoom_position_deadband: float = 0.08
    auto_zoom_scale_deadband: float = 0.12
    auto_zoom_crop_reset_threshold: float = 0.08
    max_hands: int = 2
    min_hand_detection_confidence: float = 0.6
    min_hand_presence_confidence: float = 0.6
    min_tracking_confidence: float = 0.6


DEFAULT_CONFIG = AppConfig()


ConfigParser = Callable[[dict[str, str], str, object], object]


def load_config_from_env(environ: dict[str, str] | None = None) -> AppConfig:
    values = os.environ if environ is None else environ
    defaults = AppConfig()

    config_values = {
        field_name: parser(values, env_var, getattr(defaults, field_name))
        for field_name, env_var, parser in _CONFIG_FIELDS
    }
    return AppConfig(**config_values)


def _str(values: dict[str, str], name: str, default: object) -> str:
    raw_value = values.get(name)
    return raw_value if raw_value else str(default)


def _path(values: dict[str, str], name: str, default: object) -> Path:
    raw_value = values.get(name)
    return Path(raw_value) if raw_value else default


def _float(values: dict[str, str], name: str, default: object) -> float:
    raw_value = values.get(name)
    return float(raw_value) if raw_value else float(default)


def _int(values: dict[str, str], name: str, default: object) -> int:
    raw_value = values.get(name)
    return int(raw_value) if raw_value else int(default)


def _bool(values: dict[str, str], name: str, default: object) -> bool:
    raw_value = values.get(name)
    if raw_value is None:
        return bool(default)

    return raw_value.lower() in {"1", "true", "yes", "on"}


_CONFIG_FIELDS: tuple[tuple[str, str, ConfigParser], ...] = (
    ("app_name", EnvVar.APP_NAME, _str),
    ("tv_ip", EnvVar.TV_IP, _str),
    ("cert_file", EnvVar.CERT_FILE, _path),
    ("key_file", EnvVar.KEY_FILE, _path),
    ("model_file", EnvVar.MODEL_FILE, _path),
    ("model_url", EnvVar.MODEL_URL, _str),
    ("debounce_seconds", EnvVar.DEBOUNCE_SECONDS, _float),
    ("home_chord_seconds", EnvVar.HOME_CHORD_SECONDS, _float),
    ("pointer_distance_ratio", EnvVar.POINTER_DISTANCE_RATIO, _float),
    ("pointer_min_distance", EnvVar.POINTER_MIN_DISTANCE, _float),
    ("pointer_max_distance", EnvVar.POINTER_MAX_DISTANCE, _float),
    ("pointer_dominance", EnvVar.POINTER_DOMINANCE, _float),
    ("volume_distance_ratio", EnvVar.VOLUME_DISTANCE_RATIO, _float),
    ("volume_min_distance", EnvVar.VOLUME_MIN_DISTANCE, _float),
    ("volume_max_distance", EnvVar.VOLUME_MAX_DISTANCE, _float),
    ("pinch_distance_ratio", EnvVar.PINCH_DISTANCE_RATIO, _float),
    ("require_upright_hands", EnvVar.REQUIRE_UPRIGHT_HANDS, _bool),
    ("hand_upright_max_tilt_ratio", EnvVar.HAND_UPRIGHT_MAX_TILT_RATIO, _float),
    ("voice_capture_seconds", EnvVar.VOICE_CAPTURE_SECONDS, _float),
    ("debug_log_seconds", EnvVar.DEBUG_LOG_SECONDS, _float),
    ("webcam_index", EnvVar.WEBCAM_INDEX, _int),
    ("camera_zoom", EnvVar.CAMERA_ZOOM, _float),
    ("auto_zoom_enabled", EnvVar.AUTO_ZOOM_ENABLED, _bool),
    ("auto_zoom_min", EnvVar.AUTO_ZOOM_MIN, _float),
    ("auto_zoom_max", EnvVar.AUTO_ZOOM_MAX, _float),
    ("auto_zoom_padding", EnvVar.AUTO_ZOOM_PADDING, _float),
    ("auto_zoom_smoothing", EnvVar.AUTO_ZOOM_SMOOTHING, _float),
    ("auto_zoom_position_deadband", EnvVar.AUTO_ZOOM_POSITION_DEADBAND, _float),
    ("auto_zoom_scale_deadband", EnvVar.AUTO_ZOOM_SCALE_DEADBAND, _float),
    ("auto_zoom_crop_reset_threshold", EnvVar.AUTO_ZOOM_CROP_RESET_THRESHOLD, _float),
    ("max_hands", EnvVar.MAX_HANDS, _int),
    ("min_hand_detection_confidence", EnvVar.MIN_HAND_DETECTION_CONFIDENCE, _float),
    ("min_hand_presence_confidence", EnvVar.MIN_HAND_PRESENCE_CONFIDENCE, _float),
    ("min_tracking_confidence", EnvVar.MIN_TRACKING_CONFIDENCE, _float),
)
