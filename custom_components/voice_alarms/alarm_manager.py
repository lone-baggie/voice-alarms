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

async def async_create_alarm(hass, time_str, reoccurring="once", name=None, device_id="", target_day=None):
    db = hass.data[DOMAIN]["alarms"]
    
    # 1. Parsing and Normalization
    parsed_time = None
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p", "%H"):
        try:
            parsed_time = datetime.strptime(time_str.strip().lower(), fmt).time()
            break
        except ValueError: continue
    
    if not parsed_time:
        return False, "Invalid time format."
    
    raw_time = parsed_time.strftime("%H:%M")
    new_reoccurring = reoccurring.lower().strip()
    new_score = PRIORITY.get(new_reoccurring, 1)
    
    # Set target_day to None if recurring, otherwise default to today
    if new_reoccurring != "once":
        target_day = None
    else:
        target_day = (target_day or datetime.now().strftime("%A")).lower()

    # --- PART 1: TEST FOR DUPLICATION ---
    for idx, alarm in list(db.items()):
        if alarm.get("time") == raw_time:
            existing_re = alarm.get("reoccurring", "once").lower().strip()
            existing_score = PRIORITY.get(existing_re, 1)
            existing_day = alarm.get("target_day", "today")
            existing_day = existing_day.lower() if existing_day else ""

            # Rule: Lower priority incoming = Duplicate
            if new_score < existing_score:
                return False, "Duplicate: Existing higher priority alarm exists."
            
            # Rule: Equal priority specific checks
            if new_score == existing_score:
                if new_score == 1 and target_day == existing_day:
                    return False, "Duplicate: Same time and day for one-time alarm."
                if new_score == 2 and new_reoccurring == existing_re:
                    return False, "Duplicate: Same day/reoccurring pattern."
                if new_score >= 3:
                    return False, "Duplicate: Higher priority pattern exists."

    # --- CREATE NEW ALARM ---
    allocated_idx = next((str(i) for i in range(1, 100) if str(i) not in db), None)
    if not allocated_idx:
        return False, "Maximum limit reached."
        
    db[allocated_idx] = {
        "name": name or allocated_idx, 
        "time": raw_time, 
        "target_day": target_day,
        "device_id": device_id, 
        "reoccurring": new_reoccurring,
        "persistent": new_reoccurring != "once",
        "ringing": False, 
        "enabled": True
    }
    await async_register_new_switch(hass, allocated_idx)

    # --- PART 2: SORT & CLEANUP ---
    time_sets = {}
    for idx, alarm in db.items():
        time_sets.setdefault(alarm.get("time"), []).append((idx, alarm))

    for time_key, alarms in time_sets.items():
        alarms.sort(key=lambda x: PRIORITY.get(x[1].get("reoccurring", "once"), 1), reverse=True)
        has_p4 = any(PRIORITY.get(a[1].get("reoccurring", "once"), 1) == 4 for a in alarms)
        has_p3 = any(PRIORITY.get(a[1].get("reoccurring", "once"), 1) == 3 for a in alarms)

        for idx, alarm in alarms:
            score = PRIORITY.get(alarm.get("reoccurring", "once"), 1)
            # Cleanup rules
            if has_p4 and score < 4:
                await _delete_by_index(hass, idx)
            elif has_p3 and score < 3 and any(d in (alarm.get("target_day","") or "" + (alarm.get("reoccurring","") or "")) for d in ["monday", "tuesday", "wednesday", "thursday", "friday"]):
                await _delete_by_index(hass, idx)
            elif score == 1 and any(PRIORITY.get(a[1].get("reoccurring", "once"), 1) == 2 and a[1].get("target_day") == alarm.get("target_day") for a in alarms):
                await _delete_by_index(hass, idx)

    # Finalize
    from . import save_alarms_to_disk
    await hass.async_add_executor_job(save_alarms_to_disk, hass)
    if list_sensor := hass.data[DOMAIN].get("list_sensor"):
        list_sensor.async_write_ha_state()
        
    # --- UPDATED REPLY LOGIC ---
    # Priority 1: One-time alarms
    if new_reoccurring == "once":
        return True, f"Alarm created at {raw_time} on {target_day}."
    
    # Priority 2+: Recurring alarms
    else:
        # Clean 'every everyday' to 'everyday'
        clean_re = new_reoccurring.replace("every every", "every")
        if "every" not in clean_re:
            clean_re = f"every {clean_re}"
        return True, f"Alarm created at {raw_time} {clean_re}."    

# Helper to keep code clean
async def _delete_by_index(hass, idx):
    switches = hass.data[DOMAIN]["switches"]
    if idx in switches:
        await switches[idx].async_remove()
        del switches[idx]
    del hass.data[DOMAIN]["alarms"][idx]

async def async_delete_alarm(hass, name=None, time=None, target_day=None):
    """Delete an alarm, optionally restricted by day."""
    db = hass.data[DOMAIN]["alarms"]
    switches = hass.data[DOMAIN]["switches"]
    
    # Improved selection logic to include target_day if provided
    target_idx = next((idx for idx, a in db.items() if 
                       (name and a.get("name") == name) or 
                       (time and a.get("time") == time and (not target_day or a.get("target_day") == target_day))), None)
    
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

async def async_delete_all_alarms(hass):
    db, switches = hass.data[DOMAIN]["alarms"], hass.data[DOMAIN]["switches"]
    for idx in list(switches.keys()):
        await switches[idx].async_remove()
    switches.clear()
    db.clear()
    from . import save_alarms_to_disk
    await hass.async_add_executor_job(save_alarms_to_disk, hass)
    if list_sensor := hass.data[DOMAIN].get("list_sensor"):
        await list_sensor.async_update_ha_state()

def async_get_all_alarms(hass):
    return list(hass.data[DOMAIN].get("alarms", {}).values())