"""Helper functions for Voice Alarm."""
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_cancel_alarm_logic(hass: HomeAssistant):
    """Unified logic to silence alarms."""
    db = hass.data[DOMAIN]["alarms"]
    switches = hass.data[DOMAIN]["switches"]
    master_sensor = hass.data[DOMAIN].get("master_sensor")
    
    # Import locally to avoid circular dependencies
    from . import save_alarms_to_disk
    
    any_changed = False
    for idx, alarm in db.items():
        if alarm.get("ringing"):
            alarm["ringing"] = False
            alarm["enabled"] = False 
            any_changed = True
            if idx in switches:
                switches[idx].async_write_ha_state()
    
    if any_changed:
        await hass.async_add_executor_job(save_alarms_to_disk, hass)
        if master_sensor:
            await master_sensor.async_update_state()