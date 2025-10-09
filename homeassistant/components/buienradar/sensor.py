"""Support for Buienradar.nl weather service."""

from __future__ import annotations

import logging
from typing import Any, cast

from buienradar.constants import (
    ATTRIBUTION,
    CONDCODE,
    CONDITION,
    DETAILED,
    EXACT,
    EXACTNL,
    FORECAST,
    IMAGE,
    MEASURED,
    PRECIPITATION_FORECAST,
    STATIONNAME,
    TIMEFRAME,
    VISIBILITY,
    WINDGUST,
    WINDSPEED,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DEGREE,
    PERCENTAGE,
    Platform,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BuienRadarConfigEntry
from .const import (
    CONF_TIMEFRAME,
    DEFAULT_TIMEFRAME,
    # Constants used for refactoring
    ICON_COMPASS_OUTLINE,
    ICON_GAUGE,
    ICON_WEATHER_PARTLY_CLOUDY,
    ICON_WEATHER_POURING,
    ICON_WEATHER_WINDY,
    LOG_NO_FORECAST,
    STATE_CONDITION_CODES,
    STATE_CONDITIONS,
    STATE_DETAILED_CONDITIONS,
)
from .util import BrData

_LOGGER = logging.getLogger(__name__)

MEASURED_LABEL = "Measured"
TIMEFRAME_LABEL = "Timeframe"
SYMBOL = "symbol"

# Schedule next call after (minutes):
SCHEDULE_OK = 10
# When an error occurred, new call after (minutes):
SCHEDULE_NOK = 2

STATIONNAME_LABEL = "Stationname"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="stationname",
        translation_key="stationname",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfc",
        translation_key="barometerfc",
        icon=ICON_GAUGE,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcname",
        translation_key="barometerfcname",
        icon=ICON_GAUGE,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcnamenl",
        translation_key="barometerfcnamenl",
        icon=ICON_GAUGE,
    ),
    SensorEntityDescription(
        key="condition",
        translation_key="condition",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditioncode",
        translation_key="conditioncode",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditiondetailed",
        translation_key="conditiondetailed",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditionexact",
        translation_key="conditionexact",
    ),
    SensorEntityDescription(
        key="symbol",
        translation_key="symbol",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="feeltemperature",
        translation_key="feeltemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="groundtemperature",
        translation_key="groundtemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windspeed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windforce",
        translation_key="windforce",
        native_unit_of_measurement="Bft",
        icon=ICON_WEATHER_WINDY,
    ),
    SensorEntityDescription(
        key="winddirection",
        translation_key="winddirection",
        icon=ICON_COMPASS_OUTLINE,
    ),
    SensorEntityDescription(
        key="windazimuth",
        translation_key="windazimuth",
        native_unit_of_measurement=DEGREE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        icon=ICON_GAUGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windgust",
        translation_key="windgust",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="precipitation",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SensorEntityDescription(
        key="irradiance",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="precipitation_forecast_average",
        translation_key="precipitation_forecast_average",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SensorEntityDescription(
        key="precipitation_forecast_total",
        translation_key="precipitation_forecast_total",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlast24hour",
        translation_key="rainlast24hour",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlasthour",
        translation_key="rainlasthour",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="temperature_1d",
        translation_key="temperature_1d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_2d",
        translation_key="temperature_2d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_3d",
        translation_key="temperature_3d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_4d",
        translation_key="temperature_4d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_5d",
        translation_key="temperature_5d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_1d",
        translation_key="mintemp_1d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_2d",
        translation_key="mintemp_2d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_3d",
        translation_key="mintemp_3d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_4d",
        translation_key="mintemp_4d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_5d",
        translation_key="mintemp_5d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="rain_1d",
        translation_key="rain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_2d",
        translation_key="rain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_3d",
        translation_key="rain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_4d",
        translation_key="rain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_5d",
        translation_key="rain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="minrain_1d",
        translation_key="minrain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_2d",
        translation_key="minrain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_3d",
        translation_key="minrain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_4d",
        translation_key="minrain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_5d",
        translation_key="minrain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="maxrain_1d",
        translation_key="maxrain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_2d",
        translation_key="maxrain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_3d",
        translation_key="maxrain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_4d",
        translation_key="maxrain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_5d",
        translation_key="maxrain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rainchance_1d",
        translation_key="rainchance_1d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_POURING,
    ),
    SensorEntityDescription(
        key="rainchance_2d",
        translation_key="rainchance_2d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_POURING,
    ),
    SensorEntityDescription(
        key="rainchance_3d",
        translation_key="rainchance_3d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_POURING,
    ),
    SensorEntityDescription(
        key="rainchance_4d",
        translation_key="rainchance_4d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_POURING,
    ),
    SensorEntityDescription(
        key="rainchance_5d",
        translation_key="rainchance_5d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_POURING,
    ),
    SensorEntityDescription(
        key="sunchance_1d",
        translation_key="sunchance_1d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_PARTLY_CLOUDY,
    ),
    SensorEntityDescription(
        key="sunchance_2d",
        translation_key="sunchance_2d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_PARTLY_CLOUDY,
    ),
    SensorEntityDescription(
        key="sunchance_3d",
        translation_key="sunchance_3d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_PARTLY_CLOUDY,
    ),
    SensorEntityDescription(
        key="sunchance_4d",
        translation_key="sunchance_4d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_PARTLY_CLOUDY,
    ),
    SensorEntityDescription(
        key="sunchance_5d",
        translation_key="sunchance_5d",
        native_unit_of_measurement=PERCENTAGE,
        icon=ICON_WEATHER_PARTLY_CLOUDY,
    ),
    SensorEntityDescription(
        key="windforce_1d",
        translation_key="windforce_1d",
        native_unit_of_measurement="Bft",
        icon=ICON_WEATHER_WINDY,
    ),
    SensorEntityDescription(
        key="windforce_2d",
        translation_key="windforce_2d",
        native_unit_of_measurement="Bft",
        icon=ICON_WEATHER_WINDY,
    ),
    SensorEntityDescription(
        key="windforce_3d",
        translation_key="windforce_3d",
        native_unit_of_measurement="Bft",
        icon=ICON_WEATHER_WINDY,
    ),
    SensorEntityDescription(
        key="windforce_4d",
        translation_key="windforce_4d",
        native_unit_of_measurement="Bft",
        icon=ICON_WEATHER_WINDY,
    ),
    SensorEntityDescription(
        key="windforce_5d",
        translation_key="windforce_5d",
        native_unit_of_measurement="Bft",
        icon=ICON_WEATHER_WINDY,
    ),
    SensorEntityDescription(
        key="windspeed_1d",
        translation_key="windspeed_1d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_2d",
        translation_key="windspeed_2d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_3d",
        translation_key="windspeed_3d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_4d",
        translation_key="windspeed_4d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_5d",
        translation_key="windspeed_5d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="winddirection_1d",
        translation_key="winddirection_1d",
        icon=ICON_COMPASS_OUTLINE,
    ),
    SensorEntityDescription(
        key="winddirection_2d",
        translation_key="winddirection_2d",
        icon=ICON_COMPASS_OUTLINE,
    ),
    SensorEntityDescription(
        key="winddirection_3d",
        translation_key="winddirection_3d",
        icon=ICON_COMPASS_OUTLINE,
    ),
    SensorEntityDescription(
        key="winddirection_4d",
        translation_key="winddirection_4d",
        icon=ICON_COMPASS_OUTLINE,
    ),
    SensorEntityDescription(
        key="winddirection_5d",
        translation_key="winddirection_5d",
        icon=ICON_COMPASS_OUTLINE,
    ),
    SensorEntityDescription(
        key="windazimuth_1d",
        translation_key="windazimuth_1d",
        native_unit_of_measurement=DEGREE,
        icon=ICON_COMPASS_OUTLINE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_2d",
        translation_key="windazimuth_2d",
        native_unit_of_measurement=DEGREE,
        icon=ICON_COMPASS_OUTLINE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_3d",
        translation_key="windazimuth_3d",
        native_unit_of_measurement=DEGREE,
        icon=ICON_COMPASS_OUTLINE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_4d",
        translation_key="windazimuth_4d",
        native_unit_of_measurement=DEGREE,
        icon=ICON_COMPASS_OUTLINE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_5d",
        translation_key="windazimuth_5d",
        native_unit_of_measurement=DEGREE,
        icon=ICON_COMPASS_OUTLINE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="condition_1d",
        translation_key="condition_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_2d",
        translation_key="condition_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_3d",
        translation_key="condition_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_4d",
        translation_key="condition_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_5d",
        translation_key="condition_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditioncode_1d",
        translation_key="conditioncode_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_2d",
        translation_key="conditioncode_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_3d",
        translation_key="conditioncode_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_4d",
        translation_key="conditioncode_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_5d",
        translation_key="conditioncode_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditiondetailed_1d",
        translation_key="conditiondetailed_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_2d",
        translation_key="conditiondetailed_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_3d",
        translation_key="conditiondetailed_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_4d",
        translation_key="conditiondetailed_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_5d",
        translation_key="conditiondetailed_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditionexact_1d",
        translation_key="conditionexact_1d",
    ),
    SensorEntityDescription(
        key="conditionexact_2d",
        translation_key="conditionexact_2d",
    ),
    SensorEntityDescription(
        key="conditionexact_3d",
        translation_key="conditionexact_3d",
    ),
    SensorEntityDescription(
        key="conditionexact_4d",
        translation_key="conditionexact_4d",
    ),
    SensorEntityDescription(
        key="conditionexact_5d",
        translation_key="conditionexact_5d",
    ),
    SensorEntityDescription(
        key="symbol_1d",
        translation_key="symbol_1d",
    ),
    SensorEntityDescription(
        key="symbol_2d",
        translation_key="symbol_2d",
    ),
    SensorEntityDescription(
        key="symbol_3d",
        translation_key="symbol_3d",
    ),
    SensorEntityDescription(
        key="symbol_4d",
        translation_key="symbol_4d",
    ),
    SensorEntityDescription(
        key="symbol_5d",
        translation_key="symbol_5d",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BuienRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the buienradar sensor."""
    config = entry.data
    options = entry.options

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    timeframe = options.get(
        CONF_TIMEFRAME, config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME)
    )

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {CONF_LATITUDE: float(latitude), CONF_LONGITUDE: float(longitude)}

    _LOGGER.debug(
        "Initializing buienradar sensor coordinate %s, timeframe %s",
        coordinates,
        timeframe,
    )

    # create weather entities:
    entities = [
        BrSensor(config.get(CONF_NAME, "Buienradar"), coordinates, description)
        for description in SENSOR_TYPES
    ]

    # create weather data:
    data = BrData(hass, coordinates, timeframe, entities)
    entry.runtime_data[Platform.SENSOR] = data
    await data.async_update()

    async_add_entities(entities)


class BrSensor(SensorEntity):
    """Representation of a Buienradar sensor."""

    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, client_name, coordinates, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._data: BrData | None = None
        self._measured = None
        self._attr_unique_id = (
            f"{coordinates[CONF_LATITUDE]:2.6f}{coordinates[CONF_LONGITUDE]:2.6f}"
            f"{description.key}"
        )

        # All continuous sensors should be forced to be updated
        self._attr_force_update = (
            description.key != SYMBOL and not description.key.startswith(CONDITION)
        )

        if description.key.startswith(PRECIPITATION_FORECAST):
            self._timeframe = None

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to hass."""
        if self._data is None:
            return
        self._update()

    @callback
    def data_updated(self, data: BrData):
        """Handle data update."""
        self._data = data
        if not self.hass:
            return
        self._update()

    def _update(self):
        """Update sensor data."""
        _LOGGER.debug("Updating sensor %s", self.entity_id)
        if self._load_data(self._data.data):
            self.async_write_ha_state()

    @callback
    def _load_data(self, data):
        """Load the sensor with relevant data -- refactored!"""
        if not self._has_new_measurement(data):
            return False

        sensor_type = self.entity_description.key

        # Forecast sensors: *_1d .. *_5d
        if self._is_forecast_sensor(sensor_type):
            fcday = self._forecast_day_index(sensor_type)
            if self._is_condition_sensor(sensor_type):
                return self._update_forecast_condition(sensor_type, data, fcday)
            if sensor_type.startswith(WINDSPEED):
                return self._update_forecast_windspeed(data, fcday, sensor_type)
            return self._update_forecast_generic(data, fcday, sensor_type)

        # Current (non-forecast) condition & symbol
        if self._is_current_condition_sensor(sensor_type):
            return self._update_current_condition(sensor_type, data)

        # Nested precipitation forecast block
        if sensor_type.startswith(PRECIPITATION_FORECAST):
            return self._update_precipitation_forecast_nested(sensor_type, data)

        # Wind conversions (current)
        if sensor_type in (WINDSPEED, WINDGUST):
            return self._update_current_wind(sensor_type, data)

        # Visibility conversion (current)
        if sensor_type == VISIBILITY:
            return self._update_visibility(data)

        # Generic path + common attributes
        return self._update_generic_and_attrs(sensor_type, data)

    # -----------------------------
    # Helper methods for _load_data
    # -----------------------------

    def _has_new_measurement(self, data) -> bool:
        """Check if 'MEASURED' changed; store it.

        Args:
            data: Raw Buienradar payload.

        Returns:
            True if measurement timestamp differs from previous (and is saved), else False.
        """
        measured = data.get(MEASURED)
        if self._measured == measured:
            return False
        self._measured = measured
        return True

    def _is_forecast_sensor(self, sensor_type: str) -> bool:
        """Return True if sensor key ends with a day suffix (_1d.._5d)."""
        return sensor_type.endswith(("_1d", "_2d", "_3d", "_4d", "_5d"))

    def _forecast_day_index(self, sensor_type: str) -> int:
        """Map *_Xd suffix to forecast day index (0..4).

        Args:
            sensor_type: Entity key (e.g 'temp_3d').

        Returns:
            Integer day offset: 0 for _1d (today), 1 for _2d, ... 4 for _5d.
        """
        if sensor_type.endswith("_2d"):
            return 1
        if sensor_type.endswith("_3d"):
            return 2
        if sensor_type.endswith("_4d"):
            return 3
        if sensor_type.endswith("_5d"):
            return 4
        return 0

    def _is_condition_sensor(self, sensor_type: str) -> bool:
        """Return True if sensor represents a weather condition/symbol variant."""
        return sensor_type.startswith(
            (SYMBOL, CONDITION, "conditioncode", "conditiondetailed", "conditionexact")
        )

    def _extract_condition_field(self, sensor_type: str, condition: dict):
        """Select the appropriate condition field for this sensor.

        Args:
            sensor_type: Condition-like sensor key.
            condition: Condition dict from payload.

        Returns:
            The string value (e.g exactnl/condcode/detailed/exact) or None.
        """
        if sensor_type.startswith(SYMBOL):
            return condition.get(EXACTNL)
        if sensor_type == CONDITION or sensor_type.startswith(CONDITION):
            return condition.get(CONDITION)
        if sensor_type.startswith("conditioncode"):
            return condition.get(CONDCODE)
        if sensor_type.startswith("conditiondetailed"):
            return condition.get(DETAILED)
        if sensor_type.startswith("conditionexact"):
            return condition.get(EXACT)
        return None

    def _update_forecast_condition(
        self, sensor_type: str, data: dict, fcday: int
    ) -> bool:
        """Update forecasted condition (state + image) for a given day.

        Args:
            sensor_type: Condition-like forecast sensor key.
            data: Raw Buienradar payload.
            fcday: Forecast day index (0..4).

        Returns:
            True if state or image changed and were updated; otherwise False.
        """
        forecast = cast(list[dict[str, Any]], data.get(FORECAST) or [])
        if fcday >= len(forecast):
            _LOGGER.warning(LOG_NO_FORECAST, fcday)
            return False

        condition = forecast[fcday].get(CONDITION)
        if not condition:
            return False

        new_state = self._extract_condition_field(sensor_type, condition)
        img = condition.get(IMAGE)
        if new_state != self.state or img != self.entity_picture:
            self._attr_native_value = new_state
            self._attr_entity_picture = img
            return True
        return False

    def _update_forecast_windspeed(
        self, data: dict, fcday: int, sensor_type: str
    ) -> bool:
        """Update forecast windspeed: read m/s and store km/h.

        Args:
            data: Raw Buienradar payload.
            fcday: Forecast day index (0..4).
            sensor_type: Windspeed key with day suffix (e.g 'wind_speed_2d').

        Returns:
            True if value was set; False if missing/unavailable.
        """
        forecast = cast(list[dict[str, Any]], data.get(FORECAST) or [])
        if fcday >= len(forecast):
            _LOGGER.warning(LOG_NO_FORECAST, fcday)
            return False

        value_ms = forecast[fcday].get(sensor_type[:-3])
        if value_ms is None:
            return False

        self._attr_native_value = round(float(value_ms) * 3.6, 1)
        return True

    def _update_forecast_generic(
        self, data: dict, fcday: int, sensor_type: str
    ) -> bool:
        """Update generic forecast value for a given day (non-wind, non-condition).

        Args:
            data: Raw Buienradar payload.
            fcday: Forecast day index (0..4).
            sensor_type: Sensor key with day suffix.

        Returns:
            True if value was set; False if forecast missing.
        """
        forecast = cast(list[dict[str, Any]], data.get(FORECAST) or [])
        if fcday >= len(forecast):
            _LOGGER.warning(LOG_NO_FORECAST, fcday)
            return False

        self._attr_native_value = forecast[fcday].get(sensor_type[:-3])
        return True

    def _is_current_condition_sensor(self, sensor_type: str) -> bool:
        """Return True if this is a non-forecast condition/symbol variant."""
        return (
            sensor_type == SYMBOL
            or sensor_type.startswith(CONDITION)
            or sensor_type in ("conditioncode", "conditiondetailed", "conditionexact")
        )

    def _update_current_condition(self, sensor_type: str, data: dict) -> bool:
        """Update current condition (state + image).

        Args:
            sensor_type: Condition-like sensor key.
            data: Raw Buienradar payload.

        Returns:
            True if state or image changed and were updated; otherwise False.
        """
        condition = data.get(CONDITION)
        if not condition:
            return False

        new_state = self._extract_condition_field(sensor_type, condition)
        img = condition.get(IMAGE)
        if new_state != self.state or img != self.entity_picture:
            self._attr_native_value = new_state
            self._attr_entity_picture = img
            return True
        return False

    def _update_precipitation_forecast_nested(
        self, sensor_type: str, data: dict
    ) -> bool:
        """Update nested precipitation-forecast value and related attributes.

        Args:
            sensor_type: Key under 'precipitation_forecast.*'.
            data: Raw Buienradar payload.

        Returns:
            True always after setting value and attributes.
        """
        nested = data.get(PRECIPITATION_FORECAST) or {}
        self._timeframe = nested.get(TIMEFRAME)
        key = sensor_type[len(PRECIPITATION_FORECAST) + 1 :]
        self._attr_native_value = nested.get(key)

        attrs = {ATTR_ATTRIBUTION: data.get(ATTRIBUTION)}
        if self._timeframe is not None:
            attrs[TIMEFRAME_LABEL] = f"{self._timeframe} min"
        self._attr_extra_state_attributes = attrs
        return True

    def _update_current_wind(self, sensor_type: str, data: dict) -> bool:
        """Update current windspeed/gust: read m/s and store km/h.

        Args:
            sensor_type: WINDSPEED or WINDGUST.
            data: Raw Buienradar payload.

        Returns:
            True if value was set; False if missing.
        """
        value_ms = data.get(sensor_type)
        if value_ms is None:
            return False
        self._attr_native_value = round(value_ms * 3.6, 1)
        return True

    def _update_visibility(self, data: dict) -> bool:
        """Update visibility: meters → kilometers (1 decimal).

        Args:
            data: Raw Buienradar payload.

        Returns:
            True if value was set; False if missing.
        """
        value_m = data.get(VISIBILITY)
        if value_m is None:
            return False
        self._attr_native_value = round(value_m / 1000, 1)
        return True

    def _update_generic_and_attrs(self, sensor_type: str, data: dict) -> bool:
        """Set generic value and common attributes (attribution, station, measured).

        Args:
            sensor_type: Entity key to read from data.
            data: Raw Buienradar payload.

        Returns:
            True after updating value and attributes.
        """
        self._attr_native_value = data.get(sensor_type)

        attrs = {
            ATTR_ATTRIBUTION: data.get(ATTRIBUTION),
            STATIONNAME_LABEL: data.get(STATIONNAME),
        }
        if self._measured is not None:
            local_dt = dt_util.as_local(self._measured)
            attrs[MEASURED_LABEL] = local_dt.strftime("%c")

        self._attr_extra_state_attributes = attrs
        return True
