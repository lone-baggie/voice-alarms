# alarm_manager.py
import logging
from datetime import datetime
from .const import DOMAIN
from .switch import async_register_new_switch

_LOGGER = logging.getLogger(__name__)

PRIORITY = {
    "once": 1, 
    "monday": 2, "tuesday": 2, "wednesday": 2, "thursday": 2, 
    "friday": 2, "saturday": 2, "sunday": 2,
    "weekday": 3,
    "everyday": 4, "every day": 4, "daily": 4
}

async def async_create_alarm(hass, time_str, reoccurring="once", name=None, device_id=""):
    db = hass.data[DOMAIN]["alarms"]
    
    # Parsing
    parsed_time = None
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p", "%H"):
        try:
            parsed_time = datetime.strptime(time_str.strip().lower(), fmt).time()
            break
        except ValueError: continue
    
    if not parsed_time:
        return False, "Invalid time format."
    
    raw_time = parsed_time.strftime("%H:%M")
    new_score = PRIORITY.get(reoccurring.lower(), 1)

    # Validation & Cleanup Logic
    for idx, alarm in list(db.items()):
        if alarm.get("time") == raw_time:
            existing_re = alarm.get("reoccurring", "once").lower()
            existing_score = PRIORITY.get(existing_re, 1)

            if new_score < existing_score:
                return False, f"Lower priority than existing alarm at {raw_time}."
            if new_score == existing_score and new_score != 2:
                return False, "Duplicate alarm."
            if new_score == 2 and existing_score == 2 and existing_re == reoccurring:
                return False, "Duplicate day."

    # Allocation
    allocated_idx = next((str(i) for i in range(1, 100) if str(i) not in db), None)
    if not allocated_idx:
        return False, "Maximum limit reached."

    db[allocated_idx] = {
        "name": name or allocated_idx,
        "time": raw_time,
        "device_id": device_id,
        "persistent": reoccurring != "once",
        "reoccurring": reoccurring,
        "ringing": False,
        "enabled": True
    }

    # Post-Creation Cleanup
    same_time_alarms = [(idx, alarm) for idx, alarm in db.items() if alarm.get("time") == raw_time and idx != allocated_idx]
    for idx, alarm in same_time_alarms:
        existing_score = PRIORITY.get(alarm.get("reoccurring", "once").lower(), 1)
        if new_score == 4 or (new_score == 3 and existing_score <= 2) or (new_score == 2 and existing_score == 1):
            if idx in hass.data[DOMAIN]["switches"]:
                await hass.data[DOMAIN]["switches"][idx].async_remove()
            del db[idx]

    from . import save_alarms_to_disk
    await hass.async_add_executor_job(save_alarms_to_disk, hass)
    await async_register_new_switch(hass, allocated_idx)
    if list_sensor := hass.data[DOMAIN].get("list_sensor"):
        await list_sensor.async_update_ha_state()
        
    return True, f"Alarm created for {raw_time} ({reoccurring})."

async def async_delete_alarm(hass, name=None, time=None):
    db = hass.data[DOMAIN]["alarms"]
    switches = hass.data[DOMAIN]["switches"]
    target_idx = next((idx for idx, a in db.items() if (name and a.get("name")==name) or (time and a.get("time")==time)), None)
    
    if target_idx:
        if target_idx in switches:
            await switches[target_idx].async_remove()
            del switches[target_idx]
        del db[target_idx]
        from . import save_alarms_to_disk
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        if list_sensor := hass.data[DOMAIN].get("list_sensor"):
            await list_sensor.async_update_ha_state()
        return True
    return False