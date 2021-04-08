"""Constants for the motionEye integration."""
from datetime import timedelta

DOMAIN = "motioneye"

API_PATH_ROOT = f"/api/{DOMAIN}"
API_PATH_DEVICE_ROOT = f"{API_PATH_ROOT}/device/"

EVENT_MOTION_DETECTED = "motion_detected"
EVENT_MEDIA_STORED = "media_stored"

API_PATH_EVENT_REGEXP = (
    API_PATH_DEVICE_ROOT
    + r"{device_id:[-:_a-zA-Z0-9]+}/"
    + r"{event:"
    + f"({EVENT_MOTION_DETECTED}|{EVENT_MEDIA_STORED})"
    + r"}"
)

CONF_CLIENT = "client"
CONF_COORDINATOR = "coordinator"
CONF_ON_UNLOAD = "on_unload"
CONF_ADMIN_PASSWORD = "admin_password"
CONF_ADMIN_USERNAME = "admin_username"
CONF_SURVEILLANCE_USERNAME = "surveillance_username"
CONF_SURVEILLANCE_PASSWORD = "surveillance_password"
CONF_MOTION_DETECTION_WEBHOOK_SET = "motion_detection_webhook_set"
CONF_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE = "motion_detection_webhook_set_overwrite"

DEFAULT_MOTION_DETECTION_WEBHOOK_SET = True
DEFAULT_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE = False
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

MOTIONEYE_MANUFACTURER = "motionEye"

SERVICE_SET_TEXT_OVERLAY = "set_text_overlay"

SIGNAL_CAMERA_ADD = f"{DOMAIN}_camera_add_signal." "{}"
SIGNAL_CAMERA_REMOVE = f"{DOMAIN}_camera_remove_signal." "{}"

TYPE_MOTIONEYE_MJPEG_CAMERA = "motioneye_mjpeg_camera"
TYPE_MOTIONEYE_SWITCH_BASE = "motioneye_switch"
