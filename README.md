<img src="https://github.com/dermotduffy/hass-motioneye/blob/main/images/motioneye.png?raw=true"
     alt="motionEye icon"
     width="15%"
     align="right"
     style="float: right; margin: 10px 0px 20px 20px;" />

[![GitHub Release](https://img.shields.io/github/release/dermotduffy/hass-motioneye.svg?style=flat-square)](https://github.com/dermotduffy/hass-motioneye/releases)
[![Build Status](https://img.shields.io/github/workflow/status/dermotduffy/hass-motioneye/Build?style=flat-square)](https://github.com/dermotduffy/hass-motioneye/actions/workflows/build.yaml)
[![Test Coverage](https://img.shields.io/codecov/c/gh/dermotduffy/hass-motioneye?style=flat-square)](https://app.codecov.io/gh/dermotduffy/hass-motioneye/)
[![License](https://img.shields.io/github/license/dermotduffy/hass-motioneye.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![BuyMeCoffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://www.buymeacoffee.com/dermotdu)

# motionEye Home Assistant Integration

The motionEye integration allows you to integrate your
[motionEye](https://github.com/ccrisan/motioneye) server into Home Assistant. motionEye
is an open source web-frontend for the motion daemon, used to centralize the management
and visualization of multiple types of camera.

## Features

   * Dynamic motionEye camera addition/removal.
   * View motionEye MJPEG video streams as HA camera entities with no additional configuration.
   * Control major motionEye camera options as HA switch entities.
   * Camera motion detection events, and file (image or movie) storage events propagate into
     HA events which can be used in automations.
   * Custom services to set camera overlay text, to trigger motionEye snapshots, and to perform
     arbitrary configured [motionEye Action
     Buttons](https://github.com/ccrisan/motioneye/wiki/Action-Buttons).
   * View saved movies/images straight from the Home Assistant Media Browser.

## Screenshot

<img src="https://github.com/dermotduffy/hass-motioneye/blob/main/images/screenshot-motioneye-device.png?raw=true" alt="hass-motioneye screenshot" />

## Installation

> **_NOTE:_**  As this integration is still in the [wait list for HACS default](https://github.com/hacs/default/pull/901) you must first add a custom repository.

   * Add the custom repository:

```
Home Assistant > HACS > Integrations > [...] > Custom Repositories
```

| Key            | Value                                         |
| -------------- | --------------------------------------------- |
| Repository URL | https://github.com/dermotduffy/hass-motioneye |
| Category       | Integration                                   |

   * Use [HACS](https://hacs.xyz/) to install to repository:
```
Home Assistant > HACS > Integrations > "Explore & Add Integrations" > motionEye
```
   * Restart Home Assistant.
   * Then install the integration:
```
Home Assistant > Configuration > Integrations > Add Integration > motionEye
```

### Configuration Variables

| Variable              | Description                                                                              |
| --------------------- | ---------------------------------------------------------------------------------------- |
| url                   | The URL of the motionEye server                                                          |
| admin_username        | The username of the motionEye administrative account, used for changing camera settings. |
| admin_password        | The password of the motionEye administrative account.                                    |
| surveillance_username | The username of the motionEye surveillance user, used to authenticate video streams.     |
| surveillance_password | The password of the motionEye surveillance account.                                      |

<a name="options"></a>
## Options

```
Home Assistant > Configuration > Integrations > motionEye > Options
```

* **Configure motionEye webhooks to report events to Home Assistant** [default=`True`]:
  Whether or not motionEye webhooks should be configured to callback into Home
  Assistant. If this option is disabled, no motion detected or file stored events will
  be generated unless the webhooks are manually configured.
* **Overwrite unrecognized webhooks** [default=`False`]: Whether or not to overwrite
  webhooks that are already configured and are not recognized as belonging to this
  integration (web hooks are deemed to belong to this integration if they contain
  `src=hass-motioneye` in the query string).
* [**Advanced**]: **Steam URL template** [default=`None`]: A [jinja2](https://jinja.palletsprojects.com/)
  template that is used to override the standard MJPEG stream URL (e.g. for use with reverse
  proxies). See [Camera MJPEG Streams](#streams) below. This option is only shown to
  users who have [advanced
  mode](https://www.home-assistant.io/blog/2019/07/17/release-96/#advanced-mode) enabled.

## Usage

### Entities

| Platform        | Description                                                                                                                                                                                                                                   |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `camera`        | An MJPEG camera that shows the motionEye video stream.                                                                                                                                                                                        |
| `switch`        | Switch entities to enable/disable motion detection, text overlay, video streaming, still image capture and movie capture.                                                                                                                     |
| `sensor`        | An "action sensor" that shows the number of configured [actions](https://github.com/ccrisan/motioneye/wiki/Action-Buttons) for this device. The names of the available actions are viewable in the `actions`  attribute of the sensor entity. |
| `binary_sensor` | A "motion" and "file_stored" binary sensor convenience entity. See [below](#convenience-binary-sensors).                                                                                                                                      |

Notes:
   * If the video streaming switch is turned off, the camera entity will become unavailable (but the rest of the integration will continue to work).
   * As cameras are added or removed to motionEye, devices/entities are automatically added or removed from Home Assistant.

<a name="streams"></a>
#### Camera MJPEG Streams

In order for the MJPEG streams to function they need to be accessible at
`<motioneyehost>:<streaming port>`, i.e. Home Assistant will directly connect to the streaming port
that is configured in the `motionEye` UI (under `Video Streaming`) on the host that the
motionEye integration is configured to use.

Example:
* If this integration is configured to talk to motionEye at `http://motioneye:8765`, and
  a camera is configured to stream on port `8081` -- Home Assistant needs to
  be able to communicate to `motioneye` port `8081`.

##### Stream URL Template

For advanced usecases, this behavior can be changed with the [Steam URL
template](#options) option. When set, this string will override the default stream
address that is derived from the default behavior described above. This option supports
[jinja2 templates](https://jinja.palletsprojects.com/) and has the `camera` dict
variables from motionEye
([example](https://github.com/dermotduffy/hass-motioneye/blob/main/tests/__init__.py#L22))
available for the template. Note that no Home Assistant state is available to the
template, only the camera dict from motionEye.

This is very useful when motionEye is behind a custom configured reverse proxy, and/or
when the stream ports are otherwise not accessible to Home Assistant (e.g. firewall
rules).

###### Stream URL Template Examples

The below are useful examples of how this option may be set.

Use the camera name in the stream URL:

```
http://motioneye/video/{{ name }}
```

Use the camera name in the stream URL, converting it to lowercase first:

```
http://motioneye/video/{{ name|lower }}
```

Use the camera id in the stream URL:

```
http://motioneye/video/{{ id }}
```

### Events

On receipt of a motion or file stored callbacks, events will be fired which can be used
in automations (etc). All event data includes the Home Assistant `device_id` for this
motionEye camera device, and the Home Assistant device `name`. Event data also includes
as many [Motion Conversion
Specifiers](https://motion-project.github.io/motion_config.html#conversion_specifiers)
as make sense for that event type.

Note: Any additional `&key=value` pairs added manually to the motionEye webhook (in the
motionEye UI) will automatically propagate to the event data. If you manually tweak the
web hook, remove the `src=hass-motioneye` parameter or the web hook will be overwritten.
#### Example motion detected event

```json
{
    "event_type": "motioneye.motion_detected",
    "data": {
        "device_id": "662aa1c77657dbc4af836abcdf80000a",
        "name": "Office",
        "camera_id": "2",
        "changed_pixels": "99354",
        "despeckle_labels": "55",
        "event": "02",
        "fps": "24",
        "frame_number": "10",
        "height": "1080",
        "host": "6aa7a495490c",
        "motion_center_x": "314",
        "motion_center_y": "565",
        "motion_height": "730",
        "motion_version": "4.2.2",
        "motion_width": "252",
        "noise_level": "12",
        "threshold": "20736",
        "width": "1920"
    },
    "origin": "LOCAL",
    "time_fired": "2021-04-11T04:25:41.106964+00:00",
    "context": {
        "id": "0320bb897aa3656dbb02affddce322f2",
        "parent_id": null,
        "user_id": null
    }
}
```

#### Example file stored event

```json
{
    "event_type": "motioneye.file_stored",
    "data": {
        "device_id": "662aa1c77657dbc4af836abcdf80000a",
        "name": "Office",
        "camera_id": "2",
        "event": "03",
        "file_path": "/var/lib/motioneye/Camera2/2021-04-10/21-27-53.jpg",
        "file_type": "1",
        "fps": "25",
        "frame_number": "21",
        "height": "1080",
        "host": "6aa7a495490c",
        "motion_version": "4.2.2",
        "noise_level": "12",
        "threshold": "20736",
        "width": "1920"
    },
    "origin": "LOCAL",
    "time_fired": "2021-04-11T04:27:54.528671+00:00",
    "context": {
        "id": "0358cac9457e3e3a2039da8c998e4c25",
        "parent_id": null,
        "user_id": null
    }
}
```

<a name="convenience-binary-sensors"></a>
#### Convenience binary sensor entities

For convenience (e.g. UI display, entity state recording) binary sensor entities
(`binary_sensor.<name>_motion` and `binary_sensor.<name>_file_stored`) are
included to provide the equivalent on/off signal in entity form. The state of
the binary sensors resets after 30 seconds.

### Services

All services accept either a comma-separated list of entities in `entity_id` or a hex
`device_id`. The `device_id` for a device can be found by visiting the device page:


```
Home Assistant > Configuration > Devices > "Search Devices"
```

Upon opening a given device page, the `device_id` can be found at the end of the URL:

```
https://<home_assistant>/config/devices/device/<device_id>
```

#### motioneye.snapshot

Trigger a camera snapshot (e.g. saving an image to disk).

Parameters:

| Parameter               | Description                                           |
| ----------------------- | ----------------------------------------------------- |
| `entity_id` `device_id` | An entity id or device id to set the text overlay on. |

Note: This is a thin wrapper on the [`motioneye.action` call](#action).

<a name="action"></a>
#### motioneye.action

Trigger a motionEye action (see [MotionEye Action Buttons](https://github.com/ccrisan/motioneye/wiki/Action-Buttons)).

| Parameter               | Description                                                                                                                                                                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `entity_id` `device_id` | An entity id or device id to set the text overlay on.                                                                                                                                                                                                  |
| `action`                | A string representing the motionEye action to trigger. One of `snapshot`, `record_start`, `record_stop`, `lock`, `unlock`, `light_on`, `light_off`, `alarm_on`, `alarm_off`, `up`, `right`, `down`, `left`, `zoom_in`, `zoom_out`, `preset1`-`preset9` |

Note: As of 2021-04-11 the `record_start` and `record_stop` action are not implemented in
motionEye itself and thus do not function in this integration ([relevant code](https://github.com/ccrisan/motioneye/blob/dev/motioneye/handlers.py#L1741)).

#### motioneye.set_text_overlay

Set the text overlay for a camera.

Parameters:

| Parameter                              | Description                                                                                                                                                                 |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_id` `device_id`                | An entity id or device id to set the text overlay on.                                                                                                                       |
| `left_text` `right_text`               | One of `timestamp`, `camera-name`, `custom-text` or `disabled` to show a timestamp, the  name of the camera, custom text or nothing at all, on the left or right-hand side. |
| `custom_left_text` `custom_right_text` | Custom text to show on the left or right, if the `custom-text` value is selected.                                                                                           |

Note:
   * Calling this service triggers a reset of the motionEye cameras which will pause the
     stream / recordings / motion detection (etc).
   * Ensure the `Text Overlay` switch is turned on to actually display the configured text overlays.

Example:

```yaml
service: motioneye.set_text_overlay
data:
  left_text: timestamp
  right_text: custom-text
  custom_right_text: "Alarm armed"
target:
  entity_id: camera.office
```

## Media Browsing

Saved motionEye media (movies and images) can be natively browsed from the Home Assistant "Media
Browser".

<img src="images/screenshot-media-browser.png" alt="hass-motioneye Media Browser screenshot" />

### Manually Configured Root Directories

Whlst this integration allows drilling down into the media for each camera separately,
underneath motionEye is using the directory structure to associate media items to each
individual camera. Thus if multiple cameras are manually configured to share the same
root directory, motionEye will return the _combination_ of the media items when any one
of the "overlapping" cameras are queried. Use different root directories (in motionEye:
`File Storage -> Root Directory`) to ensure motionEye (and thus this integration) will
correctly associate media with the camera from which that media was captured.

## Example Lovelace Card

A lovelace card with icons that will call the `action` service to send action commands to motionEye.

```yaml
- type: picture-glance
  title: Living Room
  camera_image: camera.living_room
  camera_view: live
  entities:
      - entity: camera.living_room
      - entity: camera.living_room
        icon: 'mdi:arrow-left'
        tap_action:
          action: call-service
          service: motioneye.action
          service_data:
            action: left
            entity_id: camera.living_room
      - entity: camera.living_room
        icon: 'mdi:arrow-right'
        tap_action:
          action: call-service
          service: motioneye.action
          service_data:
            action: right
            entity_id: camera.living_room
      - entity: camera.living_room
        icon: 'mdi:arrow-up'
        tap_action:
          action: call-service
          service: motioneye.action
          service_data:
            action: up
            entity_id: camera.living_room
      - entity: camera.living_room
        icon: 'mdi:arrow-down'
        tap_action:
          action: call-service
          service: motioneye.action
          service_data:
            action: down
            entity_id: camera.living_room
```

<img src="images/screenshot-motioneye-lovelace.png" alt="hass-motioneye lovelace card" />

## Example Automations

### Set text overlay when alarm is armed

A simple automation to set text overlay indicating the alarm armed status. Text overlay
must be switched on for this automation to work (controllable via `switch.<name>_text_overlay`).

```yaml
- alias: 'Set camera text overlay to armed'
  trigger:
    platform: state
    entity_id: alarm_control_panel.home_alarm
    to: 'armed_away'
  action:
    - service: motioneye.set_text_overlay
      target:
        entity_id: camera.living_room
      data:
        left_text: custom-text
        custom_left_text: Alarm is ARMED

- alias: 'Set camera text overlay do disarmed'
  trigger:
    platform: state
    entity_id: alarm_control_panel.home_alarm
    to: 'disarmed'
  action:
    - service: motioneye.set_text_overlay
      target:
        entity_id: camera.living_room
      data:
        left_text: custom-text
        custom_left_text: Alarm is disarmed
```

<img src="images/screenshot-alarm-armed-automation.png" alt="hass-motioneye alarm automation" />

## Debugging

### Debug Logging

To enable debug logging for both the custom component and the underlying client library,
enable the following in your `configuration.yaml` and then restart:

```yaml
logger:
  default: warning
  logs:
    motioneye_client: debug
    custom_components.motioneye: debug
```

## Long-term intention

The goal is to integrate this `custom_component` into Home Assistant Core (non-HACS)
integration. This process has an open-timeline because of the large backlog of code
reviews for Home Assistant Core code submissions, but will probably take at 6-9 months
before all of the functionality would likely be merged in (i.e. goal is to have it
merged by the end of 2021).

As part of that codereview process changes may be necessary (e.g. names, identifiers and
functionality may change). There no guarantee of seamless migration from HACS -> Core
for users as a result of these changes.

Long-term, once this functionality is fully (or mostly) in Core, this custom component
will not be necessary anymore and will be retired. You can track the PRs that are part
of this move from custom to Core in the [Core Integration Project for
hass-motioneye](https://github.com/dermotduffy/hass-motioneye/projects/3).

## Frequently Asked Questions

### Q: Why do I need to specify both admin and surveillance passwords?

**A**: The administrative password is required for making changes to cameras via the API
(e.g. for setting camera webhooks, for enabling/disabling text overlay). The
surveillance password is required to access the live stream (for the Home Assistant
camera entity) --  the administrative password will not function for this purpose, nor
is there any way to retrieve credentials using either of the passwords.

### Q: Is it safe to enter my motionEye credentials?

**A**: It is as safe as any other Home Assistant-stored credentials. Passwords
are stored using the standard Home Assistant "config entry" mechanism. They are
never logged, nor sent anywhere except (at most) to the motionEye server you
configure. Source code for this integration, and it's underlying library
([motioneye-client](https://github.com/dermotduffy/motioneye-client)) is readily
available for your review.

Good security practice includes not exposing motionEye (or Home Assistant!) to
the internet unless carefully protected by external security measures (e.g.
firewall, Apache Access Controls, VPNs, etc) -- as such, even if your
credentials were exposed you should make it the case that they are of relatively
low value in isolation.

## Development

### Updating underlying libraries

   * Update [requirements.txt](https://github.com/dermotduffy/hass-motioneye/blob/main/requirements.txt)
      * Used for CI building.
   * Update [custom_components/motioneye/manifest.json](https://github.com/dermotduffy/hass-motioneye/blob/main/custom_components/motioneye/manifest.json)
      * Used for Home Assistant.
   * Update [.pre-commit-config.yaml](https://github.com/dermotduffy/hass-motioneye/blob/main/.pre-commit-config.yaml)
      * Used for mypy type checking.

### Cutting a new release

* Update
  [custom_components/motioneye/manifest.json](https://github.com/dermotduffy/hass-motioneye/blob/main/custom_components/motioneye/manifest.json)
  with the new version number.
* Edit the draft release on the [Github Releases Page](https://github.com/dermotduffy/hass-motioneye/releases)

## Credits

Thanks to [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom
Component
Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component)
template which was used for the initial skeleton of this component.
