"""City-search weather GUI with 5-day forecast, condition icon and light/dark theme.

The city field is pre-filled from IP geolocation (ip-api.com) and falls back to
Delhi. The 5-day view samples the 3-hourly forecast once per day (every 8th
entry) and plots temperature vs humidity.

Run:  python -m homeauto.weather.city_forecast
"""

from __future__ import annotations

import logging
import tkinter as tk
from io import BytesIO
from tkinter import messagebox

import requests
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk

from .owm_client import OWMClient, WeatherError

log = logging.getLogger(__name__)

THEMES = {
    "light": {"bg": "#f0f0f0", "fg": "#000000", "entry": "#ffffff"},
    "dark": {"bg": "#2c2f33", "fg": "#ffffff", "entry": "#40444b"},
}


def detect_city(default: str = "Delhi") -> str:
    try:
        # ip-api's free tier is HTTP-only; only a public city name is read back
        return requests.get("http://ip-api.com/json/", timeout=5).json().get("city") or default
    except requests.RequestException:
        return default


class CityForecastApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.client = OWMClient()
        self.theme = "light"
        root.title("Weather Dashboard")
        root.geometry("500x760")
        root.resizable(False, False)

        tk.Label(root, text="Enter City", font=("Helvetica", 14)).pack(pady=10)
        self.city_entry = tk.Entry(root, font=("Helvetica", 16), width=30)
        self.city_entry.insert(0, detect_city())
        self.city_entry.pack(pady=5)
        self.city_entry.bind("<Return>", lambda _e: self.show_weather())
        tk.Button(root, text="Get Weather", font=("Helvetica", 12), command=self.show_weather).pack(pady=10)
        tk.Button(root, text="Toggle Theme", font=("Helvetica", 12), command=self.toggle_theme).pack()
        self.icon = tk.Label(root)
        self.icon.pack()
        self.result = tk.Label(root, font=("Helvetica", 12), justify=tk.LEFT, wraplength=450)
        self.result.pack(pady=10)
        tk.Label(root, text="5-Day Forecast", font=("Helvetica", 13, "bold")).pack(pady=5)
        self.forecast = tk.Label(root, font=("Helvetica", 11), justify=tk.LEFT, wraplength=450)
        self.forecast.pack(pady=5)
        self.graph = tk.Frame(root)
        self.graph.pack(pady=10)
        self.apply_theme()

    def show_weather(self) -> None:
        city = self.city_entry.get().strip()
        if not city:
            messagebox.showwarning("Input Error", "Please enter a city name.")
            return
        try:
            current = self.client.current_by_city(city)
            forecast = self.client.forecast_by_city(city)
        except WeatherError:
            self.result.config(text="City not found or service unavailable.")
            self.forecast.config(text="")
            return

        self._set_icon(current["weather"][0]["icon"])
        self.result.config(
            text=(
                f"{current.get('name', city.title())}\n"
                f"{current['weather'][0]['description'].title()}\n"
                f"Temp: {current['main']['temp']} °C\n"
                f"Humidity: {current['main']['humidity']}%\n"
                f"Wind: {current['wind']['speed']} m/s"
            )
        )
        days = forecast["list"][::8][:5]
        self.forecast.config(
            text="\n".join(
                f"{d['dt_txt'].split()[0]}: {d['main']['temp']} °C | {d['weather'][0]['description'].title()}"
                for d in days
            )
        )
        self.plot(
            [d["dt_txt"].split()[0][5:] for d in days],
            [d["main"]["temp"] for d in days],
            [d["main"]["humidity"] for d in days],
        )

    def _set_icon(self, code: str) -> None:
        try:
            data = requests.get(f"https://openweathermap.org/img/wn/{code}@2x.png", timeout=5).content
            photo = ImageTk.PhotoImage(Image.open(BytesIO(data)).resize((80, 80)))
            self.icon.config(image=photo)
            self.icon.image = photo  # keep a reference
        except (requests.RequestException, OSError):
            log.warning("Could not load weather icon %s", code)

    def plot(self, labels: list[str], temps: list[float], hums: list[float]) -> None:
        for child in self.graph.winfo_children():
            child.destroy()
        fig = Figure(figsize=(4.5, 2.5), dpi=100)
        ax1 = fig.add_subplot()
        ax1.plot(labels, temps, marker="o", color="tab:orange", label="Temp (°C)")
        ax1.set_ylabel("Temp (°C)")
        ax1.grid(True)
        ax2 = ax1.twinx()
        ax2.plot(labels, hums, marker="s", color="tab:blue", label="Humidity (%)")
        ax2.set_ylabel("Humidity (%)")
        fig.legend(loc="upper center", ncols=2, fontsize=8)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.graph)
        canvas.draw()
        canvas.get_tk_widget().pack()

    def toggle_theme(self) -> None:
        self.theme = "dark" if self.theme == "light" else "light"
        self.apply_theme()

    def apply_theme(self) -> None:
        colors = THEMES[self.theme]
        self.root.configure(bg=colors["bg"])
        for widget in self.root.winfo_children():
            if isinstance(widget, (tk.Label, tk.Button, tk.Frame)):
                widget.configure(bg=colors["bg"])
            if isinstance(widget, (tk.Label, tk.Button)):
                widget.configure(fg=colors["fg"])
            if isinstance(widget, tk.Entry):
                widget.configure(bg=colors["entry"], fg=colors["fg"], insertbackground=colors["fg"])


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    root = tk.Tk()
    try:
        CityForecastApp(root)
    except WeatherError as exc:
        messagebox.showerror("Configuration error", str(exc))
        return
    root.mainloop()


if __name__ == "__main__":
    main()
