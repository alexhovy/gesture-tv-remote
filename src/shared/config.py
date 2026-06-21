import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


class EnvVar:
    APP_NAME = "GESTURE_TV_APP_NAME"
    CONFIG_DB_FILE = "GESTURE_TV_CONFIG_DB"
    CONFIG_WEB_HOST = "GESTURE_TV_CONFIG_WEB_HOST"
    CONFIG_WEB_PORT = "GESTURE_TV_CONFIG_WEB_PORT"
    CONFIG_WEB_MDNS_ENABLED = "GESTURE_TV_CONFIG_WEB_MDNS_ENABLED"
    CONFIG_WEB_MDNS_NAME = "GESTURE_TV_CONFIG_WEB_MDNS_NAME"
    TV_ADAPTER = "GESTURE_TV_ADAPTER"
    TV_HOST = "GESTURE_TV_HOST"
    ANDROID_CERT_FILE = "GESTURE_TV_ANDROID_CERT_FILE"
    ANDROID_KEY_FILE = "GESTURE_TV_ANDROID_KEY_FILE"
    SAMSUNG_TOKEN_FILE = "GESTURE_TV_SAMSUNG_TOKEN_FILE"
    SAMSUNG_PORT = "GESTURE_TV_SAMSUNG_PORT"
    WEBOS_CLIENT_KEY_FILE = "GESTURE_TV_WEBOS_CLIENT_KEY_FILE"
    ROKU_PORT = "GESTURE_TV_ROKU_PORT"
    MODEL_FILE = "GESTURE_TV_MODEL_FILE"
    MODEL_URL = "GESTURE_TV_MODEL_URL"
    MODEL_DOWNLOAD_TIMEOUT_SECONDS = "GESTURE_TV_MODEL_DOWNLOAD_TIMEOUT_SECONDS"
    MODEL_DOWNLOAD_RETRIES = "GESTURE_TV_MODEL_DOWNLOAD_RETRIES"
    DEBOUNCE_SECONDS = "GESTURE_TV_DEBOUNCE_SECONDS"
    HOME_CHORD_SECONDS = "GESTURE_TV_HOME_CHORD_SECONDS"
    POINTER_DISTANCE_RATIO = "GESTURE_TV_POINTER_DISTANCE_RATIO"
    POINTER_MIN_DISTANCE = "GESTURE_TV_POINTER_MIN_DISTANCE"
    POINTER_MAX_DISTANCE = "GESTURE_TV_POINTER_MAX_DISTANCE"
    POINTER_DOMINANCE = "GESTURE_TV_POINTER_DOMINANCE"
    POINTER_RELEASE_SETTLE_FRAMES = "GESTURE_TV_POINTER_RELEASE_SETTLE_FRAMES"
    VOLUME_DISTANCE_RATIO = "GESTURE_TV_VOLUME_DISTANCE_RATIO"
    VOLUME_MIN_DISTANCE = "GESTURE_TV_VOLUME_MIN_DISTANCE"
    VOLUME_MAX_DISTANCE = "GESTURE_TV_VOLUME_MAX_DISTANCE"
    PINCH_DISTANCE_RATIO = "GESTURE_TV_PINCH_DISTANCE_RATIO"
    REQUIRE_UPRIGHT_HANDS = "GESTURE_TV_REQUIRE_UPRIGHT_HANDS"
    HAND_UPRIGHT_MAX_TILT_RATIO = "GESTURE_TV_HAND_UPRIGHT_MAX_TILT_RATIO"
    VOICE_CAPTURE_SECONDS = "GESTURE_TV_VOICE_CAPTURE_SECONDS"
    DEBUG_LOG_SECONDS = "GESTURE_TV_DEBUG_LOG_SECONDS"
    PRIMARY_LOST_GRACE_SECONDS = "GESTURE_TV_PRIMARY_LOST_GRACE_SECONDS"
    PRIMARY_MATCH_MAX_DISTANCE = "GESTURE_TV_PRIMARY_MATCH_MAX_DISTANCE"
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
    VERBOSE_PIPELINE_DIAGNOSTICS = "GESTURE_TV_VERBOSE_PIPELINE_DIAGNOSTICS"
    METRICS_LOG_SECONDS = "GESTURE_TV_METRICS_LOG_SECONDS"


@dataclass(frozen=True)
class TvConfig:
    adapter: str = "samsung"
    host: str = "192.168.8.7"
    android_cert_file: Path = Path("certs/android/cert.pem")
    android_key_file: Path = Path("certs/android/key.pem")
    samsung_token_file: Path = Path("certs/samsung/token.txt")
    samsung_port: int = 8002
    webos_client_key_file: Path = Path("certs/webos/client_key.txt")
    roku_port: int = 8060
    voice_capture_seconds: float = 5.0


