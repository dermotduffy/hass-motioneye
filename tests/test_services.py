"""Test motionEye integration services."""
import copy
import logging
from unittest.mock import AsyncMock, call

from motioneye_client.const import (
    KEY_TEXT_OVERLAY_CUSTOM_TEXT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
    KEY_TEXT_OVERLAY_LEFT,
    KEY_TEXT_OVERLAY_RIGHT,
    KEY_TEXT_OVERLAY_TIMESTAMP,
)
import pytest
import voluptuous as vol

from custom_components.motioneye.const import DOMAIN, SERVICE_SET_TEXT_OVERLAY
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    TEST_CAMERA,
    TEST_CAMERA_ENTITY_ID,
    TEST_CAMERA_ID,
    TEST_CONFIG_ENTRY_ID,
    create_mock_motioneye_client,
    setup_mock_motioneye_config_entry,
)

_LOGGER = logging.getLogger(__name__)


async def test_text_overlay_bad_extra_key(hass: HomeAssistantType) -> None:
    """Test text overlay with incorrect input data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {ATTR_DEVICE_ID: "device", "extra_key": "foo"}
    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)


async def test_text_overlay_bad_device_unique_id(hass: HomeAssistantType) -> None:
    """Test text overlay with incorrect input data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    device = dr.async_entries_for_config_entry(
        await dr.async_get_registry(hass), TEST_CONFIG_ENTRY_ID
    )[0]
    device_registry = await dr.async_get_registry(hass)

    # Set the device_unique_id to something broken (non-int camera index).
    device_registry.async_update_device(
        device_id=device.id, new_identifiers={(DOMAIN, "host:port_str")}
    )

    data = {
        ATTR_DEVICE_ID: device.id,
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert not client.async_set_camera.called


async def test_text_overlay_bad_empty(hass: HomeAssistantType) -> None:
    """Test text overlay with incorrect input data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, {})
        await hass.async_block_till_done()


async def test_setup_text_overlay_bad_no_left_or_right(hass: HomeAssistantType) -> None:
    """Test text overlay with incorrect input data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {ATTR_DEVICE_ID: "device"}
    with pytest.raises(vol.error.MultipleInvalid):
        await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
        await hass.async_block_till_done()


async def test_text_overlay_good_left(hass: HomeAssistantType) -> None:
    """Test a working text overlay with device_id."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    device = dr.async_entries_for_config_entry(
        await dr.async_get_registry(hass), TEST_CONFIG_ENTRY_ID
    )[0]

    custom_right_text = "one\ntwo\nthree"
    data = {
        ATTR_DEVICE_ID: device.id,
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
        KEY_TEXT_OVERLAY_RIGHT: KEY_TEXT_OVERLAY_CUSTOM_TEXT,
        KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT: custom_right_text,
    }
    client.async_get_camera = AsyncMock(return_value=copy.deepcopy(TEST_CAMERA))
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert client.async_get_camera.called

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_TEXT_OVERLAY_LEFT] = KEY_TEXT_OVERLAY_TIMESTAMP
    expected_camera[KEY_TEXT_OVERLAY_RIGHT] = KEY_TEXT_OVERLAY_CUSTOM_TEXT
    expected_camera[KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT] = "one\\ntwo\\nthree"
    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_text_overlay_good_entity_id(hass: HomeAssistantType) -> None:
    """Test a working text overlay with entity_id."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }
    client.async_get_camera = AsyncMock(return_value=copy.deepcopy(TEST_CAMERA))
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert client.async_get_camera.called

    expected_camera = copy.deepcopy(TEST_CAMERA)
    expected_camera[KEY_TEXT_OVERLAY_LEFT] = KEY_TEXT_OVERLAY_TIMESTAMP
    assert client.async_set_camera.call_args == call(TEST_CAMERA_ID, expected_camera)


async def test_text_overlay_missing_device(hass: HomeAssistantType) -> None:
    """Test a working text overlay."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_DEVICE_ID: "not a device",
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }
    client.async_get_camera = AsyncMock(return_value=copy.deepcopy(TEST_CAMERA))
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert not client.async_get_camera.called
    assert not client.async_set_camera.called


async def test_text_overlay_no_such_camera(hass: HomeAssistantType) -> None:
    """Test a working text overlay."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    data = {
        ATTR_ENTITY_ID: TEST_CAMERA_ENTITY_ID,
        KEY_TEXT_OVERLAY_LEFT: KEY_TEXT_OVERLAY_TIMESTAMP,
    }
    client.async_get_camera = AsyncMock(return_value={})
    await hass.services.async_call(DOMAIN, SERVICE_SET_TEXT_OVERLAY, data)
    await hass.async_block_till_done()
    assert not client.async_set_camera.called