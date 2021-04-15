"""Switch platform for motionEye."""
from __future__ import annotations

from typing import Any, Callable

from motioneye_client.client import MotionEyeClient
from motioneye_client.const import (
    KEY_ID,
    KEY_MOTION_DETECTION,
    KEY_MOVIES,
    KEY_NAME,
    KEY_STILL_IMAGES,
    KEY_TEXT_OVERLAY,
    KEY_VIDEO_STREAMING,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from . import (
    get_camera_from_cameras,
    get_motioneye_device_unique_id,
    get_motioneye_entity_unique_id,
    listen_for_new_cameras,
)
from .const import (
    CONF_CLIENT,
    CONF_COORDINATOR,
    DOMAIN,
    TYPE_MOTIONEYE_SWITCH_BASE,
)

MOTIONEYE_SWITCHES = [
    KEY_MOTION_DETECTION,
    KEY_TEXT_OVERLAY,
    KEY_VIDEO_STREAMING,
    KEY_STILL_IMAGES,
    KEY_MOVIES,
]


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: Callable
) -> bool:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    @callback  # type: ignore[misc]
    def camera_add(camera: dict[str, Any]) -> None:
        """Add a new motionEye camera."""
        async_add_entities(
            [
                MotionEyeSwitch(
                    entry.entry_id,
                    camera,
                    switch_key,
                    entry_data[CONF_CLIENT],
                    entry_data[CONF_COORDINATOR],
                )
                for switch_key in MOTIONEYE_SWITCHES
            ]
        )

    listen_for_new_cameras(hass, entry, camera_add)
    return True


class MotionEyeSwitch(SwitchEntity, CoordinatorEntity):  # type: ignore[misc]
    """MotionEyeSwitch switch class."""

    def __init__(
        self,
        config_entry_id: str,
        camera: dict[str, Any],
        switch_key: str,
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
    ):
        """Initialize the switch."""
        self._switch_key = switch_key
        self._switch_key_friendly_name = " ".join(
            [w.capitalize() for w in self._switch_key.split("_")]
        )
        self._client = client
        self._camera_id = camera[KEY_ID]
        self._device_id = get_motioneye_device_unique_id(
            config_entry_id, self._camera_id
        )
        self._unique_id = get_motioneye_entity_unique_id(
            config_entry_id,
            self._camera_id,
            slugify(f"{TYPE_MOTIONEYE_SWITCH_BASE} {switch_key}"),
        )
        self._camera = get_camera_from_cameras(self._camera_id, coordinator.data)
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        camera_name = self._camera[KEY_NAME] if self._camera else ""
        return f"{camera_name} {self._switch_key_friendly_name}"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return bool(self._camera and self._camera.get(self._switch_key, False))

    async def _async_send_set_camera(self, value: bool) -> None:
        """Set a switch value."""

        # Fetch the very latest camera config to reduce the risk of updating with a
        # stale configuration.
        camera = await self._client.async_get_camera(self._camera_id)
        if camera:
            camera[self._switch_key] = value
            await self._client.async_set_camera(self._camera_id, camera)
            await self.coordinator.async_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._async_send_set_camera(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._async_send_set_camera(False)

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return the device information."""
        return {"identifiers": {(DOMAIN, self._device_id)}}

    @callback  # type: ignore[misc]
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._camera = get_camera_from_cameras(self._camera_id, self.coordinator.data)
        CoordinatorEntity._handle_coordinator_update(self)
