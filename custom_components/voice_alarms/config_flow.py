"""Config flow for Voice Alarms."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

class VoiceAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Voice Alarms."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        
        # 1. Check if already configured to prevent duplicates
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        
        # 2. If user_input is present, the user clicked "Submit"
        if user_input is not None:
            return self.async_create_entry(title="Voice Alarm", data=user_input)

        # 3. Otherwise, show the form with an empty schema
        return self.async_show_form(
            step_id="user", 
            data_schema=vol.Schema({})
        )