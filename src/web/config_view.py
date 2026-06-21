from dataclasses import dataclass

from src.shared.config import CONFIG_FIELDS, RELOADABLE_CONFIG_FIELDS

READONLY_FIELDS = {"config_db_file"}
TV_ADAPTERS = ("androidtv", "samsung", "webos", "roku")


@dataclass(frozen=True)
class ConfigSection:
    title: str
    description: str
    fields: tuple[str, ...]


SECTIONS: tuple[ConfigSection, ...] = (
    ConfigSection(
        "TV Connection",
        "Choose the TV adapter and network address used for remote commands.",
        (
            "tv_adapter",
            "tv_host",
            "voice_capture_seconds",
            "samsung_port",
            "roku_port",
        ),
    ),
    ConfigSection(
        "Camera",
        "Select the webcam and tune the crop shown in the gesture window.",
        (
            "webcam_index",
            "camera_zoom",
            "auto_zoom_enabled",
            "auto_zoom_min",
            "auto_zoom_max",
            "auto_zoom_padding",
            "auto_zoom_smoothing",
            "auto_zoom_position_deadband",
            "auto_zoom_scale_deadband",
            "auto_zoom_crop_reset_threshold",
        ),
    ),
    ConfigSection(
        "Gestures",
        "Tune command timing and hand movement thresholds.",
        (
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
            "primary_lost_grace_seconds",
            "primary_match_max_distance",
        ),
    ),
    ConfigSection(
        "Model And Tracking",
        "Set MediaPipe model inputs and hand tracking confidence thresholds.",
        (
            "model_file",
            "model_url",
            "model_download_timeout_seconds",
            "model_download_retries",
            "max_hands",
            "min_hand_detection_confidence",
            "min_hand_presence_confidence",
            "min_tracking_confidence",
        ),
    ),
    ConfigSection(
        "Config UI",
        "Control where this settings page listens and how it is advertised.",
        (
            "app_name",
            "config_db_file",
            "config_web_host",
            "config_web_port",
            "config_web_mdns_enabled",
            "config_web_mdns_name",
        ),
    ),
    ConfigSection(
        "Debug And Performance",
        "Adjust runtime logging and pipeline metrics.",
        (
            "debug_log_seconds",
            "verbose_pipeline_diagnostics",
            "metrics_log_seconds",
        ),
    ),
    ConfigSection(
        "Pairing Files",
        "Local credential paths for paired TV sessions. Do not commit these files.",
        (
            "android_cert_file",
            "android_key_file",
            "samsung_token_file",
            "webos_client_key_file",
        ),
    ),
)

FIELD_HELP: dict[str, str] = {
    "tv_adapter": "Select the TV platform to control.",
    "tv_host": "IP address or host name of the TV.",
    "voice_capture_seconds": "Android TV voice capture duration in seconds.",
    "webcam_index": "Usually 0 for the default webcam.",
    "camera_zoom": "Digital tracking crop. Start near 1.5 if hands appear small.",
    "auto_zoom_enabled": "Moves the displayed crop while keeping tracking input stable.",
    "auto_zoom_min": "Smallest automatic display zoom.",
    "auto_zoom_max": "Largest automatic display zoom.",
    "debounce_seconds": "Minimum delay between repeated commands.",
    "home_chord_seconds": "How long the HOME chord must be held.",
    "pointer_distance_ratio": "Pointer movement threshold scaled by hand size.",
    "pointer_release_settle_frames": "Release frames required before pointer commands can emit again.",
    "volume_distance_ratio": "Volume movement threshold scaled by hand size.",
    "pinch_distance_ratio": "Finger pinch threshold scaled by hand size.",
    "require_upright_hands": "Blocks sideways or upside-down hands from activating controls.",
    "hand_upright_max_tilt_ratio": "Higher values allow more hand tilt.",
    "primary_lost_grace_seconds": "Keeps a session active through brief primary-hand dropouts.",
    "primary_match_max_distance": "Maximum movement allowed when matching the active hand.",
    "model_file": "Downloaded automatically on first run when missing.",
    "model_url": "Source URL used for model downloads.",
    "max_hands": "Two hands are required for the full gesture set.",
    "min_hand_detection_confidence": "MediaPipe detection confidence from 0.0 to 1.0.",
    "min_hand_presence_confidence": "MediaPipe hand presence confidence from 0.0 to 1.0.",
    "min_tracking_confidence": "MediaPipe tracking confidence from 0.0 to 1.0.",
    "config_db_file": "Saved settings database. Set by environment during bootstrap.",
    "config_web_host": "Bind address for the config UI.",
    "config_web_port": "Port for the config UI. Port 80 may require elevated permissions.",
    "config_web_mdns_enabled": "Advertises the UI on the local network when available.",
    "config_web_mdns_name": "Name used for the .local address.",
    "verbose_pipeline_diagnostics": "Logs detailed camera, detection, command, and queue metrics.",
}


def field_applies_live(name: str) -> bool:
    return name in RELOADABLE_CONFIG_FIELDS


def field_help(name: str) -> str | None:
    return FIELD_HELP.get(name)


def field_readonly(name: str) -> bool:
    return name in READONLY_FIELDS


def input_constraints(name: str) -> str:
    if name in {
        "config_web_port",
        "samsung_port",
        "roku_port",
    }:
        return ' min="1" max="65535"'
    if name in {
        "min_hand_detection_confidence",
        "min_hand_presence_confidence",
        "min_tracking_confidence",
        "auto_zoom_smoothing",
    }:
        return ' min="0" max="1"'
    if name in {
        "camera_zoom",
        "auto_zoom_min",
        "auto_zoom_max",
    }:
        return ' min="1"'
    if name == "max_hands":
        return ' min="1"'
    if name == "pointer_release_settle_frames":
        return ' min="1"'
    if name == "webcam_index":
        return ' min="0"'
    if name in {
        "debounce_seconds",
        "home_chord_seconds",
        "voice_capture_seconds",
        "debug_log_seconds",
        "metrics_log_seconds",
        "primary_lost_grace_seconds",
        "primary_match_max_distance",
        "pointer_distance_ratio",
        "pointer_min_distance",
        "pointer_max_distance",
        "pointer_dominance",
        "volume_distance_ratio",
        "volume_min_distance",
        "volume_max_distance",
        "pinch_distance_ratio",
        "hand_upright_max_tilt_ratio",
        "model_download_timeout_seconds",
        "model_download_retries",
        "auto_zoom_padding",
        "auto_zoom_position_deadband",
        "auto_zoom_scale_deadband",
        "auto_zoom_crop_reset_threshold",
    }:
        return ' min="0"'
    return ""


def validate_sections() -> None:
    field_names = {field.name for field in CONFIG_FIELDS}
    section_fields = [name for section in SECTIONS for name in section.fields]
    missing = field_names - set(section_fields)
    extra = set(section_fields) - field_names
    duplicates = {name for name in section_fields if section_fields.count(name) > 1}
    if missing or extra or duplicates:
        raise ValueError(
            "Config UI sections do not match config fields: "
            f"missing={sorted(missing)}, extra={sorted(extra)}, "
            f"duplicates={sorted(duplicates)}"
        )


validate_sections()
