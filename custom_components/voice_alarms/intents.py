"""Intent handlers for the Alarm and Reminders application workflow."""
import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, config_validation as cv

from .const import DOMAIN
from .alarm_manager import async_create_alarm, async_delete_alarm

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
            vol.Optional("name"): cv.string,
            vol.Optional("alarm_name"): cv.string,
            vol.Optional("custom_alarm_name"): cv.string,
        }, extra=vol.ALLOW_EXTRA)

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        """Handle the create alarm intent."""
        slots = user_intent.slots
        
        # Parse inputs
        raw_time_str = str(slots.get("time", {}).get("value", "")).lower().strip()
        for word in ["every", "at", "for"]:
            raw_time_str = raw_time_str.replace(word, "").strip()
        
        reoccurring = slots.get("reoccurring", {}).get("value", "once").lower().strip()
        raw_name = slots.get("alarm_name", {}).get("value") or slots.get("name", {}).get("value") or slots.get("custom_alarm_name", {}).get("value")

        # Delegate logic to manager
        success, message = await async_create_alarm(
            user_intent.hass, 
            raw_time_str, 
            reoccurring, 
            raw_name, 
            user_intent.device_id or ""
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

        summaries = [f"Alarm {a.get('name')} at {a.get('time')}{f' ({a.get('reoccurring')})' if a.get('reoccurring') != 'once' else ''}" for a in active_alarms]
        response.async_set_speech(". ".join(summaries) + ".")
        return response

class DeleteAllAlarmsHandler(intent.IntentHandler):
    def __init__(self):
        self.intent_type = INTENT_DELETE_ALL

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        hass = user_intent.hass
        db = hass.data[DOMAIN]["alarms"]
        switches = hass.data[DOMAIN]["switches"]
        
        for idx in list(switches.keys()):
            await switches[idx].async_remove()
        
        switches.clear()
        db.clear()
        
        from . import save_alarms_to_disk
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        
        if list_sensor := hass.data[DOMAIN].get("list_sensor"):
            await list_sensor.async_update_ha_state()
            
        response = user_intent.create_response()
        response.async_set_speech("All alarms deleted.")
        return response