To run openweathermap, you need an API key from OpenWeatherMap. You can sign up for a free API key `here <https://home.openweathermap.org/users/sign_up>`__.

Group 5 from Chalmers university in course software evolution project:
Added alert sensor, uses homeassistant standard sensor component to generate alerts.
Tests were added for sensor alerts and can be run in the terminal using for example:
pytest tests/components/openweathermap/test_sensor.py::test_alert_sensor_values

Alerts are shown in its own entity with the adition of maps to further enhance information about a location.