@dataclass(frozen=True)
class GestureConfig:
    debounce_seconds: float = 0.3
    home_chord_seconds: float = 0.35
    pointer_distance_ratio: float = 0.25
    pointer_min_distance: float = 0.02
    pointer_max_distance: float = 0.08
    pointer_dominance: float = 1.0
    pointer_release_settle_frames: int = 2
    volume_distance_ratio: float = 0.25
    volume_min_distance: float = 0.02
    volume_max_distance: float = 0.08
    pinch_distance_ratio: float = 0.22
    require_upright_hands: bool = True
    hand_upright_max_tilt_ratio: float = 0.75
    primary_lost_grace_seconds: float = 0.35
    primary_match_max_distance: float = 0.35


@dataclass(frozen=True)
class CameraConfig:
    webcam_index: int = 0
    zoom: float = 1.0
    auto_zoom_enabled: bool = True
    auto_zoom_min: float = 1.0
    auto_zoom_max: float = 10.0
    auto_zoom_padding: float = 0.5
    auto_zoom_smoothing: float = 0.1
    auto_zoom_position_deadband: float = 0.08
    auto_zoom_scale_deadband: float = 0.12
    auto_zoom_crop_reset_threshold: float = 0.08


@dataclass(frozen=True)
class ModelConfig:
    file: Path = Path("models/hand_landmarker.task")
    url: str = (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task"
    )
    download_timeout_seconds: float = 20.0
    download_retries: int = 2
    max_hands: int = 2
    min_hand_detection_confidence: float = 0.6
    min_hand_presence_confidence: float = 0.6
    min_tracking_confidence: float = 0.6


@dataclass(frozen=True)
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 80
    mdns_enabled: bool = True
    mdns_name: str = "gesturetvremote"


@dataclass(frozen=True)
class DebugConfig:
    log_seconds: float = 0.5
    verbose_pipeline_diagnostics: bool = False


@dataclass(frozen=True)
class PerformanceConfig:
    metrics_log_seconds: float = 2.0


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "Gesture TV Remote"
    config_db_file: Path = Path("data/gesture_tv_remote.sqlite3")
    tv: TvConfig = TvConfig()
    gesture: GestureConfig = GestureConfig()
    camera: CameraConfig = CameraConfig()
    model: ModelConfig = ModelConfig()
    web: WebConfig = WebConfig()
    debug: DebugConfig = DebugConfig()
    performance: PerformanceConfig = PerformanceConfig()


@dataclass(frozen=True)
class ConfigField:
    name: str
    env_var: str
    section: str | None
    attribute: str
    parser: Callable[[dict[str, str], str, object], object]


DEFAULT_CONFIG = AppConfig()

_SUPPORTED_TV_ADAPTERS = {"androidtv", "samsung", "webos", "roku"}
RELOADABLE_CONFIG_FIELDS = (
    "debounce_seconds",
    "home_chord_seconds",
    "pointer_distance_ratio",
    "pointer_min_distance",
    "pointer_max_distance",
    "pointer_dominance",
    "pointer_release_settle_frames",
    "volume_distance_ratio",
    "volume_min_distance",
    "volume_max_distance",
    "pinch_distance_ratio",
    "require_upright_hands",
    "hand_upright_max_tilt_ratio",
    "voice_capture_seconds",
    "debug_log_seconds",
    "primary_lost_grace_seconds",
    "primary_match_max_distance",
    "camera_zoom",
    "auto_zoom_enabled",
    "auto_zoom_min",
    "auto_zoom_max",
    "auto_zoom_padding",
    "auto_zoom_smoothing",
    "auto_zoom_position_deadband",
    "auto_zoom_scale_deadband",
    "auto_zoom_crop_reset_threshold",
    "verbose_pipeline_diagnostics",
    "metrics_log_seconds",
)


