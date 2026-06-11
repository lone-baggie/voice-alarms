"""The Voice Alarm Application Integration."""
import logging
import asyncio
import os
import json
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.util.dt as dt_util

from .intents import async_setup_intents
from .services import async_setup_services
from .const import DOMAIN

MASTER_SIREN = "input_boolean.alarm_ring"
STORAGE_KEY = "voice_alarm_cache.json"

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Voice Alarm component from a config entry."""
    storage_path = hass.config.path(".storage", STORAGE_KEY)
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].update({
        "alarms": {},
        "switches": {},
        "master_sensor": None,
        "list_sensor": None,
        "storage_path": storage_path
    })

    def _read_cache_file():
        if os.path.exists(storage_path):
            try:
                with open(storage_path, "r") as f:
                    return json.load(f)
            except Exception as err:
                _LOGGER.error(f"Failed to load persistent alarms: {err}")
        return {}

    hass.data[DOMAIN]["alarms"] = await hass.async_add_executor_job(_read_cache_file)
    
    if hass.data[DOMAIN]["alarms"]:
        _LOGGER.info(f"Loaded {len(hass.data[DOMAIN]['alarms'])} alarms from persistent storage.")

    async_setup_intents(hass)
    await async_setup_services(hass)

    # Set up platforms via config entry
    await hass.config_entries.async_forward_entry_setups(
        entry, ["binary_sensor", "sensor", "switch"]
    )

    hass.async_create_background_task(
        keep_alive_cron_loop(hass),
        "voice_alarm_cron_worker"
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Cleanly unload the integration platforms."""
    return await hass.config_entries.async_unload_platforms(
        entry, ["binary_sensor", "sensor", "switch"]
    )

def save_alarms_to_disk(hass: HomeAssistant) -> None:
    """Helper macro to write current memory state down to physical JSON storage."""
    try:
        storage_path = hass.data[DOMAIN]["storage_path"]
        with open(storage_path, "w") as f:
            json.dump(hass.data[DOMAIN]["alarms"], f, indent=4)
    except Exception as err:
        _LOGGER.error(f"Failed to save alarms to disk: {err}")


async def keep_alive_cron_loop(hass: HomeAssistant) -> None:
    """Continuous runner execution clock looping precisely on minute transitions."""
    while True:
        try:
            await async_run_engine_loop(hass, datetime.now())
        except Exception as err:
            _LOGGER.error(f"Error in alarm engine loop: {err}")
        
        now = datetime.now()
        await asyncio.sleep(60 - now.second)


async def async_run_engine_loop(hass: HomeAssistant, now_dt: datetime) -> None:
    """Main background loop execution matrix mimicking a system crontab."""
    db = hass.data[DOMAIN]["alarms"]
    switches = hass.data[DOMAIN]["switches"]
    master_sensor = hass.data[DOMAIN].get("master_sensor")
    list_sensor = hass.data[DOMAIN].get("list_sensor")
    
    local_now = dt_util.as_local(now_dt)
    current_hour = local_now.hour
    current_minute = local_now.minute
    current_day_name = local_now.strftime("%A").lower()
    is_weekday = local_now.weekday() in [0, 1, 2, 3, 4]

    any_ringing = False
    items_to_delete = []
    state_changed = False

# 1. Cleanup ringing, non-persistent alarms
    for idx, alarm in list(db.items()):
        if alarm.get("ringing", False):
            # Check the switch state; if it's still ON, we leave it alone.
            # If the switch is OFF (or doesn't exist), we proceed to clean up.
            is_switch_on = switches.get(idx) and switches.get(idx).is_on
            
            if is_switch_on:
                # Alarm is still ringing and switch is ON, let it continue
                continue
            
            # If we reach here, the alarm was ringing but the switch is now OFF
            sched_type = str(alarm.get("reoccurring", "once")).strip().lower()
            
            if sched_type == "once" or not alarm.get("persistent", False):
                items_to_delete.append(idx)
            else:
                # Persistent alarms just reset their state
                alarm["ringing"] = False
                alarm["enabled"] = True
                state_changed = True
                if idx in switches:
                    switches[idx].async_write_ha_state()

    # 2. Perform robust deletion
    for idx in items_to_delete:
        if idx in db:
            del db[idx]
            state_changed = True
        if idx in switches:
            # Use the improved async_remove to cleanup Registry
            await switches[idx].async_remove()
            del switches[idx]

    # 3. Check for alarm triggers
    for idx, alarm in list(db.items()):
        if not alarm.get("enabled", True):
            continue
        if alarm.get("ringing", False):
            any_ringing = True
            continue

        try:
            time_parts = [int(x) for x in alarm["time"].split(":")[:2]]
            alarm_hour = time_parts[0]
            alarm_minute = time_parts[1]
        except Exception:
            continue

        time_matched = (current_hour == alarm_hour and current_minute == alarm_minute)
        day_matched = False
        sched_type = str(alarm.get("reoccurring", "once")).strip().lower()

        if sched_type in ["once", ""]:
            day_matched = True
        elif sched_type in ["everyday", "every day", "daily"]:
            day_matched = True
        elif sched_type == "weekday" and is_weekday:
            day_matched = True
        elif sched_type == current_day_name:
            day_matched = True

        if time_matched and day_matched:
            alarm["ringing"] = True
            alarm["enabled"] = False
            any_ringing = True
            state_changed = True
            if idx in switches:
                switches[idx].async_write_ha_state()


    if state_changed:
        # 1. Save data to disk using the executor
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        
        # 2. Update the master sensor (Binary Sensor)
        if master_sensor:
            # FIX: Changed from 'master_sensor.update_state()' to 'await'
            await master_sensor.async_update_state()
            
        # 3. Update the list sensor (if you have one)
        if list_sensor:
            await list_sensor.async_update_state()
