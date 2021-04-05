"""Tests for the motionEye integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from motioneye_client.const import DEFAULT_PORT

from custom_components.motioneye.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType

from pytest_homeassistant_custom_component.common import MockConfigEntry

TEST_CONFIG_ENTRY_ID = "74565ad414754616000674c87bdc876c"
TEST_HOST = "test"
TEST_PORT = DEFAULT_PORT + 1
TEST_CAMERA_ID = 100
TEST_CAMERA_NAME = "Test Camera"
TEST_CAMERA_ENTITY_ID = "camera.test_camera"
TEST_CAMERA_DEVICE_ID = f"{TEST_HOST}:{TEST_PORT}_{TEST_CAMERA_ID}"
TEST_CAMERA = {
    "show_frame_changes": False,
    "framerate": 25,
    "actions": [],
    "preserve_movies": 0,
    "auto_threshold_tuning": True,
    "recording_mode": "motion-triggered",
    "monday_to": "",
    "streaming_resolution": 100,
    "light_switch_detect": 0,
    "command_end_notifications_enabled": False,
    "smb_shares": False,
    "upload_server": "",
    "monday_from": "",
    "movie_passthrough": False,
    "auto_brightness": False,
    "frame_change_threshold": 3.0,
    "name": TEST_CAMERA_NAME,
    "movie_format": "mp4:h264_omx",
    "network_username": "",
    "preserve_pictures": 0,
    "event_gap": 30,
    "enabled": True,
    "upload_movie": True,
    "video_streaming": True,
    "upload_location": "",
    "max_movie_length": 0,
    "movie_file_name": "%Y-%m-%d/%H-%M-%S",
    "upload_authorization_key": "",
    "still_images": False,
    "upload_method": "post",
    "max_frame_change_threshold": 0,
    "device_url": "rtsp://localhost/live",
    "text_overlay": False,
    "right_text": "timestamp",
    "upload_picture": True,
    "email_notifications_enabled": False,
    "working_schedule_type": "during",
    "movie_quality": 75,
    "disk_total": 44527655808,
    "upload_service": "ftp",
    "upload_password": "",
    "wednesday_to": "",
    "mask_type": "smart",
    "command_storage_enabled": False,
    "disk_used": 11419704992,
    "streaming_motion": 0,
    "manual_snapshots": True,
    "noise_level": 12,
    "mask_lines": [],
    "upload_enabled": False,
    "root_directory": f"/var/lib/motioneye/{TEST_CAMERA_NAME}",
    "clean_cloud_enabled": False,
    "working_schedule": False,
    "pre_capture": 1,
    "command_notifications_enabled": False,
    "streaming_framerate": 25,
    "email_notifications_picture_time_span": 0,
    "thursday_to": "",
    "streaming_server_resize": False,
    "upload_subfolders": True,
    "sunday_to": "",
    "left_text": "",
    "image_file_name": "%Y-%m-%d/%H-%M-%S",
    "rotation": 0,
    "capture_mode": "manual",
    "movies": False,
    "motion_detection": True,
    "text_scale": 1,
    "upload_username": "",
    "upload_port": "",
    "available_disks": [],
    "network_smb_ver": "1.0",
    "streaming_auth_mode": "basic",
    "despeckle_filter": "",
    "snapshot_interval": 0,
    "minimum_motion_frames": 20,
    "auto_noise_detect": True,
    "network_share_name": "",
    "sunday_from": "",
    "friday_from": "",
    "web_hook_storage_enabled": False,
    "custom_left_text": "",
    "streaming_port": 8081,
    "id": TEST_CAMERA_ID,
    "post_capture": 1,
    "streaming_quality": 75,
    "wednesday_from": "",
    "proto": "netcam",
    "extra_options": [],
    "image_quality": 85,
    "create_debug_media": False,
    "friday_to": "",
    "custom_right_text": "",
    "web_hook_notifications_enabled": False,
    "saturday_from": "",
    "available_resolutions": [
        "1600x1200",
        "1920x1080",
    ],
    "tuesday_from": "",
    "network_password": "",
    "saturday_to": "",
    "network_server": "",
    "smart_mask_sluggishness": 5,
    "mask": False,
    "tuesday_to": "",
    "thursday_from": "",
    "storage_device": "custom-path",
    "resolution": "1920x1080",
}
TEST_CAMERAS = {"cameras": [TEST_CAMERA]}
TEST_SURVEILLANCE_USERNAME = "surveillance_username"
TEST_SWITCH_ENTITY_ID_BASE = "switch.test_camera"
TEST_SWITCH_MOTION_DETECTION_ENTITY_ID = (
    f"{TEST_SWITCH_ENTITY_ID_BASE}_motion_detection"
)

TEST_UNIQUE_ID = f"{TEST_HOST}:{TEST_PORT}"


def create_mock_motioneye_client() -> AsyncMock:
    """Create mock motionEye client."""
    mock_client = AsyncMock()
    mock_client.async_client_login = AsyncMock(return_value={})
    mock_client.async_get_cameras = AsyncMock(return_value=TEST_CAMERAS)
    mock_client.async_client_close = AsyncMock(return_value=True)
    mock_client.get_camera_snapshot_url = Mock(return_value="")
    mock_client.get_camera_steam_url = Mock(return_value="")
    return mock_client


def create_mock_motioneye_config_entry(
    hass: HomeAssistantType,
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> ConfigEntry:
    """Add a test config entry."""
    config_entry: MockConfigEntry = MockConfigEntry(
        entry_id=TEST_CONFIG_ENTRY_ID,
        domain=DOMAIN,
        data=data or {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
        title=f"{TEST_HOST}:{TEST_PORT}",
        unique_id=TEST_UNIQUE_ID,
        options=options or {},
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def setup_mock_motioneye_config_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry | None = None,
    client: Mock | None = None,
) -> ConfigEntry:
    """Add a mock MotionEye config entry to hass."""
    config_entry = config_entry or create_mock_motioneye_config_entry(hass)
    client = client or create_mock_motioneye_client()

    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry
