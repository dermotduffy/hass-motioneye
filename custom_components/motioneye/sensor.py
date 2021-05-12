"""The motionEye integration."""
from __future__ import annotations

import logging
from typing import Any, Callable

from motioneye_client.client import MotionEyeClient
from motioneye_client.const import KEY_ACTIONS, KEY_NAME

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import MotionEyeEntity, listen_for_new_cameras
from .const import CONF_CLIENT, CONF_COORDINATOR, DOMAIN, TYPE_MOTIONEYE_ACTION_SENSOR

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    @callback  # type: ignore[misc]
    def camera_add(camera: dict[str, Any]) -> None:
        """Add a new motionEye camera."""
        async_add_entities(
            [
                MotionEyeActionSensor(
                    entry.entry_id,
                    camera,
                    entry_data[CONF_CLIENT],
                    entry_data[CONF_COORDINATOR],
                    entry.options,
                )
            ]
        )

    listen_for_new_cameras(hass, entry, camera_add)


class MotionEyeActionSensor(MotionEyeEntity, SensorEntity):  # type: ignore[misc]
    """motionEye action sensor camera."""

    def __init__(
        self,
        config_entry_id: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: dict[str, Any],
    ) -> None:
        """Initialize an action sensor."""
        MotionEyeEntity.__init__(
            self,
            config_entry_id,
            TYPE_MOTIONEYE_ACTION_SENSOR,
            camera,
            client,
            coordinator,
            options,
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        camera_name = self._camera[KEY_NAME] if self._camera else ""
        return f"{camera_name} Actions"

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return len(self._camera.get(KEY_ACTIONS, [])) if self._camera else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Add actions as attribute."""
        return {KEY_ACTIONS: self._camera.get(KEY_ACTIONS, []) if self._camera else []}

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Whether or not the entity is enabled by default."""
        return False
