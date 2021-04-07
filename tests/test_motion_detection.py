"""Test the motionEye camera."""
import copy
import logging
from typing import Any
from unittest.mock import AsyncMock, call, patch

from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_HTTP_METHOD_GET,
    KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
    KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
    KEY_WEB_HOOK_NOTIFICATIONS_URL,
)

from custom_components.motioneye.const import (
    API_ENDPOINT_MOTION_DETECTION,
    API_PATH_DEVICE_ROOT,
    API_PATH_ROOT,
    CONF_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE,
    DOMAIN,
    EVENT_MOTION_DETECTED,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import HTTP_NOT_FOUND, HTTP_OK
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from . import (
    TEST_CAMERA,
    TEST_CAMERA_DEVICE_ID,
    TEST_CAMERA_ID,
    TEST_CAMERA_NAME,
    TEST_CAMERAS,
    create_mock_motioneye_client,
    create_mock_motioneye_config_entry,
    setup_mock_motioneye_config_entry,
)

from pytest_homeassistant_custom_component.common import async_capture_events

_LOGGER = logging.getLogger(__name__)


async def test_setup_camera_without_webhook(hass: HomeAssistantType) -> None:
    """Test a basic camera."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    device_registry = await dr.async_get_registry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_CAMERA_DEVICE_ID)}
    )
    assert device

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[
        KEY_WEB_HOOK_NOTIFICATIONS_URL
    ] = f"http://example.local:8123/api/motioneye/device/{device.id}/motion_detection"

    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_setup_camera_with_wrong_webhook(
    hass: HomeAssistantType,
) -> None:
    """Test a basic camera."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    wrong_url = "http://wrong-url"

    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_WEB_HOOK_NOTIFICATIONS_URL] = wrong_url
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
            config_entry, options={CONF_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE: True}
        )
        await hass.async_block_till_done()

    device_registry = await dr.async_get_registry(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_CAMERA_DEVICE_ID)}
    )
    assert device

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_ENABLED] = True
    expected_camera[KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD] = KEY_HTTP_METHOD_GET
    expected_camera[
        KEY_WEB_HOOK_NOTIFICATIONS_URL
    ] = f"http://example.local:8123/api/motioneye/device/{device.id}/motion_detection"

    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_good_query(hass: HomeAssistantType, aiohttp_client: Any) -> None:
    """Test a basic camera."""
    await async_setup_component(hass, "http", {"http": {}})

    device_registry = await dr.async_get_registry(hass)
    client = create_mock_motioneye_client()
    config_entry = await setup_mock_motioneye_config_entry(hass, client=client)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, TEST_CAMERA_DEVICE_ID)},
    )

    events = async_capture_events(hass, EVENT_MOTION_DETECTED)

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(
        API_PATH_DEVICE_ROOT + TEST_CAMERA_DEVICE_ID + API_ENDPOINT_MOTION_DETECTION
    )
    assert resp.status == HTTP_OK

    assert len(events) == 1
    assert events[0].data == {
        "unique_id": "test:8766_100",
        "name": TEST_CAMERA_NAME,
        "device_id": device.id,
    }


async def test_bad_query_wrong_url(
    hass: HomeAssistantType, aiohttp_client: Any
) -> None:
    """Test a basic camera."""
    await async_setup_component(hass, "http", {"http": {}})
    await setup_mock_motioneye_config_entry(hass)

    client = await aiohttp_client(hass.http.app)

    resp = await client.get(API_PATH_ROOT)
    assert resp.status == HTTP_NOT_FOUND

    resp = await client.get(API_PATH_DEVICE_ROOT)
    assert resp.status == HTTP_NOT_FOUND


async def test_bad_query_no_device(
    hass: HomeAssistantType, aiohttp_client: Any
) -> None:
    """Test a basic camera."""
    await async_setup_component(hass, "http", {"http": {}})
    await setup_mock_motioneye_config_entry(hass)

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(
        API_PATH_DEVICE_ROOT + "not-a-real-device" + API_ENDPOINT_MOTION_DETECTION
    )
    assert resp.status == HTTP_NOT_FOUND
