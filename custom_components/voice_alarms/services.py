"""Actions (Services) configuration hooks matching the custom alarm app workflows."""
import logging
from datetime import datetime
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .switch import async_register_new_switch

_LOGGER = logging.getLogger(__name__)

SERVICE_CREATE = "create_alarm"
SERVICE_CANCEL = "cancel_alarm"
SERVICE_DELETE = "delete_alarm"
SERVICE_LIST = "list_alarms"
SERVICE_DELETE_ALL = "delete_all_alarms"

async def async_setup_services(hass: HomeAssistant) -> None:
    """Register core platform orchestration actions."""

    async def handle_create_alarm(call: ServiceCall):
        """Service handler to create a new alarm instance with strict duplicate prevention."""
        db = hass.data[DOMAIN]["alarms"]
        time_str = call.data["time"]
        name = call.data.get("name", "")
        reoccurring = call.data.get("reoccurring", "once").strip().lower()
        device_id = call.data.get("device_id", "")
        
        # 1. Parse time
        parsed_time = None
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p", "%H"):
            try:
                parsed_time = datetime.strptime(time_str.strip(), fmt).time()
                break
            except ValueError:
                continue

        if not parsed_time:
            _LOGGER.error(f"Invalid time format: {time_str}")
            return
            
        formatted_time = parsed_time.strftime("%H:%M")

        # 2. Strict Duplicate Prevention (Matching intents.py logic)
        for alarm in db.values():
            if name and alarm.get("name", "").lower() == name.lower():
                _LOGGER.warning(f"Alarm named '{name}' already exists.")
                return
            if alarm.get("time") == formatted_time:
                _LOGGER.warning(f"Alarm for {formatted_time} already exists.")
                return

        # 3. Find next available index
        allocated_idx = None
        for i in range(1, 100):
            str_idx = f"{i}"
            if str_idx not in db:
                allocated_idx = str_idx
                break
        
        if not allocated_idx:
            _LOGGER.error("Maximum alarm limit (99) reached.")
            return

        final_name = name if name else allocated_idx

        db[allocated_idx] = {
            "name": final_name,
            "time": formatted_time,
            "device_id": device_id,
            "persistent": reoccurring != "once",
            "reoccurring": reoccurring,
            "ringing": False,
            "enabled": True
        }
        
        from . import save_alarms_to_disk
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        await async_register_new_switch(hass, allocated_idx)
        _LOGGER.info(f"Alarm {final_name} created successfully.")

    async def handle_delete_all_alarms(call: ServiceCall):
        """Deletes all alarms safely."""
        db = hass.data[DOMAIN]["alarms"]
        switches = hass.data[DOMAIN].get("switches", {})
        
        if switches:
            for idx in list(switches.keys()):
                if (switch_entity := switches.get(idx)):
                    await switch_entity.async_remove()
            switches.clear()

        db.clear()
        
        from . import save_alarms_to_disk
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        
        if list_sensor := hass.data[DOMAIN].get("list_sensor"):
            await list_sensor.async_update_state()
            
        _LOGGER.info("All alarms deleted.")

    # Register services
    hass.services.async_register(DOMAIN, SERVICE_CREATE, handle_create_alarm,
        schema=vol.Schema({
            vol.Required("time"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("reoccurring"): cv.string,
            vol.Optional("device_id"): cv.string,
        }))
    hass.services.async_register(DOMAIN, SERVICE_DELETE_ALL, handle_delete_all_alarms)