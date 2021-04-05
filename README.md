# motionEye component

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

<img src="motioneye.png"
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

### Services

#### motioneye.set_text_overlay

Parameters:

| Parameter       | Description                                                               |
| --------------- | ------------------------------------------------------------------------- |
| `entity_id` / `device_id` |An entity id or device id to set the text overlay on.|
| `left_text` / `right_text`| One of `timestamp`, `camera-name`, `custom-text` or `disabled` to show a timestamp, the  name of the camera, custom text or nothing at all, on the left or right-hand side.|
| `custom_left_text` / `custom_right_text`| Custom text to show on the left or right, if the `custom-text` value is selected.|

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

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[black]: https://github.com/psf/black
[buymecoffee]: https://www.buymeacoffee.com/dermotdu
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=plastic
[motioneyelogo]: motioneye.png
[license-shield]: https://img.shields.io/github/license/dermotduffy/hass-motioneye.svg?style=flat
[releases-shield]: https://img.shields.io/github/release/dermotduffy/hass-motioneye.svg?style=flat
[releases]: https://github.com/dermotduffy/hass-motioneye/releases
