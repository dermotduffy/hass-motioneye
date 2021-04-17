"""The motionEye integration."""
from __future__ import annotations

import logging
from typing import Any, Callable

import aiohttp
from homeassistant.components.mjpeg.camera import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    CONF_VERIFY_SSL,
    MjpegCamera,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from jinja2 import Template
from motioneye_client.client import MotionEyeClient, MotionEyeClientURLParseError
from motioneye_client.const import (
    DEFAULT_SURVEILLANCE_USERNAME,
    KEY_ID,
    KEY_MOTION_DETECTION,
    KEY_NAME,
    KEY_STREAMING_AUTH_MODE,
)

from . import (
    get_camera_from_cameras,
    get_motioneye_device_unique_id,
    get_motioneye_entity_unique_id,
    is_acceptable_camera,
    listen_for_new_cameras,
)
from .const import (
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_STREAM_URL_TEMPLATE,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    DOMAIN,
    MOTIONEYE_MANUFACTURER,
    TYPE_MOTIONEYE_MJPEG_CAMERA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> bool:
    """Set up motionEye from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    @callback  # type: ignore[misc]
    def camera_add(camera: dict[str, Any]) -> None:
        """Add a new motionEye camera."""
        async_add_entities(
            [
                MotionEyeMjpegCamera(
                    entry.entry_id,
                    entry.data.get(
                        CONF_SURVEILLANCE_USERNAME, DEFAULT_SURVEILLANCE_USERNAME
                    ),
                    entry.data.get(CONF_SURVEILLANCE_PASSWORD, ""),
                    camera,
                    entry_data[CONF_CLIENT],
                    entry_data[CONF_COORDINATOR],
                    entry.options,
                )
            ]
        )

    listen_for_new_cameras(hass, entry, camera_add)
    return True


class MotionEyeMjpegCamera(MjpegCamera, CoordinatorEntity):  # type: ignore[misc]
    """motionEye mjpeg camera."""

    def __init__(
        self,
        config_entry_id: str,
        username: str,
        password: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: dict[str, Any],
    ):
        """Initialize a MJPEG camera."""
        self._surveillance_username = username
        self._surveillance_password = password
        self._client = client
        self._camera_id = camera[KEY_ID]
        self._device_id = get_motioneye_device_unique_id(
            config_entry_id, self._camera_id
        )
        self._unique_id = get_motioneye_entity_unique_id(
            config_entry_id, self._camera_id, TYPE_MOTIONEYE_MJPEG_CAMERA
        )
        self._motion_detection_enabled: bool = camera.get(KEY_MOTION_DETECTION, False)
        self._available = MotionEyeMjpegCamera._is_acceptable_streaming_camera(camera)

        # motionEye cameras are always streaming or unavailable.
        self.is_streaming = True
        self._options = options

        MjpegCamera.__init__(
            self,
            {
                CONF_VERIFY_SSL: False,
                **self._get_mjpeg_camera_properties_for_camera(camera),
            },
        )
        CoordinatorEntity.__init__(self, coordinator)

    def _get_mjpeg_camera_properties_for_camera(
        self, camera: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert a motionEye camera to MjpegCamera internal properties."""
        auth = None
        if camera.get(KEY_STREAMING_AUTH_MODE) in [
            HTTP_BASIC_AUTHENTICATION,
            HTTP_DIGEST_AUTHENTICATION,
        ]:
            auth = camera[KEY_STREAMING_AUTH_MODE]

        streaming_template = self._options.get(CONF_STREAM_URL_TEMPLATE, "").strip()
        streaming_url = None

        if streaming_template:
            streaming_url = Template(streaming_template).render(**camera)
        else:
            try:
                streaming_url = self._client.get_camera_steam_url(camera)
            except MotionEyeClientURLParseError:
                pass
        return {
            CONF_NAME: camera[KEY_NAME],
            CONF_USERNAME: self._surveillance_username if auth is not None else None,
            CONF_PASSWORD: self._surveillance_password if auth is not None else None,
            CONF_MJPEG_URL: streaming_url or "",
            CONF_STILL_IMAGE_URL: self._client.get_camera_snapshot_url(camera),
            CONF_AUTHENTICATION: auth,
        }

    def _set_mjpeg_camera_state_for_camera(self, camera: dict[str, Any]) -> None:
        """Set the internal state to match the given camera."""

        # Sets the state of the underlying (inherited) MjpegCamera based on the updated
        # MotionEye camera dictionary.
        properties = self._get_mjpeg_camera_properties_for_camera(camera)
        self._name = properties[CONF_NAME]
        self._username = properties[CONF_USERNAME]
        self._password = properties[CONF_PASSWORD]
        self._mjpeg_url = properties[CONF_MJPEG_URL]
        self._still_image_url = properties[CONF_STILL_IMAGE_URL]
        self._authentication = properties[CONF_AUTHENTICATION]

        if self._authentication == HTTP_BASIC_AUTHENTICATION:
            self._auth = aiohttp.BasicAuth(self._username, password=self._password)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    @classmethod
    def _is_acceptable_streaming_camera(cls, camera: dict[str, Any] | None) -> bool:
        """Determine if a camera is streaming/usable."""
        return is_acceptable_camera(camera) and MotionEyeClient.is_camera_streaming(
            camera
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @callback  # type: ignore[misc]
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        available = False
        if self.coordinator.last_update_success:
            camera = get_camera_from_cameras(self._camera_id, self.coordinator.data)
            if MotionEyeMjpegCamera._is_acceptable_streaming_camera(camera):
                assert camera
                self._set_mjpeg_camera_state_for_camera(camera)
                self._motion_detection_enabled = camera.get(KEY_MOTION_DETECTION, False)
                available = True
        self._available = available
        CoordinatorEntity._handle_coordinator_update(self)

    @property
    def brand(self) -> str:
        """Return the camera brand."""
        return MOTIONEYE_MANUFACTURER

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the device information."""
        return {"identifiers": {(DOMAIN, self._device_id)}}
