# AbletonBridge — Open Issues & Wishlist

Active backlog. Shipped fixes are in [`TOOLING_CHANGELOG.md`](TOOLING_CHANGELOG.md). Long crash forensics with stack traces are in [`INVESTIGATION_LOG.md`](INVESTIGATION_LOG.md). The course-project post-mortem (driving most of the safety guidance below) is in [`docs/POSTMORTEM_2026-05-18_course-project.md`](docs/POSTMORTEM_2026-05-18_course-project.md).

---

## Known Live API limitations (not bridge bugs)

- **`move_device` cannot rearrange devices on the master track.** Live's LOM exposes `Song.move_device(device, master_track, pos)` but the C++ implementation refuses the operation and returns the opaque "Internal error". `Track` objects do not have a `move_device` method (only `Song` does), and `Live.Application.get_application().get_document().move_device(...)` is just `Song.move_device` via a longer path — same call. **Workaround:** drag manually in Live's UI, or use `set_device_enabled` to bypass devices in place without reordering.

---

## Open issues

### Crash-class issues (Live 12.4 / macOS 26.x chain-mutation race)

Three documented crash signatures, same underlying race in Live's chain-mutation path. See [`INVESTIGATION_LOG.md`](INVESTIGATION_LOG.md) for full stack traces and timeline.

- **`load_instrument_or_effect` + `delete_device` triggering EXC_BREAKPOINT mid-chain-modification** — fires on dense sessions, multiple plugins implicated (ELECTRIBE-R, CR-78). Heap corruption during async chain mutation. Not fixed by macOS 26.5.
- **`load_instrument_or_effect` triggering EXC_BAD_ACCESS in `TDetailViewUi::OnDeviceDetailOpenStateChangedInMainWindow`** — null-pointer path through the Detail View update; different signature, same underlying race.
- **EXC_BREAKPOINT in `NSThemeFrame setTitle:` on Cmd+S after long edit sessions** — AppKit-level, macOS 26.3 regression. The bridge stresses the path but doesn't cause it directly.

**Mitigation (in use):** read-only default; manual drag from Ableton's browser for device add/remove/move; transport stopped before any chain change; save every ~10 min; quarantine `~/Library/Preferences/Ableton/Live 12.4/Crash/*_CrashRecoveryInfo.cfg` and `*_Undo/` on first crash. Full policy: `~/Library/Audio/Plug-Ins/music-production-assistant/knowledge/safety-tooling-policy.md`.

**Investigation candidates if anyone wants to dig:**
1. Repro on a stripped-down session with a single instrument + EQ Eight + try a ConsoleQ load → does it still crash? Isolates whether session density is required.
2. Add a small settle delay (200–500 ms) before `load_instrument_or_effect` returns, after any `delete_device` in the same session, to let `OnTargetsChanged` callbacks drain.
3. Compare Ableton 12.3 → 12.4 changes to how Remote Script chain ops interact with the audio thread.

---

### `delete_device` doesn't accept `track_type`

Observed 2026-05-16 during AU→VST3 migration. Calling `delete_device(track_index=1, device_index=0)` intending to delete the AU SuperPlate from Return B (return index 1) silently deleted **TR-909 from regular track 1 (Kick track)**. Same `track_index` value, different namespace; the tool defaults to the regular-tracks namespace because the schema has no `track_type` parameter. Caught and reverted via `undo` within ~30 seconds.

Classic foot-gun. **Fix:** add `track_type: "track" | "return" | "master"` arg to `delete_device` and plumb through the Remote Script. Same shape as the 2026-05-10 `move_device` / parameter-tool fixes (see changelog). Until fixed: only use `delete_device` for regular tracks; for master/return, delete manually via Ableton GUI.

---

### Parallel plugin loads can crash Ableton

Observed 2026-05-15 during EQ-swap Phase 2: firing 6 simultaneous `load_instrument_or_effect` calls (PSP ConsoleQ inserts on 6 different tracks) caused Ableton to crash mid-batch. 5 of 6 inserts had landed; the 6th came back as `ableton_connected: false`. Ableton itself crashed (not just the bridge connection). Likely cause: Ableton's Remote Script can't ingest many simultaneous device-load requests without choking.

**Mitigation candidates:**
1. Add an internal queue + small delay (50–100 ms) between sequential `load_instrument_or_effect` calls so the agent can fire them in parallel without worrying about the rate
2. Add a `batch_load_devices(track_indices, uri)` compound tool that serializes internally
3. Document the rate limit in the tool description and tell agents to chunk to ~2–3 parallel

Same risk likely applies to `insert_device_by_name` for native devices but hasn't been reproduced there yet.

---

### `load_instrument_or_effect` can fail with "Internal error" on specific plugins

Observed 2026-05-16 loading Soundtoys MicroShift VST3 via `query:Plugins#VST3:Soundtoys:MicroShift`. Browser cache listed it as `[loadable]`, two consecutive load attempts both returned `Command 'load_browser_item' failed after 2 attempts: Internal error`. Other Soundtoys VST3 plugins (Decapitator, EchoBoy, Radiator) loaded fine in the same session. Other PSP and Waves VST3s loaded fine via the same code path.

**Possible cause:** Soundtoys iLok auth dialog blocking the load silently.

