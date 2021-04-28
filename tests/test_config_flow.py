"""Test the motionEye config flow."""
import logging
from unittest.mock import AsyncMock, patch

from motioneye_client.client import (
    MotionEyeClientConnectionError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientRequestError,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.motioneye.const import (
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_STREAM_URL_TEMPLATE,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    CONF_WEBHOOK_SET,
    CONF_WEBHOOK_SET_OVERWRITE,
    DOMAIN,
)
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import TEST_URL, create_mock_motioneye_client, create_mock_motioneye_config_entry

_LOGGER = logging.getLogger(__name__)


async def test_user_success(hass: HomeAssistant) -> None:
    """Test successful user flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    mock_client = create_mock_motioneye_client()

    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ), patch(
        "custom_components.motioneye.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == f"{TEST_URL}"
    assert result["data"] == {
        CONF_URL: TEST_URL,
        CONF_ADMIN_USERNAME: "admin-username",
        CONF_ADMIN_PASSWORD: "admin-password",
        CONF_SURVEILLANCE_USERNAME: "surveillance-username",
        CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_client.async_client_close.called


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(
        side_effect=MotionEyeClientInvalidAuthError
    )

    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_client.async_client_close.called


async def test_user_invalid_url(hass: HomeAssistant) -> None:
    """Test invalid url is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "not a url",
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(
        side_effect=MotionEyeClientConnectionError,
    )

    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_client.async_client_close.called


async def test_user_request_error(hass: HomeAssistant) -> None:
    """Test a request error is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(side_effect=MotionEyeClientRequestError)

    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}
    assert mock_client.async_client_close.called


async def test_reauth(hass: HomeAssistant) -> None:
    """Test a reauth."""
    config_data = {
        CONF_URL: TEST_URL,
    }

    config_entry = create_mock_motioneye_config_entry(hass, data=config_data)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] == "form"
    assert not result["errors"]

    mock_client = create_mock_motioneye_client()

    new_data = {
        CONF_URL: TEST_URL,
        CONF_ADMIN_USERNAME: "admin-username",
        CONF_ADMIN_PASSWORD: "admin-password",
        CONF_SURVEILLANCE_USERNAME: "surveillance-username",
        CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
    }

    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ), patch(
        "custom_components.motioneye.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_data,
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert dict(config_entry.data) == new_data

    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_client.async_client_close.called


async def test_duplicate(hass: HomeAssistant) -> None:
    """Test that a duplicate entry (same URL) is rejected."""
    config_data = {
        CONF_URL: TEST_URL,
    }

    # Add an existing entry with the same URL.
    existing_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
    )
    existing_entry.add_to_hass(hass)

    # Now do the usual config entry process, and verify it is rejected.
    create_mock_motioneye_config_entry(hass, data=config_data)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert not result["errors"]
    mock_client = create_mock_motioneye_client()

    new_data = {
        CONF_URL: TEST_URL,
        CONF_ADMIN_USERNAME: "admin-username",
        CONF_ADMIN_PASSWORD: "admin-password",
        CONF_SURVEILLANCE_USERNAME: "surveillance-username",
        CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
    }

    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_data,
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert mock_client.async_client_close.called


async def test_options(hass: HomeAssistant) -> None:
    """Check an options flow."""

    config_entry = create_mock_motioneye_config_entry(hass)

    client = create_mock_motioneye_client()
    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=client,
    ), patch("custom_components.motioneye.async_setup", return_value=True), patch(
        "custom_components.motioneye.async_setup_entry", return_value=True
    ):
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_WEBHOOK_SET: True,
                CONF_WEBHOOK_SET_OVERWRITE: True,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_WEBHOOK_SET]
        assert result["data"][CONF_WEBHOOK_SET_OVERWRITE]
        assert CONF_STREAM_URL_TEMPLATE not in result["data"]


async def test_advanced_options(hass: HomeAssistant) -> None:
    """Check an options flow with advanced options."""

    config_entry = create_mock_motioneye_config_entry(hass)

    client = create_mock_motioneye_client()
    with patch(
        "custom_components.motioneye.MotionEyeClient",
        return_value=client,
    ), patch("custom_components.motioneye.async_setup", return_value=True), patch(
        "custom_components.motioneye.async_setup_entry", return_value=True
    ):
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            config_entry.entry_id, context={"show_advanced_options": True}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_WEBHOOK_SET: True,
                CONF_WEBHOOK_SET_OVERWRITE: True,
                CONF_STREAM_URL_TEMPLATE: "http://moo",
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_WEBHOOK_SET]
        assert result["data"][CONF_WEBHOOK_SET_OVERWRITE]
        assert result["data"][CONF_STREAM_URL_TEMPLATE] == "http://moo"
