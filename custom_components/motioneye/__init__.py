"""The motionEye integration."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from types import MappingProxyType
from typing import Any, Callable
from urllib.parse import urlencode, urljoin

from aiohttp.web import Request, Response
from motioneye_client.client import (
    MotionEyeClient,
    MotionEyeClientError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientPathError,
)
from motioneye_client.const import (
    KEY_ACTION_SNAPSHOT,
    KEY_CAMERAS,
    KEY_HTTP_METHOD_POST_JSON,
    KEY_ID,
    KEY_NAME,
    KEY_ROOT_DIRECTORY,
    KEY_TEXT_OVERLAY_CAMERA_NAME,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_LEFT,
    KEY_TEXT_OVERLAY_CUSTOM_TEXT_RIGHT,
    KEY_TEXT_OVERLAY_DISABLED,
    KEY_TEXT_OVERLAY_LEFT,
    KEY_TEXT_OVERLAY_RIGHT,
    KEY_TEXT_OVERLAY_TIMESTAMP,
    KEY_WEB_HOOK_CONVERSION_SPECIFIERS,
    KEY_WEB_HOOK_CS_FILE_PATH,
    KEY_WEB_HOOK_CS_FILE_TYPE,
    KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
    KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
    KEY_WEB_HOOK_NOTIFICATIONS_URL,
    KEY_WEB_HOOK_STORAGE_ENABLED,
    KEY_WEB_HOOK_STORAGE_HTTP_METHOD,
    KEY_WEB_HOOK_STORAGE_URL,
)
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.camera.const import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.media_source.const import URI_SCHEME
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.webhook import (
    async_generate_id,
    async_generate_path,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    CONF_URL,
    CONF_WEBHOOK_ID,
    HTTP_BAD_REQUEST,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.network import get_url
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_EVENT_TYPE,
    ATTR_WEBHOOK_ID,
    CONF_ACTION,
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_CLIENT,
    CONF_COORDINATOR,
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
    EVENT_FILE_URL,
    EVENT_MEDIA_CONTENT_ID,
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
PLATFORMS = [BINARY_SENSOR_DOMAIN, CAMERA_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN]


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
    camera_id: int, data: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Get an individual camera dict from a multiple cameras data response."""
    for camera in data.get(KEY_CAMERAS, []) if data else []:
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

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_CAMERA_ADD.format(entry.entry_id),
            add_func,
        )
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the motionEye component."""
    hass.data[DOMAIN] = {}
    MotionEyeServices(hass).async_register()
    return True


@callback  # type: ignore[misc]
def async_generate_motioneye_webhook(hass: HomeAssistant, webhook_id: str) -> str:
    """Generate the full local URL for a webhook_id."""
    return "{}{}".format(
        get_url(hass, allow_cloud=False),
        async_generate_path(webhook_id),
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
            or camera.get(key_method) != KEY_HTTP_METHOD_POST_JSON
            or camera.get(key_url) != url
        ):
            camera[key_enabled] = True
            camera[key_method] = KEY_HTTP_METHOD_POST_JSON
            camera[key_url] = url
            return True
        return False

    def _build_url(
        device: dr.DeviceEntry, base: str, event_type: str, keys: list[str]
    ) -> str:
        """Build a motionEye webhook URL."""

        # This URL-surgery cannot use YARL because the output must NOT be
        # url-encoded. This is because motionEye will do further string
        # manipulation/substitution on this value before ultimately fetching it,
        # and it cannot deal with URL-encoded input to that string manipulation.
        return urljoin(
            base,
            "?"
            + urlencode(
                {
                    **{k: KEY_WEB_HOOK_CONVERSION_SPECIFIERS[k] for k in sorted(keys)},
                    WEB_HOOK_SENTINEL_KEY: WEB_HOOK_SENTINEL_VALUE,
                    ATTR_EVENT_TYPE: event_type,
                    ATTR_DEVICE_ID: device.id,
                },
                safe="%{}",
            ),
        )

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={device_identifier},
        manufacturer=MOTIONEYE_MANUFACTURER,
        model=MOTIONEYE_MANUFACTURER,
        name=camera[KEY_NAME],
    )
    if entry.options.get(CONF_WEBHOOK_SET, DEFAULT_WEBHOOK_SET):
        url = async_generate_motioneye_webhook(hass, entry.data[CONF_WEBHOOK_ID])

        if _set_webhook(
            _build_url(
                device,
                url,
                EVENT_MOTION_DETECTED,
                EVENT_MOTION_DETECTED_KEYS,
            ),
            KEY_WEB_HOOK_NOTIFICATIONS_URL,
            KEY_WEB_HOOK_NOTIFICATIONS_HTTP_METHOD,
            KEY_WEB_HOOK_NOTIFICATIONS_ENABLED,
            camera,
        ) | _set_webhook(
            _build_url(
                device,
                url,
                EVENT_FILE_STORED,
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
    except MotionEyeClientInvalidAuthError as exc:
        await client.async_client_close()
        raise ConfigEntryAuthFailed from exc
    except MotionEyeClientError as exc:
        await client.async_client_close()
        raise ConfigEntryNotReady from exc

    # Ensure every loaded entry has a registered webhook id.
    if CONF_WEBHOOK_ID not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_WEBHOOK_ID: async_generate_id()}
        )
    webhook_register(
        hass, DOMAIN, "motionEye", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

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

        # Ensure every device associated with this config entry is still in the
        # list of motionEye cameras, otherwise remove the device (and thus
        # entities).
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
        entry.async_on_unload(
            coordinator.async_add_listener(_async_process_motioneye_cameras)
        )
        await coordinator.async_refresh()
        entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    hass.async_create_task(setup_then_listen())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    unload_ok = bool(await hass.config_entries.async_unload_platforms(entry, PLATFORMS))
    if unload_ok:
        config_data = hass.data[DOMAIN].pop(entry.entry_id)
        await config_data[CONF_CLIENT].async_client_close()

    return unload_ok


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> None | Response:
    """Handle webhook callback."""

    try:
        data = await request.json()
    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
        return Response(
            text="Could not decode request",
            status=HTTP_BAD_REQUEST,
        )

    for key in (ATTR_DEVICE_ID, ATTR_EVENT_TYPE):
        if key not in data:
            return Response(
                text=f"Missing webhook parameter: {key}",
                status=HTTP_BAD_REQUEST,
            )

    event_type = data[ATTR_EVENT_TYPE]
    device_registry = dr.async_get(hass)
    device_id = data[ATTR_DEVICE_ID]
    device = device_registry.async_get(device_id)

    if not device:
        return Response(
            text=f"Device not found: {device_id}",
            status=HTTP_BAD_REQUEST,
        )

    if KEY_WEB_HOOK_CS_FILE_PATH in data and KEY_WEB_HOOK_CS_FILE_TYPE in data:
        try:
            event_file_type = int(data[KEY_WEB_HOOK_CS_FILE_TYPE])
        except ValueError:
            pass
        else:
            data.update(
                _get_media_event_data(
                    hass,
                    device,
                    data[KEY_WEB_HOOK_CS_FILE_PATH],
                    event_file_type,
                )
            )

    hass.bus.async_fire(
        f"{DOMAIN}.{event_type}",
        {
            ATTR_DEVICE_ID: device.id,
            ATTR_NAME: device.name,
            ATTR_WEBHOOK_ID: webhook_id,
            **data,
        },
    )
    return None


def _get_media_event_data(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    event_file_path: str,
    event_file_type: int,
) -> dict[str, str]:
    config_entry_id = next(iter(device.config_entries), None)
    client = hass.data[DOMAIN].get(config_entry_id, {}).get(CONF_CLIENT)
    coordinator = hass.data[DOMAIN].get(config_entry_id, {}).get(CONF_COORDINATOR)

    if not coordinator or not client:
        return {}

    for identifier in device.identifiers:
        data = split_motioneye_device_identifier(identifier)
        if data is not None:
            camera_id = data[2]
            camera = get_camera_from_cameras(camera_id, coordinator.data)
            break
    else:
        return {}

    root_directory = camera.get(KEY_ROOT_DIRECTORY) if camera else None
    if root_directory is None:
        return {}

    kind = "images" if client.is_file_type_image(event_file_type) else "movies"

    # The file_path in the event is the full local filesystem path to the
    # media. To convert that to the media path that motionEye will
    # understanding, we need to strip the root directory from the path.
    if os.path.commonprefix([root_directory, event_file_path]) == root_directory:
        file_path = "/" + os.path.relpath(event_file_path, root_directory)
        output = {
            EVENT_MEDIA_CONTENT_ID: f"{URI_SCHEME}{DOMAIN}/{config_entry_id}#{device.id}#{kind}#{file_path}"
        }
        url = get_media_url(
            client,
            camera_id,
            file_path,
            kind == "images",
        )
        if url:
            output[EVENT_FILE_URL] = url
        return output

    return {}


def get_media_url(
    client: MotionEyeClient, camera_id: int, path: str, image: bool
) -> str | None:
    """Get the URL for a motionEye media item."""
    try:
        if image:
            return client.get_image_url(camera_id, path)
        else:
            return client.get_movie_url(camera_id, path)
    except MotionEyeClientPathError:
        return None


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


class MotionEyeEntity(CoordinatorEntity):  # type: ignore[misc]
    """Base class for motionEye entities."""

    def __init__(
        self,
        config_entry_id: str,
        type_name: str,
        camera: dict[str, Any],
        client: MotionEyeClient,
        coordinator: DataUpdateCoordinator,
        options: MappingProxyType[str, Any],
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
        self._options = options
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        """Return a unique id for this instance."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return {"identifiers": {self._device_identifier}}

    @callback  # type: ignore[misc]
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._camera = get_camera_from_cameras(self._camera_id, self.coordinator.data)
        super()._handle_coordinator_update()
