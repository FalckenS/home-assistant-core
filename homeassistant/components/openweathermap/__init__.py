"""The openweathermap component."""

from __future__ import annotations

from dataclasses import dataclass
import sys

from pyopenweathermap import create_owm_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_MODE
from homeassistant.core import HomeAssistant

from .const import (
    CONFIG_FLOW_VERSION,
    DEFAULT_OWM_MODE,
    OWM_MODE_V30,
    OWM_MODES,
    PLATFORMS,
)
from .coordinator import OWMUpdateCoordinator, get_owm_update_coordinator
from .map_view import register_map_view
from .repairs import async_create_issue, async_delete_issue
from .utils import build_data_and_options

type OpenweathermapConfigEntry = ConfigEntry["OpenweathermapData"]


@dataclass
class OpenweathermapData:
    """Runtime data definition."""

    mode: str
    coordinator: OWMUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenweathermapConfigEntry
) -> bool:
    """Set up OpenWeatherMap as config entry."""
    api_key = entry.data[CONF_API_KEY]
    language = entry.options[CONF_LANGUAGE]
    mode = entry.options[CONF_MODE]

    if mode not in OWM_MODES:
        async_create_issue(hass, entry.entry_id)
    else:
        async_delete_issue(hass, entry.entry_id)

    owm_client = create_owm_client(api_key, mode, lang=language)
    coordinator_cls = get_owm_update_coordinator(mode)
    owm_coordinator = coordinator_cls(hass, entry, owm_client)

    await owm_coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    entry.runtime_data = OpenweathermapData(mode, owm_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if mode == OWM_MODE_V30 and "pytest" not in sys.modules:  # Breaks
        register_map_view(hass)  # pragma: no cover

    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: OpenweathermapConfigEntry
) -> bool:
    """Migrate old entry."""
    config_entries = hass.config_entries
    data = entry.data
    options = entry.options
    version = entry.version

    if version < CONFIG_FLOW_VERSION:
        combined_data = {**data, **options, CONF_MODE: DEFAULT_OWM_MODE}
        new_data, new_options = build_data_and_options(combined_data)
        config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=CONFIG_FLOW_VERSION,
        )

    return True


async def async_update_options(
    hass: HomeAssistant, entry: OpenweathermapConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenweathermapConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
