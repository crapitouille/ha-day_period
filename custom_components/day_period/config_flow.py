from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_MORNING_START,
    CONF_AFTERNOON_START,
    CONF_NIGHT_START,
    DEFAULT_MORNING_START,
    DEFAULT_AFTERNOON_START,
    DEFAULT_NIGHT_START,
)


def _schema(values: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_MORNING_START,
                default=values.get(CONF_MORNING_START, DEFAULT_MORNING_START),
            ): selector({"time": {}}),
            vol.Required(
                CONF_AFTERNOON_START,
                default=values.get(CONF_AFTERNOON_START, DEFAULT_AFTERNOON_START),
            ): selector({"time": {}}),
            vol.Required(
                CONF_NIGHT_START,
                default=values.get(CONF_NIGHT_START, DEFAULT_NIGHT_START),
            ): selector({"time": {}}),
        }
    )


def _validate_periods(m: str, a: str, n: str) -> None:
    if len({m, a, n}) < 3:
        raise vol.Invalid("Les heures doivent être distinctes.")
    if not (m < a < n):
        raise vol.Invalid("Les heures doivent être dans l'ordre: matin < après-midi < nuit.")


class DayPeriodConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            try:
                _validate_periods(
                    user_input[CONF_MORNING_START],
                    user_input[CONF_AFTERNOON_START],
                    user_input[CONF_NIGHT_START],
                )
            except vol.Invalid as err:
                errors["base"] = str(err) or "Configuration invalide."
            except Exception:
                errors["base"] = "Erreur inattendue. Consultez les logs Home Assistant."

            if not errors:
                return self.async_create_entry(
                    title="Day Period",
                    data={},
                    options=user_input,
                )

        defaults = {
            CONF_MORNING_START: DEFAULT_MORNING_START,
            CONF_AFTERNOON_START: DEFAULT_AFTERNOON_START,
            CONF_NIGHT_START: DEFAULT_NIGHT_START,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults if user_input is None else user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DayPeriodOptionsFlowHandler()


class DayPeriodOptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _validate_periods(
                    user_input[CONF_MORNING_START],
                    user_input[CONF_AFTERNOON_START],
                    user_input[CONF_NIGHT_START],
                )
            except vol.Invalid as err:
                errors["base"] = str(err) or "Configuration invalide."
            except Exception:
                errors["base"] = "Erreur inattendue. Consultez les logs Home Assistant."

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={
                        CONF_MORNING_START: user_input[CONF_MORNING_START],
                        CONF_AFTERNOON_START: user_input[CONF_AFTERNOON_START],
                        CONF_NIGHT_START: user_input[CONF_NIGHT_START],
                    },
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        current = dict(self.config_entry.options) if self.config_entry else {}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current),
            errors=errors,
        )
