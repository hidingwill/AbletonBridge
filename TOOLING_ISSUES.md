# AbletonBridge — Tooling Issues & Wishlist

Open issues and feature requests for the AbletonBridge MCP / plugin codebase.

**Resolved 2026-04-26:** master device insertion (`track_type` arg added), FabFilter detection in `get_plugin_info`, M4L capability reporting in `get_server_capabilities`.

**Resolved 2026-04-27:** `target_index` validation in `insert_device`, bulk `get_devices_by_name` tool added, `sample_track_meters` tool added for time-windowed peak/avg/silence audits.

**Resolved 2026-05-10:** `track_type` arg added to M4L parameter tools — `discover_device_params`, `get_device_hidden_parameters`, `set_device_hidden_parameter`, `batch_set_hidden_parameters`, `get_automation_states`, `set_parameter_clean` now accept `"track" | "return" | "master"`. M4L bridge bumped to v4.1.0; **Devicev2.amxd must be re-saved in Max** to pick up the JS change.

**Resolved 2026-05-10 (second pass):**
- `set_track_name` now accepts `track_type` — return tracks can be renamed (master may still error from Live's API, expected).
- `move_device` now accepts `dest_track_type` (defaults to source `track_type`) — moves between regular/return/master chains now resolve the destination correctly. The Remote Script handler also clamps `dest_position` to `0..len(devices)` with a clear error instead of the opaque Live API "internal error".
- **Requires Ableton Control Surface re-import** (toggle AbletonBridge off/on in Live → Preferences → Link/Tempo/MIDI, or restart Ableton) to pick up the Remote Script changes.

**Resolved 2026-05-15:**
- **Snapshot tool family now plumbs `track_type`** end-to-end. `snapshot_device_state`, `snapshot_all_devices`, `restore_device_snapshot`, `restore_group_snapshot`, `morph_between_snapshots` all accept `track_type` ("track" / "return" / "master"). Snapshot dicts now store `track_type` so restore/morph route to the right slot automatically. Backwards compatible with pre-2026-05-15 snapshots (fall back to `"track"`). `_m4l_batch_set_params` (in both `tools/devices.py` and `connections/m4l.py`) now accepts a `track_type` kwarg and passes it to `set_hidden_param`. Macro mappings can include an optional `track_type` field. Display strings in `list_snapshots` / `get_snapshot_details` now show the track type alongside index. No Remote Script or M4L changes — the bridge handlers already supported `track_type` from the 2026-05-10 pass; this fixed the gap in the MCP wrapper layer.
- **New `set_parameter_by_display` tool** (`MCP_Server/tools/devices.py`) lets the agent target a parameter by its human-readable display value instead of fitting normalization curves. Probes the param's min/max to determine direction, then binary-searches the 0..1 value range until the parsed display matches within tolerance (~0.1% of target or 0.01 absolute, whichever larger). Handles quantized params via value_items lookup. Capped at 20 iterations by default. Kills the "set 0.36 → got 525ms → try 0.09 → got 151ms" loops.
- **`get_plugin_info` FabFilter guidance corrected.** Previously promised that the M4L bridge could expose hidden FabFilter bands — it can't (both LOM and M4L paths read the same `device.parameters` array). Guidance now tells the agent the actual fix: click the Configure button in Ableton's device wrapper and add the parameters you want exposed. The `m4l_required` flag is no longer set for FabFilter (it was misleading).

---

## Known Live API limitations (not bridge bugs)

- **`move_device` cannot rearrange devices on the master track.** Live's LOM exposes `Song.move_device(device, master_track, pos)` but the C++ implementation refuses the operation and returns the opaque "Internal error". `Track` objects do not have a `move_device` method (only `Song` does), and `Live.Application.get_application().get_document().move_device(...)` is just `Song.move_device` via a longer path — same call. **Workaround: drag manually in the Live UI, or use `set_device_enabled` to bypass devices in place without reordering.**

---

## Open issues

- **Arrangement-clip MIDI notes not directly readable** — observed 2026-05-17. `get_clip_notes`, `get_clip_notes_with_ids`, `get_notes_extended` all take `(track_index, clip_index)` where `clip_index` is the session slot row. There's no equivalent reader for arrangement clips — `get_arrangement_clip_info` returns metadata only (start/end/length, loop bounds, signature, etc.) but no notes array. `analyze_note_content` claims to "analyze note content across arrangement clips" but returned `"No MIDI notes found in arrangement clips"` for tracks that visibly have populated MIDI arrangement clips (tested on the course project's HH C Tight and Kick tracks — may be a separate bug, or those clips really are empty placeholders). **Use case**: swing/timing analysis of arrangement-only clips for Todd Edwards / UKG workflows. **Fix**: add `get_arrangement_clip_notes(track_index, clip_index_in_arrangement, ...)` mirroring the session-clip note tools. Until then, workaround is to drag the arrangement clip into a session slot manually, then read.