def load_config_from_env(
    environ: dict[str, str] | None = None,
    base_config: AppConfig | None = None,
) -> AppConfig:
    values = os.environ if environ is None else environ
    config = AppConfig() if base_config is None else base_config
    for field in CONFIG_FIELDS:
        current_value = get_config_value(config, field.name)
        value = field.parser(values, field.env_var, current_value)
        config = replace_config_value(config, field.name, value)
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    if config.tv.adapter.lower() not in _SUPPORTED_TV_ADAPTERS:
        supported = ", ".join(sorted(_SUPPORTED_TV_ADAPTERS))
        raise ValueError(f"tv_adapter must be one of: {supported}")
    if not config.web.host.strip():
        raise ValueError("config_web_host must not be empty")
    _require_between(config.web.port, "config_web_port", 1, 65535)
    if not config.web.mdns_name.strip():
        raise ValueError("config_web_mdns_name must not be empty")
    if not config.tv.host.strip():
        raise ValueError("tv_host must not be empty")
    _require_between(config.tv.samsung_port, "samsung_port", 1, 65535)
    _require_between(config.tv.roku_port, "roku_port", 1, 65535)
    _require_at_least(config.gesture.debounce_seconds, "debounce_seconds", 0.0)
    _require_at_least(config.gesture.home_chord_seconds, "home_chord_seconds", 0.0)
    _require_at_least(config.tv.voice_capture_seconds, "voice_capture_seconds", 0.0)
    _require_at_least(
        config.model.download_timeout_seconds,
        "model_download_timeout_seconds",
        0.1,
    )
    _require_at_least(config.model.download_retries, "model_download_retries", 0)
    _require_at_least(config.debug.log_seconds, "debug_log_seconds", 0.0)
    _require_at_least(
        config.performance.metrics_log_seconds,
        "metrics_log_seconds",
        0.0,
    )
    _require_at_least(
        config.gesture.primary_lost_grace_seconds,
        "primary_lost_grace_seconds",
        0.0,
    )
    _require_at_least(
        config.gesture.primary_match_max_distance,
        "primary_match_max_distance",
        0.0,
    )
    _require_at_least(config.camera.webcam_index, "webcam_index", 0)
    _require_at_least(config.camera.zoom, "camera_zoom", 1.0)
    _require_at_least(config.camera.auto_zoom_min, "auto_zoom_min", 1.0)
    _require_at_least(
        config.camera.auto_zoom_max,
        "auto_zoom_max",
        config.camera.auto_zoom_min,
    )
    _require_at_least(config.camera.auto_zoom_padding, "auto_zoom_padding", 0.0)
    _require_between(config.camera.auto_zoom_smoothing, "auto_zoom_smoothing", 0.0, 1.0)
    _require_at_least(
        config.camera.auto_zoom_position_deadband,
        "auto_zoom_position_deadband",
        0.0,
    )
    _require_at_least(
        config.camera.auto_zoom_scale_deadband,
        "auto_zoom_scale_deadband",
        0.0,
    )
    _require_at_least(
        config.camera.auto_zoom_crop_reset_threshold,
        "auto_zoom_crop_reset_threshold",
        0.0,
    )
    _require_at_least(config.model.max_hands, "max_hands", 1)
    _require_between(
        config.model.min_hand_detection_confidence,
        "min_hand_detection_confidence",
        0.0,
        1.0,
    )
    _require_between(
        config.model.min_hand_presence_confidence,
        "min_hand_presence_confidence",
        0.0,
        1.0,
    )
    _require_between(
        config.model.min_tracking_confidence,
        "min_tracking_confidence",
        0.0,
        1.0,
    )
    _require_at_least(config.gesture.pointer_distance_ratio, "pointer_distance_ratio", 0.0)
    _require_at_least(config.gesture.pointer_min_distance, "pointer_min_distance", 0.0)
    _require_at_least(
        config.gesture.pointer_max_distance,
        "pointer_max_distance",
        config.gesture.pointer_min_distance,
    )
    _require_at_least(config.gesture.pointer_dominance, "pointer_dominance", 0.0)
    _require_at_least(
        config.gesture.pointer_release_settle_frames,
        "pointer_release_settle_frames",
        1,
    )
    _require_at_least(config.gesture.volume_distance_ratio, "volume_distance_ratio", 0.0)
    _require_at_least(config.gesture.volume_min_distance, "volume_min_distance", 0.0)
    _require_at_least(
        config.gesture.volume_max_distance,
        "volume_max_distance",
        config.gesture.volume_min_distance,
    )
    _require_at_least(config.gesture.pinch_distance_ratio, "pinch_distance_ratio", 0.0)
    _require_at_least(
        config.gesture.hand_upright_max_tilt_ratio,
        "hand_upright_max_tilt_ratio",
        0.0,
    )


def apply_reloadable_config(current: AppConfig, latest: AppConfig) -> AppConfig:
    config = current
    for field_name in RELOADABLE_CONFIG_FIELDS:
        config = replace_config_value(config, field_name, get_config_value(latest, field_name))
    validate_config(config)
    return config


