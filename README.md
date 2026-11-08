## Metro Exodus VR

<p align="center">
  <img src="https://github.com/RippeR37/MetroExodusVR/blob/master/resources/header.png?raw=true" alt="Metro Exodus VR header"/>
</p>

<p align="center">
  <a href="https://buymeacoffee.com/RippeR37"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee" /></a>
  <a href="https://ko-fi.com/RippeR37"><img src="https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi" /></a>
</p>

A VR mod for **Metro Exodus**, bringing the game to Virtual Reality with
motion-controlled interactions, VR-specific mechanics, and a range of features
designed to make the experience feel natural and immersive.

The project aims to provide a complete VR experience while preserving the
atmosphere, gameplay, and visual quality of the original game.

## Features

- Full 6DoF support.
  - Room scale, standing or seated.
- Stereo and optimized AER/AFW rendering.
- Support for DLAA/DLSS up to 4.5 and FSR2.
- Motion-controlled gameplay and interactions.
  - Also supports playing with keyboard + mouse or non-VR controllers.
- Manual weapons handling and reloading with custom animations and poses.
- Support for left-handed players.
- Many performance optimizations, comfort settings and user experience features.
  - Foveated Upscaling and Foveated Rendering to name the few.
- (Experimental) bHaptics support.
- Auto-update mechanism.

> [!NOTE]
> Currently the beta supports only the main campaign. The DLCs will be available
> in VR at later version.

## Requirements and compatibility

**Currently only Standard Edition of Metro Exodus is supported.** Later support
for Enhanced Edition has not been decided yet.

| Store | Supported Versions        |
| ----- | ------------------------- |
| Steam | `1.0.0.7` (latest)        |
| Epic  | Work in progress (latest) |
| GOG   | Work in progress (latest) |

> [!IMPORTANT]
> Only legitimate copies of Metro Exodus are supported by this project.

## Installation

1. Download the latest release from the [Releases](https://github.com/RippeR37/MetroExodusVR/releases) page.
2. Extract the downloaded archive.

## Launching the game in VR

1. Ensure your store's launcher (if any) is running (Steam/Epic)
2. Ensure your VR runtime is running (SteamVR/VDXR/...)
3. Start `MetroExodusVR.exe`

> [!CAUTION]
> After starting the game please ensure it is focused, otherwise you might have
> performance or functionality issues like not being able to click anything with
> controller's pointer.

## Updates

The mod supports self-updating by downloading newer releases from this
repository, if any exists. At first startup you can configure it to:

- Update the mod for you automatically.
  - You will still receive notifications after each update.
- Ask you each time a new version is found.
- Disable automatic updates.

You can change this at any later point by e.g. removing `updater.json` config
file which will trigger this dialog again.

## Controls

The mod uses VR-specific controls designed around motion controllers.

| Action      | Default binding              |
| ----------- | ---------------------------- |
| Move        | Left stick                   |
| Turn        | Right stick (left/right)     |
| Interact    | Grip (or left A/X)           |
| Fire weapon | Right trigger                |
| Reload      | Manual (trigger) or left B/Y |
| Crouch      | Right stick (down)           |
| Sprint      | Left stick up and up again   |
| Pause Menu  | Menu / right thumbstick      |
| Recenter    | Hold menu Pause Menu button  |

You can rebind your controls in game's `Options`, `Controls`, `Controller` and
`Configure Custom Layout`.

Furthermore the mod puts your equipment on your body and requires some VR
interactions e.g. to put on/off gas mask, change its filter, apply medkit, etc.

You will find more precise instructions with precise instructions and buttons
matching your current bindings in `VR HINTS` tab in Pause Menu.

## Configuration

All configuration is available in `VR` tab inside `Options` menu which is
accessible both Main Menu and Pause Menu.

Configuration options are grouped into these tabs:

- Game
- Graphics
- Movement
- Body
- Hands
- Weapons
- Scopes
- Interface
- Comfort

The mod shares save games with the flat version of the game and stores your
preferences in a separate file (`user_vr.cfg`) **which is synchronized with
Steam**.

Configuration file location: `%USERPROFILE%\Saved Games\Metro Exodus\`.

## Performance

A lot of effort was spent to ensure widest range of players can play this game
in VR smoothly. If you're having trouble maintaining smooth playback consider:

* [VR] enabling DLSS or FSR
* [VR] enabling Foveated Upscaling
* [game] reducing quality preset
* [game] disabling tesselation
* [VR] enabling Foveated Rendering
* [VR] enabling `Performance (AER+)` mode
* [VR] reducing rendering resolution for the game in your VR runtime

## Help needed / bug reporting

For bug reporting please either:

* create an Issue in this repository
* report a bug in [**mod's Discord server**](https://discord.gg/zxtcdbTjDF)

If you need help or would like to provide feedback about the mod, check out:

* [**mod's Discord server**](https://discord.gg/zxtcdbTjDF)
  * be sure to check out [#how-to-play channel](https://discord.com/channels/1562224649474023444/1562995572745437334)
* [**mod's thread**](https://discord.com/channels/747967102895390741/1555645599767068672) in [Flat2VR Discord server](https://discord.gg/hEgHvT3PQp)

## Russian translation

This fork adds a Russian translation of the in-game menus, VR settings, hints
and popups. It patches `MetroExodusVR.dll` without touching the game's own files
and pins the mod version so an automatic update cannot replace the translated
DLL. See [`ru/README.md`](ru/README.md) for installation and update
instructions (in Russian).

## Uninstallation

To uninstall simply remove the files you extracted during the installation.

## Support

If you like my work you can support this and my other/future projects here:

<a href="https://buymeacoffee.com/RippeR37"><img src="https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee" /></a>

<a href="https://ko-fi.com/RippeR37"><img src="https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi" /></a>

## Disclaimer

This project is a community-made modification and is not affiliated with,
endorsed by, or supported by 4A Games or Deep Silver.

Metro Exodus and all related assets, trademarks, and intellectual property
belong to their respective owners.
