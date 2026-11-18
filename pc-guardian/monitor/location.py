"""
PC Guardian — Location Tracker
Multi-method location detection:
1. GPS (if available via Windows Location API)
2. WiFi-based geolocation (most accurate without GPS)
3. IP-based geolocation (always works, less precise)
Sends location + Google Maps link to Telegram on command or automatically.
"""

import os
import json
import time
import logging
import threading
import urllib.request
import urllib.parse

logger = logging.getLogger("location")

ALERT_COOLDOWN = 300  # 5 min between auto location alerts


class LocationTracker:
    def __init__(self, cfg):
        self.cfg         = cfg
        self._last_loc   = None
        self._last_alert = 0
        self._tracking   = False

    # ── PUBLIC ────────────────────────────────────────────────────────────────

    def get_location(self) -> dict:
        """
        Try all methods, return best result.
        Returns: {lat, lon, accuracy, method, address, maps_url}
        """
        # Try GPS first (Windows Location API)
        loc = self._try_windows_gps()
        if loc:
            loc["method"] = "GPS"
            return self._enrich(loc)

        # Try WiFi geolocation
        loc = self._try_wifi_geolocation()
        if loc:
            loc["method"] = "WiFi"
            return self._enrich(loc)

        # Always works — IP based
        loc = self._try_ip_geolocation()
        if loc:
            loc["method"] = "IP"
            return self._enrich(loc)

        return None

    def format_message(self, loc: dict) -> str:
        if not loc:
            return "❌ Location unavailable."
        return (
            f"📍 *Location ({loc.get('method', '?')})*\n"
            f"Address: {loc.get('address', 'Unknown')}\n"
            f"Coordinates: `{loc.get('lat', '?')}, {loc.get('lon', '?')}`\n"
            f"Accuracy: ~{loc.get('accuracy', '?')}m\n"
            f"[Open in Google Maps]({loc.get('maps_url', '')})"
        )

    def start_auto_track(self, interval_minutes: int = 30, alert_fn=None):
        """Auto-send location every N minutes."""
        self._tracking = True

        def _run():
            while self._tracking:
                loc = self.get_location()
                if loc and alert_fn:
                    alert_fn(self.format_message(loc))
                time.sleep(interval_minutes * 60)

        threading.Thread(target=_run, daemon=True, name="LocationTracker").start()
        logger.info(f"Auto location tracking every {interval_minutes} min.")

    def stop_auto_track(self):
        self._tracking = False

    # ── METHODS ───────────────────────────────────────────────────────────────

    def _try_windows_gps(self) -> dict:
        """Use Windows Location API via COM."""
        try:
            import winrt.windows.devices.geolocation as geo
            import asyncio

            async def _get():
                locator = geo.Geolocator()
                locator.desired_accuracy = geo.PositionAccuracy.HIGH
                pos = await locator.get_geoposition_async()
                coord = pos.coordinate
                return {
                    "lat": coord.latitude,
                    "lon": coord.longitude,
                    "accuracy": coord.accuracy,
                }

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_get())
            loop.close()
            return result
        except Exception:
            return None

    def _try_wifi_geolocation(self) -> dict:
        """
        Scan nearby WiFi networks → Google Geolocation API.
        Very accurate (~10-50m) without GPS.
        """
        try:
            import subprocess
            # Get WiFi scan results
            result = subprocess.run(
                "netsh wlan show networks mode=Bssid",
                shell=True, capture_output=True, text=True, timeout=10
            )
            output = result.stdout

            # Parse BSSIDs and signal strengths
            waps = []
            lines = output.split("\n")
            current_bssid = None
            current_signal = None

            for line in lines:
                line = line.strip()
                if "BSSID" in line and ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        bssid = parts[1].strip()
                        if len(bssid) == 17:  # valid MAC
                            current_bssid = bssid
                elif "Signal" in line and current_bssid:
                    try:
                        signal = int(line.split(":")[1].strip().replace("%", ""))
                        # Convert % to dBm approximately
                        dbm = (signal / 2) - 100
                        waps.append({
                            "macAddress": current_bssid,
                            "signalStrength": int(dbm)
                        })
                        current_bssid = None
                    except Exception:
                        pass

            if not waps:
                return None

            # Use Google Geolocation API (free tier — no key needed for basic)
            payload = json.dumps({
                "wifiAccessPoints": waps[:20]
            }).encode()

            req = urllib.request.Request(
                "https://www.googleapis.com/geolocation/v1/geolocate?key=AIzaSyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return {
                    "lat": data["location"]["lat"],
                    "lon": data["location"]["lng"],
                    "accuracy": data.get("accuracy", 50),
                }
        except Exception as e:
            logger.debug(f"WiFi geolocation failed: {e}")
            return None

    def _try_ip_geolocation(self) -> dict:
        """IP-based geolocation — always works, city-level accuracy."""
        try:
            with urllib.request.urlopen("https://ipapi.co/json/", timeout=8) as resp:
                data = json.loads(resp.read())
                return {
                    "lat":      data.get("latitude"),
                    "lon":      data.get("longitude"),
                    "accuracy": 5000,  # city level ~5km
                    "city":     data.get("city"),
                    "region":   data.get("region"),
                    "country":  data.get("country_name"),
                    "ip":       data.get("ip"),
                }
        except Exception:
            try:
                with urllib.request.urlopen("http://ip-api.com/json/", timeout=8) as resp:
                    data = json.loads(resp.read())
                    if data.get("status") == "success":
                        return {
                            "lat":      data.get("lat"),
                            "lon":      data.get("lon"),
                            "accuracy": 5000,
                            "city":     data.get("city"),
                            "region":   data.get("regionName"),
                            "country":  data.get("country"),
                            "ip":       data.get("query"),
                        }
            except Exception:
                pass
        return None

    def _enrich(self, loc: dict) -> dict:
        """Add Google Maps URL and reverse geocode address."""
        lat = loc.get("lat")
        lon = loc.get("lon")
        if not lat or not lon:
            return loc

        loc["maps_url"] = f"https://www.google.com/maps?q={lat},{lon}"

        # Reverse geocode for address
        if not loc.get("address"):
            try:
                url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
                req = urllib.request.Request(url, headers={"User-Agent": "PCGuardian/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read())
                    loc["address"] = data.get("display_name", f"{lat}, {lon}")
            except Exception:
                city    = loc.get("city", "")
                region  = loc.get("region", "")
                country = loc.get("country", "")
                loc["address"] = ", ".join(filter(None, [city, region, country])) or f"{lat}, {lon}"

        self._last_loc = loc
        return loc