def get_config_value(config: AppConfig, field_name: str) -> Any:
    field = _CONFIG_FIELD_BY_NAME[field_name]
    if field.section is None:
        return getattr(config, field.attribute)
    return getattr(getattr(config, field.section), field.attribute)


def replace_config_value(config: AppConfig, field_name: str, value: Any) -> AppConfig:
    field = _CONFIG_FIELD_BY_NAME[field_name]
    if field.section is None:
        return replace(config, **{field.attribute: value})
    section = getattr(config, field.section)
    return replace(config, **{field.section: replace(section, **{field.attribute: value})})


def config_field_default(field: ConfigField) -> Any:
    return get_config_value(DEFAULT_CONFIG, field.name)


def config_field_names() -> list[str]:
    return [field.name for field in CONFIG_FIELDS]


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
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _require_at_least(value: float | int, field_name: str, minimum: float | int) -> None:
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")


def _require_between(
    value: float,
    field_name: str,
    minimum: float,
    maximum: float,
) -> None:
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")


CONFIG_FIELDS: tuple[ConfigField, ...] = (
    ConfigField("app_name", EnvVar.APP_NAME, None, "app_name", _str),
    ConfigField("config_db_file", EnvVar.CONFIG_DB_FILE, None, "config_db_file", _path),
    ConfigField("config_web_host", EnvVar.CONFIG_WEB_HOST, "web", "host", _str),
    ConfigField("config_web_port", EnvVar.CONFIG_WEB_PORT, "web", "port", _int),
    ConfigField(
        "config_web_mdns_enabled",
        EnvVar.CONFIG_WEB_MDNS_ENABLED,
        "web",
        "mdns_enabled",
        _bool,
    ),
    ConfigField("config_web_mdns_name", EnvVar.CONFIG_WEB_MDNS_NAME, "web", "mdns_name", _str),
    ConfigField("tv_adapter", EnvVar.TV_ADAPTER, "tv", "adapter", _str),
    ConfigField("tv_host", EnvVar.TV_HOST, "tv", "host", _str),
    ConfigField("android_cert_file", EnvVar.ANDROID_CERT_FILE, "tv", "android_cert_file", _path),
    ConfigField("android_key_file", EnvVar.ANDROID_KEY_FILE, "tv", "android_key_file", _path),
    ConfigField("samsung_token_file", EnvVar.SAMSUNG_TOKEN_FILE, "tv", "samsung_token_file", _path),
    ConfigField("samsung_port", EnvVar.SAMSUNG_PORT, "tv", "samsung_port", _int),
    ConfigField(
        "webos_client_key_file",
        EnvVar.WEBOS_CLIENT_KEY_FILE,
        "tv",
        "webos_client_key_file",
        _path,
    ),
    ConfigField("roku_port", EnvVar.ROKU_PORT, "tv", "roku_port", _int),
    ConfigField("model_file", EnvVar.MODEL_FILE, "model", "file", _path),
    ConfigField("model_url", EnvVar.MODEL_URL, "model", "url", _str),
    ConfigField(
        "model_download_timeout_seconds",
        EnvVar.MODEL_DOWNLOAD_TIMEOUT_SECONDS,
        "model",
        "download_timeout_seconds",
        _float,
    ),
    ConfigField(
        "model_download_retries",
        EnvVar.MODEL_DOWNLOAD_RETRIES,
        "model",
        "download_retries",
        _int,
    ),
    ConfigField("debounce_seconds", EnvVar.DEBOUNCE_SECONDS, "gesture", "debounce_seconds", _float),
    ConfigField("home_chord_seconds", EnvVar.HOME_CHORD_SECONDS, "gesture", "home_chord_seconds", _float),
    ConfigField(
        "pointer_distance_ratio",
        EnvVar.POINTER_DISTANCE_RATIO,
        "gesture",
        "pointer_distance_ratio",
        _float,
    ),
    ConfigField("pointer_min_distance", EnvVar.POINTER_MIN_DISTANCE, "gesture", "pointer_min_distance", _float),
    ConfigField("pointer_max_distance", EnvVar.POINTER_MAX_DISTANCE, "gesture", "pointer_max_distance", _float),
    ConfigField("pointer_dominance", EnvVar.POINTER_DOMINANCE, "gesture", "pointer_dominance", _float),
    ConfigField(
        "pointer_release_settle_frames",
        EnvVar.POINTER_RELEASE_SETTLE_FRAMES,
        "gesture",
        "pointer_release_settle_frames",
        _int,
    ),
    ConfigField(
        "volume_distance_ratio",
        EnvVar.VOLUME_DISTANCE_RATIO,
        "gesture",
        "volume_distance_ratio",
        _float,
    ),
    ConfigField("volume_min_distance", EnvVar.VOLUME_MIN_DISTANCE, "gesture", "volume_min_distance", _float),
    ConfigField("volume_max_distance", EnvVar.VOLUME_MAX_DISTANCE, "gesture", "volume_max_distance", _float),
    ConfigField("pinch_distance_ratio", EnvVar.PINCH_DISTANCE_RATIO, "gesture", "pinch_distance_ratio", _float),
    ConfigField(
        "require_upright_hands",
        EnvVar.REQUIRE_UPRIGHT_HANDS,
        "gesture",
        "require_upright_hands",
        _bool,
    ),
    ConfigField(
        "hand_upright_max_tilt_ratio",
        EnvVar.HAND_UPRIGHT_MAX_TILT_RATIO,
        "gesture",
        "hand_upright_max_tilt_ratio",
        _float,
    ),
    ConfigField(
        "voice_capture_seconds",
        EnvVar.VOICE_CAPTURE_SECONDS,
        "tv",
        "voice_capture_seconds",
        _float,
    ),
    ConfigField("debug_log_seconds", EnvVar.DEBUG_LOG_SECONDS, "debug", "log_seconds", _float),
    ConfigField(
        "verbose_pipeline_diagnostics",
        EnvVar.VERBOSE_PIPELINE_DIAGNOSTICS,
        "debug",
        "verbose_pipeline_diagnostics",
        _bool,
    ),
    ConfigField(
        "metrics_log_seconds",
        EnvVar.METRICS_LOG_SECONDS,
        "performance",
        "metrics_log_seconds",
        _float,
    ),
    ConfigField(
        "primary_lost_grace_seconds",
        EnvVar.PRIMARY_LOST_GRACE_SECONDS,
        "gesture",
        "primary_lost_grace_seconds",
        _float,
    ),
    ConfigField(
        "primary_match_max_distance",
        EnvVar.PRIMARY_MATCH_MAX_DISTANCE,
        "gesture",
        "primary_match_max_distance",
        _float,
    ),
    ConfigField("webcam_index", EnvVar.WEBCAM_INDEX, "camera", "webcam_index", _int),
    ConfigField("camera_zoom", EnvVar.CAMERA_ZOOM, "camera", "zoom", _float),
    ConfigField("auto_zoom_enabled", EnvVar.AUTO_ZOOM_ENABLED, "camera", "auto_zoom_enabled", _bool),
    ConfigField("auto_zoom_min", EnvVar.AUTO_ZOOM_MIN, "camera", "auto_zoom_min", _float),
    ConfigField("auto_zoom_max", EnvVar.AUTO_ZOOM_MAX, "camera", "auto_zoom_max", _float),
    ConfigField("auto_zoom_padding", EnvVar.AUTO_ZOOM_PADDING, "camera", "auto_zoom_padding", _float),
    ConfigField("auto_zoom_smoothing", EnvVar.AUTO_ZOOM_SMOOTHING, "camera", "auto_zoom_smoothing", _float),
    ConfigField(
        "auto_zoom_position_deadband",
        EnvVar.AUTO_ZOOM_POSITION_DEADBAND,
        "camera",
        "auto_zoom_position_deadband",
        _float,
    ),
    ConfigField(
        "auto_zoom_scale_deadband",
        EnvVar.AUTO_ZOOM_SCALE_DEADBAND,
        "camera",
        "auto_zoom_scale_deadband",
        _float,
    ),
    ConfigField(
        "auto_zoom_crop_reset_threshold",
        EnvVar.AUTO_ZOOM_CROP_RESET_THRESHOLD,
        "camera",
        "auto_zoom_crop_reset_threshold",
        _float,
    ),
    ConfigField("max_hands", EnvVar.MAX_HANDS, "model", "max_hands", _int),
    ConfigField(
        "min_hand_detection_confidence",
        EnvVar.MIN_HAND_DETECTION_CONFIDENCE,
        "model",
        "min_hand_detection_confidence",
        _float,
    ),
    ConfigField(
        "min_hand_presence_confidence",
        EnvVar.MIN_HAND_PRESENCE_CONFIDENCE,
        "model",
        "min_hand_presence_confidence",
        _float,
    ),
    ConfigField(
        "min_tracking_confidence",
        EnvVar.MIN_TRACKING_CONFIDENCE,
        "model",
        "min_tracking_confidence",
        _float,
    ),
)

_CONFIG_FIELD_BY_NAME = {field.name: field for field in CONFIG_FIELDS}
