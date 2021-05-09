"""The motionEye integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, cast
from urllib.parse import urlencode

from aiohttp import web
from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientError,
    MotionEyeClientInvalidAuthError,
)
from motioneye_client.const import (
    KEY_ACTION_SNAPSHOT,
    KEY_CAMERAS,
    KEY_HTTP_METHOD_GET,
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
    KEY_WEB_HOOK_CONVERSION_SPECIFIERS,
    KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
    KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
    KEY_WEB_HOOK_NOTIFICATIONS_URL,
    KEY_WEB_HOOK_STORAGE_ENABLED,
    KEY_WEB_HOOK_STORAGE_HTTP_METHOD,
    KEY_WEB_HOOK_STORAGE_URL,
)
from multidict import MultiDictProxy
import voluptuous as vol

from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_SOURCE,
    CONF_URL,
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
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    API_PATH_DEVICE_ROOT,
    API_PATH_EVENT_REGEXP,
    CONF_ACTION,
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_CLIENT,
    CONF_COORDINATOR,
    CONF_ON_UNLOAD,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    CONF_WEBHOOK_SET,
    CONF_WEBHOOK_SET_OVERWRITE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WEBHOOK_SET,
    DEFAULT_WEBHOOK_SET_OVERWRITE,
    DOMAIN,
    EVENT_FILE_STORED,
    EVENT_FILE_STORED_KEYS,
    EVENT_MOTION_DETECTED,
    EVENT_MOTION_DETECTED_KEYS,
    MOTIONEYE_MANUFACTURER,
    SERVICE_ACTION,
    SERVICE_SET_TEXT_OVERLAY,
    SERVICE_SNAPSHOT,
    SIGNAL_CAMERA_ADD,
    WEB_HOOK_SENTINEL_KEY,
    WEB_HOOK_SENTINEL_VALUE,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [CAMERA_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN]


def create_motioneye_client(
    *args: Any,
    **kwargs: Any,
) -> MotionEyeClient:
    """Create a MotionEyeClient."""
    return MotionEyeClient(*args, **kwargs)


def get_motioneye_device_identifier(
    config_entry_id: str, camera_id: int
) -> tuple[str, str]:
    """Get the identifiers for a motionEye device."""
    return (DOMAIN, f"{config_entry_id}_{camera_id}")


def split_motioneye_device_identifier(
    identifier: tuple[str, str]
) -> tuple[str, str, int] | None:
    """Get the identifiers for a motionEye device."""
    if len(identifier) != 2 or identifier[0] != DOMAIN or "_" not in identifier[1]:
        return None
    config_id, camera_id_str = identifier[1].split("_", 1)
    try:
        camera_id = int(camera_id_str)
    except ValueError:
        return None
    return (DOMAIN, config_id, camera_id)


def get_motioneye_entity_unique_id(
    config_entry_id: str, camera_id: int, entity_type: str
) -> str:
    """Get the unique_id for a motionEye entity."""
    return f"{config_entry_id}_{camera_id}_{entity_type}"


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the motionEye component."""
    hass.data[DOMAIN] = {}
    MotionEyeServices(hass).async_register()
    hass.http.register_view(MotionEyeView())
    return True


async def _create_reauth_flow(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                CONF_SOURCE: SOURCE_REAUTH,
            },
            data=config_entry.data,
        )
    )


