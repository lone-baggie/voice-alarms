# Voice Alarms

![Version](https://img.shields.io/github/v/release/lone-baggie/voice_alarms)
![License](https://img.shields.io/github/license/lone-baggie/voice_alarms)
![HACS](https://img.shields.io/badge/HACS-Custom_orange.svg)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Compatible-blue.svg)

Voice Alarms is an intent-based alarm system for Home Assistant voice satellites, designed to replicate the convenience of commercial assistants like Amazon Alexa or Google Home.

Based on the [HA-Alarms-and-Reminders](https://github.com/omaramin-2000/HA-Alarms-and-Reminders) and [HA-Alarm-Clock](https://github.com/nirnachmani/HA-Alarm-Clock/tree/main) 

This integration allows you to create, delete, and list alarms using simple voice commands or Home Assistant actions.

## Features

* **Flexible Scheduling:** Set one-off or recurring alarms (daily, workdays, or specific days of the week).
* **Named Alarms:** Create alarms with unique names or let the system assign them numerical identifiers.
* **Automation Ready:** A global boolean sensor tracks when *any* alarm triggers, exposing the alarm name, satellite device ID, and media player info for custom automations.
* **Dynamic Management:** Alarms are created as individual Home Assistant switches. Deleting an alarm removes the switch; disabling a switch disables the alarm.

## Voice Commands & Actions

| Intent                                                     | Description                                                                                                                                                                                |
|:---------------------------------------------------------- |:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **create alarm** {name} **at** {time} **on / every** {day} | Creates alarm if **on** single one off alarm. If **every** Recurring by day,weekday or every day. if **on** omitted will assume today. If **name** omitted next alarm number will be used. |
| **delete (all) alarm(s)**  {name} **at** {time }           | delete  an alarm by name or time or all alarms.                                                                                                                                            |
| **List alarms**                                            | Lists current active alarms alarms                                                                                                                                                         |
| **Cancel alarm**                                           | Cancels ringing  alarm                                                                                                                                                                     |

**Available Actions:** 

* `voice_alarms.create_alarm`
* `voice_alarms.alarm_on_off`
* `voice_alarms.delete_alarm`
* `voice_alarms.delete_all_alarms`
* `voice_alarms.cancel_alarm`

**Examples**

create alarm at ten thirty am 

create alarm roast at two thirty pm on sunday

create alarm dinner at six pm  every weekday

delete alarm dinner

delete alarm at 10 pm 

## Entity Details

### Switches (switch.1 - switch.99)

Each alarm is represented as a switch. Turning it **OFF** disables it; turning it **ON** enables it.

* **State:** On/Off
* **Attributes:** `alarm_id`, `device_id`, `name`, `time`, `persistent`, `target day reoccurring`, `ringing`.

### Binary Sensor (binary_sensor.active_alarm)

This sensor turns **ON** when an alarm triggers.

- **State**: Clear / Detected
- **Attributes:** `device_id,alarm_ID,name,media player`

### Sensor (sensor.list_alarms)

* **State:** Count of active alarms.
* **Attributes:**  `alarm_id, Friendly name, time,Reoccurring,persistant`

## Setup Instructions

### 1. Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lone-baggie&repository=voice_alarms&category=integration)

Install via **HACS** as a "Custom Repository" (`https://github.com/lone-baggie/voice_alarms`), or manually copy the `custom_components/voice_alarms` directory into your `/config/custom_components/` directory and restart.

### 2. Custom Sentences

This integration requires a custom intent file to process your speech:

1. Navigate to `/config/custom_sentences/en/` (create the directory if it doesn't exist).
2. Save the [alarm.yaml](https://github.com/lone-baggie/voice_alarms/blob/main/assets/alarm.yaml) file into this folder.
3. Reload your voice intents in Home Assistant.

> **Warning:** Intent syntax is sensitive. Any accidental space or character change may break functionality.

## Automations & Sirens

This integration does not contain built-in sounds. Use the `binary_sensor.active_alarm` to trigger your preferred response.

### Example: ESPHome Alarm Trigger

If using an ESPHome device (M5Stack Atom Echo or HA Voice preview ), you can expose a local "alarm switch" via a [package](https://github.com/lone-baggie/voice_alarms/blob/main/assets/add_switch.yaml) .  This will expose the internal siren used for timers as a home assistant switch.

    packages:
      add_switch: !include packages/add_switch.yaml

Here is an example automation.

     alias: "Atom Alarm Trigger"
    trigger:
      - trigger: state
        entity_id: binary_sensor.active_alarm
        attribute: device_id
        to: "YOUR_DEVICE_ID_HERE"
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.YOUR_ALARM_SWITCH_NAME

You can obtain the device ID from the alarm switch attributes.

## Notes

* **Ringing Alarms:**  When an alarm is trigged the switch that triggered the alarm will be turned off.  The active alarm sensor (binary_sensor.active_alarm) will be set  true and contain the switch attributes that triggered the alarm. If the cancel alarm intent or action calll is activated the active alarm sensor will be set false . After 1 minute the active alarm senor will be set false.  if the switch that triggerred the alarm was non-persistant it will be deleted, otherwise it will be turned back on.
* **Duplicate alarms:** There is extensive logic to try and avoid duplicate alarms. No duplicate names allowed. Duplicate time is handled on a priority basis. Duplicate time alarms will be merged into one alarm based on the recurring pattern. A one-off alarm will be replaced by a recurring day alarm; a day alarm will be replaced by a weekday alarm , etc. An everyday alarm has the highest priority so cannot be duplicated. If  alarms have the same priority the new alarm will not be created as it is a duplicate.
* **Alarm Behavior:** When created, alarm switches are turned **ON** (active). Turning a switch off disables the alarm.  One-off alarm switches that have been turned off will not be deleted, until turned back on and triggered.
* **Alarm list:**  Only active alarm switches will be listed in the intent 'List Alarms' .   Actions 'voice_alarms.list_alarms' will list all alarm switches regardless of state.
* **Deleting  Alarms:** 'Delete alarm' and 'delete all alarms' action or intent  will delete  alarm switches  regardless of state.
* **Changing Alarm state:**  Use the the action voice_alarms_on_off in your automations to change alarm state as you cannot guarantee the switch ID name.
* **Reboot Recovery:** If Home Assistant is rebooted, all alarm switches will be reset to **ON** (active).

## Attribution

Based on [HA-Alarms-and-Reminders](https://github.com/omaramin-2000/HA-Alarms-and-Reminders) by  [omaramin-2000](https://github.com/omaramin-2000) and [HA-Alarm-Clock](https://github.com/nirnachmani/HA-Alarm-Clock/tree/main) by @[nirnachmani](https://github.com/nirnachmani)  (thank you)
