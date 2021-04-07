"""The motionEye integration."""
from __future__ import annotations

import asyncio
import logging
from multidict import MultiDictProxy
import re
from typing import cast, Any, Callable

from aiohttp import web
from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientError,
    MotionEyeClientInvalidAuth,
)
import voluptuous as vol
from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_ID,
    KEY_NAME,
    KEY_TEXT_OVERLAY_CAMERA_NAME,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
    KEY_TEXT_OVERLAY_DISABLED,
    KEY_TEXT_OVERLAY_LEFT,
    KEY_TEXT_OVERLAY_RIGHT,
    KEY_TEXT_OVERLAY_TIMESTAMP,
    KEY_HTTP_METHOD_GET,
    KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
    KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
    KEY_WEB_HOOK_NOTIFICATIONS_URL,
)

from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SOURCE,
    HTTP_NOT_FOUND,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_ENDPOINT_MOTION_DETECTION,
    API_PATH_DEVICE_ROOT,
    API_PATH_MOTION_DETECTION_REGEXP,
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_MOTION_DETECTION_WEBHOOK_SET,
    CONF_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE,
    CONF_ON_UNLOAD,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    DEFAULT_MOTION_DETECTION_WEBHOOK_SET,
    DEFAULT_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_MOTION_DETECTED,
    MOTIONEYE_MANUFACTURER,
    SERVICE_SET_TEXT_OVERLAY,
    SIGNAL_CAMERA_ADD,
)

_LOGGER = logging.getLogger(__name__)

REGEXP_DEVICE_UNIQUE_ID = re.compile(r"^(?P<host>[^:]+):(?P<port>\d+)_(?P<index>\d+)$")
PLATFORMS = [CAMERA_DOMAIN, SWITCH_DOMAIN]


def create_motioneye_client(
    *args: Any,
    **kwargs: Any,
) -> MotionEyeClient:
    """Create a MotionEyeClient."""
    return MotionEyeClient(*args, **kwargs)


def get_motioneye_config_unique_id(host: str, port: int) -> str:
    """Get the unique_id for a motionEye config."""
    return f"{host}:{port}"


def get_motioneye_device_unique_id(host: str, port: int, camera_id: int) -> str:
    """Get the unique_id for a motionEye device."""
    return f"{get_motioneye_config_unique_id(host, port)}_{camera_id}"


def _split_motioneye_device_unique_id(
    device_unique_id: str,
) -> tuple[str, int, int] | None:
    """Split a unique_id into a (host, port, camera index) tuple."""
    data = REGEXP_DEVICE_UNIQUE_ID.search(device_unique_id)
    return (
        (data.group("host"), int(data.group("port")), int(data.group("index")))
        if data
        else None
    )


def get_motioneye_entity_unique_id(
    host: str, port: int, camera_id: int, entity_type: str
) -> str:
    """Get the unique_id for a motionEye entity."""
    return f"{get_motioneye_device_unique_id(host, port, camera_id)}_{entity_type}"


def get_camera_from_cameras(
    camera_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Get an individual camera dict from a multiple cameras data response."""
    for camera in data.get(KEY_CAMERAS) or []:
        if camera.get(KEY_ID) == camera_id:
            val: dict[str, Any] = camera
            return val
    return None


def is_acceptable_camera(camera: dict[str, Any] | None) -> bool:
    """Determine if a camera dict is acceptable."""
    return bool(camera and KEY_ID in camera and KEY_NAME in camera)


@callback  # type: ignore[misc]
def listen_for_new_cameras(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_func: Callable,
) -> None:
    """Listen for new cameras."""

    hass.data[DOMAIN][entry.entry_id][CONF_ON_UNLOAD].extend(
        [
            async_dispatcher_connect(
                hass,
                SIGNAL_CAMERA_ADD.format(entry.entry_id),
                add_func,
            ),
        ]
    )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the motionEye component."""
    hass.data[DOMAIN] = {}
    MotionEyeServices(hass).async_register()
    hass.http.register_view(MotionEyeMotionDetectedView())
    return True


async def _create_reauth_flow(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_REAUTH}, data=config_entry.data
        )
    )


