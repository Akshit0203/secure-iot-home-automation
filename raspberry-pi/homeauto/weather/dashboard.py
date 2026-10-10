"""Real-time Weather & Air-Quality dashboard for Raspberry Pi 5.

Features
* IP-based geolocation (geocoder) with a configurable fallback (New Delhi)
* Current conditions, AQI (1-5) with pollutant breakdown (PM2.5, PM10, CO, NO2, SO2, O3, NH3)
* Next-24 h forecast (8 x 3 h blocks) - temperature/humidity dual-axis plot embedded in Tk
* Spoken temperature via gTTS (Indian English, ``tld="co.in"``) + mpg123
* Interactive Folium map with live OpenWeatherMap temperature & cloud tile overlays

Run:  python -m homeauto.weather.dashboard [--no-voice] [--no-map]
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..config import SETTINGS
from .owm_client import AQI_LABELS, OWMClient, WeatherError

log = logging.getLogger(__name__)


def detect_location() -> tuple[float, float]:
    try:
        import geocoder

        g = geocoder.ip("me")
        if g.ok and g.latlng:
            return float(g.latlng[0]), float(g.latlng[1])
    except Exception as exc:  # noqa: BLE001 - geolocation is best effort
        log.warning("Geolocation failed (%s); using fallback", exc)
    return SETTINGS.default_lat, SETTINGS.default_lon


def speak(text: str) -> None:
    """Text-to-speech in a background thread so the GUI never freezes."""

    def _run() -> None:
        if not shutil.which("mpg123"):
            log.warning("mpg123 not installed - voice output skipped")
            return
        from gtts import gTTS

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            gTTS(text, lang="en", tld="co.in").save(path)
            subprocess.run(["mpg123", "-q", path], check=False)  # no shell -> no injection
        except Exception as exc:  # noqa: BLE001
            log.warning("TTS failed: %s", exc)
        finally:
            Path(path).unlink(missing_ok=True)

    threading.Thread(target=_run, daemon=True).start()


def open_map(client: OWMClient, lat: float, lon: float) -> None:
    import folium

    fmap = folium.Map(location=[lat, lon], zoom_start=7, tiles="cartodbpositron")
    for layer, name in (("temp_new", "Temperature"), ("clouds_new", "Clouds")):
        folium.TileLayer(tiles=client.tile_url(layer), attr="OpenWeatherMap", name=name, overlay=True).add_to(fmap)
    folium.Marker([lat, lon], tooltip="You are here").add_to(fmap)
    folium.LayerControl().add_to(fmap)
    path = Path(tempfile.gettempdir()) / "homeauto_weather_map.html"
    fmap.save(str(path))
    webbrowser.open(path.as_uri())


class WeatherDashboard:
    def __init__(self, root: tk.Tk, voice: bool, show_map: bool) -> None:
        self.root, self.voice, self.show_map = root, voice, show_map
        self.client = OWMClient()
        root.title("Weather Dashboard")
        root.geometry("600x720")
        ttk.Style(root).theme_use("clam")

        self.city = ttk.Label(root, text="Detecting location...", font=("Helvetica", 18))
        self.city.pack(pady=10)
        self.details = ttk.Label(root, text="", font=("Helvetica", 14), justify=tk.CENTER)
        self.details.pack()
        ttk.Separator(root).pack(fill=tk.X, pady=10)
        self.aqi = ttk.Label(root, text="AQI: loading...", font=("Helvetica", 14, "bold"))
        self.aqi.pack()
        self.components = ttk.Label(root, text="", font=("Courier", 10))
        self.components.pack()
        ttk.Separator(root).pack(fill=tk.X, pady=10)
        self.graph = ttk.Frame(root)
        self.graph.pack(pady=10)
        ttk.Button(root, text="Refresh", command=self.update).pack(pady=5)

        self.update()

    def update(self) -> None:
        lat, lon = detect_location()
        try:
            weather = self.client.current(lat, lon)
            forecast = self.client.forecast(lat, lon)
            aqi, components = self.client.air_quality(lat, lon)
        except WeatherError as exc:
            self.city.config(text=str(exc))
            return

        name, main = weather.get("name", "your location"), weather["main"]
        self.city.config(text=f"Weather in {name}")
        self.details.config(
            text=(
                f"Temperature: {main['temp']:.1f} °C\n"
                f"Description: {weather['weather'][0]['description'].title()}\n"
                f"Humidity: {main['humidity']}%\n"
                f"Wind Speed: {weather['wind']['speed']} m/s"
            )
        )
        if aqi:
            self.aqi.config(text=f"AQI Index: {aqi} - {AQI_LABELS.get(aqi, '?')} (1=Good, 5=Very Poor)")
            self.components.config(text="\n".join(f"{k.upper():>6}: {v:8.2f} µg/m³" for k, v in components.items()))
        self.plot(forecast)

        if self.voice:
            speak(f"The current temperature in {name} is {round(main['temp'])} degrees Celsius.")
        if self.show_map:
            open_map(self.client, lat, lon)
            self.show_map = False  # open the browser map only once

    def plot(self, forecast: dict) -> None:
        entries = forecast["list"][:8]  # next 24 h in 3 h steps
        times = [datetime.fromtimestamp(e["dt"]).strftime("%H:%M") for e in entries]
        temps = [e["main"]["temp"] for e in entries]
        hums = [e["main"]["humidity"] for e in entries]

        fig = Figure(figsize=(5, 2.6), dpi=100)
        ax1 = fig.add_subplot()
        ax1.plot(times, temps, marker="o", color="tab:orange")
        ax1.set_ylabel("Temperature (°C)", color="tab:orange")
        ax1.tick_params(axis="x", rotation=45)
        ax2 = ax1.twinx()
        ax2.plot(times, hums, marker="x", color="tab:blue")
        ax2.set_ylabel("Humidity (%)", color="tab:blue")
        ax1.set_title("Next 24H Forecast")
        fig.tight_layout()

        for child in self.graph.winfo_children():
            child.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.graph)
        canvas.draw()
        canvas.get_tk_widget().pack()


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi weather & AQI dashboard")
    parser.add_argument("--no-voice", action="store_true", help="disable spoken temperature")
    parser.add_argument("--no-map", action="store_true", help="do not open the Folium map")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    root = tk.Tk()
    WeatherDashboard(root, voice=not args.no_voice, show_map=not args.no_map)
    root.mainloop()


if __name__ == "__main__":
    main()
