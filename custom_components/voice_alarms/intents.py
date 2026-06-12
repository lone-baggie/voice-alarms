"""Intent handlers for the Alarm and Reminders application workflow."""
import logging
import voluptuous as vol # pyright: ignore[reportMissingImports]   

from homeassistant.core import HomeAssistant # pyright: ignore[reportMissingImports]
from homeassistant.helpers import intent, config_validation as cv # pyright: ignore[reportMissingImports]
from .helpers import async_cancel_alarm_logic
from .const import DOMAIN
from .switch import async_register_new_switch

_LOGGER = logging.getLogger(__name__)

INTENT_CREATE = "CreateAlarmIntent"
INTENT_CANCEL = "CancelAlarmIntent"
INTENT_DELETE = "DeleteAlarmIntent"
INTENT_LIST = "ListAlarmsIntent"
INTENT_DELETE_ALL = "DeleteAllAlarmsIntent"

# Priority mapping for alarm upgrades
PRIORITY = {
    "once": 1, 
    "monday": 2, "tuesday": 2, "wednesday": 2, "thursday": 2, 
    "friday": 2, "saturday": 2, "sunday": 2,
    "weekday": 3,
    "everyday": 4, "every day": 4, "daily": 4
}

def async_setup_intents(hass: HomeAssistant) -> None:
    """Register custom slots intent scripts."""
    _LOGGER.info("Registering Voice Alarm Intents...")
    
    intent.async_register(hass, CreateAlarmHandler())
    intent.async_register(hass, CancelAlarmHandler())
    intent.async_register(hass, DeleteAlarmHandler())
    intent.async_register(hass, ListAlarmsHandler())
    intent.async_register(hass, DeleteAllAlarmsHandler())
    
    _LOGGER.info("Voice Alarm Intents Registered Successfully.")


"""Intent handlers for the Alarm and Reminders application workflow."""
import logging
import voluptuous as vol
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, config_validation as cv
from .helpers import async_cancel_alarm_logic
from .const import DOMAIN
from .switch import async_register_new_switch

_LOGGER = logging.getLogger(__name__)

INTENT_CREATE = "CreateAlarmIntent"
INTENT_CANCEL = "CancelAlarmIntent"
INTENT_DELETE = "DeleteAlarmIntent"
INTENT_LIST = "ListAlarmsIntent"
INTENT_DELETE_ALL = "DeleteAllAlarmsIntent"

# Priority mapping for alarm upgrades
PRIORITY = {
    "once": 1, "monday": 2, "tuesday": 2, "wednesday": 2, "thursday": 2, 
    "friday": 2, "saturday": 2, "sunday": 2,
    "weekday": 3,
    "everyday": 4, "every day": 4, "daily": 4
}

def async_setup_intents(hass: HomeAssistant) -> None:
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
        hass = user_intent.hass
        slots = user_intent.slots
        db = hass.data[DOMAIN]["alarms"]
        calling_device = user_intent.device_id or ""

        # Parse Time
        raw_time_str = str(slots.get("time", {}).get("value", "")).lower().strip()
        for word in ["every", "at", "for"]:
            raw_time_str = raw_time_str.replace(word, "").strip()
        
        # Parse Name and Reoccurrence
        raw_name = slots.get("alarm_name", {}).get("value") or slots.get("name", {}).get("value") or slots.get("custom_alarm_name", {}).get("value")
        reoccurring = slots.get("reoccurring", {}).get("value", "once").lower().strip()
        parsed_time = None
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p", "%H"):
            try:
                parsed_time = datetime.strptime(raw_time_str, fmt).time()
                break
            except ValueError: continue

        if not parsed_time:
            response = user_intent.create_response()
            response.async_set_speech(f"Sorry, I couldn't understand the time format.")
            return response

        raw_time = parsed_time.strftime("%H:%M")
        
        # Logic: Check for Conflicts/Upgrades
        for idx, alarm in db.items():
            if raw_name and alarm.get("name", "").lower() == raw_name.lower():
                response = user_intent.create_response()
                response.async_set_speech(f"An alarm named {raw_name} already exists.")
                return response
            
            if alarm.get("time") == raw_time:
                existing_re = alarm.get("reoccurring", "once").lower()
                existing_score = PRIORITY.get(existing_re, 1)
                new_score = PRIORITY.get(reoccurring, 1)

                if new_score == existing_score:
                    response = user_intent.create_response()
                    response.async_set_speech(f"An alarm is already set for {raw_time} with the same schedule.")
                    return response
                elif new_score > existing_score:
                    alarm["reoccurring"] = reoccurring
                    alarm["persistent"] = True
                    if idx in hass.data[DOMAIN]["switches"]:
                        hass.data[DOMAIN]["switches"][idx].async_write_ha_state()
                    from . import save_alarms_to_disk
                    await hass.async_add_executor_job(save_alarms_to_disk, hass)
                    response = user_intent.create_response()
                    response.async_set_speech(f"Upgraded your {raw_time} alarm to {reoccurring}.")
                    return response
                else:
                    response = user_intent.create_response()
                    response.async_set_speech(f"A higher priority alarm already exists at {raw_time}.")
                    return response

        # Standard Creation
        allocated_idx = next((str(i) for i in range(1, 100) if str(i) not in db), None)
        if not allocated_idx:
            response = user_intent.create_response()
            response.async_set_speech("Maximum alarm limit reached.")
            return response

        db[allocated_idx] = {
            "name": raw_name or allocated_idx,
            "time": raw_time,
            "device_id": calling_device,
            "persistent": reoccurring != "once",
            "reoccurring": reoccurring,
            "ringing": False,
            "enabled": True
        }
        
        from . import save_alarms_to_disk
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        await async_register_new_switch(hass, allocated_idx)
        
        if list_sensor := hass.data[DOMAIN].get("list_sensor"):
            await list_sensor.async_update_ha_state()
        
        response = user_intent.create_response()
        response.async_set_speech(f"Alarm created for {raw_time} ({reoccurring}).")
        return response