**Workaround:** manual drag from the Ableton browser worked instantly.

**Investigation candidate:** bridge could detect the failure pattern and surface a clearer error ("plugin may need first-launch auth — drag from browser once to clear, then retry MCP load").

---

### Arrangement-clip MIDI notes not directly readable

Observed 2026-05-17. `get_clip_notes`, `get_clip_notes_with_ids`, `get_notes_extended` all take `(track_index, clip_index)` where `clip_index` is the session slot row. There's no equivalent reader for arrangement clips — `get_arrangement_clip_info` returns metadata only (start/end/length, loop bounds, signature, etc.) but no notes array.

`analyze_note_content` claims to "analyze note content across arrangement clips" but returned `"No MIDI notes found in arrangement clips"` for tracks that visibly have populated MIDI arrangement clips (tested on the course project's HH C Tight and Kick tracks — may be a separate bug, or those clips really are empty placeholders).

**Use case:** swing/timing analysis of arrangement-only clips for Todd Edwards / UKG workflows.

**Fix:** add `get_arrangement_clip_notes(track_index, clip_index_in_arrangement, ...)` mirroring the session-clip note tools. Until then, workaround is to drag the arrangement clip into a session slot manually, then read.

---

### Live 12.4 `SimplerDevice.replace_sample` not exposed

Observed 2026-05-17. Live 12.4 GA release notes (5 May 2026) added `replace_sample(absolute_path)` to the Simpler LOM API, letting agents programmatically reload a Simpler with a new audio file. **Direct relevance to Todd Edwards / UKG chop workflow:** would let the bridge rotate vocal chops on a single Simpler instance without dragging files.

AbletonBridge's current Simpler surface (`simpler_sample_action` actions = reverse/crop/warp_as/warp_double/warp_half; `set_simpler_properties` ~20 params; `load_sample` loads onto a *track* not into an existing Simpler) does not cover this.

**Fix:** add a `replace_simpler_sample(track_index, device_index, sample_path, track_type="track")` tool wrapping `Live.SimplerDevice.SimplerDevice.replace_sample`. Should also handle the M4L path for hidden-state preservation. Tag for fork or upstream PR.

**Status (2026-05-19):** Covered upstream by **Producer Pal v1.4.8+** — `ppal-update-device` now accepts a Simpler `replace_sample` action on Live 12.4+. See `.planning/research/UPSTREAM.md` §Producer Pal v1.4.8-pre1 (Bug fixes / Developer changes). AbletonBridge implementation remains desirable for parity but is **not blocking** — agents needing this feature today should route through Pal per `.planning/research/BRIDGE_PAL_ROUTING.md` §Chain mutation section.

---

### Other M4L bridge tools still hardcode regular tracks

Chain tools (`discover_chains_m4l`, `get_chain_device_params_m4l`, `set_chain_device_param_m4l`, `get_chain_mixing`, `set_chain_mixing`, `rack_insert_chain_m4l`, `chain_insert_device_m4l`, `rack_store_variation`, `rack_recall_variation`), Simpler/Wavetable, AB compare, and split-stereo all still use `live_set tracks N devices M` paths in `m4l_bridge.js`. Same shape of fix as the parameter-tools resolution in [`TOOLING_CHANGELOG.md`](TOOLING_CHANGELOG.md) (2026-05-10). Lower priority — most users don't put racks/Simpler/Wavetable on master/return.

---

## Feature wishlist

- **Read FabFilter EQ band info without M4L** — investigate whether parameters can be read via OSC, plugin state introspection, or preset XML inspection. Lower priority now that FabFilter detection clearly tells the agent to load M4L; would remove the M4L dependency entirely. Real research task — not a quick fix.

- **Read FabFilter band info / VST plugin internal state (real research)** — once a user has not Configured the relevant params, neither the LOM `device.parameters` nor the M4L `plugin~` path can see the FabFilter band positions, EQ curves, frequency/gain/Q values, etc. The state lives in a proprietary binary blob inside the plugin's VST chunk. Three possible routes, all heavyweight:
  1. **Preset XML / VST chunk parsing** — extract the chunk from the `.als` (gzipped XML) and decode FabFilter's binary format. Format isn't documented; would need reverse engineering. Highest payoff (works for FabFilter, Roland Cloud, Korg, etc.) but largest effort.
  2. **UI accessibility scraping via computer-use** — read the rendered GUI to extract band positions. Brittle to plugin updates; coordinate-dependent; slow. Already implicitly used for one-off debugging.
  3. **Extend M4L bridge to enumerate `plugin~` host parameters** — Max's `plugin~` object exposes a `params` message that lists ALL VST/AU parameters, not just Configured ones. Currently `m4l_bridge.js` only uses `plugin~` for audio analysis. Cross-track access from the bridge device to another track's `plugin~` instance is non-trivial — needs LiveAPI patcher navigation. Moderate effort but most architecturally clean.

- **`sample_parameter_curve` for batch workflows** — `set_parameter_by_display` (shipped 2026-05-15) handles one-shot display-value targeting. For batch workflows where the same parameter is set repeatedly, sampling the `value (0..1) ↔ display_value` curve once and reusing it would be faster than binary-searching per call.
