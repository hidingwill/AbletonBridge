# Plugin Format Cleanup — AbletonBridge Reliability

**Created**: 2026-05-16
**Author**: Claude / Sam
**Status**: Reference doc

## Why this matters

When the same plugin is installed in multiple formats (AU + VST3 + VST2) on macOS, **AbletonBridge becomes unreliable**:

1. **Browser name-match ambiguity** — `load_instrument_or_effect` matches by name. With duplicates in the browser, the bridge can pick the wrong format or fail entirely.
2. **Connection drops on load** — failed name resolution can crash the Remote Script connection.
3. **Inconsistent parameter exposure** — VST3 exposes parameters with proper unit displays (e.g., "129 Hz") while AU sometimes shows generic values (e.g., "0.37"). Same plugin, different state.
4. **Ableton's own rule**: only one format of the same plugin should be inserted in a Live Set. Mixing formats in a set is unsupported and creates session-level instability.

**Recommendation**: pick **VST3** as the standard. It's the modern format, exposes parameters most reliably in Live, and is what AbletonBridge handles cleanest.

## The trade-off you need to know

If you have existing projects with AU instances of plugins, **uninstalling AU will break those instances** ("missing plugin" warnings). The existing AU instances must be migrated to VST3 manually, one by one.

**Two strategies**:

### Strategy A — Disable, don't uninstall (low risk, partial benefit)

In Ableton:
- Preferences → Plug-Ins → toggle OFF **Use Audio Units** and **Use VST2 Plug-In System Folders**
- Keep **Use VST3 Plug-In System Folders** ON
- Rescan

**Effect**: AU + VST2 hidden from browser → MCP loads VST3 cleanly. But existing AU instances in saved projects show as "missing" until you re-enable AU.

**Best for**: starting new projects fresh in VST3-only mode, while keeping current projects running with AU re-enabled when working on them.

### Strategy B — Full uninstall (clean end state, requires migration)

For each plugin vendor, uninstall AU + VST2 versions, keep only VST3 installed. Then migrate every existing AU instance in your projects to VST3 (manual per-instance).

**Best for**: clean-slate moments or when starting a major new project.

### Strategy C (recommended for the current `course Project`) — Hybrid

- Keep AU enabled in Live preferences for now
- For **new MCP loads**, explicitly use VST3 URIs (format: `query:Plugins#VST3:Vendor:PluginName`) to avoid name-match ambiguity
- Migrate existing AU instances to VST3 gradually, track-by-track, over time
- Only commit to Strategy B once all instances are migrated

## Per-vendor cleanup steps (for Strategy B)

| Vendor | Plugins | Cleanup method |
|---|---|---|
| **FabFilter** | Pro-Q 4 | Re-run installer → uncheck AU + VST2 |
| **Soundtoys 5** | Decapitator, EchoBoy, EchoBoy Jr, PhaseMistress, FilterFreak1/2, Little Plate, SuperPlate, SpaceBlender, Radiator, Effect Rack, PrimalTap, Crystallizer, Tremolator, PanMan, MicroShift, AlterBoy, Devil-Loc, Sie-Q | Soundtoys Installer Manager → uninstall AU + VST2 components |
| **PSP 25th Anniversary** | BussPressor, MasterComp, FETpressor, MicroComp, Impressor, oldTimer/oldTimerME, MasterQ2, ConsoleQ, NobleQ, NobleQex, VintageWarmer2, Saturator, EasyVerb, PianoVerb, SpringBox, Echo, 285, 608 MultiDelay, stepDelay, stompDelay, Xenon, Twin-L, HertzRider2, BinAmp, Lotary2, stompFilter, stereoController2, stereoAnalyser2, Spector, TripleMeter | PSPaudioware.com → re-download bundle installer → VST3 only during install |
| **D16** | Decimort 2 | Installer → VST3 only |
| **Valhalla** | Room, VintageVerb, Supermassive | Per-plugin installer (3 installers) → VST3 only |
| **Waves** | MetaFlanger (Mono / Stereo / Mono+Stereo) | Waves Central → manage installed components, uninstall AU + VST2 |
| **TAL** | Chorus-LX | Manual delete of AU + VST files; keep VST3 only |
| **Dexed** | DX7 emulation | Manual; verify formats present |
| **Airwindows** | Consolidated (Mackity, MackEQ, hundreds more) | Often single-format installs; verify and remove duplicates |
| **Splice** | Creator, Astra, Beatmaker, Bridge | Splice app → manage installations |
| **Roland Cloud** | TR-909, TR-808, TR-606, TR-707, TR-727, CR-78, SH-101, JUNO-60, JUNO-106, TB-303, RE-201, JD-800, JV-1080 (VST), XV-5080 (VST), JUPITER-4/8, SH-2, PROMARS, SYSTEM-100, D-50 | Roland Cloud Manager → per-instrument format options where available. **Some Roland Cloud instruments may not have VST3** — verify before uninstalling AU |
| **KORG Collection 5** | Polysix, M1, Wavestation, MS-20, MS-20FX, Mono/Poly, miniKORG, Prophecy, microKORG, PS-3300, Triton, Triton Extreme, Trinity, ARP Odyssey, ARP 2600, MDE-X, Vox Super Continental | KORG Software Pass → per-instrument format choice. **Some KORG instruments may not have VST3** — verify before uninstalling AU |

## Plugins that may force you to keep AU enabled

Some older plugins don't have VST3 versions yet. **Verify each before uninstalling AU.** Likely candidates:
- Older Roland Cloud instruments (verify TR-606, CR-78, JX-3P specifically)
- Some KORG Collection 5 vintage instruments (M1, Wavestation are AU-leaning historically)
- Certain Airwindows utilities

If a plugin is AU-only, keep AU enabled but install only ONE format (so no duplicates). Mixed format installs are the problem — single-format installs in any format are fine.

## Final verification

After cleanup:
1. **Restart Ableton** completely
2. **Preferences → Plug-Ins → Rescan**
3. Open the plugin browser — verify each plugin appears **only once** per name
4. Open `The best so far nb1.als` (or whatever project) — fix any "missing plugin" warnings by re-inserting VST3 versions
5. Test AbletonBridge by loading a known-good plugin via MCP — verify connection stays stable across 5+ consecutive loads

## Special case: hidden vs missing in current project

If you toggle AU off in preferences with AU instances loaded in your project, Ableton shows "missing plugin" warnings. **Re-enable AU and the instances return.** No data loss — settings are preserved in the project file even when AU is disabled. Migration just means swapping the instance type.

## Related files

- `/Users/samrodd/Code/AbletonBridge/TOOLING_ISSUES.md` — running list of AbletonBridge bugs
- `/Users/samrodd/Desktop/Ableton files/course Project/HANDOVER_VST_MIGRATION.md` — task brief for the migration session