- **Live 12.4 `SimplerDevice.replace_sample` not exposed** — observed 2026-05-17. Live 12.4 GA release notes (5 May 2026) added `replace_sample(absolute_path)` to the Simpler LOM API, letting agents programmatically reload a Simpler with a new audio file. **Direct relevance to Todd Edwards / UKG chop workflow**: would let the bridge rotate vocal chops on a single Simpler instance without dragging files. AbletonBridge's current Simpler surface (`simpler_sample_action` actions = reverse/crop/warp_as/warp_double/warp_half; `set_simpler_properties` ~20 params; `load_sample` loads onto a *track* not into an existing Simpler) does not cover this. **Fix**: add a new `replace_simpler_sample(track_index, device_index, sample_path, track_type="track")` tool wrapping `Live.SimplerDevice.SimplerDevice.replace_sample`. Should also handle the M4L path for hidden-state preservation. Tag for fork or upstream PR.

- **`load_instrument_or_effect` + `delete_device` causing Ableton 12.4 EXC_BREAKPOINT crashes mid-chain-modification** — observed 2026-05-16 during EQ swap drum sweep on Sam's "trynow.als" course-project session. Two separate crashes, both with identical signature:
  - Crash signal: `EXC_BREAKPOINT / SIGTRAP` (Ableton internal assertion, not a memory corruption)
  - Crashing thread: MainThread, deep inside Ableton's own callback machinery — top frames `LRoutable::OnTargetsChanged(ARemoteable*, TUpdate)` → `ATransport::OnAbletonLinkAudioChannelsChanged()` → `operator new()` → malloc
  - No plugin in the crashing stack — plugins appear in the loaded-images list only
  - **Crash 1 (14:48)**: sequence was — successful `delete_device` on Snare (track 3) EQ Eight at position 4 → cmd+S via computer-use → `load_instrument_or_effect` on Tap (track 10) for PSP ConsoleQ VST3 → Ableton crashed mid-load.
  - **Crash 2 (15:19, after recovery)**: project reopened cleanly, Clap+Snare ConsoleQ swaps intact, fresh first call of session was `load_instrument_or_effect` on Tap (track 10) → Ableton crashed again on the load.
  - **Common factor**: target track 10 (Tap), instrument = **ELECTRIBE-R** (Korg Collection VST3/AU). Other tracks with CR-78 CompuRhythm or TR-909 as the source plugin (Clap track 2, Snare track 3) accepted multiple `load_instrument_or_effect` + `delete_device` sequences in the same session without issue. Sample size of 2 isn't conclusive but the pattern is strong.
  - **Possible causes**:
    1. Race between bridge's `load_browser_item` and Ableton's `OnTargetsChanged` callback when the target track's input plugin is doing something async (ELECTRIBE-R may render or precache something on chain change)
    2. ELECTRIBE-R-specific plugin instance state that fails an internal assertion when the host adds another device behind it
    3. Cumulative session state — Ableton 12.4's chain-mutation invariants get fragile after N modifications via Remote Script (we did Clap delete → Snare delete → Tap load = third chain modification in the session)
  - **Cost to Sam**: ~15 crash-recovery cycles, ~30 min lost reopening Ableton. The crash dialog's "Recover crashed set?" path re-loads the corrupt state and crashes again, creating a tight loop. Manual fix was to quarantine `~/Library/Preferences/Ableton/Live 12.4/Crash/*_CrashRecoveryInfo.cfg` and `*_Undo/` so Ableton launches clean.
  - **Investigation candidates**: (a) repro on a stripped-down session with just ELECTRIBE-R + EQ Eight + try ConsoleQ load — does it still crash? (b) add a small settle delay (200-500 ms) before `load_instrument_or_effect` returns, after any `delete_device` in the same session, to let `OnTargetsChanged` callbacks drain. (c) check if Ableton 12.4 changed how Remote Script chain ops interact with the audio thread vs 12.3 (the audit doc says the project is on 12.4, the crash logs confirm `app_version: 12.4`).
  - **Mitigation for now**: do NOT use bridge `load_instrument_or_effect` or `delete_device` on tracks whose source plugin is ELECTRIBE-R until repro'd & fixed. Manual drag from Ableton's browser works fine.

