"""Intent handlers for the Alarm and Reminders application workflow."""
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, config_validation as cv

from .const import DOMAIN
from .alarm_manager import (
    async_create_alarm, 
    async_delete_alarm, 
    async_delete_all_alarms, 
    async_get_all_alarms
)

_LOGGER = logging.getLogger(__name__)

INTENT_CREATE = "CreateAlarmIntent"
INTENT_CANCEL = "CancelAlarmIntent"
INTENT_DELETE = "DeleteAlarmIntent"
INTENT_LIST = "ListAlarmsIntent"
INTENT_DELETE_ALL = "DeleteAllAlarmsIntent"

def async_setup_intents(hass: HomeAssistant) -> None:
    """Register custom slots intent scripts."""
    _LOGGER.info("Registering Voice Alarm Intents...")
    intent.async_register(hass, CreateAlarmHandler())
    intent.async_register(hass, CancelAlarmHandler())
    intent.async_register(hass, DeleteAlarmHandler())
    intent.async_register(hass, ListAlarmsHandler())
    intent.async_register(hass, DeleteAllAlarmsHandler())

class CreateAlarmHandler(intent.IntentHandler):
    def __init__(self):
        self.intent_type = INTENT_CREATE

    @property
    def slot_schema(self) -> vol.Schema:
        return vol.Schema({
            vol.Required("time"): cv.string,
            vol.Optional("reoccurring"): cv.string,
            vol.Optional("day"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("alarm_name"): cv.string,
            vol.Optional("custom_alarm_name"): cv.string,
        }, extra=vol.ALLOW_EXTRA)

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        slots = user_intent.slots
        raw_time_str = str(slots.get("time", {}).get("value", "")).lower().strip()
        for word in ["every", "at", "for", "on"]:
            raw_time_str = raw_time_str.replace(word, "").strip()
        
        reoccurring = slots.get("reoccurring", {}).get("value", "once").lower().strip()
        day = slots.get("day", {}).get("value")
        
        # --- CORRECTED LOGIC ---
        # If no day was explicitly captured, check if reoccurring contains a day
        days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if not day:
            for d in days_of_week:
                if d in reoccurring:
                    day = d
                    break
        # -----------------------

        raw_name = slots.get("alarm_name", {}).get("value") or slots.get("name", {}).get("value") or slots.get("custom_alarm_name", {}).get("value")

        success, message = await async_create_alarm(
            user_intent.hass, 
            raw_time_str, 
            reoccurring, 
            raw_name, 
            user_intent.device_id or "",
            target_day=day
        )
        response = user_intent.create_response()
        response.async_set_speech(message)
        return response

class CancelAlarmHandler(intent.IntentHandler):
    def __init__(self):
        self.intent_type = INTENT_CANCEL

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        from .helpers import async_cancel_alarm_logic
        await async_cancel_alarm_logic(user_intent.hass)
        response = user_intent.create_response()
        response.async_set_speech("Alarm canceled.")
        return response

class DeleteAlarmHandler(intent.IntentHandler):
    def __init__(self):
        self.intent_type = INTENT_DELETE

    @property
    def slot_schema(self) -> vol.Schema:
        return vol.Schema({
            vol.Optional("alarm_name"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("time"): cv.string,
        }, extra=vol.ALLOW_EXTRA)

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        slots = user_intent.slots
        name_input = slots.get("alarm_name", {}).get("value") or slots.get("name", {}).get("value")
        time_input = slots.get("time", {}).get("value")

        if await async_delete_alarm(user_intent.hass, name=name_input, time=time_input):
            response = user_intent.create_response()
            response.async_set_speech("Deleted.")
            return response
        
        response = user_intent.create_response()
        response.async_set_speech("I couldn't find an alarm with that name or time.")
        return response

class ListAlarmsHandler(intent.IntentHandler):
    def __init__(self):
        self.intent_type = INTENT_LIST

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        hass = user_intent.hass
        db = hass.data[DOMAIN].get("alarms", {})
        active_alarms = [a for a in db.values() if a.get("enabled", True)]
        response = user_intent.create_response()

        if not active_alarms:
            response.async_set_speech("You have no active alarms scheduled.")
            return response

        summaries = []
        for a in active_alarms:
            name = a.get("name")
            time = a.get("time")
            day = a.get("target_day") 
            repeat = a.get("reoccurring", "once").lower().strip()
            
            if repeat == "once":
                # For one-time alarms: "Alarm at 12:10 on sunday"
                display_day = f" on {day}" if day else ""
                summary = f"Alarm {name} at {time}{display_day}"
            else:
                # For recurring alarms: Clean up "every every" and ensure "every " prefix
                clean_repeat = repeat.replace("every every", "every")
                if not clean_repeat.startswith("every "):
                    clean_repeat = f"every {clean_repeat}"
                
                # Format: "Alarm at 16:00 every sunday"
                summary = f"Alarm {name} at {time} {clean_repeat}"
            
            summaries.append(summary)

        response.async_set_speech(". ".join(summaries) + ".")
        return response

class DeleteAllAlarmsHandler(intent.IntentHandler):
    def __init__(self):
        self.intent_type = INTENT_DELETE_ALL

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        await async_delete_all_alarms(user_intent.hass)
        response = user_intent.create_response()
        response.async_set_speech("All alarms deleted.")
        return response