@callback  # type: ignore[misc]
def _add_camera(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MotionEyeClient,
    entry: ConfigEntry,
    camera_id: int,
    camera: dict[str, Any],
    device_identifier: tuple[str, str],
) -> None:
    """Add a motionEye camera to hass."""

    def _is_recognized_web_hook(url: str) -> bool:
        """Determine whether this integration set a web hook."""
        return f"{WEB_HOOK_SENTINEL_KEY}={WEB_HOOK_SENTINEL_VALUE}" in url

    def _set_webhook(
        url: str,
        key_url: str,
        key_method: str,
        key_enabled: str,
        camera: dict[str, Any],
    ) -> bool:
        """Set a web hook."""
        if (
            entry.options.get(
                CONF_WEBHOOK_SET_OVERWRITE,
                DEFAULT_WEBHOOK_SET_OVERWRITE,
            )
            or not camera.get(key_url)
            or _is_recognized_web_hook(camera[key_url])
        ) and (
            not camera.get(key_enabled, False)
            or camera.get(key_method) != KEY_HTTP_METHOD_GET
            or camera.get(key_url) != url
        ):
            camera[key_enabled] = True
            camera[key_method] = KEY_HTTP_METHOD_GET
            camera[key_url] = url
            return True
        return False

    def _build_url(base: str, keys: list[str]) -> str:
        """Build a motionEye webhook URL."""

        return (
            base
            + "?"
            + urlencode(
                {
                    **{k: KEY_WEB_HOOK_CONVERSION_SPECIFIERS[k] for k in sorted(keys)},
                    WEB_HOOK_SENTINEL_KEY: WEB_HOOK_SENTINEL_VALUE,
                },
                safe="%{}",
            )
        )

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={device_identifier},
        manufacturer=MOTIONEYE_MANUFACTURER,
        model=MOTIONEYE_MANUFACTURER,
        name=camera[KEY_NAME],
    )
    if entry.options.get(CONF_WEBHOOK_SET, DEFAULT_WEBHOOK_SET):
        url = None
        try:
            url = get_url(hass)
        except NoURLAvailableError:
            pass
        if url:
            if _set_webhook(
                _build_url(
                    f"{url}{API_PATH_DEVICE_ROOT}{device.id}/{EVENT_MOTION_DETECTED}",
                    EVENT_MOTION_DETECTED_KEYS,
                ),
                KEY_WEB_HOOK_NOTIFICATIONS_URL,
                KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
                KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
                camera,
            ) | _set_webhook(
                _build_url(
                    f"{url}{API_PATH_DEVICE_ROOT}{device.id}/{EVENT_FILE_STORED}",
                    EVENT_FILE_STORED_KEYS,
                ),
                KEY_WEB_HOOK_STORAGE_URL,
                KEY_WEB_HOOK_STORAGE_HTTP_METHOD,
                KEY_WEB_HOOK_STORAGE_ENABLED,
                camera,
            ):
                hass.async_create_task(client.async_set_camera(camera_id, camera))

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
    hass.data.setdefault(DOMAIN, {})

    client = create_motioneye_client(
        entry.data[CONF_URL],
        admin_username=entry.data.get(CONF_ADMIN_USERNAME),
        admin_password=entry.data.get(CONF_ADMIN_PASSWORD),
        surveillance_username=entry.data.get(CONF_SURVEILLANCE_USERNAME),
        surveillance_password=entry.data.get(CONF_SURVEILLANCE_PASSWORD),
    )

    try:
        await client.async_client_login()
    except MotionEyeClientInvalidAuthError:
        await client.async_client_close()
        await _create_reauth_flow(hass, entry)
        return False
    except MotionEyeClientError as exc:
        await client.async_client_close()
        raise ConfigEntryNotReady from exc

    @callback  # type: ignore[misc]
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

    current_cameras: set[tuple[str, str]] = set()
    device_registry = await dr.async_get_registry(hass)

    @callback  # type: ignore[misc]
    def _async_process_motioneye_cameras() -> None:
        """Process motionEye camera additions and removals."""
        inbound_camera: set[tuple[str, str]] = set()
        if coordinator.data is None or KEY_CAMERAS not in coordinator.data:
            return

        for camera in coordinator.data[KEY_CAMERAS]:
            if not is_acceptable_camera(camera):
                return
            camera_id = camera[KEY_ID]
            device_identifier = get_motioneye_device_identifier(
                entry.entry_id, camera_id
            )
            inbound_camera.add(device_identifier)

            if device_identifier in current_cameras:
                continue
            current_cameras.add(device_identifier)
            _add_camera(
                hass,
                device_registry,
                client,
                entry,
                camera_id,
                camera,
                device_identifier,
            )

        # Ensure every device associated with this config entry is still in the list of
        # motionEye cameras, otherwise remove the device (and thus entities).
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            for identifier in device_entry.identifiers:
                if identifier in inbound_camera:
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


