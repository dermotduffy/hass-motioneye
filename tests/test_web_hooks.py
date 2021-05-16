"""Test the motionEye camera web hooks."""
import copy
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_HTTP_METHOD_GET,
    KEY_ROOT_DIRECTORY,
    KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
    KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
    KEY_WEB_HOOK_NOTIFICATIONS_URL,
    KEY_WEB_HOOK_STORAGE_ENABLED,
    KEY_WEB_HOOK_STORAGE_HTTP_METHOD,
    KEY_WEB_HOOK_STORAGE_URL,
)
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.motioneye.const import (
    API_PATH_DEVICE_ROOT,
    API_PATH_ROOT,
    CONF_WEBHOOK_SET_OVERWRITE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_FILE_STORED,
    EVENT_MOTION_DETECTED,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import HTTP_NOT_FOUND, HTTP_OK
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    TEST_CAMERA,
    TEST_CAMERA_DEVICE_IDENTIFIER,
    TEST_CAMERA_ID,
    TEST_CAMERA_NAME,
    TEST_CAMERAS,
    TEST_CONFIG_ENTRY_ID,
    create_mock_motioneye_client,
    create_mock_motioneye_config_entry,
    setup_mock_motioneye_config_entry,
)

_LOGGER = logging.getLogger(__name__)


WEB_HOOK_MOTION_DETECTED_QUERY_STRING = (
    "camera_id=%t&changed_pixels=%D&despeckle_labels=%Q&event=%v&fps=%{fps}"
    "&frame_number=%q&height=%h&host=%{host}&motion_center_x=%K&motion_center_y=%L"
    "&motion_height=%J&motion_version=%{ver}&motion_width=%i&noise_level=%N"
    "&threshold=%o&width=%w&src=hass-motioneye"
)

WEB_HOOK_FILE_STORED_QUERY_STRING = (
    "camera_id=%t&event=%v&file_path=%f&file_type=%n&fps=%{fps}&frame_number=%q"
    "&height=%h&host=%{host}&motion_version=%{ver}&noise_level=%N&threshold=%o&width=%w"
    "&src=hass-motioneye"
)


async def test_setup_camera_without_webhook(hass: HomeAssistant) -> None:
    """Test a camera with no webhook."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    device_registry = await dr.async_get_registry(hass)
    device = device_registry.async_get_device(
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER}
    )
    assert device

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/motion_detected?"
        f"{WEB_HOOK_MOTION_DETECTED_QUERY_STRING}"
    )

    expected_camera[KEY_WEB_HOOK_STORAGE_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_STORAGE_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[KEY_WEB_HOOK_STORAGE_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/file_stored?"
        f"{WEB_HOOK_FILE_STORED_QUERY_STRING}"
    )

    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_setup_camera_with_wrong_webhook(
    hass: HomeAssistant,
) -> None:
    """Test camera with wrong web hook."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    wrong_url = "http://wrong-url"

    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_NOTIFICATIONS_URL] = wrong_url
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_STORAGE_URL] = wrong_url
    client.async_get_cameras = AsyncMock(return_value=cameras)

    config_entry = create_mock_motioneye_config_entry(hass)
    await setup_mock_motioneye_config_entry(
        hass,
        config_entry=config_entry,
        client=client,
    )
    assert not client.async_set_camera.called

    # Update the options, which will trigger a reload with the new behavior.
    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=client,
    ):
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_WEBHOOK_SET_OVERWRITE: True}
        )
        await hass.async_block_till_done()

    device_registry = await dr.async_get_registry(hass)
    device = device_registry.async_get_device(
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER}
    )
    assert device

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/motion_detected?"
        f"{WEB_HOOK_MOTION_DETECTED_QUERY_STRING}"
    )

    expected_camera[KEY_WEB_HOOK_STORAGE_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_STORAGE_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[KEY_WEB_HOOK_STORAGE_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/file_stored?"
        f"{WEB_HOOK_FILE_STORED_QUERY_STRING}"
    )

    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_setup_camera_with_old_webhook(
    hass: HomeAssistant,
) -> None:
    """Verify that webhooks are overwritten if they are from this integration.

    Even if the overwrite option is disabled, verify the behavior is still to
    overwrite incorrect versions of the URL that were set by this integration.

    (To allow the web hook URL to be seamlessly updated in future versions)
    """

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    old_url = "http://old-url?src=hass-motioneye"

    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_NOTIFICATIONS_URL] = old_url
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_STORAGE_URL] = old_url
    client.async_get_cameras = AsyncMock(return_value=cameras)

    config_entry = create_mock_motioneye_config_entry(hass)
    await setup_mock_motioneye_config_entry(
        hass,
        config_entry=config_entry,
        client=client,
    )
    assert client.async_set_camera.called

    device_registry = await dr.async_get_registry(hass)
    device = device_registry.async_get_device(
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER}
    )
    assert device

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/motion_detected?"
        f"{WEB_HOOK_MOTION_DETECTED_QUERY_STRING}"
    )

    expected_camera[KEY_WEB_HOOK_STORAGE_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_STORAGE_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[KEY_WEB_HOOK_STORAGE_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/file_stored?"
        f"{WEB_HOOK_FILE_STORED_QUERY_STRING}"
    )

    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_setup_camera_with_correct_webhook(
    hass: HomeAssistant,
) -> None:
    """Verify that webhooks are not overwritten if they are already correct."""

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    client = create_mock_motioneye_client()
    config_entry = create_mock_motioneye_config_entry(hass)

    device_registry = await dr.async_get_registry(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER},
    )

    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_NOTIFICATIONS_ENABLED] = True
    cameras[KEY_CAMERAS][0][
        KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD
    ] = KEY_HTTP_METHOD_GET
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_NOTIFICATIONS_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/motion_detected?"
        f"{WEB_HOOK_MOTION_DETECTED_QUERY_STRING}"
    )
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_STORAGE_ENABLED] = True
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_STORAGE_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_STORAGE_URL] = (
        f"http://example.local:8123/api/motioneye/device/{device.id}/file_stored?"
        f"{WEB_HOOK_FILE_STORED_QUERY_STRING}"
    )
    client.async_get_cameras = AsyncMock(return_value=cameras)

    await setup_mock_motioneye_config_entry(
        hass,
        config_entry=config_entry,
        client=client,
    )

    # Webhooks are correctly configured, so no set call should have been made.
    assert not client.async_set_camera.called


