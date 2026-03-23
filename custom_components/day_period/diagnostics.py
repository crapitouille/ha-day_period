from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_MORNING_START,
    CONF_AFTERNOON_START,
    CONF_EVENING_START,
    CONF_NIGHT_START,
    DEFAULT_MORNING_START,
    DEFAULT_AFTERNOON_START,
    DEFAULT_EVENING_START,
    DEFAULT_NIGHT_START,
)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    state = hass.states.get("sensor.day_period")
    return {
        "options": {
            CONF_MORNING_START: entry.options.get(CONF_MORNING_START, DEFAULT_MORNING_START),
            CONF_AFTERNOON_START: entry.options.get(CONF_AFTERNOON_START, DEFAULT_AFTERNOON_START),
            CONF_EVENING_START: entry.options.get(CONF_EVENING_START, DEFAULT_EVENING_START),
            CONF_NIGHT_START: entry.options.get(CONF_NIGHT_START, DEFAULT_NIGHT_START),
        },
        "sensor_state": state.state if state else None,
        "sensor_attributes": dict(state.attributes) if state else None,
    }
