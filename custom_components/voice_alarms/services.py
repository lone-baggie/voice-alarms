import logging
from datetime import datetime
import voluptuous as vol  # pyright: ignore[reportMissingImports]   

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse # pyright: ignore[reportMissingImports]
from homeassistant.helpers import config_validation as cv # pyright: ignore[reportMissingImports]
from .helpers import async_cancel_alarm_logic
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
        db = hass.data[DOMAIN]["alarms"]
        time_str = call.data["time"]
        name = call.data.get("name", "")
        reoccurring = call.data.get("reoccurring", "once").strip().lower()
        device_id = call.data.get("device_id", "")
        
        # Priority mapping for upgrade logic
        PRIORITY = {
            "once": 1, "monday": 2, "tuesday": 2, "wednesday": 2, "thursday": 2, 
            "friday": 2, "saturday": 2, "sunday": 2,
            "weekday": 3,
            "everyday": 4, "every day": 4, "daily": 4
        }

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

        # 2. Duplicate & Upgrade Prevention Logic
        for idx, alarm in db.items():
            # Name conflict
            if name and alarm.get("name", "").lower() == name.lower():
                _LOGGER.warning(f"Alarm named '{name}' already exists.")
                return
            
            # Time conflict check
            if alarm.get("time") == formatted_time:
                existing_re = alarm.get("reoccurring", "once").lower()
                existing_score = PRIORITY.get(existing_re, 1)
                new_score = PRIORITY.get(reoccurring, 1)

                # EQUAL: Reject
                if new_score == existing_score:
                    _LOGGER.warning(f"Alarm for {formatted_time} with {reoccurring} already exists.")
                    return
                
                # HIGHER: Upgrade
                elif new_score > existing_score:
                    alarm["reoccurring"] = reoccurring
                    alarm["persistent"] = True
                    # Sync UI
                    if idx in hass.data[DOMAIN]["switches"]:
                        hass.data[DOMAIN]["switches"][idx].async_write_ha_state()
                    
                    from . import save_alarms_to_disk
                    await hass.async_add_executor_job(save_alarms_to_disk, hass)
                    _LOGGER.info(f"Upgraded alarm {idx} at {formatted_time} to {reoccurring}.")
                    return

                # LOWER: Reject
                else:
                    _LOGGER.warning(f"Higher priority alarm exists for {formatted_time}.")
                    return

        # 3. Find next available index (Standard creation)
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
        db = hass.data[DOMAIN]["alarms"]
        time_str = call.data["time"]
        name = call.data.get("name", "")
        reoccurring = slots.get("reoccurring", {}).get("value", "once").lower().strip()
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

        # 2. Hierarchical Duplicate Prevention
        # Define scheduling groups
        high_priority = ["everyday", "every day", "daily"]
        
        for alarm in db.values():
            if name and alarm.get("name", "").lower() == name.lower():
                _LOGGER.warning(f"Alarm named '{name}' already exists.")
                return
            
            if alarm.get("time") == formatted_time:
                existing_re = alarm.get("reoccurring", "once").lower()
                
                # REJECTION LOGIC:
                # 1. If existing is high priority, reject everything.
                # 2. If new is high priority, reject everything existing.
                # 3. If both are weekday/day, reject.
                if (reoccurring in high_priority or existing_re in high_priority) or \
                   (reoccurring == existing_re) or \
                   (reoccurring == "weekday" or existing_re == "weekday"):
                    _LOGGER.warning(f"Conflicting alarm already exists for {formatted_time}.")
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

    async def handle_alarm_on_off(call: ServiceCall):
        name = call.data.get("name")
        time = call.data.get("time")
        state = call.data.get("state").lower()  # "on" or "off"
        
        db = hass.data[DOMAIN]["alarms"]
        switches = hass.data[DOMAIN]["switches"]
        target_idx = None

        # Find the index for the alarm
        for idx, alarm in db.items():
            if name and alarm.get("name") == name:
                target_idx = idx
                break
            if time and alarm.get("time") == time:
                target_idx = idx
                break
        
        if not target_idx or target_idx not in switches:
            _LOGGER.warning(f"Could not find active alarm switch for: {name or time}")
            return

        # Execute the switch change
        if state == "on":
            await switches[target_idx].async_turn_on()
        else:
            await switches[target_idx].async_turn_off()
            
        _LOGGER.info(f"Alarm {target_idx} turned {state}.")
 
    async def handle_cancel_alarm(call: ServiceCall):
        await async_cancel_alarm_logic(call.hass)
                
    async def handle_delete_alarm(call: ServiceCall):
        name = call.data.get("name")
        time = call.data.get("time")
        db = hass.data[DOMAIN]["alarms"]
        switches = hass.data[DOMAIN]["switches"]
        target_idx = None

        for idx, alarm in db.items():
            if name and alarm.get("name") == name:
                target_idx = idx
                break
            if time and alarm.get("time") == time:
                target_idx = idx
                break
        
        if target_idx:
            if target_idx in switches:
                await switches[target_idx].async_remove()
                del switches[target_idx]
            del db[target_idx]
            
            from . import save_alarms_to_disk
            await hass.async_add_executor_job(save_alarms_to_disk, hass)
            if list_sensor := hass.data[DOMAIN].get("list_sensor"):
                list_sensor.update_state()
                
    async def handle_list_alarms(call: ServiceCall) -> ServiceResponse:
        db = hass.data[DOMAIN]["alarms"]
        return {"alarms": list(db.values())}

    async def handle_delete_all_alarms(call: ServiceCall):
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

    # --- REGISTRATIONS ---
    hass.services.async_register(DOMAIN, SERVICE_CREATE, handle_create_alarm,
        schema=vol.Schema({
            vol.Required("time"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("reoccurring"): cv.string,
            vol.Optional("device_id"): cv.string,
        }))

    hass.services.async_register(DOMAIN, "alarm_on_off", handle_alarm_on_off,
        schema=vol.Schema({
            vol.Required("state"): vol.In(["on", "off"]),
            vol.Optional("name"): cv.string,
            vol.Optional("time"): cv.string,
        }))

    hass.services.async_register(DOMAIN, SERVICE_CANCEL, handle_cancel_alarm)
    
    hass.services.async_register(DOMAIN, SERVICE_DELETE, handle_delete_alarm,
        schema=vol.Schema({
            vol.Optional("name"): cv.string,
            vol.Optional("time"): cv.string,
        }))
        
    hass.services.async_register(DOMAIN, SERVICE_LIST, handle_list_alarms,
        supports_response=SupportsResponse.ONLY)
        
    hass.services.async_register(DOMAIN, SERVICE_DELETE_ALL, handle_delete_all_alarms)