async def test_good_query(hass: HomeAssistant, aiohttp_client: Any) -> None:
    """Test good callbacks."""
    await async_setup_component(hass, "http", {"http": {}})

    device_registry = await dr.async_get_registry(hass)
    client = create_mock_motioneye_client()
    config_entry = await setup_mock_motioneye_config_entry(hass, client=client)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER},
    )

    data = {
        "one": "1",
        "two": "2",
    }
    client = await aiohttp_client(hass.http.app)

    for event in (EVENT_MOTION_DETECTED, EVENT_FILE_STORED):
        events = async_capture_events(hass, f"{DOMAIN}.{event}")

        resp = await client.get(
            API_PATH_DEVICE_ROOT + device.id + "/" + event + "?" + "&one=1&two=2"
        )
        assert resp.status == HTTP_OK

        assert len(events) == 1
        assert events[0].data == {
            "name": TEST_CAMERA_NAME,
            "device_id": device.id,
            **data,
        }


async def test_bad_query_wrong_url(hass: HomeAssistant, aiohttp_client: Any) -> None:
    """Test an incorrect query."""
    await async_setup_component(hass, "http", {"http": {}})
    await setup_mock_motioneye_config_entry(hass)

    client = await aiohttp_client(hass.http.app)

    resp = await client.get(API_PATH_ROOT)
    assert resp.status == HTTP_NOT_FOUND

    resp = await client.get(API_PATH_DEVICE_ROOT)
    assert resp.status == HTTP_NOT_FOUND


async def test_bad_query_no_device(hass: HomeAssistant, aiohttp_client: Any) -> None:
    """Test a correct query with incorrect device."""
    await async_setup_component(hass, "http", {"http": {}})
    await setup_mock_motioneye_config_entry(hass)

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(
        API_PATH_DEVICE_ROOT + "not-a-real-device" + "/" + EVENT_MOTION_DETECTED
    )
    assert resp.status == HTTP_NOT_FOUND


