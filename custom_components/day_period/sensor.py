from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import json
from pathlib import Path

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_MORNING_START,
    CONF_AFTERNOON_START,
    CONF_NIGHT_START,
    DEFAULT_MORNING_START,
    DEFAULT_AFTERNOON_START,
    DEFAULT_NIGHT_START,
    SENSOR_OBJECT_ID,
)


@dataclass(frozen=True, kw_only=True)
class DayPeriodSensorDescription(SensorEntityDescription):
    pass


def _parse_time(value: str, default: str) -> time:
    t = dt_util.parse_time(value)
    if t is None:
        t = dt_util.parse_time(default)
    return t if t is not None else time(0, 0, 0)


def _get_boundaries(options: dict) -> tuple[time, time, time]:
    m = _parse_time(options.get(CONF_MORNING_START, DEFAULT_MORNING_START), DEFAULT_MORNING_START)
    a = _parse_time(options.get(CONF_AFTERNOON_START, DEFAULT_AFTERNOON_START), DEFAULT_AFTERNOON_START)
    n = _parse_time(options.get(CONF_NIGHT_START, DEFAULT_NIGHT_START), DEFAULT_NIGHT_START)
    return m, a, n


def _period_for(now_local: datetime, m: time, a: time, n: time) -> tuple[str, datetime]:
    """Return (period, next_change_local_dt). Assumes m < a < n."""
    today = now_local.date()

    dt_m = dt_util.as_local(datetime.combine(today, m))
    dt_a = dt_util.as_local(datetime.combine(today, a))
    dt_n = dt_util.as_local(datetime.combine(today, n))

    if now_local < dt_m:
        return "night", dt_m
    if now_local < dt_a:
        return "morning", dt_a
    if now_local < dt_n:
        return "afternoon", dt_n

    dt_m_tomorrow = dt_util.as_local(datetime.combine(today + timedelta(days=1), m))
    return "night", dt_m_tomorrow


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    description = DayPeriodSensorDescription(
        key="day_period",
        name="Day period",
    )
    async_add_entities([DayPeriodSensor(hass, entry, description)], update_before_add=True)


class DayPeriodSensor(SensorEntity):
    _attr_icon = "mdi:weather-sunset"
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, description: DayPeriodSensorDescription) -> None:
        self.hass = hass
        self.entry = entry
        self.entity_description = description

        self._attr_unique_id = entry.entry_id
        self._attr_suggested_object_id = SENSOR_OBJECT_ID

        # Device page in UI (Automations/Scenes/Scripts cards)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Day Period",
            "manufacturer": "Custom",
            "model": "Day Period Metric",
        }

        self._period: str | None = None
        self._next_change: datetime | None = None
        self._unsub_timer = None
        self._usage: list[str] = []

    @property
    def native_value(self) -> str | None:
        return self._period

    @property
    def extra_state_attributes(self) -> dict:
        m, a, n = _get_boundaries(self.entry.options)
        return {
            "boundaries": {
                "morning_start": m.isoformat(),
                "afternoon_start": a.isoformat(),
                "night_start": n.isoformat(),
            },
            "next_change": self._next_change.isoformat() if self._next_change else None,
            "used_by_automations": self._usage,  # best-effort
        }

    async def async_added_to_hass(self) -> None:
        self.hass.async_create_task(self._async_refresh_usage())

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def async_update(self) -> None:
        await self._async_recompute_and_schedule()

    async def _async_recompute_and_schedule(self) -> None:
        now = dt_util.now()
        m, a, n = _get_boundaries(self.entry.options)

        period, next_change = _period_for(now, m, a, n)
        self._period = period
        self._next_change = next_change

        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

        @callback
        def _scheduled(_now) -> None:
            self.hass.async_create_task(self._async_recompute_and_schedule())
            self.async_write_ha_state()

        self._unsub_timer = async_track_point_in_time(self.hass, _scheduled, next_change)

    async def _async_refresh_usage(self) -> None:
        entity_id = self.entity_id or f"sensor.{SENSOR_OBJECT_ID}"

        def _scan() -> list[str]:
            hass_config_dir = Path(self.hass.config.path())
            storage_dir = hass_config_dir / ".storage"
            results: list[str] = []

            def scan_file(p: Path, kind: str) -> None:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    return
                if entity_id not in text:
                    return

                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and isinstance(data.get("data"), list):
                        for it in data["data"]:
                            if isinstance(it, dict):
                                alias = it.get("alias") or it.get("name") or it.get("id")
                                results.append(f"{kind}: {alias}" if alias else f"{kind}: (unknown)")
                        return
                except Exception:
                    pass

                results.append(f"{kind}: {p.name}")

            if storage_dir.exists():
                scan_file(storage_dir / "automations", "automation")
                scan_file(storage_dir / "scripts", "script")

            for yaml_name, kind in (("automations.yaml", "automation"), ("scripts.yaml", "script")):
                p = hass_config_dir / yaml_name
                if p.exists():
                    scan_file(p, kind)

            # Deduplicate
            dedup: list[str] = []
            seen: set[str] = set()
            for r in results:
                if r not in seen:
                    seen.add(r)
                    dedup.append(r)
            return dedup

        self._usage = await self.hass.async_add_executor_job(_scan)
        self.async_write_ha_state()