- **`delete_device` doesn't accept `track_type`** — observed 2026-05-16 during AU→VST3 migration session. Calling `delete_device(track_index=1, device_index=0)` intending to delete the AU SuperPlate from Return B (return index 1) silently deleted **TR-909 from regular track 1 (Kick track)**. Same `track_index` value, different namespace; the tool defaults to the regular-tracks namespace because the schema has no `track_type` parameter. Caught and reverted via `undo` within ~30 seconds (TR-909 was restored intact). Classic foot-gun. **Fix**: add `track_type: "track" | "return" | "master"` arg to `delete_device` and plumb through the Remote Script. Same shape as the 2026-05-10 `move_device` / parameter-tool fixes. Until fixed: only use `delete_device` for regular tracks; for master/return, delete manually via Ableton GUI.

- **Parallel plugin loads can crash Ableton** — observed 2026-05-15 during EQ-swap Phase 2: firing 6 simultaneous `load_instrument_or_effect` calls (PSP ConsoleQ inserts on 6 different tracks) caused Ableton to crash mid-batch. 5 of 6 inserts had landed; the 6th came back as `ableton_connected: false`. Ableton itself crashed (not just the bridge connection). Likely cause: Ableton's Remote Script can't ingest many simultaneous device-load requests without choking. **Mitigation candidates**:
  1. Add an internal queue + small delay (50–100 ms) between sequential `load_instrument_or_effect` calls so the agent can fire them in parallel without worrying about the rate
  2. Add a `batch_load_devices(track_indices, uri)` compound tool that serializes internally
  3. Document the rate limit in the tool description and tell agents to chunk to ~2–3 parallel
  Same risk likely applies to `insert_device_by_name` for native devices but I haven't reproduced it there yet.

- **`load_instrument_or_effect` can fail with "Internal error" on specific plugins** — observed 2026-05-16 loading Soundtoys MicroShift VST3 via `query:Plugins#VST3:Soundtoys:MicroShift`. Browser cache listed it as `[loadable]`, two consecutive load attempts both returned `Command 'load_browser_item' failed after 2 attempts: Internal error`. Other Soundtoys VST3 plugins (Decapitator, EchoBoy, Radiator) loaded fine in the same session. Other PSP and Waves VST3s loaded fine via the same code path. Possible cause: Soundtoys iLok auth dialog blocking the load silently. **Workaround**: manual drag from the Ableton browser worked instantly. **Investigation candidate**: bridge could detect the failure pattern and surface a clearer error ("plugin may need first-launch auth — drag from browser once to clear, then retry MCP load").