async def test_event_media_data(hass: HomeAssistant, aiohttp_client: Any) -> None:
    """Test an event with a file path generates media data."""
    await async_setup_component(hass, "http", {"http": {}})

    device_registry = await dr.async_get_registry(hass)
    client = create_mock_motioneye_client()
    config_entry = await setup_mock_motioneye_config_entry(hass, client=client)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER},
    )

    aio_client = await aiohttp_client(hass.http.app)

    events = async_capture_events(hass, f"{DOMAIN}.{EVENT_FILE_STORED}")

    client.get_movie_url = Mock(return_value="http://movie-url")
    client.get_image_url = Mock(return_value="http://image-url")

    # Test: Movie storage.
    client.is_file_type_image = Mock(return_value=False)
    resp = await aio_client.get(
        API_PATH_DEVICE_ROOT
        + device.id
        + f"/{EVENT_FILE_STORED}"
        + "?"
        + f"&file_path=/var/lib/motioneye/{TEST_CAMERA_NAME}/dir/one"
        + "&file_type=8"
    )
    assert resp.status == HTTP_OK
    assert len(events) == 1
    assert events[-1].data["file_url"] == "http://movie-url"
    assert (
        events[-1].data["media_content_id"]
        == f"media-source://motioneye/{TEST_CONFIG_ENTRY_ID}#{device.id}#movies#/dir/one"
    )
    assert client.get_movie_url.call_args == call(TEST_CAMERA_ID, "/dir/one")

    # Test: Image storage.
    client.is_file_type_image = Mock(return_value=True)
    resp = await aio_client.get(
        API_PATH_DEVICE_ROOT
        + device.id
        + f"/{EVENT_FILE_STORED}"
        + "?"
        + f"&file_path=/var/lib/motioneye/{TEST_CAMERA_NAME}/dir/two"
        + "&file_type=4"
    )
    assert resp.status == HTTP_OK
    assert len(events) == 2
    assert events[-1].data["file_url"] == "http://image-url"
    assert (
        events[-1].data["media_content_id"]
        == f"media-source://motioneye/{TEST_CONFIG_ENTRY_ID}#{device.id}#images#/dir/two"
    )
    assert client.get_image_url.call_args == call(TEST_CAMERA_ID, "/dir/two")

    # Test: Invalid file type.
    resp = await aio_client.get(
        API_PATH_DEVICE_ROOT
        + device.id
        + f"/{EVENT_FILE_STORED}"
        + "?"
        + f"&file_path=/var/lib/motioneye/{TEST_CAMERA_NAME}/dir/two"
        + "&file_type=NOT_AN_INT"
    )
    assert resp.status == HTTP_OK
    assert len(events) == 3
    assert "file_url" not in events[-1].data
    assert "media_content_id" not in events[-1].data

    # Test: Different file path.
    resp = await aio_client.get(
        API_PATH_DEVICE_ROOT
        + device.id
        + f"/{EVENT_FILE_STORED}"
        + "?"
        + "&file_path=/var/random"
        + "&file_type=8"
    )
    assert resp.status == HTTP_OK
    assert len(events) == 4
    assert "file_url" not in events[-1].data
    assert "media_content_id" not in events[-1].data

    # Test: Not a loaded motionEye config entry.
    wrong_device = device_registry.async_get_or_create(
        config_entry_id="wrong_config_id", identifiers={("motioneye", "a_1")}
    )
    resp = await aio_client.get(
        API_PATH_DEVICE_ROOT
        + wrong_device.id
        + f"/{EVENT_FILE_STORED}"
        + "?"
        + f"&file_path=/var/lib/motioneye/{TEST_CAMERA_NAME}/dir/two"
        + "&file_type=8"
    )
    assert resp.status == HTTP_OK
    assert len(events) == 5
    assert "file_url" not in events[-1].data
    assert "media_content_id" not in events[-1].data

    # Test: No root directory.
    camera = copy.deepcopy(TEST_CAMERA)
    del camera[KEY_ROOT_DIRECTORY]
    client.async_get_cameras = AsyncMock(return_value={"cameras": [camera]})
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    resp = await aio_client.get(
        API_PATH_DEVICE_ROOT
        + device.id
        + f"/{EVENT_FILE_STORED}"
        + "?"
        + f"&file_path=/var/lib/motioneye/{TEST_CAMERA_NAME}/dir/two"
        + "&file_type=8"
    )
    assert resp.status == HTTP_OK
    assert len(events) == 6
    assert "file_url" not in events[-1].data
    assert "media_content_id" not in events[-1].data

    # Test: Device has incorrect device identifiers.
    device_registry.async_update_device(
        device_id=device.id, new_identifiers={"not", "motioneye"}
    )

    resp = await aio_client.get(
        API_PATH_DEVICE_ROOT
        + device.id
        + f"/{EVENT_FILE_STORED}"
        + "?"
        + f"&file_path=/var/lib/motioneye/{TEST_CAMERA_NAME}/dir/two"
        + "&file_type=8"
    )
    assert resp.status == HTTP_OK
    assert len(events) == 7
    assert "file_url" not in events[-1].data
    assert "media_content_id" not in events[-1].data
