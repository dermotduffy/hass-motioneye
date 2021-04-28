"""Xbox Media Source Implementation."""
from __future__ import annotations

import logging
from pathlib import PurePath
from typing import Optional, Tuple, cast

from motioneye_client.client import MotionEyeClientPathError
from motioneye_client.const import KEY_MEDIA_LIST, KEY_MIME_TYPE, KEY_PATH

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_IMAGE,
    MEDIA_CLASS_VIDEO,
)
from homeassistant.components.media_source.const import MEDIA_MIME_TYPES
from homeassistant.components.media_source.error import MediaSourceError, Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType

from . import split_motioneye_device_identifier
from .const import CONF_CLIENT, DOMAIN

MIME_TYPE_MAP = {
    "movies": "video/mp4",
    "images": "image/jpeg",
}

MEDIA_CLASS_MAP = {
    "movies": MEDIA_CLASS_VIDEO,
    "images": MEDIA_CLASS_IMAGE,
}

_LOGGER = logging.getLogger(__name__)


# Hierarchy:
#
# url (e.g. http://my-motioneye-1, http://my-motioneye-2)
# -> Camera (e.g. "Office", "Kitchen")
#   -> kind (e.g. Images, Movies)
#     -> path folder hierarchy as configured on motionEye


async def async_get_media_source(hass: HomeAssistantType) -> MotionEyeMediaSource:
    """Set up motionEye media source."""
    return MotionEyeMediaSource(hass)


