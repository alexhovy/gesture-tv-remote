from dataclasses import dataclass

from src.shared.config import (
    CONFIG_FIELDS,
    RELOADABLE_CONFIG_FIELDS,
    AppConfig,
    VoiceInputTarget,
    get_config_value,
)

READONLY_FIELDS = {"config_db_file"}
TV_ADAPTERS = ("androidtv", "samsung", "webos", "roku", "appletv")
VOICE_INPUT_TARGETS = tuple(target.value for target in VoiceInputTarget)


@dataclass(frozen=True)
class ConfigGroup:
    title: str
    description: str
    fields: tuple[str, ...]
    advanced: bool = False


@dataclass(frozen=True)
class ConfigTab:
    slug: str
    title: str
    description: str
    groups: tuple[ConfigGroup, ...]


TABS: tuple[ConfigTab, ...] = (
    ConfigTab(
        "tv",
        "TV",
        "Choose the TV adapter and network address used for remote commands.",
        (
            ConfigGroup(
                "Connection",
                "The settings most often needed to connect and control the TV.",
                (
                    "tv_adapter",
                    "tv_host",
                    "voice_input_target",
                    "voice_capture_seconds",
                ),
            ),
            ConfigGroup(
                "Advanced TV Integration",
                "Adapter ports and local credential files for paired TV sessions.",
                (
                    "samsung_port",
                    "roku_port",
                    "android_cert_file",
                    "android_key_file",
                    "samsung_token_file",
                    "webos_client_key_file",
                    "appletv_storage_file",
                ),
                advanced=True,
            ),
        ),
    ),
    ConfigTab(
        "gesture",
        "Gesture",
        "Tune the gesture rules used to turn hand movement into TV commands.",
        (
            ConfigGroup(
                "Core Gesture Behavior",
                "Common timing and hand-pose controls for everyday tuning.",
                (
                    "debounce_seconds",
                    "fist_hold_home_seconds",
                    "require_upright_hands",
                ),
            ),
            ConfigGroup(
                "Advanced Gesture Thresholds",
                (
                    "Fine-grained movement, pinch, pointer, volume, and hand "
                    "matching thresholds."
                ),
                (
                    "pointer_screen_radius_ratio",
                    "pointer_dominance",
                    "volume_distance_ratio",
                    "volume_min_distance",
                    "volume_max_distance",
                    "pinch_distance_ratio",
                    "hand_upright_max_tilt_ratio",
                    "active_hand_lost_grace_seconds",
                    "active_hand_match_max_distance",
                ),
                advanced=True,
            ),
        ),
    ),
    ConfigTab(
        "camera",
        "Camera",
        "Select the camera input and tune the displayed gesture crop.",
        (
            ConfigGroup(
                "Camera Input",
                "The camera and zoom settings most users need.",
                (
                    "webcam_index",
                    "camera_zoom",
                    "auto_zoom_enabled",
                ),
            ),
            ConfigGroup(
                "Advanced Auto Zoom",
                "Crop sizing, smoothing, deadband, and reset behavior.",
                (
                    "auto_zoom_min",
                    "auto_zoom_max",
                    "auto_zoom_padding",
                    "auto_zoom_smoothing",
                    "auto_zoom_position_deadband",
                    "auto_zoom_scale_deadband",
                    "auto_zoom_crop_reset_threshold",
                ),
                advanced=True,
            ),
        ),
    ),
    ConfigTab(
        "system",
        "System",
        "Manage model, tracking, web serving, diagnostics, and local storage.",
        (
            ConfigGroup(
                "App",
                "Application identity and saved configuration storage.",
                (
                    "app_name",
                    "config_db_file",
                ),
            ),
            ConfigGroup(
                "Model And Tracking",
                "MediaPipe model inputs and hand tracking confidence thresholds.",
                (
                    "model_file",
                    "max_hands",
                    "min_hand_detection_confidence",
                    "min_hand_presence_confidence",
                    "min_tracking_confidence",
                ),
            ),
            ConfigGroup(
                "Advanced Model Download",
                "Model source and download retry behavior.",
                (
                    "model_url",
                    "model_download_timeout_seconds",
                    "model_download_retries",
                ),
                advanced=True,
            ),
            ConfigGroup(
                "Advanced Web Serving",
                "Bind address, port, mDNS advertising, and TLS certificate files.",
                (
                    "config_web_host",
                    "config_web_port",
                    "config_web_mdns_enabled",
                    "config_web_mdns_name",
                    "config_web_tls_enabled",
                    "config_web_tls_cert_file",
                    "config_web_tls_key_file",
                ),
                advanced=True,
            ),
            ConfigGroup(
                "Advanced Diagnostics",
                "Runtime logging and pipeline metrics.",
                (
                    "debug_log_seconds",
                    "verbose_pipeline_diagnostics",
                    "metrics_log_seconds",
                ),
                advanced=True,
            ),
        ),
    ),
)