- **Other M4L bridge tools still hardcode regular tracks** — chain tools (`discover_chains_m4l`, `get_chain_device_params_m4l`, `set_chain_device_param_m4l`, `get_chain_mixing`, `set_chain_mixing`, `rack_insert_chain_m4l`, `chain_insert_device_m4l`, `rack_store_variation`, `rack_recall_variation`), Simpler/Wavetable, AB compare, and split-stereo all still use `live_set tracks N devices M` paths in `m4l_bridge.js`. Same shape of fix as the parameter-tools resolution above. Lower priority — most users don't put racks/Simpler/Wavetable on master/return.

- ~~**`snapshot_device_state` doesn't accept `track_type`**~~ — **Resolved 2026-05-15**, see Recently shipped section.

---

## Feature wishlist

- **Read FabFilter EQ band info without M4L** — investigate whether parameters can be read via OSC, plugin state introspection, or preset XML inspection. Lower priority now that FabFilter detection clearly tells the agent to load M4L; would remove the M4L dependency entirely. Real research task — not a quick fix.

- ~~**Help agents map `value (0..1) ↔ display_value` per plugin parameter**~~ — Option 2 (`set_parameter_by_display`) **Resolved 2026-05-15**, see Recently shipped section. Option 1 (`sample_parameter_curve`) still on the wishlist for batch workflows where the curve will be reused.

- **Real research: read FabFilter band info / VST plugin internal state** — once a user has not Configured the relevant params, neither the LOM `device.parameters` nor the M4L `plugin~` path can see the FabFilter band positions, EQ curves, frequency/gain/Q values, etc. The state lives in a proprietary binary blob inside the plugin's VST chunk. Three possible routes, all heavyweight:
  1. **Preset XML / VST chunk parsing** — extract the chunk from the `.als` (gzipped XML) and decode FabFilter's binary format. Format isn't documented; would need reverse engineering. Highest payoff (works for FabFilter, Roland Cloud, Korg, etc.) but largest effort.
  2. **UI accessibility scraping via computer-use** — read the rendered GUI to extract band positions. Brittle to plugin updates; coordinate-dependent; slow. Already implicitly used for one-off debugging today.
  3. **Extend M4L bridge to enumerate `plugin~` host parameters** — Max's `plugin~` object exposes a `params` message that lists ALL VST/AU parameters, not just Configured ones. Currently `m4l_bridge.js` only uses `plugin~` for audio analysis. Cross-track access from the bridge device to another track's `plugin~` instance is non-trivial — needs LiveAPI patcher navigation. Moderate effort but most architecturally clean. Spent the 2026-05-15 session being unable to verify Pro-Q 4 band state or instrument patch names; this remains the highest-leverage unresolved blocker.

---

## Recently shipped (this session)

### `target_index` validation in `insert_device` ✅ 2026-04-27

The Live API's "Internal error" on out-of-range `target_index` is now caught up-front in the Remote Script. Valid range is `[0, len(track.devices)]` inclusive. Out-of-range calls return a clear error: `"target_index N out of range — track 'X' has K device(s), so valid target_index is 0..K. Use None or omit target_index to insert at end of chain."` plus `device_count` and `valid_target_index_range` fields on the response.

### `get_devices_by_name` ✅ 2026-04-27

New MCP tool that walks regular tracks + return tracks + master in one pass and returns every device matching a name string. Substring match, case-insensitive by default. Returns `{track_type, track_index, track_name, device_index, device_name, class_name, parameter_count}` per match. Replaces N round-trips with 1 — ideal for "find every Utility and read its Width" audits.

Example: `get_devices_by_name(name="Utility")` → returns every Utility on every track plus their devices indices ready to feed into `get_device_parameters`.

### `sample_track_meters` ✅ 2026-04-27

New MCP tool that samples `output_meter_left` / `output_meter_right` over a time window (default 1 second, max 5 s) at a configurable interval (default 50 ms ≈ 20 Hz). Returns peak / avg / min for L and R per track plus an `is_silent` flag (peak < 0.001 ≈ -60 dBFS). Optional `include_returns` and `include_master` flags.

