"""Thin OpenWeatherMap REST client (Current Weather, 5-day/3-h Forecast, Air Pollution)."""

from __future__ import annotations

import requests

from ..config import SETTINGS

BASE_URL = "https://api.openweathermap.org/data/2.5"
TIMEOUT_S = 10
AQI_LABELS = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}


class WeatherError(RuntimeError):
    pass


class OWMClient:
    def __init__(self, api_key: str = SETTINGS.owm_api_key) -> None:
        if not api_key:
            raise WeatherError("OWM_API_KEY is not set - add it to raspberry-pi/.env")
        self.api_key = api_key
        self.session = requests.Session()

    def _get(self, endpoint: str, **params) -> dict:
        params["appid"] = self.api_key
        try:
            response = self.session.get(f"{BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT_S)
            response.raise_for_status()
        except requests.RequestException as exc:
            # Strip the query string so the API key never ends up in logs
            raise WeatherError(f"OpenWeatherMap /{endpoint} failed: {type(exc).__name__}") from None
        return response.json()

    def current(self, lat: float, lon: float) -> dict:
        return self._get("weather", lat=lat, lon=lon, units="metric")

    def current_by_city(self, city: str) -> dict:
        return self._get("weather", q=city, units="metric")

    def forecast(self, lat: float, lon: float) -> dict:
        return self._get("forecast", lat=lat, lon=lon, units="metric")

    def forecast_by_city(self, city: str) -> dict:
        return self._get("forecast", q=city, units="metric")

    def air_quality(self, lat: float, lon: float) -> tuple[int | None, dict]:
        data = self._get("air_pollution", lat=lat, lon=lon)
        if not data.get("list"):
            return None, {}
        entry = data["list"][0]
        return entry["main"]["aqi"], entry["components"]

    def tile_url(self, layer: str) -> str:
        return f"https://tile.openweathermap.org/map/{layer}/{{z}}/{{x}}/{{y}}.png?appid={self.api_key}"
