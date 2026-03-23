from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_ENTITY_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.trigger import async_validate_trigger_config as _base_validate_trigger
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import event

from .const import DOMAIN

TRIGGER_TYPES = {"period_changed"}
CONDITION_TYPES = {"is_morning", "is_afternoon", "is_night"}


def _get_entity_id_for_device(hass: HomeAssistant, device_id: str) -> str | None:
    ent_reg = er.async_get(hass)
    for reg_entry in ent_reg.entities.values():
        if reg_entry.device_id == device_id and reg_entry.domain == "sensor" and reg_entry.platform == DOMAIN:
            return reg_entry.entity_id
    return None


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    entity_id = _get_entity_id_for_device(hass, device_id)
    if not entity_id:
        return []
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entity_id,
            CONF_TYPE: "period_changed",
        }
    ]


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    entity_id = _get_entity_id_for_device(hass, device_id)
    if not entity_id:
        return []
    return [
        {CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN, CONF_ENTITY_ID: entity_id, CONF_TYPE: "is_morning"},
        {CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN, CONF_ENTITY_ID: entity_id, CONF_TYPE: "is_afternoon"},
        {CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN, CONF_ENTITY_ID: entity_id, CONF_TYPE: "is_night"},
    ]


async def async_validate_trigger_config(hass: HomeAssistant, config: dict) -> dict:
    config = dict(config)
    if config.get(CONF_TYPE) not in TRIGGER_TYPES:
        raise vol.Invalid("Invalid trigger type")
    config = await _base_validate_trigger(hass, config)
    cv.entity_id(config[CONF_ENTITY_ID])
    return config


async def async_attach_trigger(hass: HomeAssistant, config: dict, action, trigger_info):
    entity_id = config[CONF_ENTITY_ID]

    async def _handle(event_obj):
        await action(trigger_info, event_obj)

    return event.async_track_state_change_event(hass, [entity_id], _handle)


async def async_validate_condition_config(hass: HomeAssistant, config: dict) -> dict:
    config = dict(config)
    if config.get(CONF_TYPE) not in CONDITION_TYPES:
        raise vol.Invalid("Invalid condition type")
    cv.entity_id(config[CONF_ENTITY_ID])
    return config


async def async_condition_from_config(hass: HomeAssistant, config: dict):
    entity_id = config[CONF_ENTITY_ID]
    cond_type = config[CONF_TYPE]

    expected = {
        "is_morning": "morning",
        "is_afternoon": "afternoon",
        "is_night": "night",
    }[cond_type]

    async def _cond(hass: HomeAssistant, variables: dict) -> bool:
        state = hass.states.get(entity_id)
        return state is not None and state.state == expected

    return _cond
