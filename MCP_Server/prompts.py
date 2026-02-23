"""MCP prompt templates for guided Ableton workflows."""


def register_prompts(mcp):
    """Register all MCP prompts with the server instance."""

    @mcp.prompt()
    def create_beat(genre: str = "electronic", bpm: int = 120, bars: int = 4) -> str:
        """Guided drum pattern creation workflow."""
        return f"""Create a {genre} drum beat at {bpm} BPM, {bars} bars long.

Follow these steps:
1. First, check current session with get_session_info
2. Set tempo to {bpm} using set_tempo
3. Create a new MIDI track using create_instrument_track with a Drum Rack
4. Create a {bars * 4}-beat clip using create_clip
5. Generate an appropriate {genre} drum pattern:
   - For electronic: four-on-the-floor kick, offbeat hi-hats, snare on 2 and 4
   - For hip-hop: syncopated kick, heavy snare, sparse hi-hats
   - For jazz: ride cymbal swing, ghost notes on snare, kick accents
   - For rock: steady kick-snare, open/closed hi-hats
6. Add notes using add_notes_to_clip with appropriate velocities and timing
7. Set clip name to "{genre} beat {bpm}bpm"
8. Fire the clip to preview

Use humanized velocities (not all 127) for a natural feel."""

    @mcp.prompt()
    def mix_track(track_name: str = "") -> str:
        """Structured mixing workflow for a track."""
        target = f"track '{track_name}'" if track_name else "the selected track"
        return f"""Mix {target} following this structured workflow:

## Step 1: Assess
- Use get_full_session_state to see all tracks and current mixer settings
- Identify {target} and note its current volume, pan, and devices

## Step 2: Gain Staging
- Set volume to approximately 0.7 (about -3dB) as a starting point
- Use set_track_volume to adjust

## Step 3: EQ
- Load "EQ Eight" using load_instrument_or_effect if not already present
- Cut low frequencies below 80Hz for non-bass instruments
- Address any muddy frequencies (200-500Hz)
- Add presence (2-5kHz) or air (10kHz+) as needed

## Step 4: Dynamics
- Load "Compressor" for dynamic control
- Set threshold, ratio, attack, and release appropriate to the source material
- For vocals: moderate ratio (3:1), medium attack
- For drums: fast attack for punch, or slow attack for transient preservation

## Step 5: Spatial Placement
- Set pan position using set_track_pan based on arrangement needs
- Consider adding send to a reverb return for depth
- Use setup_send_return if a reverb bus doesn't exist yet

## Step 6: Review
- Use get_device_parameters to verify all settings
- Listen in context with other tracks"""

    @mcp.prompt()
    def sound_design(instrument: str = "Wavetable") -> str:
        """Parameter exploration guide for sound design."""
        return f"""Explore and design a sound using {instrument}.

## Setup
1. Create a new MIDI track with create_instrument_track using "{instrument}"
2. Get all device parameters with get_device_parameters to see available controls
3. Create a test clip (2 bars, simple chord or melody) for auditioning

## Design Process
For {instrument}, explore these parameter categories:

### Oscillator Section
- Examine oscillator type/shape parameters
- Try different waveforms and adjust pitch/detune

### Filter Section
- Find filter frequency and resonance parameters
- Sweep the filter to find sweet spots
- Try different filter types (LP, HP, BP)

### Modulation
- Look for LFO and envelope parameters
- Map modulation to filter frequency for movement
- Adjust envelope attack/decay/sustain/release

### Effects
- Check for built-in effects (chorus, delay, reverb)
- Add external effects with apply_effect_chain if needed

## Workflow
1. Adjust one parameter at a time using set_device_parameter
2. After each change, describe what the parameter does and how it affects the sound
3. Build up the patch incrementally
4. Name the track descriptively when done"""

    @mcp.prompt()
    def arrange_section(bars: int = 8, genre: str = "electronic") -> str:
        """Arrangement section creation workflow."""
        return f"""Create a {bars}-bar {genre} arrangement section.

## Planning
1. Get current session state with get_full_session_state
2. Identify existing tracks and their roles
3. Plan which tracks should play in this {bars}-bar section

## Building Blocks (create if needed)
- **Drums**: Use create_instrument_track + create_clip_with_notes for rhythm
- **Bass**: Create bass track with appropriate synth
- **Harmony**: Chords or pads for harmonic foundation
- **Melody**: Lead or melodic element

## Arrangement Rules for {genre}
- Start sections with drums establishing the groove
- Layer instruments progressively (add elements every 2-4 bars for builds)
- Use filter automation for transitions (create_clip_automation)
- Vary velocities between sections for dynamics

## Implementation
For each track in the section:
1. Create or select the appropriate clip slot
2. Write the musical content (notes, grid patterns)
3. Set appropriate volume levels with batch_set_mixer
4. Add automation for movement and interest

## Finishing
- Name all clips descriptively (e.g., "Verse Drums", "Chorus Bass")
- Set scene name for the section
- Review with get_full_session_state"""
