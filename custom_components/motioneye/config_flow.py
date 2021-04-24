"""Config flow for motionEye integration."""
from __future__ import annotations

import logging
from typing import Any

from motioneye_client.client import (
    MotionEyeClientConnectionError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientRequestError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_SOURCE, CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import create_motioneye_client
from .const import (
    CONF_ADMIN_USERNAME,
    CONF_STREAM_URL_TEMPLATE,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    CONF_WEBHOOK_SET,
    CONF_WEBHOOK_SET_OVERWRITE,
    DEFAULT_WEBHOOK_SET,
    DEFAULT_WEBHOOK_SET_OVERWRITE,
    DOMAIN,
)
from .const import CONF_ADMIN_PASSWORD  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class MotionEyeConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg, misc]
    """Handle a config flow for motionEye."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: ConfigType | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""

        def _get_form(
            user_input: ConfigType, errors: dict[str, str] | None = None
        ) -> dict[str, Any]:
            """Show the form to the user."""
            out: dict[str, Any] = self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_URL, default=user_input.get(CONF_URL, "")
                        ): str,
                        vol.Optional(
                            CONF_ADMIN_USERNAME,
                            default=user_input.get(CONF_ADMIN_USERNAME),
                        ): str,
                        vol.Optional(
                            CONF_ADMIN_PASSWORD,
                            default=user_input.get(CONF_ADMIN_PASSWORD),
                        ): str,
                        vol.Optional(
                            CONF_SURVEILLANCE_USERNAME,
                            default=user_input.get(CONF_SURVEILLANCE_USERNAME),
                        ): str,
                        vol.Optional(
                            CONF_SURVEILLANCE_PASSWORD,
                            default=user_input.get(CONF_SURVEILLANCE_PASSWORD),
                        ): str,
                    }
                ),
                errors=errors,
            )
            return out

        reauth_entry = None
        if self.context.get("entry_id"):
            reauth_entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )

        out: dict[str, Any] = {}
        if user_input is None:
            return _get_form(reauth_entry.data if reauth_entry else {})

        try:
            # Cannot use cv.url validation in the schema itself, so
            # apply extra validation here.
            cv.url(user_input[CONF_URL])
        except vol.Invalid:
            return _get_form(user_input, {"base": "invalid_url"})

        client = create_motioneye_client(
            user_input[CONF_URL],
            admin_username=user_input.get(CONF_ADMIN_USERNAME),
            admin_password=user_input.get(CONF_ADMIN_PASSWORD),
            surveillance_username=user_input.get(CONF_SURVEILLANCE_USERNAME),
            surveillance_password=user_input.get(CONF_SURVEILLANCE_PASSWORD),
        )

        try:
            await client.async_client_login()
        except MotionEyeClientConnectionError:
            return _get_form(user_input, {"base": "cannot_connect"})
        except MotionEyeClientInvalidAuthError:
            return _get_form(user_input, {"base": "invalid_auth"})
        except MotionEyeClientRequestError:
            return _get_form(user_input, {"base": "unknown"})
        finally:
            await client.async_client_close()

        if self.context.get(CONF_SOURCE) == SOURCE_REAUTH and reauth_entry is not None:
            self.hass.config_entries.async_update_entry(reauth_entry, data=user_input)
            # Need to manually reload, as the listener won't have been
            # installed because the initial load did not succeed (the reauth
            # flow will not be initiated if the load succeeds).
            await self.hass.config_entries.async_reload(reauth_entry.entry_id)
            out = self.async_abort(reason="reauth_successful")
            return out

        # Search for duplicates: there isn't a useful unique_id, but
        # at least prevent entries with the same motionEye URL.
        for existing_entry in self.hass.config_entries.async_entries(DOMAIN):
            if existing_entry.data.get(CONF_URL) == user_input[CONF_URL]:
                out = self.async_abort(reason="already_configured")
                return out

        out = self.async_create_entry(
            title=f"{user_input[CONF_URL]}",
            data=user_input,
        )
        return out

    async def async_step_reauth(
        self,
        config_data: ConfigType | None = None,
    ) -> dict[str, Any]:
        """Handle a reauthentication flow."""
        return await self.async_step_user(config_data)

    @staticmethod
    @callback  # type: ignore[misc]
    def async_get_options_flow(config_entry: ConfigEntry) -> MotionEyeOptionsFlow:
        """Get the Hyperion Options flow."""
        return MotionEyeOptionsFlow(config_entry)


class MotionEyeOptionsFlow(OptionsFlow):  # type: ignore[misc]
    """motionEye options flow."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize a motionEye options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Manage the options."""
        out: dict[str, Any] = {}

        if user_input is not None:
            out = self.async_create_entry(title="", data=user_input)
            return out

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_WEBHOOK_SET,
                default=self._config_entry.options.get(
                    CONF_WEBHOOK_SET,
                    DEFAULT_WEBHOOK_SET,
                ),
            ): bool,
            vol.Required(
                CONF_WEBHOOK_SET_OVERWRITE,
                default=self._config_entry.options.get(
                    CONF_WEBHOOK_SET_OVERWRITE,
                    DEFAULT_WEBHOOK_SET_OVERWRITE,
                ),
            ): bool,
        }

        if self.show_advanced_options:
            # The input URL is not validated as being a URL, to allow for the possibility
            # the template input won't be a valid URL until after it's rendered.
            schema[
                vol.Required(
                    CONF_STREAM_URL_TEMPLATE,
                    default=self._config_entry.options.get(
                        CONF_STREAM_URL_TEMPLATE,
                        "",
                    ),
                )
            ] = str

        out = self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
        return out
