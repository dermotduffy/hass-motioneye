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

<a name="migration-warning"></a>
# Migration complete: Custom Integration Is Now Retired

This integration has completed migration into Home Assistant Core. There are some permanent differences in functionality, these are listed below. This custom integration is now retired. Please use the default version that comes with Home Assistant Core.

* **Binary sensors**: The Core version of the motionEye integration does not feature binary sensors (see [relevant codereview feedback](https://github.com/home-assistant/core/pull/52493#discussion_r673674561)). Instead users should convert events into a binary sensors [see example](#synthetic-binary-sensor).
* **Switches**: The Core version of the motionEye integration disables the `Text Overlay`, `Video Streaming` and `Upload Enabled` switches by default. They can be manually enabled in the UI for the device in Home Assistant.

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

<a name="addon"></a>
### Usage with the motionEye add-on

This integretion can optionally be used in conjunction with the community
[add-on for motionEye](https://github.com/hassio-addons/addon-motioneye).

To configure the integration to use the add-on, simply use
`http://localhost:28765` as the URL field in the integration configuration.

**Note**: This is a temporary solution, usage of which will render the Media Browser inoperable for motionEye. The full solution depends on the ongoing migration of this functionality to Home Assistant Core.

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
* [**Advanced**]: **Event binary sensor seconds** [default=30]: The number of
  seconds after a [motion or file store event](#events), after which the [binary
  sensor](#convenience-binary-sensors) turns off.

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

<a name="events"></a>
### Events

On receipt of a motion or file stored callbacks, events will be fired which can be used
in automations (etc).

#### Data in events

   * All event data includes the Home Assistant `device_id` for this motionEye
     camera device, and the Home Assistant device `name`.
   * Event data also includes as many [Motion Conversion
     Specifiers](https://motion-project.github.io/motion_config.html#conversion_specifiers)
     as make sense for that event type.
   * Any additional `&key=value` pairs added manually to the motionEye webhook
     (in the motionEye UI) will automatically propagate to the event data. If
     you manually tweak the web hook, remove the `src=hass-motioneye` parameter
     or the web hook will be overwritten.
   * For file storage events, the integration will automatically add
     `media_content_id` (an identifier that can be used to play the media in a
     Home Assistant media player) and `file_url` (a raw URL to the media). See
     [example automation](#automation-movies) below for an illustration of how
     this can be used.
   * `file_type` will be less than 8 if the media stored is an image, otherwise
     it is a movie/video. See [the motion
     source](https://github.com/Motion-Project/motion/blob/master/src/motion.h#L177)
     for more details.


<a name="motion-event"></a>
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
        "file_path": "/var/lib/motioneye/Camera2/2021-04-10/21-27-53.mp4",
        "file_type": "8",
        "media_content_id": "media-source://motioneye/74565ad414754616000674c87bdc876c#662aa1c77657dbc4af836abcdf80000a#movies#/2021-04-10/21-27-53.mp4",
        "file_url": "https://cctv/movie/2/playback/2021-04-10/21-27-53.mp4?_username=admin&_signature=bc4565fe414754616000674c87bdcacbd",
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

<a name="synthetic-binary-sensor"></a>
### Example event to binary_sensor conversion

Generate a synthetic binary sensor from an event:

```yaml
template:
  trigger:
    platform: event
    event_type: "motioneye.motion_detected"
    event_data:
      name: "<your_camera_name>"
  binary_sensor:
    - name: Event recently fired
      auto_off: 5
      state: "true"
```

The `device_id` and `camera_id` fields can also be used to differentiate cameras, see full [event contents](#motion-event) above.

See [related Home Assistant documentation](https://www.home-assistant.io/integrations/template/#turning-an-event-into-a-binary-sensor).

### Example event automation

Generate a notification from detected motion on the "Office" camera (note that name is case sensitive and should match the name of the camera in motionEye):

```yaml
trigger:
  platform: event
  event_type: "motioneye.motion_detected"
  event_data:
    name: "Office"
action:
  service: notify.<notifier>
  data:
    message: "Motion detected in the Office!"
    title: "Motion Detected"
```

<a name="convenience-binary-sensors"></a>
#### Convenience binary sensor entities

For convenience (e.g. UI display, entity state recording) binary sensor entities
(`binary_sensor.<name>_motion` and `binary_sensor.<name>_file_stored`) are
included to provide the equivalent on/off signal in entity form. The state of
the binary sensors resets after a configurable number of seconds (see
[options](#options) above).

Please see the [migration warning](#migration-warning) above.

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

<a name="automation-movies"></a>
### Automatically play stored movies

An automation to cast stored movie clips to a TV as they arrive.

```yaml
- alias: 'Cast motionEye movie clips'
  trigger:
    platform: event
    event_type: 'motioneye.file_stored'
    event_data:
      # Only cast video.
      file_type: '8'
  action:
    - service: media_player.play_media
      target:
        entity_id: media_player.kitchen_tv
      data:
        media_content_id: "{{ trigger.event.data.media_content_id }}"
        media_content_type: video
```

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