FIELD_HELP: dict[str, str] = {
    "tv_adapter": "Select the TV platform to gesture.",
    "tv_host": "IP address or host name of the TV.",
    "voice_input_target": (
        "Voice target for the MIC gesture: auto, remote_search, or native_search."
    ),
    "voice_capture_seconds": "Microphone capture duration in seconds.",
    "appletv_storage_file": (
        "pyatv credential storage file for paired Apple TV devices."
    ),
    "webcam_index": "Usually 0 for the default webcam.",
    "camera_zoom": "Digital tracking crop. Start near 1.5 if hands appear small.",
    "auto_zoom_enabled": (
        "Keeps the active hand larger in the tracking and display crop."
    ),
    "auto_zoom_min": "Smallest automatic tracking zoom.",
    "auto_zoom_max": "Largest automatic tracking zoom.",
    "debounce_seconds": "Minimum delay between repeated commands.",
    "fist_hold_home_seconds": "How long a fist must be held before HOME is emitted.",
    "pointer_screen_radius_ratio": (
        "Pointer neutral radius as a fraction of the displayed crop."
    ),
    "volume_distance_ratio": "Volume movement threshold scaled by hand size.",
    "pinch_distance_ratio": "Finger pinch threshold scaled by hand size.",
    "require_upright_hands": (
        "Blocks sideways or upside-down hands from activating gestures."
    ),
    "hand_upright_max_tilt_ratio": "Higher values allow more hand tilt.",
    "active_hand_lost_grace_seconds": (
        "Keeps a session active through brief active-hand dropouts."
    ),
    "active_hand_match_max_distance": (
        "Maximum movement allowed when matching the active hand."
    ),
    "model_file": "Downloaded automatically on first run when missing.",
    "model_url": "Source URL used for model downloads.",
    "max_hands": (
        "Maximum hands MediaPipe tracks. Two hands are required to start gestures."
    ),
    "min_hand_detection_confidence": "MediaPipe detection confidence from 0.0 to 1.0.",
    "min_hand_presence_confidence": (
        "MediaPipe hand presence confidence from 0.0 to 1.0."
    ),
    "min_tracking_confidence": "MediaPipe tracking confidence from 0.0 to 1.0.",
    "config_db_file": "Saved settings database. Set by environment during bootstrap.",
    "config_web_host": "Bind address for the config UI.",
    "config_web_port": (
        "Port for the config UI. Port 80 may require elevated permissions."
    ),
    "config_web_mdns_enabled": "Advertises the UI on the local network when available.",
    "config_web_mdns_name": "Name used for the .local address.",
    "config_web_tls_enabled": (
        "Serves the web UI over HTTPS. Required for browser camera/microphone "
        "access from .local addresses."
    ),
    "config_web_tls_cert_file": "TLS certificate file for HTTPS web serving.",
    "config_web_tls_key_file": "TLS private key file for HTTPS web serving.",
    "verbose_pipeline_diagnostics": (
        "Logs detailed camera, detection, command, and queue metrics."
    ),
    "app_name": "Display name used in the web UI.",
    "samsung_port": "Samsung websocket control port.",
    "roku_port": "Roku ECP control port.",
    "android_cert_file": "Android TV pairing certificate file.",
    "android_key_file": "Android TV pairing private key file.",
    "samsung_token_file": "Samsung pairing token file.",
    "webos_client_key_file": "LG webOS pairing client key file.",
    "model_download_timeout_seconds": (
        "Maximum time to wait for each model download attempt."
    ),
    "model_download_retries": (
        "Number of model download retries after the first attempt."
    ),
    "auto_zoom_padding": "Extra crop padding around the detected active hand.",
    "auto_zoom_smoothing": "How quickly auto zoom follows target crop changes.",
    "auto_zoom_position_deadband": (
        "Ignored hand-position movement before the crop recenters."
    ),
    "auto_zoom_scale_deadband": "Ignored hand-scale movement before the crop resizes.",
    "auto_zoom_crop_reset_threshold": (
        "Crop-change threshold used before resetting tracking crop."
    ),
    "pointer_dominance": "Pointer horizontal dominance multiplier.",
    "volume_min_distance": "Smallest vertical volume movement threshold.",
    "volume_max_distance": "Largest vertical volume movement threshold.",
    "debug_log_seconds": "Minimum delay between debug log entries.",
    "metrics_log_seconds": "Minimum delay between pipeline metrics log entries.",
}

_TAB_BY_SLUG = {tab.slug: tab for tab in TABS}


def field_applies_live(name: str) -> bool:
    return name in RELOADABLE_CONFIG_FIELDS


def field_help(name: str) -> str | None:
    return FIELD_HELP.get(name)


def field_readonly(name: str) -> bool:
    return name in READONLY_FIELDS


def default_tab() -> ConfigTab:
    return TABS[0]


def tab_by_slug(slug: str | None) -> ConfigTab:
    if slug is None:
        return default_tab()
    return _TAB_BY_SLUG.get(slug, default_tab())


def tab_fields(tab: ConfigTab) -> tuple[str, ...]:
    return tuple(name for group in tab.groups for name in group.fields)


def changed_restart_fields(before: AppConfig, after: AppConfig) -> tuple[str, ...]:
    return tuple(
        field.name
        for field in CONFIG_FIELDS
        if not field_applies_live(field.name)
        and get_config_value(before, field.name) != get_config_value(after, field.name)
    )


def field_label(name: str) -> str:
    return name.replace("_", " ").title()


def select_options(name: str) -> tuple[str, ...]:
    if name == "tv_adapter":
        return TV_ADAPTERS
    if name == "voice_input_target":
        return VOICE_INPUT_TARGETS
    return ()


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
        return ' min="2"'
    if name == "webcam_index":
        return ' min="0"'
    if name in {
        "debounce_seconds",
        "fist_hold_home_seconds",
        "voice_capture_seconds",
        "debug_log_seconds",
        "metrics_log_seconds",
        "active_hand_lost_grace_seconds",
        "active_hand_match_max_distance",
        "pointer_screen_radius_ratio",
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
    section_fields = [
        name for tab in TABS for group in tab.groups for name in group.fields
    ]
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
