"""Support for the OpenWeatherMap (OWM) service."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEGREE,
    PERCENTAGE,
    UV_INDEX,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import OpenweathermapConfigEntry
from .const import (
    ATTR_API_AIRPOLLUTION_AQI,
    ATTR_API_AIRPOLLUTION_CO,
    ATTR_API_AIRPOLLUTION_NO,
    ATTR_API_AIRPOLLUTION_NO2,
    ATTR_API_AIRPOLLUTION_O3,
    ATTR_API_AIRPOLLUTION_PM2_5,
    ATTR_API_AIRPOLLUTION_PM10,
    ATTR_API_AIRPOLLUTION_SO2,
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_CURRENT,
    ATTR_API_DEW_POINT,
    ATTR_API_FEELS_LIKE_TEMPERATURE,
    ATTR_API_HUMIDITY,
    ATTR_API_PRECIPITATION_KIND,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_SNOW,
    ATTR_API_TEMPERATURE,
    ATTR_API_UV_INDEX,
    ATTR_API_VISIBILITY_DISTANCE,
    ATTR_API_WEATHER,
    ATTR_API_WEATHER_CODE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_GUST,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_FREE_FORECAST,
)
from .coordinator import OWMUpdateCoordinator

ALERTS_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        name="OpenWeatherMap Alert Source",
        key="sender_name",  # alerts.sender_name
        icon="mdi:source-branch",
    ),
    SensorEntityDescription(
        name="OpenWeatherMap Alert Event",
        key="event",  # alerts.event
        icon="mdi:alert-circle-outline",
    ),
    SensorEntityDescription(
        name="OpenWeatherMap Alert From",
        key="start",  # alerts.start
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        name="OpenWeatherMap Alert To",
        key="end",  # alerts.end
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        name="OpenWeatherMap Alert Description",
        key="description",  # alerts.description
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        name="OpenWeatherMap Alert Type",
        key="tags",  # alerts.tags
        icon="mdi:tag-outline",
    ),
)

WEATHER_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_API_WEATHER,
        translation_key=ATTR_API_WEATHER,
    ),
    SensorEntityDescription(
        key=ATTR_API_DEW_POINT,
        translation_key=ATTR_API_DEW_POINT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_FEELS_LIKE_TEMPERATURE,
        translation_key=ATTR_API_FEELS_LIKE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_WIND_GUST,
        translation_key=ATTR_API_WIND_GUST,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_WIND_BEARING,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key=ATTR_API_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key=ATTR_API_CLOUDS,
        translation_key=ATTR_API_CLOUDS,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_RAIN,
        translation_key=ATTR_API_RAIN,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_SNOW,
        translation_key=ATTR_API_SNOW,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PRECIPITATION_KIND,
        translation_key=ATTR_API_PRECIPITATION_KIND,
    ),
    SensorEntityDescription(
        key=ATTR_API_UV_INDEX,
        translation_key=ATTR_API_UV_INDEX,
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_VISIBILITY_DISTANCE,
        translation_key=ATTR_API_VISIBILITY_DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key=ATTR_API_CONDITION,
        translation_key=ATTR_API_CONDITION,
    ),
    SensorEntityDescription(
        key=ATTR_API_WEATHER_CODE,
        translation_key=ATTR_API_WEATHER_CODE,
    ),
)

AIRPOLLUTION_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_AQI,
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_CO,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_NO,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_NO2,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_O3,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_SO2,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_PM2_5,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_AIRPOLLUTION_PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenweathermapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = config_entry.runtime_data
    unique_id = config_entry.unique_id
    assert unique_id is not None
    coordinator = domain_data.coordinator

    if domain_data.mode == OWM_MODE_FREE_FORECAST:
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for entry in entries:
            entity_registry.async_remove(entry.entity_id)
    elif domain_data.mode == OWM_MODE_AIRPOLLUTION:
        async_add_entities(
            OpenWeatherMapSensor(
                unique_id,
                description,
                coordinator,
            )
            for description in AIRPOLLUTION_SENSOR_TYPES
        )
    else:
        async_add_entities(
            OpenWeatherMapSensor(
                unique_id,
                description,
                coordinator,
            )
            for description in WEATHER_SENSOR_TYPES
        )

        async_add_entities(
            OWMNationalWeatherAlerts(
                unique_id,
                description,
                coordinator,
            )
            for description in ALERTS_SENSOR_TYPES
        )


class AbstractOpenWeatherMapSensor(SensorEntity):
    """Abstract class for an OpenWeatherMap sensor."""

    _attr_should_poll = False
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        description: SensorEntityDescription,
        coordinator: OWMUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._coordinator = coordinator

        self._attr_unique_id = f"{unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Get the latest data from OWM and updates the states."""
        await self._coordinator.async_request_refresh()


class OpenWeatherMapSensor(AbstractOpenWeatherMapSensor):
    """Implementation of an OpenWeatherMap sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self._coordinator.data[ATTR_API_CURRENT].get(self.entity_description.key)


class OWMNationalWeatherAlerts(SensorEntity):
    """Implementation of an OpenWeatherMap alert sensor.

    This class reads alert information from the OWMUpdateCoordinator
    and exposes alert fields for example sender, event, start time,
    as individual sensor values. As of this implementation only one alert is handled.

    As we can not garantee that there is always an alert present, you can mock an alert
    through an insertion in the coordinator data.
    """

    def __init__(
        self,
        unique_id: str,
        description: SensorEntityDescription,
        coordinator: OWMUpdateCoordinator,
    ) -> None:
        """Initialize the sensor.

        Parameters:
            unique_id: Base unique ID for sensor.
            description: Entity description that defines which alert field.
            coordinator: Data update coordinator providing OWM alert data.
        """
        self.entity_description = description
        self._coordinator = coordinator

        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{unique_id}-nwa-{description.key}"
        self._attr_icon = f"{description.icon}"

    @property
    def native_value(self) -> StateType:
        """Return alert info.

        Return the sensor value basied on the current weather alert.

        Behavior:
            - If no alert data is available, return N/A.
            - Otherwise extract the value from this sensor's
              description key from the first alert entry.
            - Converts UNIX timestamps (`start`, `end`) to a formatted
              `YYYY-MM-DD HH:MM` string.
            - Joins alert `tags` to one string seperated by a comma.

        Returns:
            The formatted alert field value or N/A if the field is
            missing or alerts are not present.
        """
        alerts = self._coordinator.data.get("alerts")

        # this is for testing the sensor with some fake data

        # if not self._coordinator.data.get("alerts"):
        #     self._coordinator.data["alerts"] = [
        #         {
        #             "sender_name": "National Weather Service",
        #             "event": "Flood Warning",
        #             "start": 1731154800,
        #             "end": 1731187200,
        #             "description": "Flooding expected near rivers and low-lying areas.",
        #             "tags": ["Flood", "Warning"],
        #         }
        #     ]

        # if there is no alerts value in the api resonse we just return N/A.
        if not alerts:
            return "N/A"

        # alerts[0] = we only handle 1 alert for now
        value = alerts[0].get(self.entity_description.key, "N/A")

        # convert timestamps (start/end) to human-readable
        # this allows either int or float values from the api
        if self.entity_description.key in ("start", "end") and isinstance(
            value, (int, float)
        ):
            value = datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")

        # concat tags if multiple
        if self.entity_description.key == "tags" and isinstance(value, list):
            value = ", ".join(value)

        return value
