# Readme for custom weather alerts extension for the OWM integration
Team 2 from Chalmers university in course DAT266 Software evolution project:
- Added alert sensor entity which uses homeassistant standard sensor card component to display active alert.
- Added tests for sensor alerts.
- Added custom web card that displays a map view of an active alert with overlays.
- Added tests for the custom web card.
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
**Usage:**
An API key from Openweathermap is required to run the integration extension, (You can sign up for a free API key `at <https://home.openweathermap.org/users/sign_up>`__.). **NOTE:** the key requires both 2.0 and 3.0 access.

The alert sensor card will be displayed automatically once the integration is active, however bare in mind that it will only display an alert if one is currently active (which is unlikely). A mock alert can be activated by uncommenting the lines 404-414 in the sensor.py file.

The custom map card must be activated manually before it will be displayed, this is done by navigating to Settings > Dashboards > Add dashboard and select Webpage and enter /api/openweathermap/map (this refers to a local generated .html file). Just like the sensor entity this will not display any overlays unless an alert is active.