async def _add_camera(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MotionEyeClient,
    entry: ConfigEntry,
    camera_id: int,
    camera: dict[str, Any],
    device_id: str,
) -> None:
    """Add a motionEye camera to hass."""
    device_registry = await dr.async_get_registry(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer=MOTIONEYE_MANUFACTURER,
        name=camera[KEY_NAME],
    )
    _LOGGER.error("==============> %s" % device.id)
    if entry.options.get(
        CONF_MOTION_DETECTION_WEBHOOK_SET, DEFAULT_MOTION_DETECTION_WEBHOOK_SET
    ):
        webhook_url = None
        try:
            webhook_url = f"{get_url(hass)}{API_PATH_DEVICE_ROOT}{device.id}{API_ENDPOINT_MOTION_DETECTION}"
        except NoURLAvailableError:
            pass

        if (
            webhook_url is not None
            and (
                entry.options.get(
                    CONF_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE,
                    DEFAULT_MOTION_DETECTION_WEBHOOK_SET_OVERWRITE,
                )
                or not camera.get(KEY_WEB_HOOK_NOTIFICATIONS_URL)
            )
            and (
                camera.get(KEY_WEB_HOOK_NOTIFICATIONS_ENABLED, False)
                or camera.get(KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD)
                != KEY_HTTP_METHOD_GET
                or camera.get(KEY_WEB_HOOK_NOTIFICATIONS_URL) != webhook_url
            )
        ):
            camera[KEY_WEB_HOOK_NOTIFICATIONS_ENABLED] = True
            camera[KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD] = KEY_HTTP_METHOD_GET
            camera[KEY_WEB_HOOK_NOTIFICATIONS_URL] = webhook_url
            await client.async_set_camera(camera_id, camera)

    async_dispatcher_send(
        hass,
        SIGNAL_CAMERA_ADD.format(entry.entry_id),
        camera,
    )


async def _async_entry_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle entry updates."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up motionEye from a config entry."""
    client = create_motioneye_client(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        admin_username=entry.data.get(CONF_ADMIN_USERNAME),
        admin_password=entry.data.get(CONF_ADMIN_PASSWORD),
        surveillance_username=entry.data.get(CONF_SURVEILLANCE_USERNAME),
        surveillance_password=entry.data.get(CONF_SURVEILLANCE_PASSWORD),
    )

    try:
        await client.async_client_login()
    except MotionEyeClientInvalidAuth:
        await client.async_client_close()
        await _create_reauth_flow(hass, entry)
        return False
    except MotionEyeClientError as exc:
        await client.async_client_close()
        raise ConfigEntryNotReady from exc

    async def async_update_data() -> dict[str, Any] | None:
        try:
            return await client.async_get_cameras()
        except MotionEyeClientError as exc:
            raise UpdateFailed("Error communicating with API") from exc

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_CLIENT: client,
        CONF_COORDINATOR: coordinator,
        CONF_ON_UNLOAD: [],
    }

    current_cameras: set[str] = set()
    device_registry = await dr.async_get_registry(hass)

    def _async_process_motioneye_cameras() -> None:
        """Process motionEye camera additions and removals."""
        inbound_camera: set[str] = set()
        if KEY_CAMERAS not in coordinator.data:
            return

        for camera in coordinator.data[KEY_CAMERAS]:
            if not is_acceptable_camera(camera):
                return
            camera_id = camera[KEY_ID]
            device_unique_id = get_motioneye_device_unique_id(
                entry.data[CONF_HOST], entry.data[CONF_PORT], camera_id
            )
            inbound_camera.add(device_unique_id)

            if device_unique_id in current_cameras:
                continue
            current_cameras.add(device_unique_id)
            hass.async_create_task(
                _add_camera(
                    hass,
                    device_registry,
                    client,
                    entry,
                    camera_id,
                    camera,
                    device_unique_id,
                )
            )

        # Ensure every device associated with this config entry is still in the list of
        # motionEye cameras, otherwise remove the device (and thus entities).
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            for (kind, key) in device_entry.identifiers:
                if kind == DOMAIN and key in inbound_camera:
                    break
            else:
                device_registry.async_remove_device(device_entry.id)

    async def setup_then_listen() -> None:
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            ]
        )
        hass.data[DOMAIN][entry.entry_id][CONF_ON_UNLOAD].append(
            coordinator.async_add_listener(_async_process_motioneye_cameras)
        )
        await coordinator.async_refresh()
        hass.data[DOMAIN][entry.entry_id][CONF_ON_UNLOAD].append(
            entry.add_update_listener(_async_entry_updated)
        )

    hass.async_create_task(setup_then_listen())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        config_data = hass.data[DOMAIN].pop(entry.entry_id)
        await config_data[CONF_CLIENT].async_client_close()
        for func in config_data[CONF_ON_UNLOAD]:
            func()

    return unload_ok


SCHEMA_TEXT_OVERLAY = vol.In(
    [
        KEY_TEXT_OVERLAY_DISABLED,
        KEY_TEXT_OVERLAY_TIMESTAMP,
        KEY_TEXT_OVERLAY_CUSTOM_TEXT,
        KEY_TEXT_OVERLAY_CAMERA_NAME,
    ]
)


