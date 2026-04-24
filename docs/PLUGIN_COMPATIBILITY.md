# Plugin Compatibility Guide

## Overview

AbletonBridge can interact with native Ableton devices, Max for Live devices, and third-party VST/VST3/AU plugins. However, the level of control varies significantly by plugin type.

## Device Types

### Native Ableton Devices (Full Support)
- **Parameter access**: All parameters exposed and controllable
- **Presets**: Can browse and load presets from Ableton's browser
- **Special features**: Device-specific tools available (EQ Eight bands, Compressor sidechain, Simpler controls, etc.)
- **Examples**: EQ Eight, Compressor, Wavetable, Drift, Operator, Analog, Collision

### Max for Live Devices (Extended Support via M4L Bridge)
- **Parameter access**: All parameters exposed through Live API + hidden parameters via M4L bridge
- **Presets**: Can browse and load from Ableton's browser
- **Special features**: Direct access to internal state via the M4L bridge device
- **Requirements**: M4L bridge device must be installed and active
- **Examples**: Any .amxd device

### VST3 Plugins (Partial Support)
- **Parameter access**: First 128 parameters exposed by default through Live API
- **Configure mode**: Use Ableton's Configure mode to expose additional parameters (up to the host limit)
- **Presets**: Internal plugin presets are NOT accessible via the API. Only Ableton .fxp/.vstpreset files in the browser are visible
- **Known limitation**: Parameter names may differ from the plugin's own UI labels

### VST2 Plugins (Limited Support)
- **Parameter access**: Similar to VST3, first 128 parameters by default
- **Configure mode**: Same as VST3
- **Presets**: Internal bank/program presets NOT accessible
- **Note**: VST2 is deprecated; prefer VST3 when available

### Audio Units (macOS only) (Partial Support)
- **Parameter access**: Parameters exposed through Live's AU wrapper
- **Configure mode**: Available for exposing additional parameters
- **Presets**: Internal AU presets NOT accessible via the API
- **Note**: Only available on macOS

## Parameter Access Patterns

### Accessing More Than 128 Parameters

By default, Ableton exposes a limited set of parameters for third-party plugins. To access more:

1. **In Ableton**: Click the "Configure" button on the device title bar
2. **Touch parameters**: Click on parameters in the plugin UI while Configure is active
3. **Parameters become visible**: They'll now appear in the Remote Script's parameter list
4. **Save the Live Set**: Configuration is saved per-device-instance

### Working with Plugin Parameters

```
# Get all exposed parameters
get_device_parameters(track_index=0, device_index=0)

# Set a parameter by name (must be exposed/configured)
set_device_parameter(track_index=0, device_index=0, parameter_name="Cutoff", value=0.75)

# For real-time parameter changes, use the UDP interface
# (no round-trip overhead, fire-and-forget)
```

## Known-Good Patterns for Popular Plugins

### Serum (VST3)
- Most macro parameters are exposed by default
- Use Configure mode for oscillator and filter parameters
- Wavetable position is typically available as a macro

### Fabfilter Pro-Q 3 (VST3)
- Band parameters are exposed in groups
- Use Configure for per-band gain/frequency/Q
- Global output gain usually available by default

### Kontakt (VST3)
- Macro knobs are exposed by default
- Internal instrument parameters require Configure mode
- Note: Some parameters may not respond to automation

### Omnisphere (VST2/VST3)
- Macro controls exposed by default
- Layer parameters require extensive Configure setup
- Recommend using the VST3 version when available

## Troubleshooting

### "Parameter not found" errors
1. Check if the parameter is exposed: `get_device_parameters()`
2. If not listed, use Configure mode in Ableton to expose it
3. Parameter names are case-sensitive and must match exactly

### Sidechain not working with plugins
- Use `set_compressor_sidechain(source_track_name="...")` for native Compressor/Glue Compressor
- For VST plugin sidechaining, set up routing in Ableton's I/O section manually
- Some plugins handle sidechain internally (not through Live's routing)

### Plugin parameters reset on reload
- This is a known Live behavior for some plugins
- Save parameter states using `save_snapshot()` as a backup
- Use `batch_set_mixer()` or macros for quick recall

## Limitations Summary

| Feature | Native | M4L | VST3 | VST2 | AU |
|---------|--------|-----|------|------|-----|
| Parameter read | All | All + hidden | 128+ with Configure | 128+ with Configure | 128+ with Configure |
| Parameter write | Yes | Yes | Yes (exposed only) | Yes (exposed only) | Yes (exposed only) |
| Browse presets | Yes | Yes | No (internal) | No (internal) | No (internal) |
| Load presets | Yes | Yes | .vstpreset only | .fxp only | No |
| Sidechain | Yes | Yes | Varies | Varies | Varies |
| Device-specific tools | Yes | Via bridge | No | No | No |
