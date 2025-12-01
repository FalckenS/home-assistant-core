"""Tests for OpenWeatherMap sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mode", [OWM_MODE_V30, OWM_MODE_FREE_CURRENT, OWM_MODE_AIRPOLLUTION], indirect=True
)
async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    mode: str,
) -> None:
    """Test sensor states are correctly collected from library with different modes and mocked function responses."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("mode", [OWM_MODE_FREE_FORECAST], indirect=True)
async def test_mode_no_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    mode: str,
) -> None:
    """Test modes that do not provide any sensor."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert len(entity_registry.entities) == 0


@pytest.mark.parametrize("mode", [OWM_MODE_V30], indirect=True)
async def test_alert_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    mode: str,
) -> None:
    """Test weather alert sensor values are correctly populated."""
    # Access the pre-configured mock return value from the fixture
    weather_report = owm_client_mock.get_weather.return_value

    # Inject alert data into the mock report
    weather_report.alerts = [
        {
            "sender_name": "National Weather Service",
            "event": "Flood Warning",
            "start": 1731154800,
            "end": 1731187200,
            "description": "Flooding expected near rivers and low-lying areas.",
            "tags": ["Flood", "Warning"],
        }
    ]

    # Set up the platform
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    # Check 'event'
    state = hass.states.get("sensor.openweathermap_alert_event")
    assert state is not None
    assert state.state == "Flood Warning"

    # Check 'sender_name'
    state = hass.states.get("sensor.openweathermap_alert_source")
    assert state is not None
    assert state.state == "National Weather Service"

    # Check 'tags'
    state = hass.states.get("sensor.openweathermap_alert_type")
    assert state is not None
    assert state.state == "Flood, Warning"

    # Check 'description'
    state = hass.states.get("sensor.openweathermap_alert_description")
    assert state is not None
    assert state.state == "Flooding expected near rivers and low-lying areas."
