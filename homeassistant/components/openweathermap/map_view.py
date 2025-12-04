"""HTTP view that serves the OpenWeatherMap Leaflet map."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE
from homeassistant.core import HomeAssistant

from .const import DEFAULT_OWM_MODE, DOMAIN, OWM_MODE_V30

_LOGGER = logging.getLogger(__name__)


ALERT_KEYWORD_TO_LAYERS: dict[str, list[str]] = {
    # wind warnings.
    "wind": ["WND"],
    "gale": ["WND"],
    # storms -> wind and precipitation.
    "storm": ["WND", "PR0"],
    "thunderstorm": ["WND", "PR0"],
    # heat / temperature extremes.
    "heat": ["TA2"],
    "hot": ["TA2"],
    "cold": ["TA2"],
    # rain / flood.
    "rain": ["PR0"],
    "flood": ["PA0"],
    # snow / ice.
    "snow": ["PAS0"],
    "ice": ["PAS0"],
}

# NOTE: doubled {{ }} escape Python .format so Leaflet can still use {z}/{x}/{y}/{s}.
MAP_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>OpenWeatherMap – Map (v3.0)</title>

  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  />

  <style>
    html, body {{
      height: 100%;
      margin: 0;
    }}
    #map {{
      width: 100%;
      height: 100%;
    }}
  </style>
</head>
<body>
  <div id="map"></div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    // Center from the v3.0 config entry
    const CENTER = [{lat}, {lon}];

    // OpenWeatherMap API key injected from the config entry.
    // Must be enabled for Weather Maps 2.0.
    const OWM_API_KEY = "{api_key}";

    // List of active layer codes from the backend, e.g. ["WND","PR0"]
    const ACTIVE_LAYERS = {active_layers};
    console.log("OWM map active layers:", ACTIVE_LAYERS);

    const map = L.map("map").setView(CENTER, 8);

    // Base OSM layer
    const baseLayer = L.tileLayer(
      "https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
      {{
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
      }}
    ).addTo(map);

    // Marker at center
    L.marker(CENTER).addTo(map);

    // Small on-map debug box showing which layers are active
    const debugControl = L.control({{ position: "bottomleft" }});
    debugControl.onAdd = function () {{
      const div = L.DomUtil.create("div", "owm-debug");
      div.style.background = "rgba(0, 0, 0, 0.5)";
      div.style.color = "#fff";
      div.style.padding = "4px 8px";
      div.style.fontSize = "12px";
      div.innerHTML =
        "Layers: " +
        (ACTIVE_LAYERS.length ? ACTIVE_LAYERS.join(", ") : "none");
      return div;
    }};
    debugControl.addTo(map);

    // All OWM layers we might use
    const OWM_LAYERS = {{
      TA2: L.tileLayer(
        "https://maps.openweathermap.org/maps/2.0/weather/TA2/{{z}}/{{x}}/{{y}}?appid=" +
          OWM_API_KEY,
        {{
          tileSize: 256,
          opacity: 0.7,
          attribution: "Weather data © OpenWeatherMap",
        }}
      ),
      WND: L.tileLayer(
        "https://maps.openweathermap.org/maps/2.0/weather/WND/{{z}}/{{x}}/{{y}}?appid=" +
          OWM_API_KEY,
        {{
          tileSize: 256,
          opacity: 0.7,
          attribution: "Weather data © OpenWeatherMap",
        }}
      ),
      PR0: L.tileLayer(
        "https://maps.openweathermap.org/maps/2.0/weather/PR0/{{z}}/{{x}}/{{y}}?appid=" +
          OWM_API_KEY,
        {{
          tileSize: 256,
          opacity: 0.7,
          attribution: "Weather data © OpenWeatherMap",
        }}
      ),
      PA0: L.tileLayer(
        "https://maps.openweathermap.org/maps/2.0/weather/PA0/{{z}}/{{x}}/{{y}}?appid=" +
          OWM_API_KEY,
        {{
          tileSize: 256,
          opacity: 0.7,
          attribution: "Weather data © OpenWeatherMap",
        }}
      ),
      PAS0: L.tileLayer(
        "https://maps.openweathermap.org/maps/2.0/weather/PAS0/{{z}}/{{x}}/{{y}}?appid=" +
          OWM_API_KEY,
        {{
          tileSize: 256,
          opacity: 0.7,
          attribution: "Weather data © OpenWeatherMap",
        }}
      ),
    }};

    // Add only the layers selected by the backend
    ACTIVE_LAYERS.forEach(code => {{
      const layer = OWM_LAYERS[code];
      if (layer) {{
        layer.addTo(map);
      }}
    }});
  </script>
</body>
</html>
"""


def _layers_for_alerts(alerts: list[dict[str, Any]]) -> list[str]:
    """Return a list of Weather Maps 2.0 layer codes based on active alerts.

    Alert structure comes directly from pyopenweathermap's One Call 3.0 response
    and is also used by OWMNationalWeatherAlerts, which expects keys like:
      sender_name, event, start, end, description, tags.
    """
    if not alerts:
        return []

    alert = alerts[
        0
    ]  # We currently only use the first tag identified so that only one layer is used, this can be changed but would probably make the individual overlays much harder to see.

    tags = [str(t).lower() for t in alert.get("tags", [])]
    event = str(alert.get("event", "")).lower()

    selected: set[str] = set()

    def maybe_add_from_text(text: str) -> None:
        """Match our keyword table against a text fragment."""
        if not text:
            return
        lower = text.lower()
        for keyword, layers in ALERT_KEYWORD_TO_LAYERS.items():
            if keyword in lower:
                selected.update(layers)

    for tag in tags:
        maybe_add_from_text(tag)

    if not selected:
        maybe_add_from_text(event)

    return sorted(selected)


class OWMMapView(HomeAssistantView):
    """Serve the Leaflet map for the v3.0 OWM entry."""

    url = "/api/openweathermap/map"
    name = "api:openweathermap:map"

    requires_auth = False  # Needs to be False to work inside a Webpage dashboard without extra frontend work. This does not follow HA Guidelines but we lack the time and experience to work with both the back & frontend.

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the OpenWeatherMap map view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle a GET request and return the HTML map page."""
        hass = self.hass
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.options.get(CONF_MODE, DEFAULT_OWM_MODE) == OWM_MODE_V30
        ]

        if not entries:
            return web.Response(
                text="No OpenWeatherMap entry configured with mode v3.0.",
                status=404,
            )

        entry = entries[0]

        lat = entry.data.get(CONF_LATITUDE, hass.config.latitude)
        lon = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
        api_key = entry.data.get(CONF_API_KEY, "")

        runtime_data = entry.runtime_data
        coordinator = runtime_data.coordinator
        alerts: list[dict[str, Any]] = coordinator.data.get("alerts", []) or []
        _LOGGER.warning("OWM map alerts: %s", alerts)

        active_layers = _layers_for_alerts(alerts)
        active_layers_json = json.dumps(active_layers)
        _LOGGER.warning("OWM map active_layers: %s", active_layers)

        html = MAP_HTML_TEMPLATE.format(
            lat=lat,
            lon=lon,
            api_key=api_key,
            active_layers=active_layers_json,
        )
        return web.Response(text=html, content_type="text/html")


def register_map_view(hass: HomeAssistant) -> None:
    """Register the map view once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("map_view_registered"):
        return
    hass.http.register_view(OWMMapView(hass))
    domain_data["map_view_registered"] = True
