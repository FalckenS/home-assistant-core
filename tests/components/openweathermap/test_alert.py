"""Define tests for the OpenWeatherMap map view."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.openweathermap.const import DOMAIN, OWM_MODE_V30
from homeassistant.components.openweathermap.coordinator import WeatherUpdateCoordinator
from homeassistant.components.openweathermap.map_view import (
    OWMMapView,
    _layers_for_alerts,
    register_map_view,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize("mode", [OWM_MODE_V30], indirect=True)
async def test_weather_coordinator_calls_onecall_for_alerts(
    hass: HomeAssistant,
    mock_config_entry,
    owm_client_mock,
) -> None:
    """Ensure _async_update_data performs the One Call 3.0 request."""

    # Dummy HTTP response for the alerts fetch
    class DummyResp:
        status = 500  # non-200 path (logs warning, no alerts)

        async def json(self):
            return {}

    session = AsyncMock()
    session.get.return_value = DummyResp()

    # Patch the HTTP session used inside the coordinator
    with patch(
        "homeassistant.components.openweathermap.coordinator.async_get_clientsession",
        return_value=session,
    ):
        coordinator = WeatherUpdateCoordinator(hass, mock_config_entry, owm_client_mock)
        # Avoid relying on the full WeatherReport structure
        coordinator._convert_weather_response = lambda weather_report: {}
        await coordinator._async_update_data()

    # If this assertion passes, the HTTP call for alerts was made
    session.get.assert_awaited_once()


def test_layers_for_alerts_from_tags_and_empty_list() -> None:
    """Cover _layers_for_alerts for empty and non-empty alerts.

    - Empty list exercises the early-return branch.
    - Non-empty list with tags exercises the keyword matching & sorting.
    """
    # No alerts -> early return []
    assert _layers_for_alerts([]) == []

    # Alert with tags that should map to specific layers via ALERT_KEYWORD_TO_LAYERS
    alerts = [
        {
            "event": "Snow and wind warning",
            "tags": ["Wind", "Snow and Ice"],
        }
    ]

    layers = _layers_for_alerts(alerts)

    # wind  -> "WND"
    # snow/ice -> "PAS0"
    assert layers == sorted(layers)
    assert set(layers) == {"WND", "PAS0"}


async def test_map_view_get_html_uses_entry_and_alert_layers(
    hass: HomeAssistant,
) -> None:
    """Cover OWMMapView.get with a v3.0 entry present."""

    # Create a v3.0 config entry so the view finds it
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenWeatherMap",
        unique_id="12.34-56.78",
        data={
            CONF_API_KEY: "test-key",
            CONF_LATITUDE: 12.34,
            CONF_LONGITUDE: 56.78,
        },
        options={CONF_MODE: OWM_MODE_V30},
    )
    entry.add_to_hass(hass)

    # Stub runtime_data and coordinator with an alert that should map to layer "WND"
    class DummyCoordinator:
        def __init__(self) -> None:
            self.data = {"alerts": [{"event": "Storm warning", "tags": ["Wind"]}]}

    class DummyRuntimeData:
        def __init__(self) -> None:
            self.coordinator = DummyCoordinator()

    entry.runtime_data = DummyRuntimeData()

    view = OWMMapView(hass)

    # Request object is unused in get(), so we can pass None
    resp = await view.get(None)

    assert resp.status == 200
    html = resp.text

    # Values injected via MAP_HTML_TEMPLATE
    assert "OpenWeatherMap – Map (v3.0)" in html
    assert "[12.34, 56.78]" in html  # CENTER = [lat, lon]
    assert '"test-key"' in html  # OWM_API_KEY
    assert '"WND"' in html  # ACTIVE_LAYERS from our "Wind" alert


def test_register_map_view_registers_once(hass: HomeAssistant) -> None:
    """Cover register_map_view, including the early-return branch."""

    # Provide a minimal HTTP object with register_view
    class DummyHTTP:
        def __init__(self) -> None:
            self.views = []

        def register_view(self, view) -> None:
            self.views.append(view)

    # Attach dummy http server to hass
    hass.http = DummyHTTP()  # type: ignore[attr-defined]

    # First call: should register the view and set the flag
    register_map_view(hass)

    assert DOMAIN in hass.data
    assert hass.data[DOMAIN]["map_view_registered"] is True
    assert len(hass.http.views) == 1

    # Second call: should hit the "already registered" early return,
    # so no new view is added
    register_map_view(hass)
    assert len(hass.http.views) == 1
