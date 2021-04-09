# motionEye Home Assistant Integration

[![GitHub Release][releases_badge]][releases]
[![Build Status][build_badge]][build]
[![Test Coverage][coverage_badge]][coverage]
[![License][license_badge]](LICENSE)
[![hacs][hacs_badge]][hacs]
[![BuyMeCoffee][buymecoffee_badge]][buymecoffee]

<img src="https://github.com/dermotduffy/hass-motioneye/blob/main/motioneye.png"
     alt="motionEye icon"
     width="10%"
     align="right" />

The motionEye integration allows you to integrate your
[motionEye](https://github.com/ccrisan/motioneye) server into Home Assistant. motionEye
is an open source web-frontend for the motion daemon, used to centralize the management
and visualization of multiple types of camera.

## Installation

Use [HACS](https://hacs.xyz/) to install.

```
Home Assistant > HACS > Integrations > "Explore & Add Integrations" > motionEye
```

## Usage

### Entities

| Platform        | Description                                                               |
| --------------- | ------------------------------------------------------------------------- |
| `camera`        | An MJPEG camera that shows the motionEye video stream.                     |
| `switch`        | Switch entities to enable/disable motion detection, text overlay, video streaming, still image capture and movie capture. |

Notes:
   * If the video streaming switch is turned off, the camera entity will become unavailable (but the rest of the integration will continue to work).
   * As cameras are added or removed to motionEye, devices/entities are automatically added or removed from Home Assistant.

### Events

On receipt of a motion callback, an event will be fired which can be used in automations (etc). Example event:

```json
{
    "event_type": "motioneye.motion_detected",
    "data": {
        "device_id": "localhost:8765_2",
        "name": "Office"
    },
    "origin": "LOCAL",
    "time_fired": "2021-03-05T02:11:07.334122+00:00",
    "context": {
        "id": "ba692123787e03911779baa36ee1d333",
        "parent_id": null,
        "user_id": null
    }
}
```

### Services

#### motioneye.set_text_overlay

Parameters:

| Parameter       | Description                                                               |
| --------------- | ------------------------------------------------------------------------- |
| `entity_id` `device_id` |An entity id or device id to set the text overlay on.|
| `left_text` `right_text`| One of `timestamp`, `camera-name`, `custom-text` or `disabled` to show a timestamp, the  name of the camera, custom text or nothing at all, on the left or right-hand side.|
| `custom_left_text` `custom_right_text`| Custom text to show on the left or right, if the `custom-text` value is selected.|

Note:
   * Calling this service triggers a reset of the motionEye cameras which will pause the stream / recordings / motion detection (etc).

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

## Credits

Thanks to [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom
Component
Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component)
template which was used for the initial skeleton of this component.

---

[build_badge]: https://img.shields.io/github/workflow/status/dermotduffy/hass-motioneye/Build
[build]: https://github.com/dermotduffy/hass-motioneye/actions/workflows/tests.yaml
[coverage_badge]: https://img.shields.io/codecov/c/gh/dermotduffy/hass-motioneye?style=flat-square
[coverage]: https://app.codecov.io/gh/dermotduffy/hass-motioneye/
[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[buymecoffee]: https://www.buymeacoffee.com/dermotdu
[buymecoffee_badge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square
[hacs]: https://hacs.xyz
[hacs_badge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square
[motioneyelogo]: motioneye.png
[license_badge]: https://img.shields.io/github/license/dermotduffy/hass-motioneye.svg?style=flat-square
[releases_badge]: https://img.shields.io/github/release/dermotduffy/hass-motioneye.svg?style=flat-square
[releases]: https://github.com/dermotduffy/hass-motioneye/releases