class CancelAlarmHandler(intent.IntentHandler):
    def __init__(self):
        self.intent_type = "CancelAlarmIntent"

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        await async_cancel_alarm_logic(user_intent.hass)
        response = user_intent.create_response()
        response.async_set_speech("Alarm canceled.")
        return response

class DeleteAlarmHandler(intent.IntentHandler):
    """Handles deleting a specific alarm by name or time."""
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
        hass = user_intent.hass
        db = hass.data[DOMAIN].get("alarms", {})
        switches = hass.data[DOMAIN].get("switches", {})
        response = user_intent.create_response()
        slots = user_intent.slots

        name_input = slots.get("alarm_name", {}).get("value") or slots.get("name", {}).get("value")
        time_input = slots.get("time", {}).get("value")

        target_idx = None
        for idx, alarm in db.items():
            if name_input and str(alarm.get("name", "")).lower() == str(name_input).lower():
                target_idx = idx
                break
            if time_input and str(alarm.get("time", "")) == str(time_input):
                target_idx = idx
                break

        if not target_idx:
            response.async_set_speech("I couldn't find an alarm with that name or time.")
            return response

        if target_idx in switches:
            await switches[target_idx].async_remove()
            del switches[target_idx]

        del db[target_idx]
        
        from . import save_alarms_to_disk
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        
        list_sensor = hass.data[DOMAIN].get("list_sensor")
        if list_sensor:
            # FIXED: Use async_update_ha_state
            await list_sensor.async_update_ha_state()
        
        response.async_set_speech("Deleted")
        return response

class ListAlarmsHandler(intent.IntentHandler):
    """Handles listing scheduled alarms, excluding disabled ones and adding reoccurrence info."""
    def __init__(self):
        self.intent_type = INTENT_LIST

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        hass = user_intent.hass
        db = hass.data[DOMAIN].get("alarms", {})
        response = user_intent.create_response()

        # Filter only enabled alarms
        active_alarms = [a for a in db.values() if a.get("enabled", True)]

        if not active_alarms:
            response.async_set_speech("You have no active alarms scheduled.")
            return response

        alarm_summaries = []
        for alarm in active_alarms:
            name = alarm.get("name")
            time_val = alarm.get("time", "00:00")
            reoccurring = alarm.get("reoccurring", "once")
            
            # Format the summary string
            summary = f"Alarm {name} at {time_val}"
            
            # Add reoccurrence detail if it's not a one-time alarm
            if reoccurring != "once":
                summary += f" ({reoccurring})"
            
            alarm_summaries.append(summary)

        response.async_set_speech("" + ". ".join(alarm_summaries) + ".")
        return response

class DeleteAllAlarmsHandler(intent.IntentHandler):
    """Handles deleting all active alarms."""
    def __init__(self):
        self.intent_type = INTENT_DELETE_ALL

    async def async_handle(self, user_intent: intent.Intent) -> intent.IntentResponse:
        hass = user_intent.hass
        db = hass.data[DOMAIN]["alarms"]
        switches = hass.data[DOMAIN]["switches"]
        
        for idx in list(switches.keys()):
            switch_entity = switches[idx]
            await switch_entity.async_remove()
            del switches[idx]

        db.clear()
        
        from . import save_alarms_to_disk
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        
        list_sensor = hass.data[DOMAIN].get("list_sensor")
        if list_sensor:
            # FIXED: Use async_update_ha_state
            await list_sensor.async_update_ha_state()
            
        response = user_intent.create_response()
        response.async_set_speech("All alarms deleted.")
        return response