class MotionEyeServices:
    """Class that holds motionEye services that should be published to hass."""

    SCHEMA_TEXT_OVERLAY = vol.In(
        [
            KEY_TEXT_OVERLAY_DISABLED,
            KEY_TEXT_OVERLAY_TIMESTAMP,
            KEY_TEXT_OVERLAY_CUSTOM_TEXT,
            KEY_TEXT_OVERLAY_CAMERA_NAME,
        ]
    )

    SCHEMA_DEVICE_OR_ENTITIES = {
        vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }

    SERVICE_TO_ACTION = {
        SERVICE_SNAPSHOT: KEY_ACTION_SNAPSHOT,
    }

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
                    **self.SCHEMA_DEVICE_OR_ENTITIES,
                    vol.Optional(KEY_TEXT_OVERLAY_LEFT): self.SCHEMA_TEXT_OVERLAY,
                    vol.Optional(KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT): cv.string,
                    vol.Optional(KEY_TEXT_OVERLAY_RIGHT): self.SCHEMA_TEXT_OVERLAY,
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
        self._hass.services.async_register(
            DOMAIN,
            SERVICE_ACTION,
            self._async_action,
            schema=vol.All(
                {
                    **self.SCHEMA_DEVICE_OR_ENTITIES,
                    vol.Required(CONF_ACTION): cv.string,
                },
                cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
            ),
        )

        # Wrapper service calls for snapshot.
        self._hass.services.async_register(
            DOMAIN,
            SERVICE_SNAPSHOT,
            self._async_action,
            schema=vol.All(
                {
                    **self.SCHEMA_DEVICE_OR_ENTITIES,
                },
                cv.has_at_least_one_key(ATTR_DEVICE_ID, ATTR_ENTITY_ID),
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

            for identifier in entry.identifiers:
                data = split_motioneye_device_identifier(identifier)
                if data is not None:
                    output.add((client, data[2]))
                break
        return output

    async def _async_set_text_overlay(self, service: ServiceCall) -> None:
        """Set camera text overlay."""
        cameras = await self._get_clients_and_camera_indices_from_request(service)
        for client, camera_id in cameras or {}:
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

    async def _async_action(self, service: ServiceCall) -> None:
        """Perform a motionEye action."""
        cameras = await self._get_clients_and_camera_indices_from_request(service)
        for client, camera_id in cameras or {}:
            await client.async_action(
                camera_id,
                (
                    self.SERVICE_TO_ACTION.get(service.service)
                    or service.data[CONF_ACTION]
                ),
            )


class MotionEyeView(HomeAssistantView):  # type: ignore[misc]
    """View to handle motionEye motion detection."""

    name = f"api:{DOMAIN}"
    requires_auth = False
    url = API_PATH_EVENT_REGEXP

    async def get(
        self, request: web.Request, device_id: str, event: str
    ) -> web.Response:
        """Handle the GET request received from motionEye."""
        hass = request.app["hass"]
        device_registry = await dr.async_get_registry(hass)
        device = device_registry.async_get(device_id)

        if not device:
            return cast(
                web.Response,
                self.json_message(
                    f"Device not found: {device_id}",
                    status_code=HTTP_NOT_FOUND,
                ),
            )
        await self._fire_event(hass, event, device, request.query)
        return cast(web.Response, self.json({}))

    async def _fire_event(
        self,
        hass: HomeAssistant,
        event_type: str,
        device: dr.DeviceEntry,
        data: MultiDictProxy[str],
    ) -> None:
        """Fire a Home Assistant event."""
        hass.bus.async_fire(
            f"{DOMAIN}.{event_type}",
            {
                CONF_DEVICE_ID: device.id,
                CONF_NAME: device.name,
                **data,
            },
        )


class MotionEyeEntity(CoordinatorEntity):  # type: ignore[misc]
    """Base class for motionEye entities."""

    def __init__(
        self,
        config_entry_id: str,
        type_name: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize a motionEye entity."""
        self._camera_id = camera[KEY_ID]
        self._device_identifier = get_motioneye_device_identifier(
            config_entry_id, self._camera_id
        )
        self._unique_id = get_motioneye_entity_unique_id(
            config_entry_id,
            self._camera_id,
            type_name,
        )
        self._client = client
        self._camera: dict[str, Any] | None = camera
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the device information."""
        return {"identifiers": {self._device_identifier}}

    @callback  # type: ignore[misc]
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._camera = get_camera_from_cameras(self._camera_id, self.coordinator.data)
        super()._handle_coordinator_update()