class MotionEyeMediaSource(MediaSource):  # type: ignore[misc]
    """Provide motionEye stills and videos as media sources."""

    name: str = "motionEye Media"

    def __init__(self, hass: HomeAssistantType):
        """Initialize Xbox source."""
        super().__init__(DOMAIN)

        self.hass: HomeAssistantType = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        config_id, device_id, kind, path = self._parse_identifier(item.identifier)

        if not config_id or not device_id or not kind or not path:
            raise Unresolvable(
                f"Incomplete media identifier specified: {item.identifier}"
            )

        config = self._get_config_or_raise(config_id)
        device = self._get_device_or_raise(device_id)
        camera_id = self._get_camera_id_or_raise(config, device)
        self._verify_kind_or_raise(kind)

        client = self.hass.data[DOMAIN][config.entry_id][CONF_CLIENT]
        try:
            if kind == "movies":
                url = client.get_movie_url(camera_id, path)
            else:
                url = client.get_image_url(camera_id, path)
        except MotionEyeClientPathError as exc:
            raise Unresolvable from exc

        return PlayMedia(url, MIME_TYPE_MAP[kind])

    @callback  # type: ignore[misc]
    def _parse_identifier(
        self, identifier: str
    ) -> tuple[str | None, str | None, str | None, str | None]:
        base = [None] * 4
        data = identifier.split("#", 3)
        return cast(
            Tuple[Optional[str], Optional[str], Optional[str], Optional[str]],
            tuple(data + base)[:4],  # type: ignore[operator]
        )

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: tuple[str] = MEDIA_MIME_TYPES
    ) -> BrowseMediaSource:
        """Return media."""
        _LOGGER.error(f"async_browse_media: {item} / {media_types}")

        if item.identifier:
            config_id, device_id, kind, path = self._parse_identifier(item.identifier)
            config = device = None
            if config_id:
                config = self._get_config_or_raise(config_id)
            if device_id:
                device = self._get_device_or_raise(device_id)
            if kind:
                self._verify_kind_or_raise(kind)

            if kind:
                return await self._build_media_path(config, device, kind, path)
            elif device_id:
                return self._build_media_kinds(config, device)
            elif config_id:
                return self._build_media_devices(config)
        return self._build_media_configs()

    def _get_config_or_raise(self, config_id: str) -> ConfigEntry:
        """Get a config entry from a URL."""
        entry = self.hass.config_entries.async_get_entry(config_id)
        if not entry:
            raise MediaSourceError(f"Unable to find config entry with id: {config_id}")
        return entry

    def _get_device_or_raise(self, device_id: str) -> dr.DeviceEntry:
        """Get a config entry from a URL."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get(device_id)
        if not device:
            raise MediaSourceError(f"Unable to find device with id: {device_id}")
        return device

    def _verify_kind_or_raise(self, kind: str) -> None:
        """Verify kind is an expected value."""
        if kind in MEDIA_CLASS_MAP:
            return
        raise MediaSourceError(f"Unknown media type: {kind}")

    def _get_camera_id_or_raise(
        self, config: ConfigEntry, device: dr.DeviceEntry
    ) -> dr.DeviceEntry:
        """Get a config entry from a URL."""
        for identifier in device.identifiers:
            data = split_motioneye_device_identifier(identifier)
            if data is not None:
                return data[2]
        raise MediaSourceError(f"Could not find camera id for device id: {device.id}")

    def _build_media_config(self, config: ConfigEntry) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=config.entry_id,
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="",
            title=config.title,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )

    def _build_media_configs(self) -> BrowseMediaSource:
        """Build the media sources for config entries."""
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="",
            title="motionEye Media",
            can_play=False,
            can_expand=True,
            children=[
                self._build_media_config(entry)
                for entry in self.hass.config_entries.async_entries(DOMAIN)
            ],
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )

    def _build_media_device(
        self,
        config: ConfigEntry,
        device: dr.DeviceEntry,
        full_title: bool = True,
    ) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{config.entry_id}#{device.id}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type="",
            title=f"{config.title} {device.name}" if full_title else device.name,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )

    def _build_media_devices(self, config: ConfigEntry) -> BrowseMediaSource:
        """Build the media sources for device entries."""
        device_registry = dr.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(device_registry, config.entry_id)

        base = self._build_media_config(config)
        base.children = [
            self._build_media_device(config, device, full_title=False)
            for device in devices
        ]
        return base

    def _build_media_kind(
        self,
        config: ConfigEntry,
        device: dr.DeviceEntry,
        kind: str,
        full_title: bool = True,
    ) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{config.entry_id}#{device.id}#{kind}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_CLASS_DIRECTORY,
            title=f"{config.title} {device.name} {kind.title()}"
            if full_title
            else kind.title(),
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )

    def _build_media_kinds(
        self, config: ConfigEntry, device: dr.DeviceEntry
    ) -> BrowseMediaSource:
        base = self._build_media_device(config, device)
        base.children = [
            self._build_media_kind(config, device, kind, full_title=False)
            for kind in MEDIA_CLASS_MAP
        ]
        return base

    # TODO: Make pictures work

    async def _build_media_path(
        self,
        config: ConfigEntry,
        device: dr.DeviceEntry,
        kind: str,
        path: str | None,
    ) -> BrowseMediaSource:
        """Build the media sources for media kinds."""
        _LOGGER.error(f"_build_media_path: {config} / {device} / {kind} / {path}")

        base = self._build_media_kind(config, device, kind)

        # Media paths from motionEye start with a /.
        if not path:
            path = "/"
        else:
            # Don't include the leading / in the title.
            base.title += " " + str(PurePath(*PurePath(path).parts[1:]))
        base.children = []

        client = self.hass.data[DOMAIN][config.entry_id][CONF_CLIENT]
        camera_id = self._get_camera_id_or_raise(config, device)

        if kind == "movies":
            resp = await client.async_get_movies(camera_id)
        else:
            resp = await client.async_get_images(camera_id)

        sub_dirs: set[str] = set()
        parts = PurePath(path).parts
        for media in resp.get(KEY_MEDIA_LIST, []):
            if (
                KEY_PATH not in media
                or KEY_MIME_TYPE not in media
                or media[KEY_MIME_TYPE] not in MIME_TYPE_MAP.values()
            ):
                continue

            # Example path: '/2021-04-21/21-13-10.mp4'
            parts_media = PurePath(media[KEY_PATH]).parts

            if parts_media[: len(parts)] == parts and len(parts_media) > len(parts):
                full_child_path = str(PurePath(*parts_media[: len(parts) + 1]))
                display_child_path = parts_media[len(parts)]

                # Child is a media file.
                if len(parts) + 1 == len(parts_media):
                    base.children.append(
                        BrowseMediaSource(
                            domain=DOMAIN,
                            identifier=f"{config.entry_id}#{device.id}#{kind}#{full_child_path}",
                            media_class=MEDIA_CLASS_MAP[kind],
                            media_content_type=media[KEY_MIME_TYPE],
                            title=display_child_path,
                            can_play=True,
                            can_expand=False,
                        )
                    )

                # Child is a subdirectory.
                elif len(parts) + 1 < len(parts_media):
                    if full_child_path not in sub_dirs:
                        sub_dirs.add(full_child_path)
                        base.children.append(
                            BrowseMediaSource(
                                domain=DOMAIN,
                                identifier=f"{config.entry_id}#{device.id}#{kind}#{full_child_path}",
                                media_class=MEDIA_CLASS_DIRECTORY,
                                media_content_type=MEDIA_CLASS_DIRECTORY,
                                title=display_child_path,
                                can_play=False,
                                can_expand=True,
                                children_media_class=MEDIA_CLASS_DIRECTORY,
                            )
                        )
        return base
