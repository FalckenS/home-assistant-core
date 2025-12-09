"""Define tests for the OpenWeatherMap config flow."""

from unittest.mock import AsyncMock, patch

from pyopenweathermap import RequestError
import pytest

from homeassistant.components.openweathermap.const import (
    ATTR_API_CURRENT,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DEFAULT_OWM_MODE,
    DOMAIN,
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_V30,
    WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT,
)
from homeassistant.components.openweathermap.coordinator import (
    AirPollutionUpdateCoordinator,
    WeatherUpdateCoordinator,
)
from homeassistant.components.weather import ATTR_CONDITION_SUNNY
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_MODE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import LATITUDE, LONGITUDE

from tests.common import MockConfigEntry

CONFIG = {
    CONF_API_KEY: "foo",
    CONF_LATITUDE: LATITUDE,
    CONF_LONGITUDE: LONGITUDE,
    CONF_LANGUAGE: DEFAULT_LANGUAGE,
    CONF_MODE: OWM_MODE_V30,
}

USER_INPUT = {
    CONF_API_KEY: "foo",
    CONF_LOCATION: {CONF_LATITUDE: LATITUDE, CONF_LONGITUDE: LONGITUDE},
    CONF_LANGUAGE: DEFAULT_LANGUAGE,
    CONF_MODE: OWM_MODE_V30,
}

VALID_YAML_CONFIG = {CONF_API_KEY: "foo"}


async def test_successful_config_flow(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test successful config flow and that the created entry loads and unloads."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # create entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_LATITUDE] == USER_INPUT[CONF_LOCATION][CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == USER_INPUT[CONF_LOCATION][CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == USER_INPUT[CONF_API_KEY]

    # validate entry state
    conf_entries = hass.config_entries.async_entries(DOMAIN)
    entry = conf_entries[0]
    assert entry.state is ConfigEntryState.LOADED

    # unload entry
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("mode", [OWM_MODE_V30], indirect=True)
async def test_abort_config_flow(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort the flow when a config entry already exists."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT


async def test_config_flow_options_change(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test changing options via the options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="openweathermap_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_language = "es"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MODE: DEFAULT_OWM_MODE, CONF_LANGUAGE: new_language},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: new_language,
        CONF_MODE: DEFAULT_OWM_MODE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    updated_language = "es"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_LANGUAGE: updated_language}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: updated_language,
        CONF_MODE: DEFAULT_OWM_MODE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_form_invalid_api_key(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test handling of invalid API key in the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    # invalid api key
    owm_client_mock.validate_key.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_api_key"}
    # valid api key
    owm_client_mock.validate_key.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_api_call_error(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test handling of errors when validating the API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    # simulate api call error
    owm_client_mock.validate_key.side_effect = RequestError("oops")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    # simulate successful api call
    owm_client_mock.validate_key.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("mode", [OWM_MODE_AIRPOLLUTION], indirect=True)
async def test_air_pollution_coordinator_no_current(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    owm_client_mock,
    mode,
) -> None:
    """Test air pollution coordinator when report has no current field."""

    class FakeAirPollutionReport:
        def __init__(self) -> None:
            self.current = None  # triggers the `else {}` branch

    # Make the OWM client return a report with current=None
    owm_client_mock.get_air_pollution.return_value = FakeAirPollutionReport()

    coordinator = AirPollutionUpdateCoordinator(
        hass, mock_config_entry, owm_client_mock
    )

    data = await coordinator._async_update_data()

    # When current is None, coordinator should return an empty dict for "current"
    assert data[ATTR_API_CURRENT] == {}


@pytest.mark.parametrize("mode", [OWM_MODE_V30], indirect=True)
async def test_get_condition_sunny_with_timestamp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    owm_client_mock,
    mode: str,
) -> None:
    """Test _get_condition sunny branch when a timestamp is provided."""
    coordinator = WeatherUpdateCoordinator(hass, mock_config_entry, owm_client_mock)
    ts = 1_700_000_000  # any non-zero timestamp so `if timestamp:` is truthy

    with (
        patch(
            "homeassistant.components.openweathermap.coordinator.dt_util.utc_from_timestamp",
            return_value="converted-time",
        ) as mock_utc,
        patch(
            "homeassistant.components.openweathermap.coordinator.sun.is_up",
            return_value=True,
        ) as mock_is_up,
    ):
        condition = coordinator._get_condition(
            WEATHER_CODE_SUNNY_OR_CLEAR_NIGHT,
            ts,
        )

    # We hit the SUNNY branch when sun.is_up(...) is True
    assert condition == ATTR_CONDITION_SUNNY

    # Ensure the timestamp path was actually used
    mock_utc.assert_called_once_with(ts)
    mock_is_up.assert_called_once_with(hass, "converted-time")


def test_convert_weather_response_object_alerts(hass: HomeAssistant) -> None:
    """Test _convert_weather_response normalizes object-style alerts."""
    # Create a coordinator instance without running its full __init__
    coordinator = WeatherUpdateCoordinator.__new__(WeatherUpdateCoordinator)
    coordinator.hass = hass  # not actually used in this path, but harmless

    class FakeAlert:
        def __init__(self) -> None:
            self.sender_name = "MET"
            self.event = "Storm Warning"
            self.start = 1111111111
            self.end = 2222222222
            self.description = "Very windy"
            self.tags = ["Wind", "Warning"]

    class FakeWeatherReport:
        def __init__(self) -> None:
            # Force current/minutely to skip any deeper processing
            self.current = None
            self.minutely_forecast = None
            self.hourly_forecast = []
            self.daily_forecast = []
            # Here is the important part: a list with a *non-dict* alert object
            self.alerts = [FakeAlert()]

    weather_report = FakeWeatherReport()

    result = coordinator._convert_weather_response(weather_report)

    # We only care that the alert was normalized using getattr(...)
    assert result["alerts"] == [
        {
            "sender_name": "MET",
            "event": "Storm Warning",
            "start": 1111111111,
            "end": 2222222222,
            "description": "Very windy",
            "tags": ["Wind", "Warning"],
        }
    ]
