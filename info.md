# motionEye Home Assistant Integration

The motionEye integration allows you to integrate your [motionEye](https://github.com/ccrisan/motioneye) server into Home Assistant. motionEye is an open source web-frontend for the motion daemon, used to centralize the management and visualization of multiple types of camera.

See [repository](https://github.com/dermotduffy/hass-motioneye) for more information.

<div style="clear: both"></div>

## Features

   * Dynamic motionEye camera addition/removal.
   * View motionEye MJPEG video streams as HA camera entities with no additional configuration.
   * Control major motionEye camera options as HA switch entities.
   * Camera motion detection events, and file (image or movie) storage events propagate into
     HA events which can be used in automations.
   * Custom services to set camera overlay text, to trigger motionEye snapshots, and to perform
     arbitrary configured [motionEye Action
     Buttons](https://github.com/ccrisan/motioneye/wiki/Action-Buttons).

## Screenshot

<img
src="https://github.com/dermotduffy/hass-motioneye/blob/main/images/screenshot-motioneye-device.png?raw=true"
alt="hass-motioneye screenshot"
style="max-width: 200px; width: 100%" />

[![BuyMeCoffee][buymecoffee_badge]][buymecoffee]
---
[buymecoffee]: https://www.buymeacoffee.com/dermotdu
[buymecoffee_badge]:
https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square
