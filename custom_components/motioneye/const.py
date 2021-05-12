"""Constants for the motionEye integration."""
from datetime import timedelta

from motioneye_client.const import (
    KEY_WEB_HOOK_CS_CAMERA_ID,
    KEY_WEB_HOOK_CS_CHANGED_PIXELS,
    KEY_WEB_HOOK_CS_DESPECKLE_LABELS,
    KEY_WEB_HOOK_CS_EVENT,
    KEY_WEB_HOOK_CS_FILE_PATH,
    KEY_WEB_HOOK_CS_FILE_TYPE,
    KEY_WEB_HOOK_CS_FPS,
    KEY_WEB_HOOK_CS_FRAME_NUMBER,
    KEY_WEB_HOOK_CS_HEIGHT,
    KEY_WEB_HOOK_CS_HOST,
    KEY_WEB_HOOK_CS_MOTION_CENTER_X,
    KEY_WEB_HOOK_CS_MOTION_CENTER_Y,
    KEY_WEB_HOOK_CS_MOTION_HEIGHT,
    KEY_WEB_HOOK_CS_MOTION_VERSION,
    KEY_WEB_HOOK_CS_MOTION_WIDTH,
    KEY_WEB_HOOK_CS_NOISE_LEVEL,
    KEY_WEB_HOOK_CS_THRESHOLD,
    KEY_WEB_HOOK_CS_WIDTH,
)

DOMAIN = "motioneye"

API_PATH_ROOT = f"/api/{DOMAIN}"
API_PATH_DEVICE_ROOT = f"{API_PATH_ROOT}/device/"

EVENT_MOTION_DETECTED = "motion_detected"
EVENT_FILE_STORED = "file_stored"

API_PATH_EVENT_REGEXP = (
    API_PATH_DEVICE_ROOT
    + r"{device_id:[-:_a-zA-Z0-9]+}/"
    + r"{event:"
    + f"({EVENT_MOTION_DETECTED}|{EVENT_FILE_STORED})"
    + r"}"
)

CONF_ACTION = "action"
CONF_CLIENT = "client"
CONF_COORDINATOR = "coordinator"
CONF_ON_UNLOAD = "on_unload"
CONF_ADMIN_PASSWORD = "admin_password"
CONF_ADMIN_USERNAME = "admin_username"
CONF_SURVEILLANCE_USERNAME = "surveillance_username"
CONF_SURVEILLANCE_PASSWORD = "surveillance_password"
CONF_WEBHOOK_SET = "webhook_set"
CONF_WEBHOOK_SET_OVERWRITE = "webhook_set_overwrite"
CONF_STREAM_URL_TEMPLATE = "stream_url_template"
CONF_EVENT_DURATION = "event_duration"

DEFAULT_WEBHOOK_SET = True
DEFAULT_WEBHOOK_SET_OVERWRITE = False
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_EVENT_DURATION = 30

EVENT_MOTION_DETECTED_KEYS = [
    KEY_WEB_HOOK_CS_EVENT,
    KEY_WEB_HOOK_CS_FRAME_NUMBER,
    KEY_WEB_HOOK_CS_CAMERA_ID,
    KEY_WEB_HOOK_CS_CHANGED_PIXELS,
    KEY_WEB_HOOK_CS_NOISE_LEVEL,
    KEY_WEB_HOOK_CS_WIDTH,
    KEY_WEB_HOOK_CS_HEIGHT,
    KEY_WEB_HOOK_CS_MOTION_WIDTH,
    KEY_WEB_HOOK_CS_MOTION_HEIGHT,
    KEY_WEB_HOOK_CS_MOTION_CENTER_X,
    KEY_WEB_HOOK_CS_MOTION_CENTER_Y,
    KEY_WEB_HOOK_CS_THRESHOLD,
    KEY_WEB_HOOK_CS_DESPECKLE_LABELS,
    KEY_WEB_HOOK_CS_FPS,
    KEY_WEB_HOOK_CS_HOST,
    KEY_WEB_HOOK_CS_MOTION_VERSION,
]

EVENT_FILE_STORED_KEYS = [
    KEY_WEB_HOOK_CS_EVENT,
    KEY_WEB_HOOK_CS_FRAME_NUMBER,
    KEY_WEB_HOOK_CS_CAMERA_ID,
    KEY_WEB_HOOK_CS_NOISE_LEVEL,
    KEY_WEB_HOOK_CS_WIDTH,
    KEY_WEB_HOOK_CS_HEIGHT,
    KEY_WEB_HOOK_CS_FILE_PATH,
    KEY_WEB_HOOK_CS_FILE_TYPE,
    KEY_WEB_HOOK_CS_THRESHOLD,
    KEY_WEB_HOOK_CS_FPS,
    KEY_WEB_HOOK_CS_HOST,
    KEY_WEB_HOOK_CS_MOTION_VERSION,
]

MOTIONEYE_MANUFACTURER = "motionEye"

SERVICE_SET_TEXT_OVERLAY = "set_text_overlay"
SERVICE_ACTION = "action"
SERVICE_SNAPSHOT = "snapshot"

SIGNAL_CAMERA_ADD = f"{DOMAIN}_camera_add_signal." "{}"
SIGNAL_CAMERA_REMOVE = f"{DOMAIN}_camera_remove_signal." "{}"

TYPE_MOTIONEYE_MJPEG_CAMERA = f"{DOMAIN}_mjpeg_camera"
TYPE_MOTIONEYE_SWITCH_BASE = f"{DOMAIN}_switch"
TYPE_MOTIONEYE_ACTION_SENSOR = f"{DOMAIN}_action_sensor"
TYPE_MOTIONEYE_MOTION_BINARY_SENSOR = f"{DOMAIN}_motion_binary_sensor"
TYPE_MOTIONEYE_FILE_STORED_BINARY_SENSOR = f"{DOMAIN}_file_stored_binary_sensor"

WEB_HOOK_SENTINEL_KEY = "src"
WEB_HOOK_SENTINEL_VALUE = "hass-motioneye"