class MotionEyeServices:
    """Class that holds motionEye services that should be published to hass."""

    def __init__(self, hass: HomeAssistant):
        """Initialize with hass object."""
        self._hass = hass

    @callback  # type: ignore[misc]
    def async_register(self) -> None:
        """Register all our services."""
        self._hass.services.async_register(
            DOMAIN,
            SERVICE_SET_TEXT_OVERLAY,
            self._async_set_text_overlay,
            schema=vol.All(
                {
                    vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
                    vol.Optional(KEY_TEXT_OVERLAY_LEFT): SCHEMA_TEXT_OVERLAY,
                    vol.Optional(KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT): cv.string,
                    vol.Optional(KEY_TEXT_OVERLAY_RIGHT): SCHEMA_TEXT_OVERLAY,
                    vol.Optional(KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT): cv.string,
                },
                cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
                cv.has_at_least_one_key(
                    KEY_TEXT_OVERLAY_LEFT,
                    KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
                    KEY_TEXT_OVERLAY_RIGHT,
                    KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
                ),
            ),
        )

    async def _get_clients_and_camera_indices_from_request(
        self, service: ServiceCall
    ) -> set[tuple[MotionEyeClient, int]]:
        """Get a tuple of client and camera indices from a service request."""
        entity_registry = await er.async_get_registry(self._hass)
        device_registry = await dr.async_get_registry(self._hass)
        devices_ids = service.data.get(ATTR_DEVICE_ID) or []

        for entity_id in service.data.get(ATTR_ENTITY_ID) or []:
            entry = entity_registry.async_get(entity_id)
            if entry and entry.device_id:
                devices_ids.append(entry.device_id)

        output: set[tuple[MotionEyeClient, int]] = set()
        for device_id in devices_ids:
            entry = device_registry.async_get(device_id)
            if not entry:
                continue

            # A device will always have at least 1 config_entry.
            config_entry_id = next(iter(entry.config_entries), None)
            client: MotionEyeClient = (
                self._hass.data[DOMAIN].get(config_entry_id, {}).get(CONF_CLIENT)
            )

            for key, value in entry.identifiers:
                if key == DOMAIN:
                    components = _split_motioneye_device_unique_id(value)
                    if components:
                        output.add((client, components[2]))
                        break
        return output

    async def _async_set_text_overlay(self, service: ServiceCall) -> None:
        """Set camera text overlay."""
        cameras = await self._get_clients_and_camera_indices_from_request(service)

        if not cameras:
            return
        for client, camera_id in cameras:
            camera = await client.async_get_camera(camera_id)
            if not camera:
                continue

            for key in (KEY_TEXT_OVERLAY_LEFT, KEY_TEXT_OVERLAY_RIGHT):
                if service.data.get(key):
                    camera[key] = service.data[key]

            for key in (
                KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
                KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
            ):
                if service.data.get(key):
                    camera[key] = (
                        service.data[key].encode("unicode_escape").decode("UTF-8")
                    )

            await client.async_set_camera(camera_id, camera)


class MotionEyeMotionDetectedView(HomeAssistantView):  # type: ignore[misc]
    """View to handle motionEye motion detection."""

    url = API_PATH_MOTION_DETECTION_REGEXP
    name = f"api:{DOMAIN}"
    requires_auth = False

    async def get(self, request: web.Request, device_id: str) -> web.Response:
        """Handle the GET request received from motionEye."""
        return await self._handle(request.app["hass"], device_id, request.query)

    async def _handle(
        self, hass: HomeAssistant, device_id: str, data: MultiDictProxy[str]
    ) -> web.Response:
        """Handle requests to the motionEye endpoint."""
        device_registry = await dr.async_get_registry(hass)
        device_entry = device_registry.async_get_device({(DOMAIN, device_id)})
        if not device_entry or (DOMAIN, device_id) not in device_entry.identifiers:
            return cast(
                web.Response,
                self.json_message(
                    f"Device not found: {device_id}",
                    status_code=HTTP_NOT_FOUND,
                ),
            )
        await self._fire_event(hass, device_id, device_entry)
        return cast(web.Response, self.json_message({}))

    async def _fire_event(
        self, hass: HomeAssistant, device_id: str, device_entry: dr.DeviceEntry
    ) -> None:
        """Fire a Home Assistant event."""
        event_data = {
            CONF_DEVICE_ID: device_id,
            CONF_NAME: device_entry.name,
        }
        hass.bus.async_fire(EVENT_MOTION_DETECTED, event_data)