Use this during playback for "which tracks are actually contributing" audits — a single `get_track_meters` reading at the wrong moment can mis-label a transient track as silent.

- **Ableton 12.4 EXC_BAD_ACCESS in `TDetailViewUi::OnDeviceDetailOpenStateChangedInMainWindow` on `load_instrument_or_effect`** — observed 2026-05-16 19:49 during EQ swap drum sweep on Sam's `trynow2.als`. Sequence: bridge `load_instrument_or_effect` for PSP ConsoleQ on Maracas (track 11, source = **CR-78 CompuRhythm, NOT ELECTRIBE-R**) → Live crashed immediately.
  - Crash signal: `EXC_BAD_ACCESS / SIGSEGV` (KERN_INVALID_ADDRESS at `0x25` — null-pointer-ish small offset)
  - Crashing thread: MainThread (com.apple.main-thread)
  - Top symbolicated frame: `void ableton::utility::detail::CallbackTypes<TDetailViewUi, void, ARemoteable*, ARemoteableTypes::TUpdate>::CallMemberFunc<&TDetailViewUi::OnDeviceDetailOpenStateChangedInMainWindow(ARemoteable*, ARemoteableTypes::TUpdate)>`
  - Stack contains `boost::python::detail::translate_exception<...>` frames → the call came in via the Python Remote Script, so the bridge's `load_instrument_or_effect` was the trigger
  - **Different signature from the ELECTRIBE-R / LRoutable::OnTargetsChanged crash** logged earlier — this is the Detail View null-pointer path, and **it fires on non-ELECTRIBE-R source plugins**. CR-78 is no safer than ELECTRIBE-R under this bug.
  - **Mitigation**: don't use bridge `load_instrument_or_effect` on the trynow2.als project at all. Have the user manually drag instruments/effects from Ableton's browser. Bridge `set_device_parameter` / `set_device_parameters` / `set_parameter_by_display` / `set_device_enabled` are safe (confirmed across Maracas, Conga, Clav, Tap chain swaps in the same session).

- **Ableton 12.4 EXC_BREAKPOINT in `NSThemeFrame setTitle:` / `NSConcreteMapTable grow` on Cmd+S** — observed 2026-05-16 21:01 on `trynow2.als`. User hit Cmd+S; Live crashed during the window-title-bar update that Cocoa performs when the document's modified flag changes after save. Stack:
  - `NSConcreteMapTable grow` → `NSDisplayCycle addObserver:` → `NSWindow _updateStructuralRegionsOnNextDisplayCycle` → `NSFrameView addSubview:` → `NSThemeFrame addSubview:` → `NSThemeFrame _addKnownSubview:` → `NSThemeFrame _updateTitleTextField` → `NSThemeFrame _tileTitlebarAndRedisplay:` → `NSTitledFrame _titleDidChange` → `NSTitledFrame setTitle:subtitle:` → `NSThemeFrame setTitle:` → `NSFrameView _updateTitleProperties:animated:` → `NSThemeFrame _updateTitleProperties:animated:`
  - This is **AppKit / macOS code**, not Live code. Triggered by a Cmd+S after a long session of bridge-mediated edits. The save itself eventually completed when Live respawned and re-saved on recovery (file modified time `21:03` two minutes after crash at `21:01`).
  - Likely a macOS 26.3 (build 25D125) AppKit regression — see [Apple Feedback / forums](https://forums.developer.apple.com/) for similar reports. Not directly attributable to the bridge, but the long bridge-mediated edit chain probably stresses Live's title-bar refresh path.
  - **Mitigation**: nothing the bridge can do directly. Save more often during long sessions so any single crash loses less work. Keep crash-recovery quarantine procedure in mind (see 2026-05-16 ELECTRIBE-R entry).

