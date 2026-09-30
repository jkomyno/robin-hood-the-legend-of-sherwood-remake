//! Console command dispatch — the engine-side glue that turns a parsed
//! `ConsoleCommand` into actual mutations of engine, AI, and campaign
//! state.
//!
//! The parser lives in `crate::console`; this module is the single
//! consumer of `ConsoleCommand`.

use super::{DevState, EngineInner, LevelAssets};
use crate::ai::AiLockFlags;
use crate::campaign::CampaignValue;
use crate::console::ConsoleCommand;
#[cfg(test)]
use crate::console::parse_with_final;
use crate::element::{Camp, Command, Entity, EntityId, ObjectType, Posture};
use crate::engine::TickCtx;
use crate::sequence::SequenceElement;

/// Any authoritative console command makes the current attempt ineligible
/// for persistent achievement unlocks. Host-only inspection/rendering never
/// enters deterministic command admission.
const CHEAT_CONSOLE_COMMAND: u32 = 0x0000_0002;

/// Outcome of running a single console command.
#[derive(Debug, Clone, PartialEq)]
pub enum ConsoleResponse {
    /// The input parsed and the command ran.  The string is a
    /// human-readable reply to echo back to the console history/UI.
    /// Empty string is allowed for silent commands.
    Ok(String),
    /// The input did not parse to any known command.
    Unknown,
    /// The command parsed but is not yet implemented on the Rust side.
    /// The string names the variant so the operator knows which stub
    /// they hit.  Distinct from `Ok` so callers (and tests) can tell
    /// when a command was a no-op.
    NotImplemented(&'static str),
    /// The `CAMPAIGN <file>` console cheat requested a save load.
    /// EngineInner can't reach into the save-file parser (host-owned format),
    /// so the host drains this variant and performs the load itself.
    /// Decision 6B.
    LoadCampaignRequested(std::path::PathBuf),
    /// The `_FINAL`-build deity easter egg fired: the input's MD5
    /// matched, `use_final` has been cleared, and the "Praised be His
    /// Name." message has already been pushed onto
    /// `Console::pending_output`.  The host drains this variant and
    /// applies the input-translator rebind table (engine has no access
    /// to the host-owned `InputTranslator`).
    DeityInvoked,
}

impl EngineInner {
    /// Parse `input` using the console's current dev/final mode,
    /// dispatch the command, and record the raw input in history.
    ///
    /// Returns `ConsoleResponse::Unknown` if the input doesn't parse.
    #[cfg(test)]
    pub(crate) fn run_console_command(
        &mut self,
        tcx: TickCtx<'_>,
        dev: &mut DevState,
        selected_view_element: &mut Option<EntityId>,
        input: &str,
    ) -> ConsoleResponse {
        let cmd_opt = parse_with_final(input, dev.console.use_final);

        // Deity easter egg: when `use_final` is set, match the line
        // buffer against the hidden token, clear `use_final`, print
        // "Praised be His Name.", and have the input translator
        // rebind the SLOW_MOTION/TELEPORT/RECORD_MOVIE/REQUEST_INFO keys.
        // The command-line parser destructively uppercases + NUL-splits
        // the buffer before checking the token, so the comparison sees
        // only the first (uppercased) token. The original binary compared
        // MD5(token) to 8f986776f01f52c1225231ae93ab634f; brute-forcing
        // likely all-caps cheat words recovered GLOIRE, confirmed with
        // `printf GLOIRE | md5sum`. The rebind itself lives in the
        // host-owned `InputTranslator`, so emit `DeityInvoked` for the
        // host to drain.
        if dev.console.use_final
            && let Some(token) = input
                .split_whitespace()
                .next()
                .map(|t| t.to_ascii_uppercase())
            && token == "GLOIRE"
        {
            dev.console.use_final = false;
            dev.console.push_history(input);
            dev.console.push_output("Praised be His Name.");
            return ConsoleResponse::DeityInvoked;
        }

        let Some(cmd) = cmd_opt else {
            return ConsoleResponse::Unknown;
        };
        dev.console.push_history(input);
        self.dispatch_console_command(tcx, dev, selected_view_element, &cmd)
    }

    /// Dispatch an already-parsed console command.  Exposed for tests
    /// that want to bypass the parser.
    ///
    /// `selected_view_element` is the host-side UI selection (the NPC
    /// whose vision cone is being displayed).  Four cheats — Honolulu,
    /// Morpheus, Hades, LastManStanding — act on "the NPC you're
    /// currently looking at" and some also clear the selection on
    /// success; the caller hands in a mutable reference so those cheats
    /// can write back.
    pub(crate) fn dispatch_console_command(
        &mut self,
        tcx: TickCtx<'_>,
        dev: &mut DevState,
        selected_view_element: &mut Option<EntityId>,
        cmd: &ConsoleCommand,
    ) -> ConsoleResponse {
        self.dispatch_console_command_resolved(tcx, Some(dev), selected_view_element, cmd)
    }

    /// Dispatch a command that was parsed and classified by the host before
    /// frame admission. This path deliberately has no access to `DevState`.
    pub(crate) fn dispatch_sim_console_command(
        &mut self,
        tcx: TickCtx<'_>,
        selected_view_element: &mut Option<EntityId>,
        cmd: &ConsoleCommand,
    ) -> ConsoleResponse {
        assert!(!cmd.is_host_only(), "host-only console command admitted");
        self.dispatch_console_command_resolved(tcx, None, selected_view_element, cmd)
    }

    fn dispatch_console_command_resolved(
        &mut self,
        tcx: TickCtx<'_>,
        mut dev: Option<&mut DevState>,
        selected_view_element: &mut Option<EntityId>,
        cmd: &ConsoleCommand,
    ) -> ConsoleResponse {
        if !cmd.is_host_only() {
            self.mission_domain.cheat_used_flags |= CHEAT_CONSOLE_COMMAND;
        }
        use ConsoleCommand::*;
        match cmd {
            // ── Campaign value mutations ─────────────────────────
            GiveMoney { amount, show_help } => {
                self.console_give_money(tcx.assets, *amount, *show_help)
            }
            GiveBlazon { amount } => self.console_give_blazon(tcx.assets, *amount),
            GiveAmulets { amount } => self.console_give_amulets(*amount),
            AddPeasant => self.console_add_peasant(tcx),
            CampaignReport => self.console_campaign_report(tcx.assets),

            // ── Mission flow ─────────────────────────────────────
            LoseMission => self.console_lose_mission(),
            WinMission => self.console_win_mission(tcx.assets),
            WinCampaign => self.console_win_campaign(),
            // The save-file format lives in the host (robin_rs::save_file).
            // EngineInner returns the request; host dispatches the actual load.
            LoadCampaign { filename } => {
                ConsoleResponse::LoadCampaignRequested(std::path::PathBuf::from(filename))
            }
            SetDiplomacy {
                first,
                second,
                relationship,
            } => self.console_set_diplomacy(*first, *second, *relationship),

            // ── Blip / stealth cheats ────────────────────────────
            Ubiquity => self.console_ubiquity(),

            // ── Simple AI-global toggles ─────────────────────────
            Freeze | StupidSoldiers | Goldeneye | Babylon | Ai | DiesIrae => {
                self.console_ai_global_toggle(cmd)
            }

            // ── Debug flag toggles ───────────────────────────────
            Elevation
            | Railroad
            | Einstein
            | Projection
            | Euler
            | Motion
            | Noise
            | SeekAndDestroy
            | Light
            | PcSight
            | Shadow
            | Sphere
            | SpriteMasks
            | Surface
            | EnergyDisplay
            | Anim
            | Companies
            | CestLaZone
            | BigBrother
            | LevelText { .. } => console_debug_display(&mut dev, cmd),

            // ── PC invulnerability ───────────────────────────────
            Highlander => {
                self.console_make_camp_invulnerable(Camp::Royalists, "Friends invulnerable")
            }
            Highlander2 => {
                self.console_make_camp_invulnerable(Camp::Lacklandists, "Foes invulnerable")
            }

            // ── Commands needing features not yet implemented ────
            Nuke => self.console_nuke(tcx),
            Wakeup => self.console_wake_npcs(tcx),
            BudSpencer => self.console_knock_out_enemy_soldiers(tcx),
            Honolulu => self.console_honolulu(dev.as_deref_mut(), selected_view_element),
            Morpheus => self.console_morpheus(tcx, selected_view_element),
            Hades => self.console_hades(tcx, selected_view_element),
            LastManStanding => self.console_last_man_standing(selected_view_element),
            RoterAlarm => self.console_alert_soldiers(tcx),
            MisterSandman => self.console_mister_sandman(tcx),
            Coma => self.console_coma(tcx),
            Reinforcement => self.console_reinforcement(tcx),
            SanPetrus => self.console_san_petrus(tcx),
            WaspMaster | GiveArrows => self.console_force_ammo_cheat(tcx.assets, cmd),
            GiveAmmo => self.console_give_ammo(tcx.assets),
            Lukas { pcs } => self.console_lukas(tcx, pcs.as_deref()),
            Call { actor, method } => self.console_call_actor(tcx.assets, actor, method),
            StatusFramecache | StatusShadow | StatusHardware | StatusPc | Optimize | Forget
            | Sarkozy | Fps => self.console_status_report(&mut dev, cmd),

            // ── Misc dev-mode ────────────────────────────────────
            Help => {
                // Original 0x0045ccb0 calls FUN_0045bff0, which prints one
                // console message per active registry entry.
                let dev = host_dev(&mut dev);
                for line in crate::console::help_lines(dev.console.use_final) {
                    dev.console.push_output(line);
                }
                ConsoleResponse::Ok(String::new())
            }
            AssertFalse => {
                // This cheat only logs; it does not interrupt execution.
                tracing::warn!("console: assert(false) cheat invoked");
                ConsoleResponse::Ok("assert( false );".to_string())
            }
            UsageError(msg) => ConsoleResponse::Ok((*msg).to_string()),
        }
    }
}

/// Per-arm handlers of `dispatch_console_command_resolved`. Family handlers
/// receive the whole command and are only reachable from their dispatch arm.
impl EngineInner {
    /// `WAPPEN` (original 0x0045f2a0): `FUN_00450b60(3, n)` adds blazons.
    fn console_give_blazon(&mut self, assets: &LevelAssets, amount: u32) -> ConsoleResponse {
        let amount = i32::try_from(amount).expect("parser bounds blazon amounts to i32");
        self.add_campaign_value(assets, CampaignValue::Blazon, amount);
        ConsoleResponse::Ok("Blazons !".to_string())
    }

    /// `AMULETS`/`GOODLUCK` (original 0x0045eaa0): `FUN_004520e0(0, n)`
    /// *sets* the amulet total, although the message says "added".
    fn console_give_amulets(&mut self, amount: u32) -> ConsoleResponse {
        let total = i32::try_from(amount).expect("parser bounds amulet amounts to i32");
        self.campaign_mut_or_panic()
            .set_value(CampaignValue::Amulets, total);
        ConsoleResponse::Ok(format!(
            "Amulets [amount]\n{amount} amulets added to the campaign."
        ))
    }

    /// `KOLKOZ`/`MERRYMAN` (original 0x004600b0): arguments are ignored and
    /// `FUN_004524b0(0xffff)` recruits a random peasant or returns a
    /// reservist.
    fn console_add_peasant(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        self.campaign_mut_or_panic().add_new_peasant_to_gang(
            tcx.sim,
            None,
            &tcx.assets.profile_manager,
        );
        ConsoleResponse::Ok("New member !".to_string())
    }

    fn console_campaign_report(&mut self, assets: &LevelAssets) -> ConsoleResponse {
        self.campaign_mut_or_panic()
            .log_report(&assets.profile_manager);
        ConsoleResponse::Ok("Reporting...".to_string())
    }

    fn console_lose_mission(&mut self) -> ConsoleResponse {
        self.mission_domain.state.quit_lost = true;
        ConsoleResponse::Ok("Mission lost !".to_string())
    }

    /// `I AM THE WINNER` (original 0x0045d580): set the current mission
    /// profile's byte `+0x60` (ARES state) to 9, then request the ordinary
    /// mission win. The original assumes a current mission.
    fn console_win_campaign(&mut self) -> ConsoleResponse {
        // Rust profiles are `Arc`-shared, so we stash the override on
        // `Mission::ares_state_override` — read by
        // `Campaign::set_mission_done` when the win lands.
        let campaign = &mut self.mission_domain.campaign;
        let Some(idx) = campaign.current_mission_idx else {
            tracing::warn!("I AM THE WINNER without a current campaign mission");
            return ConsoleResponse::Ok("Error: no current campaign mission.".to_string());
        };
        campaign.missions[idx].ares_state_override = Some(9);
        self.win(true);
        self.mission_domain.state.quit_won = true;
        ConsoleResponse::Ok("Campaign won !".to_string())
    }

    fn console_set_diplomacy(
        &mut self,
        first: u16,
        second: u16,
        relationship: crate::diplomacy::Relationship,
    ) -> ConsoleResponse {
        self.mission_domain
            .diplomacy
            .set_relationship_ids(first, second, relationship)
            .unwrap_or_else(|error| panic!("invalid DIPLOMACY command: {error}"));
        crate::diplomacy::reconcile_entities(
            &mut self.world.entities,
            &self.mission_domain.diplomacy,
        );
        ConsoleResponse::Ok(format!(
            "Diplomacy {first}<->{second} set to {relationship:?}."
        ))
    }

    fn console_ubiquity(&mut self) -> ConsoleResponse {
        self.reveal_all_blips();
        ConsoleResponse::Ok("Unblip !".to_string())
    }

    /// Simple `ai.global` flag toggles.
    fn console_ai_global_toggle(&mut self, cmd: &ConsoleCommand) -> ConsoleResponse {
        use ConsoleCommand::*;
        match cmd {
            Freeze => {
                // Prints a leading "freeze" banner line, then the
                // frozen/defrosted status line.
                self.ai.global.freeze = !self.ai.global.freeze;
                let status = if self.ai.global.freeze {
                    "Enemies frozen."
                } else {
                    "Enemies defrosted."
                };
                ConsoleResponse::Ok(format!("freeze\n{status}"))
            }
            StupidSoldiers => {
                // Prints a leading "Pamela Anderson" banner line before
                // the stupid/smart status line.
                self.ai.global.stupid_soldiers_cheat = !self.ai.global.stupid_soldiers_cheat;
                let status = if self.ai.global.stupid_soldiers_cheat {
                    "Soldiers are stupid !"
                } else {
                    "Soldiers are smart !"
                };
                ConsoleResponse::Ok(format!("Pamela Anderson\n{status}"))
            }
            Goldeneye => {
                self.ai.global.golden_eye_mode = !self.ai.global.golden_eye_mode;
                ConsoleResponse::Ok(
                    if self.ai.global.golden_eye_mode {
                        "Invisibility On."
                    } else {
                        "Invisibility Off."
                    }
                    .to_string(),
                )
            }
            Babylon => {
                self.ai.global.speech_display = !self.ai.global.speech_display;
                ConsoleResponse::Ok(
                    if self.ai.global.speech_display {
                        "Patati Patata Bla Bla Laber Rhabarber Patatitata..."
                    } else {
                        "Shht !"
                    }
                    .to_string(),
                )
            }
            Ai => {
                self.ai.global.attribute_display = !self.ai.global.attribute_display;
                ConsoleResponse::Ok(
                    if self.ai.global.attribute_display {
                        "Attributes displayed"
                    } else {
                        "Attributes hidden"
                    }
                    .to_string(),
                )
            }
            DiesIrae => {
                // Prints "Dies irae" banner, toggles
                // `ai_global.ezekiel_2517`, then prints either "Mine is
                // the vengeance, says the Lord !" or "The Lord pardons...".
                // The flag is consumed by view-cone selection and script
                // `EnableViewCone`, matching the original cheat hook.
                self.ai.global.ezekiel_2517 = !self.ai.global.ezekiel_2517;
                let status = if self.ai.global.ezekiel_2517 {
                    "Mine is the vengeance, says the Lord !"
                } else {
                    "The Lord pardons..."
                };
                ConsoleResponse::Ok(format!("Dies irae\n{status}"))
            }
            _ => unreachable!("console command routed to the wrong AI-global toggle: {cmd:?}"),
        }
    }

    /// `HIGHLANDER`/`IMMUNITY` (original 0x0045d840) and `HIGHLANDER2`
    /// (0x0045d8b0) set the invulnerable byte (`human+0x496 = 1`) on every
    /// entry of the engine's camp-indexed fighter vector: `E+0x4ccc` for
    /// camp 0 and `E+0x4cec` for camp 1 (`0x4ccc + camp * 0x20`, the camp
    /// coming from the actor's vtable `+0x130`). There is no toggle-off.
    /// PCs and soldiers of the camp are fighters; civilians are not.
    fn console_make_camp_invulnerable(&mut self, camp: Camp, reply: &str) -> ConsoleResponse {
        let ids: Vec<_> = self.world.entities.fighter_ids_for_camp(camp).collect();
        for id in ids {
            if let Some(entity) = self.get_entity_mut(id)
                && let Some(h) = entity.human_data_mut()
            {
                h.invulnerable = true;
            }
        }
        ConsoleResponse::Ok(reply.to_string())
    }

    fn console_mister_sandman(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        // For every PC, launch a damage(100, 0) sequence —
        // hp=100, concussion=0, *not* the reverse.  Swapping
        // the two would change a death roll into a concussion
        // roll.
        let pcs = self.world.pc_ids.clone();
        for id in pcs {
            self.launch_damage(tcx, id, 100, 0);
        }
        ConsoleResponse::Ok("Sweet dreams !".to_string())
    }

    fn console_reinforcement(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        self.create_reinforcement(tcx, None);
        ConsoleResponse::Ok(String::new())
    }

    fn console_force_ammo_cheat(
        &mut self,
        assets: &LevelAssets,
        cmd: &ConsoleCommand,
    ) -> ConsoleResponse {
        match cmd {
            ConsoleCommand::WaspMaster => {
                // Always prints "Wasps", then either the typo-preserved
                // error or force-sets every selected PC's wasp ammo to
                // `0xFFFF`.  Re-enables the action slot via
                // `enable_pc_action` when amount > 0.
                self.force_ammo_with_banner(
                    assets,
                    crate::profiles::Action::WaspNest,
                    0xFFFF,
                    "Wasps",
                    "You must selected at meast one PC which must go to paradise.",
                )
            }
            ConsoleCommand::GiveArrows => {
                // Always prints "Arrows", then either the typo-preserved
                // error or force-sets every selected PC's bow ammo to
                // `0xFFFF` (and re-enables the action slot).
                self.force_ammo_with_banner(
                    assets,
                    crate::profiles::Action::Bow,
                    0xFFFF,
                    "Arrows",
                    "You must selected at meast one PC.",
                )
            }
            _ => unreachable!("console command routed to the wrong ammo cheat: {cmd:?}"),
        }
    }

    /// `LUKAS` (original 0x0045f330): print the banner, decode every
    /// initial of the first argument through `FUN_0045f6f0` (printing a
    /// warning per unknown initial), then call `FUN_00577500(actor, 100,
    /// true)` on each resolved PC, i.e. an hp=100 / concussion=100 damage
    /// sequence. Later arguments and the PC selection are ignored.
    fn console_lukas(&mut self, tcx: TickCtx<'_>, pcs: Option<&str>) -> ConsoleResponse {
        let mut out = String::from("PCs knocked out !");
        let mut targets = Vec::new();
        for ch in pcs.unwrap_or_default().chars() {
            match pc_initial_to_profile_name(ch) {
                // Original text (0x006add44); it lists S twice and omits C,
                // although C is accepted.
                None => {
                    out.push_str("\nUnknown character (use one or more of these : RJTSWMABS) !")
                }
                Some(name) => targets.extend(self.resolve_pc_by_profile_name(tcx.assets, name, ch)),
            }
        }
        for id in targets {
            self.launch_damage(tcx, id, 100, 100);
        }
        ConsoleResponse::Ok(out)
    }

    /// `STATUS *`, `OPTIMIZE`, `FORGET`, `SARKOZY` and `FPS` diagnostics.
    fn console_status_report(
        &mut self,
        dev: &mut Option<&mut DevState>,
        cmd: &ConsoleCommand,
    ) -> ConsoleResponse {
        use ConsoleCommand::*;
        match cmd {
            Fps => {
                // Idempotent set (not a toggle): unconditionally
                // enables FPS display and prints "FPS displayed."
                // every time.
                host_dev(dev).debug.fps_display = true;
                ConsoleResponse::Ok("FPS displayed.".to_string())
            }
            StatusFramecache | StatusShadow => {
                // The Rust port has no frame cache and no legacy shadow
                // buffer — the diagnostics these variants used to
                // print are meaningless here.
                ConsoleResponse::Ok(
                    "STATUS: no frame cache / shadow buffer in Rust port.".to_string(),
                )
            }
            StatusHardware => console_status_hardware(host_dev(dev)),
            StatusPc => {
                // Per-PC dump of the actor identity + its
                // interface-displayed state.  Hex pointers are
                // meaningless in the Rust runtime, so we print the
                // stable `EntityId` instead.
                if self.world.pc_ids.is_empty() {
                    return ConsoleResponse::Ok("No PCs in the mission.".to_string());
                }
                for &id in &self.world.pc_ids.clone() {
                    let displayed = self
                        .get_entity(id)
                        .and_then(|e| e.pc_data())
                        .map(|pc| !pc.interface_hidden)
                        .unwrap_or(true);
                    host_dev(dev)
                        .console
                        .push_output(format!("Actor id ........................ {}", id.index()));
                    host_dev(dev).console.push_output(format!(
                        "Interface Displayed ............. {}",
                        if displayed { "YES" } else { "NO" }
                    ));
                }
                ConsoleResponse::Ok(String::new())
            }
            Optimize => {
                // No frame cache to defragment — the Rust port uses
                // the system allocator.
                ConsoleResponse::Ok(
                    "No frame cache to optimize; Rust port uses the system allocator.".to_string(),
                )
            }
            Forget => {
                // No-op in the shipping binary (memory-check command
                // was compiled out).
                ConsoleResponse::Ok(String::new())
            }
            Sarkozy => {
                // No-op in the shipping binary (alloc-check command was
                // compiled out).
                ConsoleResponse::Ok(String::new())
            }
            _ => unreachable!("console command routed to the wrong status report: {cmd:?}"),
        }
    }
}

/// Host-only debug display toggles; every arm requires `DevState`.
fn console_debug_display(dev: &mut Option<&mut DevState>, cmd: &ConsoleCommand) -> ConsoleResponse {
    use ConsoleCommand::*;
    match cmd {
        Elevation => toggle_debug(
            &mut host_dev(dev).debug.elevation_display,
            "Elevation display enabled.",
            "Elevation display disabled.",
        ),
        Railroad => toggle_debug(
            &mut host_dev(dev).debug.railroad_display,
            "Railroads displayed.",
            "Railroads hidden.",
        ),
        Einstein => toggle_debug(
            &mut host_dev(dev).debug.all_obstacles_display,
            "3D-obstacles displayed.",
            "3D-obstacles hidden.",
        ),
        Projection => toggle_debug(
            &mut host_dev(dev).debug.projection_areas_display,
            "Projection areas displayed.",
            "Projection areas hidden.",
        ),
        Euler => {
            // Toggles motion-graph display and resets the index to 0.
            host_dev(dev).debug.motion_graph_display = !host_dev(dev).debug.motion_graph_display;
            host_dev(dev).debug.motion_graph_display_index = 0;
            ConsoleResponse::Ok(
                if host_dev(dev).debug.motion_graph_display {
                    "The seven bridges of Koenigsberg."
                } else {
                    "Graph hidden."
                }
                .to_string(),
            )
        }
        Motion => {
            host_dev(dev).debug.motion_obstacles_display =
                !host_dev(dev).debug.motion_obstacles_display;
            host_dev(dev).debug.door_display = !host_dev(dev).debug.door_display;
            ConsoleResponse::Ok(
                if host_dev(dev).debug.motion_obstacles_display {
                    "Motion obstacles displayed."
                } else {
                    "Motion obstacles hidden."
                }
                .to_string(),
            )
        }
        Noise => {
            // "noise" banner, then on enable four lines (status +
            // three legend lines), on disable just the status line.
            host_dev(dev).debug.noise_display = !host_dev(dev).debug.noise_display;
            let body = if host_dev(dev).debug.noise_display {
                "Noise display enabled.\n\
                     \x20 White circles: Noises\n\
                     \x20 Black circles: Deafness because of covering noises, explosions etc...\n\
                     \x20 A NPC can hear a nois when he resp. his black circle is entirely within a white circle."
            } else {
                "Noise display disabled."
            };
            ConsoleResponse::Ok(format!("noise\n{body}"))
        }
        SeekAndDestroy => toggle_debug(
            &mut host_dev(dev).debug.display_seek_points,
            "Seek points displayed",
            "Seek points hidden",
        ),
        Light => toggle_debug(
            &mut host_dev(dev).debug.display_light_zones,
            "Light zones enabled.",
            "Light zones disabled.",
        ),
        PcSight => {
            // Prints the *old* state then toggles, so the displayed
            // text is inverted vs. the new value.
            let was = host_dev(dev).debug.pc_sight;
            host_dev(dev).debug.pc_sight = !was;
            ConsoleResponse::Ok(if was { "PCs can't see" } else { "PCs can see" }.to_string())
        }
        Shadow => toggle_debug(
            &mut host_dev(dev).debug.free_shadow_polygon,
            "Free shadow polygon enabled",
            "Free shadow polygon disabled",
        ),
        Sphere => {
            host_dev(dev).debug.shadow_polygon_sphere = !host_dev(dev).debug.shadow_polygon_sphere;
            ConsoleResponse::Ok(String::new())
        }
        SpriteMasks => toggle_debug(
            &mut host_dev(dev).debug.sprite_masks_display,
            "Sprite masks displayed.",
            "Sprite masks hidden.",
        ),
        Surface => toggle_debug(
            &mut host_dev(dev).debug.surface_display,
            "Surface overlay displayed.",
            "Surface overlay hidden.",
        ),
        EnergyDisplay => toggle_debug(
            &mut host_dev(dev).debug.combat_energy_display,
            "Combat energy display enabled !",
            "Combat energy display disabled !",
        ),
        Anim => toggle_debug(
            &mut host_dev(dev).debug.display_animation_lines,
            "Animation lines displayed.",
            "Animation lines hidden.",
        ),
        Companies => {
            host_dev(dev).debug.company_number_display =
                !host_dev(dev).debug.company_number_display;
            let on = host_dev(dev).debug.company_number_display;
            ConsoleResponse::Ok(
                if on {
                    "Company number displayed"
                } else {
                    "Company number hidden"
                }
                .to_string(),
            )
        }
        CestLaZone => {
            // "Zone" banner then the enabled/disabled status line.
            host_dev(dev).debug.script_zone_display = !host_dev(dev).debug.script_zone_display;
            let status = if host_dev(dev).debug.script_zone_display {
                "Script zone display enabled."
            } else {
                "Script zone display disabled."
            };
            ConsoleResponse::Ok(format!("Zone\n{status}"))
        }
        BigBrother => {
            host_dev(dev).debug.actor_info_display = !host_dev(dev).debug.actor_info_display;
            // TODO: Port the original actor-info text overlay. Until then,
            // make BIG BROTHER drive the live numeric ID overlay that is
            // already rendered by the host.
            host_dev(dev).debug.entity_ids = host_dev(dev).debug.actor_info_display;
            ConsoleResponse::Ok(
                if host_dev(dev).debug.actor_info_display {
                    "Actor infos displayed !"
                } else {
                    "Actors infos hidden !"
                }
                .to_string(),
            )
        }
        LevelText { option } => match option.as_deref() {
            Some("DG") => {
                host_dev(dev).debug.all_dialogues = true;
                ConsoleResponse::Ok("Displaying all dialogues...".to_string())
            }
            Some("DB") => {
                host_dev(dev).debug.all_debriefings = true;
                ConsoleResponse::Ok("Displaying all debriefings...".to_string())
            }
            Some("PT") => {
                host_dev(dev).debug.all_popup_texts = true;
                ConsoleResponse::Ok("Displaying all popup texts...".to_string())
            }
            Some("SB") => ConsoleResponse::Ok(
                "Short-briefing DisplayAll cheat is no longer available.".to_string(),
            ),
            _ => ConsoleResponse::Ok("Displayes all texts. Options: DG DB PT".to_string()),
        },
        _ => unreachable!("console command routed to the wrong debug display toggle: {cmd:?}"),
    }
}

/// Print a multi-section hardware report.  We push every line through
/// `Console::pending_output` so the overlay scrollback shows them
/// interleaved with the user's input line.  Rust port uses the system
/// allocator and portable feature detection, so we surface the subset we can
/// actually query (arch, SIMD features, CPU count); the rest (cache sizes,
/// physical memory) were platform-detection stubs even in the shipping
/// original.
fn console_status_hardware(dev: &mut DevState) -> ConsoleResponse {
    dev.console.push_output("=> CPU Information");
    dev.console.push_output("");
    dev.console.push_output(format!(
        "Vendor String................. {}",
        std::env::consts::ARCH
    ));
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    let (has_mmx, has_sse, has_sse2, has_avx) = (
        std::is_x86_feature_detected!("mmx"),
        std::is_x86_feature_detected!("sse"),
        std::is_x86_feature_detected!("sse2"),
        std::is_x86_feature_detected!("avx"),
    );
    #[cfg(not(any(target_arch = "x86", target_arch = "x86_64")))]
    let (has_mmx, has_sse, has_sse2, has_avx) = (false, false, false, false);
    dev.console
        .push_output("FPU........................... Detected");
    dev.console.push_output(format!(
        "Multi Media eXtension......... {}",
        if has_mmx { "Detected" } else { "Not Detected" }
    ));
    dev.console.push_output(format!(
        "Streaming SIMD Extension...... {}",
        if has_sse { "Detected" } else { "Not Detected" }
    ));
    dev.console.push_output(format!(
        "SSE2.......................... {}",
        if has_sse2 { "Detected" } else { "Not Detected" }
    ));
    dev.console.push_output(format!(
        "AVX........................... {}",
        if has_avx { "Detected" } else { "Not Detected" }
    ));
    let procs = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1);
    dev.console.push_output(format!(
        "Architecture.................. {}",
        if procs > 1 {
            "Multiprocessor"
        } else {
            "Monoprocessor"
        }
    ));
    dev.console
        .push_output(format!("Logical Processors............ {procs}"));
    ConsoleResponse::Ok(String::new())
}

impl EngineInner {
    fn console_give_money(
        &mut self,
        assets: &LevelAssets,
        amount: u32,
        show_help: bool,
    ) -> ConsoleResponse {
        // Original 0x0045f0c0 adds through `FUN_00450b60(1, amount)`.
        let amount = i32::try_from(amount).expect("parser bounds money amounts to i32");
        self.add_campaign_value(assets, CampaignValue::Ransom, amount);
        // Always prints "Money !" first; the no-argument branch then
        // lists the suggestions. `CASH CENT` is only a suggestion: CENT
        // is not a keyword and scans as 0.
        let mut out = String::from("Money !");
        if show_help {
            out.push_str(
                "\nTry also the following :\n\
                 CASH CENT\n\
                 CASH THOUSAND\n\
                 CASH TENTHOUSAND\n\
                 CASH HUNDREDTHOUSAND",
            );
        }
        ConsoleResponse::Ok(out)
    }

    /// `WIN`/`WINNER` (original 0x0045cda0).
    fn console_win_mission(&mut self, assets: &LevelAssets) -> ConsoleResponse {
        // No-op in Sherwood; otherwise adds mission-stat money
        // (soldier + bonus − collected) + rescue PCs + pending
        // bonus-blazon pickups to the campaign totals before
        // calling `engine.win(true)`.
        let in_sherwood = Some(&self.mission_domain.campaign)
            .and_then(|c| {
                let idx = c.current_mission_idx?;
                Some(
                    c.missions[idx].profile(&assets.profile_manager).location
                        == crate::profiles::MissionLocation::Sherwood,
                )
            })
            .unwrap_or(false);
        if in_sherwood {
            // Whole cheat is gated on `location != SHERWOOD`.
            return ConsoleResponse::Ok(String::new());
        }

        let money_delta = self.mission_domain.mission_stat.soldier_money as i32
            + self.mission_domain.mission_stat.bonus_money as i32
            - self.mission_domain.mission_stat.collected_money as i32;

        // Sum quantities of still-active BONUS_BLAZON pickups
        // left on the map.
        let mut pending_blazons: i32 = 0;
        for (_, bonus) in self.world.entities.bonuses() {
            if bonus.element.active && bonus.object.object_type == ObjectType::BonusBlazon {
                pending_blazons += bonus.object.quantity as i32;
            }
        }

        self.add_campaign_value(assets, CampaignValue::Ransom, money_delta);
        if let Some(campaign) = Some(&mut self.mission_domain.campaign) {
            // Per-mission rescue-PC table — adds recruits
            // matching the current mission filename (e.g.
            // S01_Not_VL → Stutely + Paysan A/B/C).
            let added = campaign.rescue_pcs_for_current_mission_win(
                &assets.profile_manager,
                self.control.sim_config.difficulty,
            );
            if added > 0 {
                tracing::info!("WIN cheat: rescued {added} PC(s)");
            }
            campaign.add_value(CampaignValue::Blazon, pending_blazons);
        }
        self.win(true);
        self.mission_domain.state.quit_won = true;
        ConsoleResponse::Ok("Mission won !".to_string())
    }

    fn console_nuke(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        // Prints "Nuking ..." before walking every soldier,
        // launches a damage(1000, 1000) sequence per victim,
        // then prints "Nuked N soldiers".
        let victims: Vec<_> = self
            .world
            .entities
            .soldiers()
            .map(|(id, _)| id.into())
            .collect();
        let count = victims.len();
        for id in victims {
            self.launch_damage(tcx, id, 1000, 1000);
        }
        ConsoleResponse::Ok(format!("Nuking ...\nNuked {count} soldiers"))
    }

    fn console_wake_npcs(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        // Walk every NPC and, if unconscious, force concussion
        // to `31` — one above `CONCUSSION_WAKEUP_THRESHOLD` —
        // which drops them back to conscious via the normal
        // threshold transition in `set_concussion`.
        let ids: Vec<EntityId> = self
            .world
            .entities
            .npcs()
            .filter_map(|(id, e)| {
                if e.is_unconscious() {
                    Some(id.into())
                } else {
                    None
                }
            })
            .collect();
        for id in ids {
            // Apply wake guards and finish the resulting callbacks inline.
            self.apply_concussion(tcx, id, 31, false);
        }
        ConsoleResponse::Ok("Wake up !".to_string())
    }

    fn console_knock_out_enemy_soldiers(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        // Original 0x0045e2e0 keeps NPC-list soldiers whose vtable `+0x130`
        // returns 1; that slot is the camp getter used to index the
        // per-camp fighter vectors, so the filter is camp 1 (Lacklandists).
        // Knock out every Lacklandist soldier via
        // concussion(100) + posture LYING + a trivial Wait
        // sequence element.  Concussion application reads the
        // target's own invulnerable / tied / carried state via
        // `concussion_ctx_for`.
        let ids: Vec<_> = self
            .world
            .entities
            .soldier_ids_for_camp(Camp::Lacklandists)
            .collect();
        for id in ids {
            // Route through `apply_concussion` so a swordfighting
            // victim is dropped from opponents' lists and gets
            // the unconscious-star titbit + lose-consciousness
            // stimulus.
            self.apply_concussion(tcx, id, 100, false);
            self.set_entity_posture(id, Posture::Lying);
            self.launch_element(tcx, SequenceElement::new(1, Command::Wait, Some(id)));
        }
        ConsoleResponse::Ok("NPCs knocked out !".to_string())
    }

    /// `HONOLULU` (original 0x0045d920) against the target the host resolved
    /// with [`resolve_honolulu`]: an active NPC goes on holiday (inactive,
    /// AI frozen, view cleared); an inactive NPC comes back. Coordinates
    /// never change. No target or a non-NPC target is silent, like the
    /// original's outer guard.
    fn console_honolulu(
        &mut self,
        mut dev: Option<&mut DevState>,
        selected_view_element: &mut Option<EntityId>,
    ) -> ConsoleResponse {
        let Some(id) = *selected_view_element else {
            return ConsoleResponse::Ok(String::new());
        };
        let Some(entity) = self.get_entity_mut(id) else {
            return ConsoleResponse::Ok(format!("Error: selected entity {id:?} no longer exists"));
        };
        if !entity.is_npc() {
            return ConsoleResponse::Ok(String::new());
        }
        let send_away = entity.element_data().active;
        entity.element_data_mut().active = !send_away;
        if let Some(npc) = entity.npc_data_mut()
            && let Some(base) = npc.ai_brain.base_mut()
        {
            if send_away {
                base.non_script_lock(AiLockFlags::FREEZE);
            } else {
                base.non_script_unlock(AiLockFlags::FREEZE);
            }
        }
        if !send_away {
            return ConsoleResponse::Ok("Honolulu\nI'm back!".to_string());
        }
        if let Some(host) = dev.as_deref_mut() {
            host.last_actor_in_honolulu = Some(id);
        }
        *selected_view_element = None;
        ConsoleResponse::Ok("Honolulu\nBye, I'm on holiday.".to_string())
    }

    fn console_morpheus(
        &mut self,
        tcx: TickCtx<'_>,
        selected_view_element: &mut Option<EntityId>,
    ) -> ConsoleResponse {
        // Always prints "MORPHEUS" first, then gates on
        // selection being an NPC.  On success: concussion 100
        // + posture LYING + Wait element + clear selection +
        // "Sleep well...".  On failure (no selection / not NPC):
        // the "please enable view cone" message.  Concussion
        // application reads the target's own invulnerable /
        // tied / carried state via `concussion_ctx_for`.
        let is_npc = selected_view_element
            .and_then(|id| self.get_entity(id).map(|e| e.is_npc()))
            .unwrap_or(false);
        if !is_npc {
            return ConsoleResponse::Ok(
                "MORPHEUS\n\
                 Please enable view cone of a NPC before using this command."
                    .to_string(),
            );
        }
        let id = selected_view_element.expect("NPC-selected implies id present");
        // Route through `apply_concussion` so the KO side-effects
        // (drop from sword-fight opponents' lists,
        // unconscious-star titbit, lose-consciousness stimulus)
        // fire — a direct `set_concussion` call would skip them.
        self.apply_concussion(tcx, id, 100, false);
        self.set_entity_posture(id, Posture::Lying);
        self.launch_element(tcx, SequenceElement::new(1, Command::Wait, Some(id)));
        *selected_view_element = None;
        ConsoleResponse::Ok("MORPHEUS\nSleep well...".to_string())
    }

    fn console_hades(
        &mut self,
        tcx: TickCtx<'_>,
        selected_view_element: &mut Option<EntityId>,
    ) -> ConsoleResponse {
        let is_npc = selected_view_element
            .and_then(|id| self.get_entity(id).map(|e| e.is_npc()))
            .unwrap_or(false);
        if !is_npc {
            return ConsoleResponse::Ok(
                "HADES\n\
                 Please enable view cone of a NPC before using this command."
                    .to_string(),
            );
        }
        let id = selected_view_element.expect("NPC-selected implies id present");
        self.kill_npc_directly(tcx, id);
        self.set_entity_posture(id, Posture::Dead);
        self.launch_element(tcx, SequenceElement::new(1, Command::Wait, Some(id)));
        *selected_view_element = None;
        ConsoleResponse::Ok("HADES\nSleep well... forever!".to_string())
    }

    fn console_last_man_standing(
        &mut self,
        selected_view_element: &mut Option<EntityId>,
    ) -> ConsoleResponse {
        // Original 0x0045da50 prints "Last man standing" unconditionally,
        // then either deactivates and AI-locks every NPC other than the
        // viewed element and prints "Lonely hero...", or prints the
        // no-view error. It checks only that a view exists (no NPC type
        // check) and leaves the view and the Honolulu slot alone.
        let Some(keep) = *selected_view_element else {
            return ConsoleResponse::Ok(
                "Last man standing\n\
                 Please enable view cone of a NPC before using this command."
                    .to_string(),
            );
        };
        if self.get_entity(keep).is_none() {
            return ConsoleResponse::Ok(format!(
                "Last man standing\nError: selected entity {keep:?} no longer exists"
            ));
        }
        let ids: Vec<EntityId> = self.world.entities.npc_ids().collect::<Vec<_>>();
        for id in ids {
            if id == keep {
                continue;
            }
            if let Some(entity) = self.get_entity_mut(id) {
                entity.element_data_mut().active = false;
                if let Some(npc) = entity.npc_data_mut()
                    && let Some(base) = npc.ai_brain.base_mut()
                {
                    base.non_script_lock(AiLockFlags::FREEZE);
                }
            }
        }
        ConsoleResponse::Ok("Last man standing\nLonely hero...".to_string())
    }

    fn console_alert_soldiers(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        // Sets attentive mode on every soldier — silent cheat,
        // emits no console output.
        let soldier_ids: Vec<EntityId> = self
            .world
            .entities
            .soldiers()
            .map(|(id, _)| id.into())
            .collect();
        for id in soldier_ids {
            self.set_soldier_attentive_mode_from(
                tcx,
                id,
                true,
                false,
                crate::engine::soldier_helpers::AttentiveModeCaller::ConsoleCheat,
            );
        }
        ConsoleResponse::Ok(String::new())
    }

    /// `COMA` (original 0x0045e8d0): print "Coma !" before any check, then
    /// require a selected PC and at least one campaign amulet, and launch
    /// hp=10000 / concussion=0 damage on the first selected PC. The amulet
    /// is spent later by the ordinary coma lifecycle, not here.
    fn console_coma(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        let selected = self.players.seats[0].selection.first().copied();
        let amulets = self
            .mission_domain
            .campaign
            .get_value(CampaignValue::Amulets);
        match (selected, amulets) {
            (None, _) => {
                ConsoleResponse::Ok("Coma !\nPlease, select the PC to make sleep.".to_string())
            }
            (Some(_), n) if n < 1 => ConsoleResponse::Ok(
                "Coma !\nThere not enough amulets left to put the selected PC in the coma."
                    .to_string(),
            ),
            (Some(id), _) => {
                self.launch_damage(tcx, id, 10000, 0);
                ConsoleResponse::Ok("Coma !".to_string())
            }
        }
    }

    fn console_san_petrus(&mut self, tcx: TickCtx<'_>) -> ConsoleResponse {
        // Unconditionally prints "San Petrus", then either the
        // no-selection error or — per selected PC — launches a
        // hp=10000 / concussion=0 damage sequence and prints
        // `"<profile name> has been recalled by San Petrus."`.
        let selected = self.players.seats[0].selection.clone();
        if selected.is_empty() {
            return ConsoleResponse::Ok("San Petrus\nYou must select at least one PC.".to_string());
        }
        let mut out = String::from("San Petrus");
        // Resolve profile names before mutating via
        // `launch_damage` so the campaign borrow stays clean.
        let names: Vec<String> = selected
            .iter()
            .map(|&id| {
                let profile_idx = self
                    .get_entity(id)
                    .and_then(|e| e.pc_data())
                    .map(|pc| pc.profile_index);
                match (profile_idx, Some(&self.mission_domain.campaign)) {
                    (Some(idx), Some(_)) => tcx
                        .assets
                        .profile_manager
                        .get_character(idx)
                        .map(|p| p.profile_name.to_string())
                        .unwrap_or_else(|| format!("PC {id:?}")),
                    _ => format!("PC {id:?}"),
                }
            })
            .collect();
        for (id, name) in selected.iter().zip(names.iter()) {
            self.launch_damage(tcx, *id, 10000, 0);
            out.push_str(&format!("\n{name} has been recalled by San Petrus."));
        }
        ConsoleResponse::Ok(out)
    }

    fn console_give_ammo(&mut self, assets: &LevelAssets) -> ConsoleResponse {
        // For every PC, force all 3 action slots to 999.
        // Forcing ammo also re-enables the slot when the amount
        // is non-zero — that ripple fires here via
        // `enable_pc_action` so a PC who had run out of a given
        // action can fire again immediately.
        let pcs: Vec<_> = self
            .world
            .pc_ids
            .iter()
            .filter_map(|&id| {
                self.get_entity(id).and_then(|e| match e {
                    Entity::Pc(pc) => Some((
                        id,
                        pc.pc.profile_index,
                        self.pc_description_index_for_pc_data(&pc.pc)?,
                    )),
                    _ => None,
                })
            })
            .collect();
        for (id, profile_idx, status_idx) in pcs {
            let Some(campaign) = Some(&mut self.mission_domain.campaign) else {
                continue;
            };
            let actions = match assets.profile_manager.get_character(profile_idx) {
                Some(p) => p.actions,
                None => continue,
            };
            if let Some(desc) = campaign.characters.get_mut(status_idx) {
                for action in actions {
                    desc.status.force_set_ammo(action, 999);
                }
            }
            // Re-enable every slot now that it has ammo again.
            for action in actions {
                if action != crate::profiles::Action::NoAction {
                    self.enable_pc_action(assets, id, action);
                }
            }
        }
        ConsoleResponse::Ok("Ammunition !".to_string())
    }

    fn console_call_actor(
        &mut self,
        assets: &LevelAssets,
        actor: &str,
        method: &str,
    ) -> ConsoleResponse {
        // Dispatch a named method on a named actor; the only
        // methods actually reachable from the shipping console
        // are `HideInterface` / `DisplayInterface` on a PC.
        // The original console identifies the actor by hex
        // pointer; the Rust port uses a single-letter initial
        // instead, since `EntityId` is a stable index rather
        // than a raw memory address.
        //
        // We flip the per-PC `interface_hidden` flag and emit
        // the "Hiding interface for PC(...)" /
        // "Displaying interface for PC(...)" response.
        // The HUD portrait row is derived from live PC entities
        // and filters on `pc_data().interface_hidden`.
        let mut ch = actor.chars();
        let (Some(c), None) = (ch.next(), ch.next()) else {
            return ConsoleResponse::Ok("CALL: expected single PC initial.".to_string());
        };
        let ids = self.resolve_pcs_by_initials(assets, &c.to_string());
        let Some(&id) = ids.first() else {
            return ConsoleResponse::Ok("CALL: no such PC.".to_string());
        };
        let hide = match method.to_ascii_uppercase().as_str() {
            "HIDEINTERFACE" => true,
            "DISPLAYINTERFACE" => false,
            _ => {
                return ConsoleResponse::Ok(format!("CALL: unknown method {method}."));
            }
        };
        if let Some(pc) = self.get_entity_mut(id).and_then(|e| e.pc_data_mut()) {
            pc.interface_hidden = hide;
        }
        let verb = if hide { "Hiding" } else { "Displaying" };
        ConsoleResponse::Ok(format!(
            "{verb} interface for PC({}:{})",
            c.to_ascii_uppercase(),
            id.index()
        ))
    }

    /// Force the ammo counter for `action` to `amount` on every
    /// currently-selected PC, printing a leading banner line plus
    /// either the no-selection error or the banner alone.  The
    /// "header print then branch" shape is shared by the `Arrows` and
    /// `WaspMaster` cheats: `"<banner>"` is always emitted, then either
    /// `"<err>"` or the ammo-forcing loop silently proceeds.  Also
    /// calls [`EngineInner::enable_pc_action`] per PC so the slot is
    /// re-enabled now that it has ammo again.
    fn force_ammo_with_banner(
        &mut self,
        assets: &LevelAssets,
        action: crate::profiles::Action,
        amount: u16,
        banner: &str,
        err_if_empty: &str,
    ) -> ConsoleResponse {
        if self.players.seats[0].selection.is_empty() {
            return ConsoleResponse::Ok(format!("{banner}\n{err_if_empty}"));
        }
        // Ammunition lives on the PC's campaign description, which is
        // identified independently of its character profile index.
        let targets: Vec<(EntityId, usize)> = self.players.seats[0]
            .selection
            .iter()
            .filter_map(|&id| {
                let pc = self.get_entity(id)?.pc_data()?;
                Some((id, self.pc_description_index_for_pc_data(pc)?))
            })
            .collect();
        for &(_, description_idx) in &targets {
            self.mission_domain.campaign.characters[description_idx]
                .status
                .force_set_ammo(action, amount);
        }
        for (id, _) in targets {
            if amount > 0 {
                self.enable_pc_action(assets, id, action);
            } else {
                self.disable_pc_action(assets, id, action);
            }
        }
        ConsoleResponse::Ok(banner.to_string())
    }

    /// Resolve a `LUKAS`-style PC initial string (e.g. `"RJS"`) to the
    /// entity IDs of the matching PCs on the map.
    ///
    /// For the `'R'` initial there are two profile entries named
    /// "Robin des bois" (town / forest variants).  We walk *every*
    /// profile that matches the name and return the first one that
    /// resolves to a live PC.
    ///
    /// Unknown initials emit a warning and are otherwise skipped — the
    /// hint string is "Unknown character (use one or more of these:
    /// RJTSWMABC) !".
    fn resolve_pcs_by_initials(&self, assets: &LevelAssets, initials: &str) -> Vec<EntityId> {
        let mut out = Vec::new();
        for ch in initials.chars() {
            let Some(name) = pc_initial_to_profile_name(ch) else {
                tracing::warn!(
                    "console: unknown PC initial {ch:?} — use one or more of these: RJTSWMABC"
                );
                continue;
            };
            out.extend(self.resolve_pc_by_profile_name(assets, name, ch));
        }
        out
    }

    /// Find the live PC using a profile named `name`.
    ///
    /// Walks *all* profiles named `name` to handle the 'R' fallback (Robin
    /// has two profile entries — town and forest). Profile-name lookup is
    /// case-sensitive. A miss is logged: the original can fall back to an
    /// unrelated first profile or reach its fatal reporter instead.
    fn resolve_pc_by_profile_name(
        &self,
        assets: &LevelAssets,
        name: &str,
        initial: char,
    ) -> Option<EntityId> {
        let found = assets
            .profile_manager
            .characters
            .iter()
            .enumerate()
            .filter(|(_, cp)| cp.profile_name == name)
            .map(|(i, _)| crate::profiles::CharacterProfileIdx(i as u32))
            .find_map(|profile_idx| {
                self.world.pc_ids.iter().copied().find(|&pc_id| {
                    self.get_entity(pc_id)
                        .and_then(|e| e.pc_data())
                        .is_some_and(|pc| pc.profile_index == profile_idx)
                })
            });
        if found.is_none() {
            tracing::warn!("console: no PC found for profile {name:?} (initial {initial:?})");
        }
        found
    }

    /// Helper that panics if a console command tries to touch campaign
    /// state outside of a mission.  Matches the "don't fabricate data"
    /// project rule — failing loudly is better than silently no-opping.
    fn campaign_mut_or_panic(&mut self) -> &mut crate::campaign::Campaign {
        &mut self.mission_domain.campaign
    }
}

/// Original HONOLULU usage lines (0x006ad298, 0x006ad228, 0x006ad1dc,
/// 0x006ad17c), printed when the viewed NPC is already on holiday and no
/// remembered NPC can come back.
pub const HONOLULU_USAGE: [&str; 4] = [
    "Honolulu",
    "Cheat couldn't be performed. There are two possibilities to do this cheat:",
    "(1) Enable a view cone, then use this cheat to send this guy to Honolulu",
    "(2) If (1) already done: Disable view cone, use this cheat to get last guy back from Honolulu.",
];

/// How HONOLULU applies, decided by the host before frame admission so the
/// journal records a concrete target.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HonoluluResolution {
    /// Admit HONOLULU against `target`. `sends_away` marks an active NPC
    /// that goes on holiday; the host remembers it for the way back.
    Admit {
        target: Option<EntityId>,
        sends_away: bool,
    },
    /// Print [`HONOLULU_USAGE`]; the command would change nothing.
    Usage,
}

/// Resolve HONOLULU's target from the viewed element and the host's
/// remembered holiday NPC (the original's single `DAT_006c080c` slot).
///
/// Matches the original handler whenever an NPC is viewed: an active one is
/// sent away; for an inactive one the *remembered* NPC comes back if it is
/// still on holiday, otherwise the usage lines are printed. With nothing
/// viewed the original returns silently, which makes its printed step (2),
/// "Disable view cone, use this cheat to get last guy back", unreachable
/// once the view is cleared. The remake instead brings the remembered NPC
/// back in that case, the two-step flow the usage text describes.
pub fn resolve_honolulu<'a>(
    viewed: Option<EntityId>,
    remembered: Option<EntityId>,
    lookup: impl Fn(EntityId) -> Option<&'a Entity>,
) -> HonoluluResolution {
    let on_holiday = |id: EntityId| {
        lookup(id).is_some_and(|entity| entity.is_npc() && !entity.element_data().active)
    };
    let returning = remembered.filter(|&id| on_holiday(id));
    let Some(viewed_id) = viewed else {
        return HonoluluResolution::Admit {
            target: returning,
            sends_away: false,
        };
    };
    match lookup(viewed_id) {
        Some(entity) if entity.is_npc() && !entity.element_data().active => match returning {
            Some(id) => HonoluluResolution::Admit {
                target: Some(id),
                sends_away: false,
            },
            None => HonoluluResolution::Usage,
        },
        entity => HonoluluResolution::Admit {
            target: viewed,
            sends_away: entity.is_some_and(|entity| entity.is_npc()),
        },
    }
}

fn host_dev<'a>(dev: &'a mut Option<&mut DevState>) -> &'a mut DevState {
    dev.as_deref_mut()
        .expect("host-only console command reached authoritative dispatch")
}

/// Toggle a bool debug flag and produce an on/off reply in one expression.
fn toggle_debug(flag: &mut bool, on_msg: &'static str, off_msg: &'static str) -> ConsoleResponse {
    *flag = !*flag;
    ConsoleResponse::Ok(if *flag { on_msg } else { off_msg }.to_string())
}

/// Map a single PC initial to its character-profile name.  Used by
/// `LUKAS` and shared with the campaign-side `create_gang_from_pcs`
/// fallback.
fn pc_initial_to_profile_name(c: char) -> Option<&'static str> {
    match c.to_ascii_uppercase() {
        'R' => Some("Robin des bois"),
        'J' => Some("Petit Jean"),
        'T' => Some("Frere Tuck"),
        'S' => Some("Stutely"),
        'W' => Some("Will Ecarlate"),
        // The original decoder looks up "Marianne" (0x006add80), which
        // names no profile in the shipped profile.cpf; "Lady Marianne" is
        // her actual profile.
        'M' => Some("Lady Marianne"),
        'A' => Some("Paysan A"),
        'B' => Some("Paysan B"),
        'C' => Some("Paysan C"),
        // Remake extension for the Leicester demo; the original has no F.
        'F' => Some("Ferris"),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::campaign::{Campaign, CampaignValue};
    use crate::element::{
        ActorData, ActorSoldier, ElementData, ElementKind, Entity, HumanData, NpcData, SoldierData,
    };

    fn soldier(blipped: bool) -> Entity {
        Entity::Soldier(ActorSoldier {
            element: {
                let mut initial_element = ElementData::from_initial_posture(Posture::Upright);
                initial_element.kind = ElementKind::ActorSoldier;
                initial_element.active = true;
                initial_element.blipped = blipped;
                // Soldiers loaded from a level always carry a concrete
                // posture (the deserialiser remaps `Undefined` to the
                // kind-specific default).  Test helpers don't go
                // through that path, so seed `Upright` here — without
                // it the `posture_after_transition` stamp picks up
                // `Undefined` and the posture-transition panic
                // arm fires when the test launches a sequence.
                initial_element
            },
            actor: ActorData::default(),
            human: HumanData::default(),
            npc: NpcData {
                life_points: 50,
                ai: crate::element::AiActorData {
                    ai_brain: crate::element::AiBrain::Enemy(Box::default()),
                    ..Default::default()
                },
            },
            soldier: SoldierData {
                // Real enemy soldiers always have a defined camp, so
                // derived fighter/soldier iterators include them.
                cached_camp: crate::element::Camp::Lacklandists,
                ..SoldierData::default()
            },
        })
    }

    fn engine_with_campaign() -> (EngineInner, DevState) {
        let dev = DevState::default();
        let mut engine = EngineInner::new();
        engine.mission_domain.campaign = Campaign::new();
        (engine, dev)
    }

    fn assets() -> crate::engine::LevelAssets {
        crate::engine::LevelAssets::new()
    }

    #[test]
    fn hades_completes_death_and_registers_wait_before_returning() {
        let sim = crate::sim_rng::test_context();
        let mut engine = EngineInner::new();
        let id = engine.add_test_entity(soldier(false));
        let assets = engine.test_runtime_assets();
        let mut selected = Some(id);

        engine.dispatch_sim_console_command(
            TickCtx::new(&sim, &assets),
            &mut selected,
            &ConsoleCommand::Hades,
        );

        let victim = engine.expect_entity(id, "Hades victim");
        assert_eq!(victim.npc_data().unwrap().life_points, 0);
        assert_eq!(victim.element_data().posture(), Posture::Dead);
        assert_eq!(
            victim.ai_controller().unwrap().current_substate,
            crate::ai::Substate::SleepingForever
        );
        assert_eq!(selected, None);
        assert_eq!(
            engine
                .mission_domain
                .campaign
                .get_value(CampaignValue::Score),
            0,
            "direct life updates do not award combat score"
        );
        assert_eq!(engine.orders.sequence_manager.sequence_count(), 1);
        let command = engine
            .orders
            .sequence_manager
            .sequences_iter()
            .next()
            .unwrap()
            .elements[0]
            .command;
        assert_eq!(
            command,
            Command::Wait,
            "direct life update must not synthesize a damage instruction"
        );
    }

    #[test]
    fn hades_keeps_invulnerability_but_still_sets_dead_posture_and_wait() {
        let sim = crate::sim_rng::test_context();
        let mut engine = EngineInner::new();
        let mut victim = soldier(false);
        victim.human_data_mut().unwrap().invulnerable = true;
        let id = engine.add_test_entity(victim);
        let assets = engine.test_runtime_assets();
        let mut selected = Some(id);
        engine.dispatch_sim_console_command(
            TickCtx::new(&sim, &assets),
            &mut selected,
            &ConsoleCommand::Hades,
        );
        let victim = engine.expect_entity(id, "invulnerable Hades victim");
        assert_eq!(victim.npc_data().unwrap().life_points, 100);
        assert_eq!(victim.element_data().posture(), Posture::Dead);
        assert_eq!(selected, None);
        assert_eq!(engine.orders.sequence_manager.sequence_count(), 1);
    }

    #[test]
    fn help_prints_one_console_line_per_active_registry_entry() {
        let sim = crate::sim_rng::test_context();
        let (mut engine, mut dev) = engine_with_campaign();
        for use_final in [false, true] {
            dev.console.use_final = use_final;
            let response = engine.run_console_command(
                TickCtx::new(&sim, &assets()),
                &mut dev,
                &mut None,
                "HELP",
            );
            if use_final {
                // The release vector has no HELP entry.
                assert_eq!(response, ConsoleResponse::Unknown);
                assert!(dev.console.drain_output().is_empty());
            } else {
                assert_eq!(response, ConsoleResponse::Ok(String::new()));
                assert_eq!(
                    dev.console.drain_output(),
                    crate::console::help_lines(false)
                );
            }
        }
        assert_eq!(engine.mission_domain.cheat_used_flags, 0);
    }

    #[test]
    fn unknown_input_returns_unknown() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        assert_eq!(
            engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "XYZZY"),
            ConsoleResponse::Unknown
        );
    }

    #[test]
    fn parsed_input_pushes_history() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let (mut engine, mut dev) = engine_with_campaign();
        let _ =
            engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "NUKE");
        assert_eq!(dev.console.history.last().map(String::as_str), Some("NUKE"));
    }

    #[test]
    fn big_brother_toggles_rendered_entity_ids() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let (mut engine, mut dev) = engine_with_campaign();

        let resp = engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "BIG BROTHER",
        );
        assert_eq!(
            resp,
            ConsoleResponse::Ok("Actor infos displayed !".to_string())
        );
        assert!(dev.debug.actor_info_display);
        assert!(dev.debug.entity_ids);

        let resp = engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "BIG BROTHER",
        );
        assert_eq!(
            resp,
            ConsoleResponse::Ok("Actors infos hidden !".to_string())
        );
        assert!(!dev.debug.actor_info_display);
        assert!(!dev.debug.entity_ids);

        let resp =
            engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "IDS");
        assert_eq!(
            resp,
            ConsoleResponse::Ok("Actor infos displayed !".to_string())
        );
        assert!(dev.debug.actor_info_display);
        assert!(dev.debug.entity_ids);
    }

    #[test]
    fn sprite_masks_toggles_overlay() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let (mut engine, mut dev) = engine_with_campaign();

        let resp = engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "SPRITEMASKS",
        );
        assert_eq!(
            resp,
            ConsoleResponse::Ok("Sprite masks displayed.".to_string())
        );
        assert!(dev.debug.sprite_masks_display);

        let resp = engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "SPRITE MASKS",
        );
        assert_eq!(
            resp,
            ConsoleResponse::Ok("Sprite masks hidden.".to_string())
        );
        assert!(!dev.debug.sprite_masks_display);
    }

    #[test]
    fn give_money_mutates_campaign() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let (mut engine, mut dev) = engine_with_campaign();
        let before = engine
            .mission_domain
            .campaign
            .get_value(CampaignValue::Ransom);
        let resp = engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "EZB 500",
        );
        assert_eq!(resp, ConsoleResponse::Ok("Money !".to_string()));
        let after = engine
            .mission_domain
            .campaign
            .get_value(CampaignValue::Ransom);
        assert_eq!(after, before + 500);
    }

    fn run(engine: &mut EngineInner, dev: &mut DevState, input: &str) -> ConsoleResponse {
        let sim = crate::sim_rng::test_context();
        engine.run_console_command(TickCtx::new(&sim, &assets()), dev, &mut None, input)
    }

    fn campaign_value(engine: &EngineInner, value: CampaignValue) -> i32 {
        engine.mission_domain.campaign.get_value(value)
    }

    #[test]
    fn cash_uses_the_first_argument_only_and_scans_like_percent_u() {
        let (mut engine, mut dev) = engine_with_campaign();
        engine
            .mission_domain
            .campaign
            .set_value(CampaignValue::Ransom, 7);
        for (input, expected_total) in [
            ("CASH HUNDRED", 107),
            ("EZB CENT", 107),
            ("CASH HUNDRED THOUSAND", 207),
            ("CASH THOUSAND HUNDRED", 1207),
            ("CASH TENTHOUSAND", 11_207),
            ("CASH HUNDREDTHOUSAND", 111_207),
            ("CASH 12ABC", 111_219),
            ("CASH +1", 111_220),
        ] {
            assert_eq!(
                run(&mut engine, &mut dev, input),
                ConsoleResponse::Ok("Money !".to_owned()),
                "{input}"
            );
            assert_eq!(
                campaign_value(&engine, CampaignValue::Ransom),
                expected_total,
                "{input}"
            );
        }
        for input in ["CASH -5", "CASH 2147483648"] {
            assert!(
                matches!(run(&mut engine, &mut dev, input), ConsoleResponse::Ok(text) if text.starts_with("Money !\nUSAGE: CASH")),
                "{input}"
            );
        }
        assert_eq!(campaign_value(&engine, CampaignValue::Ransom), 111_220);
    }

    #[test]
    fn cash_without_argument_adds_thousand_and_prints_suggestions() {
        let (mut engine, mut dev) = engine_with_campaign();
        let before = campaign_value(&engine, CampaignValue::Ransom);
        assert_eq!(
            run(&mut engine, &mut dev, "CASH"),
            ConsoleResponse::Ok(
                "Money !\nTry also the following :\nCASH CENT\nCASH THOUSAND\n\
                 CASH TENTHOUSAND\nCASH HUNDREDTHOUSAND"
                    .to_owned()
            )
        );
        assert_eq!(
            campaign_value(&engine, CampaignValue::Ransom),
            before + 1000
        );
    }

    #[test]
    fn goodluck_sets_the_amulet_total_despite_saying_added() {
        let (mut engine, mut dev) = engine_with_campaign();
        for _ in 0..2 {
            assert_eq!(
                run(&mut engine, &mut dev, "GOODLUCK 5"),
                ConsoleResponse::Ok(
                    "Amulets [amount]\n5 amulets added to the campaign.".to_owned()
                )
            );
            assert_eq!(campaign_value(&engine, CampaignValue::Amulets), 5);
        }
        run(&mut engine, &mut dev, "AMULETS MANY");
        assert_eq!(campaign_value(&engine, CampaignValue::Amulets), 100);
    }

    #[test]
    fn wappen_adds_blazons_and_rejects_unscannable_amounts() {
        let (mut engine, mut dev) = engine_with_campaign();
        assert_eq!(
            run(&mut engine, &mut dev, "WAPPEN"),
            ConsoleResponse::Ok("Blazons !".to_owned())
        );
        assert_eq!(campaign_value(&engine, CampaignValue::Blazon), 1);
        run(&mut engine, &mut dev, "WAPPEN 4 9");
        assert_eq!(campaign_value(&engine, CampaignValue::Blazon), 5);
        assert_eq!(
            run(&mut engine, &mut dev, "WAPPEN MANY"),
            ConsoleResponse::Ok("Blazons !\nUSAGE: WAPPEN [<amount>]".to_owned())
        );
        assert_eq!(campaign_value(&engine, CampaignValue::Blazon), 5);
    }

    fn bonus_blazon(quantity: u16, active: bool) -> Entity {
        let mut element = ElementData::from_initial_posture(Posture::Upright);
        element.kind = ElementKind::ObjectBonus;
        element.active = active;
        Entity::Bonus(crate::element::ElementBonus {
            element,
            object: crate::element::ObjectData {
                object_type: ObjectType::BonusBlazon,
                quantity,
                ..Default::default()
            },
        })
    }

    /// One current mission with the given location and filename, plus a
    /// Will Scarlet character profile for the S02 rescue entry.
    fn engine_in_mission(
        location: crate::profiles::MissionLocation,
        filename: &str,
    ) -> (EngineInner, DevState, LevelAssets) {
        let (mut engine, dev) = engine_with_campaign();
        let mut profiles = crate::profiles::ProfileManager::new();
        profiles.missions.push(crate::profiles::MissionProfile {
            location,
            mission_filename: filename.into(),
            ..Default::default()
        });
        profiles.characters.push(crate::profiles::CharacterProfile {
            profile_name: "Will Ecarlate".into(),
            vip: true,
            ..Default::default()
        });
        let campaign = &mut engine.mission_domain.campaign;
        campaign.missions.push(crate::mission::Mission {
            profile_idx: Some(0),
            ..Default::default()
        });
        campaign.current_mission_idx = Some(0);
        let assets = LevelAssets {
            profile_manager: std::sync::Arc::new(profiles),
            ..LevelAssets::default()
        };
        (engine, dev, assets)
    }

    #[test]
    fn win_pays_mission_money_rescues_and_collects_remaining_blazons() {
        let sim = crate::sim_rng::test_context();
        for input in ["WIN", "WINNER"] {
            let (mut engine, mut dev, assets) =
                engine_in_mission(crate::profiles::MissionLocation::default(), "S02_Lei_MP");
            let stat = &mut engine.mission_domain.mission_stat;
            stat.soldier_money = 300;
            stat.bonus_money = 50;
            stat.collected_money = 20;
            engine.add_test_entity(bonus_blazon(2, true));
            engine.add_test_entity(bonus_blazon(5, false));
            let ransom = campaign_value(&engine, CampaignValue::Ransom);
            let blazons = campaign_value(&engine, CampaignValue::Blazon);

            let response =
                engine.run_console_command(TickCtx::new(&sim, &assets), &mut dev, &mut None, input);
            assert_eq!(response, ConsoleResponse::Ok("Mission won !".to_owned()));
            assert_eq!(campaign_value(&engine, CampaignValue::Ransom), ransom + 330);
            assert_eq!(campaign_value(&engine, CampaignValue::Blazon), blazons + 2);
            assert!(
                engine
                    .mission_domain
                    .campaign
                    .is_in_gang(crate::profiles::CharacterProfileIdx(0)),
                "S02_Lei_MP returns Will Ecarlate"
            );
            assert!(engine.mission_domain.state.quit_won);
        }
    }

    #[test]
    fn win_does_nothing_in_sherwood() {
        let sim = crate::sim_rng::test_context();
        let (mut engine, mut dev, assets) =
            engine_in_mission(crate::profiles::MissionLocation::Sherwood, "S02_Lei_MP");
        engine.mission_domain.mission_stat.soldier_money = 300;
        let ransom = campaign_value(&engine, CampaignValue::Ransom);
        let response =
            engine.run_console_command(TickCtx::new(&sim, &assets), &mut dev, &mut None, "WIN");
        assert_eq!(response, ConsoleResponse::Ok(String::new()));
        assert_eq!(campaign_value(&engine, CampaignValue::Ransom), ransom);
        assert!(!engine.mission_domain.state.quit_won);
        assert_eq!(engine.mission_domain.campaign.gang_indices.len(), 0);
    }

    #[test]
    fn i_am_the_winner_overrides_the_ares_state_of_the_current_mission() {
        let sim = crate::sim_rng::test_context();
        let (mut engine, mut dev, assets) =
            engine_in_mission(crate::profiles::MissionLocation::default(), "S02_Lei_MP");
        let response = engine.run_console_command(
            TickCtx::new(&sim, &assets),
            &mut dev,
            &mut None,
            "I AM THE WINNER",
        );
        assert_eq!(response, ConsoleResponse::Ok("Campaign won !".to_owned()));
        assert_eq!(
            engine.mission_domain.campaign.missions[0].ares_state_override,
            Some(9)
        );
        assert!(engine.mission_domain.state.quit_won);

        let (mut engine, mut dev) = engine_with_campaign();
        let response = run(&mut engine, &mut dev, "I AM THE WINNER");
        assert_eq!(
            response,
            ConsoleResponse::Ok("Error: no current campaign mission.".to_owned())
        );
        assert!(!engine.mission_domain.state.quit_won);
    }

    #[test]
    fn report_logs_the_campaign_and_acknowledges_in_the_console() {
        let (mut engine, mut dev) = engine_with_campaign();
        assert_eq!(
            run(&mut engine, &mut dev, "REPORT"),
            ConsoleResponse::Ok("Reporting...".to_owned())
        );
        assert!(dev.console.drain_output().is_empty());
    }

    #[test]
    fn campaign_requests_a_host_load_of_exactly_one_file() {
        let (mut engine, mut dev) = engine_with_campaign();
        assert_eq!(
            run(&mut engine, &mut dev, "CAMPAIGN Slot1.sav"),
            ConsoleResponse::LoadCampaignRequested("Slot1.sav".into())
        );
        for input in ["CAMPAIGN", "CAMPAIGN A B"] {
            assert_eq!(
                run(&mut engine, &mut dev, input),
                ConsoleResponse::Ok("Verboten : Please enter a valid filename !".to_owned())
            );
        }
    }

    #[test]
    fn lose_mission_sets_quit_lost() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let (mut engine, mut dev) = engine_with_campaign();
        assert!(!engine.mission_domain.state.quit_lost);
        let resp =
            engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "LOOSE");
        assert_eq!(resp, ConsoleResponse::Ok("Mission lost !".to_owned()));
        assert!(engine.mission_domain.state.quit_lost);
    }

    #[test]
    fn freeze_toggles_ai_global_flag() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        assert!(!engine.ai.global.freeze);
        engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "FREEZE");
        assert!(engine.ai.global.freeze);
        engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "FREEZE");
        assert!(!engine.ai.global.freeze);
    }

    #[test]
    fn ubiquity_reveals_all_blipped_npcs() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        let id_blipped = engine.add_test_entity(soldier(true));
        let id_plain = engine.add_test_entity(soldier(false));
        let id_away = engine.add_test_entity(soldier(true));
        let spot = crate::coordinates::MapPoint::new(12.0, 34.0);
        {
            let element = engine.get_entity_mut(id_away).unwrap().element_data_mut();
            element.active = false;
            element.set_position_map(spot);
        }

        for input in ["UBIQUITY", "UNBLIP"] {
            let resp = engine.run_console_command(
                TickCtx::new(sim, &assets()),
                &mut dev,
                &mut None,
                input,
            );
            assert_eq!(resp, ConsoleResponse::Ok("Unblip !".to_owned()));
        }
        // Revealing neither activates nor moves an inactive NPC.
        let away = engine.get_entity(id_away).unwrap().element_data();
        assert!(!away.blipped);
        assert!(!away.active);
        assert_eq!(away.position_map(), spot);

        assert!(
            !engine
                .get_entity(id_blipped)
                .unwrap()
                .element_data()
                .blipped
        );
        assert!(!engine.get_entity(id_plain).unwrap().element_data().blipped);
    }

    #[test]
    fn highlander2_marks_enemy_npcs_invulnerable() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        let id = engine.add_test_entity(soldier(false));
        // Sanity: starts vulnerable.
        assert!(
            !engine
                .get_entity(id)
                .unwrap()
                .human_data()
                .unwrap()
                .invulnerable
        );

        engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "HIGHLANDER2",
        );

        assert!(
            engine
                .get_entity(id)
                .unwrap()
                .human_data()
                .unwrap()
                .invulnerable
        );
    }

    fn camp_soldier(camp: Camp) -> Entity {
        let mut entity = soldier(false);
        if let Entity::Soldier(soldier) = &mut entity {
            soldier.soldier.cached_camp = camp;
        }
        entity
    }

    fn royalist_pc() -> Entity {
        Entity::Pc(crate::element::ActorPc {
            element: {
                let mut element = ElementData::from_initial_posture(Posture::Upright);
                element.kind = ElementKind::ActorPc;
                element.active = true;
                element
            },
            actor: ActorData::default(),
            human: HumanData::default(),
            pc: crate::element::PcData {
                cached_camp: Camp::Royalists,
                ..Default::default()
            },
        })
    }

    fn royalist_civilian() -> Entity {
        Entity::Civilian(crate::element::ActorCivilian {
            element: {
                let mut element = ElementData::from_initial_posture(Posture::Upright);
                element.kind = ElementKind::ActorCivilian;
                element.active = true;
                element
            },
            actor: ActorData::default(),
            human: HumanData::default(),
            npc: NpcData::default(),
            civilian: crate::element::CivilianData {
                cached_camp: Camp::Royalists,
                ..Default::default()
            },
        })
    }

    #[test]
    fn highlander_commands_protect_one_camps_fighters_idempotently() {
        let (mut engine, mut dev) = engine_with_campaign();
        let pc = engine.add_test_entity(royalist_pc());
        let ally = engine.add_test_entity(camp_soldier(Camp::Royalists));
        let foe = engine.add_test_entity(camp_soldier(Camp::Lacklandists));
        let civilian = engine.add_test_entity(royalist_civilian());
        let invulnerable = |engine: &EngineInner| {
            [pc, ally, foe, civilian].map(|id| {
                engine
                    .expect_entity(id, "fixture")
                    .human_data()
                    .unwrap()
                    .invulnerable
            })
        };

        for _ in 0..2 {
            assert_eq!(
                run(&mut engine, &mut dev, "IMMUNITY"),
                ConsoleResponse::Ok("Friends invulnerable".to_owned())
            );
            assert_eq!(invulnerable(&engine), [true, true, false, false]);
        }
        assert_eq!(
            run(&mut engine, &mut dev, "HIGHLANDER"),
            ConsoleResponse::Ok("Friends invulnerable".to_owned())
        );
        assert_eq!(
            run(&mut engine, &mut dev, "HIGHLANDER2"),
            ConsoleResponse::Ok("Foes invulnerable".to_owned())
        );
        assert_eq!(invulnerable(&engine), [true, true, true, false]);
    }

    fn damage_targets(engine: &EngineInner) -> Vec<EntityId> {
        engine
            .orders
            .sequence_manager
            .sequences_iter()
            .map(|sequence| {
                let element = &sequence.elements[0];
                assert_eq!(element.command, Command::ReceiveDamage);
                element.owner.expect("damage element has an owner")
            })
            .collect()
    }

    /// Assets naming character profiles 0.. in order, and one live PC per
    /// profile.
    fn engine_with_named_pcs(
        names: &[&str],
    ) -> (EngineInner, DevState, LevelAssets, Vec<EntityId>) {
        let (mut engine, dev) = engine_with_campaign();
        let mut profiles = crate::profiles::ProfileManager::new();
        let mut pcs = Vec::new();
        for (index, name) in names.iter().enumerate() {
            profiles.characters.push(crate::profiles::CharacterProfile {
                index: index as u32,
                profile_name: (*name).into(),
                ..Default::default()
            });
            let mut pc = royalist_pc();
            if let Entity::Pc(actor) = &mut pc {
                actor.pc.profile_index = crate::profiles::CharacterProfileIdx(index as u32);
            }
            pcs.push(engine.add_test_entity(pc));
        }
        let assets = LevelAssets {
            profile_manager: std::sync::Arc::new(profiles),
            ..LevelAssets::default()
        };
        (engine, dev, assets, pcs)
    }

    #[test]
    fn lukas_reports_unknown_initials_and_damages_only_named_pcs() {
        let sim = crate::sim_rng::test_context();
        let (mut engine, mut dev, assets, pcs) =
            engine_with_named_pcs(&["Robin des bois", "Paysan C", "Lady Marianne"]);
        // The PC selection plays no part in LUKAS.
        engine.players.seats[0].selection = vec![pcs[0]];
        let response = engine.run_console_command(
            TickCtx::new(&sim, &assets),
            &mut dev,
            &mut None,
            "LUKAS CQM R",
        );
        assert_eq!(
            response,
            ConsoleResponse::Ok(
                "PCs knocked out !\n\
                 Unknown character (use one or more of these : RJTSWMABS) !"
                    .to_owned()
            )
        );
        assert_eq!(damage_targets(&engine), [pcs[1], pcs[2]]);

        let response =
            engine.run_console_command(TickCtx::new(&sim, &assets), &mut dev, &mut None, "LUKAS");
        assert_eq!(
            response,
            ConsoleResponse::Ok("PCs knocked out !".to_owned())
        );
        assert_eq!(damage_targets(&engine).len(), 2);
    }

    #[test]
    fn coma_prints_its_banner_before_each_failed_check() {
        let sim = crate::sim_rng::test_context();
        let (mut engine, mut dev, assets, pcs) = engine_with_named_pcs(&["Robin des bois"]);
        let mut coma = |engine: &mut EngineInner| {
            engine.run_console_command(TickCtx::new(&sim, &assets), &mut dev, &mut None, "COMA")
        };
        assert_eq!(
            coma(&mut engine),
            ConsoleResponse::Ok("Coma !\nPlease, select the PC to make sleep.".to_owned())
        );
        engine.players.seats[0].selection = vec![pcs[0]];
        engine
            .mission_domain
            .campaign
            .set_value(CampaignValue::Amulets, 0);
        assert_eq!(
            coma(&mut engine),
            ConsoleResponse::Ok(
                "Coma !\nThere not enough amulets left to put the selected PC in the coma."
                    .to_owned()
            )
        );
        assert!(damage_targets(&engine).is_empty());
        engine
            .mission_domain
            .campaign
            .set_value(CampaignValue::Amulets, 1);
        assert_eq!(coma(&mut engine), ConsoleResponse::Ok("Coma !".to_owned()));
        assert_eq!(damage_targets(&engine), [pcs[0]]);
        assert_eq!(
            engine
                .mission_domain
                .campaign
                .get_value(CampaignValue::Amulets),
            1,
            "the handler itself spends no amulet"
        );
    }

    #[test]
    fn amor_and_wasp_master_force_stock_on_the_selected_pcs_campaign_description() {
        use crate::profiles::Action;
        let sim = crate::sim_rng::test_context();
        for (input, action, banner, empty_error) in [
            (
                "AMOR",
                Action::Bow,
                "Arrows",
                "You must selected at meast one PC.",
            ),
            (
                "WASP MASTER",
                Action::WaspNest,
                "Wasps",
                "You must selected at meast one PC which must go to paradise.",
            ),
        ] {
            let (mut engine, mut dev, mut assets, pcs) =
                engine_with_named_pcs(&["Robin des bois", "Petit Jean"]);
            let mut profiles = (*assets.profile_manager).clone();
            profiles.characters[0].actions[0] = action;
            assets.profile_manager = std::sync::Arc::new(profiles);
            // Campaign descriptions are stored in the opposite order of the
            // profiles, so a profile index would address the other PC.
            engine.mission_domain.campaign.characters = [1, 0]
                .map(|profile| crate::campaign::PcDescription {
                    character_profile_idx: Some(crate::profiles::CharacterProfileIdx(profile)),
                    ..Default::default()
                })
                .into();
            for (pc, description) in [(pcs[0], 1), (pcs[1], 0)] {
                let data = engine.get_entity_mut(pc).unwrap().pc_data_mut().unwrap();
                data.campaign_description_index = Some(description);
                data.disabled_actions = vec![true, false, false];
            }

            let mut dispatch = |engine: &mut EngineInner| {
                engine.run_console_command(TickCtx::new(&sim, &assets), &mut dev, &mut None, input)
            };
            assert_eq!(
                dispatch(&mut engine),
                ConsoleResponse::Ok(format!("{banner}\n{empty_error}"))
            );
            engine.players.seats[0].selection = vec![pcs[0]];
            assert_eq!(
                dispatch(&mut engine),
                ConsoleResponse::Ok(banner.to_owned())
            );

            let ammo = |description: usize| {
                engine.mission_domain.campaign.characters[description]
                    .status
                    .get_ammo(action)
            };
            assert_eq!((ammo(1), ammo(0)), (0xFFFF, 0), "{input}");
            let disabled = |pc: EntityId| {
                engine
                    .get_entity(pc)
                    .unwrap()
                    .pc_data()
                    .unwrap()
                    .disabled_actions
                    .clone()
            };
            assert_eq!(disabled(pcs[0]), [false, false, false], "{input}");
            assert_eq!(disabled(pcs[1]), [true, false, false], "{input}");
        }
    }

    #[test]
    fn goldeneye_toggles_detection_invisibility() {
        let (mut engine, mut dev) = engine_with_campaign();
        assert_eq!(
            run(&mut engine, &mut dev, "GOLDENEYE"),
            ConsoleResponse::Ok("Invisibility On.".to_owned())
        );
        assert!(engine.ai.global.golden_eye_mode);
        assert_eq!(
            run(&mut engine, &mut dev, "GOLDENEYE"),
            ConsoleResponse::Ok("Invisibility Off.".to_owned())
        );
        assert!(!engine.ai.global.golden_eye_mode);
    }

    #[test]
    fn elevation_is_debug_toggle() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        assert!(!dev.debug.elevation_display);
        engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "ELEVATION",
        );
        assert!(dev.debug.elevation_display);
    }

    #[test]
    fn level_text_routes_by_option() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "LEVEL TEXT DB",
        );
        assert!(dev.debug.all_debriefings);
        assert!(!dev.debug.all_dialogues);
    }

    #[test]
    fn roter_alarm_launches_enter_attentive_sequence_on_every_soldier() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        let id = engine.add_test_entity(soldier(false));
        {
            let e = engine.get_entity(id).unwrap().enemy_ai().unwrap();
            assert!(!e.attentive);
            assert!(!e.will_be_attentive);
        }
        assert_eq!(engine.orders.sequence_manager.sequence_count(), 0);
        let resp = engine.run_console_command(
            TickCtx::new(sim, &assets()),
            &mut dev,
            &mut None,
            "ROTER ALARM",
        );
        // ROTER ALARM is a silent cheat — emits no console text.
        assert_eq!(resp, ConsoleResponse::Ok(String::new()));
        // The sequence element launch flips `will_be_attentive` immediately;
        // `attentive` only flips once the transition animation completes
        // (see `engine::animation` for the anim-done handler).
        let e = engine.get_entity(id).unwrap().enemy_ai().unwrap();
        assert!(e.will_be_attentive);
        assert_eq!(engine.orders.sequence_manager.sequence_count(), 1);
    }

    #[test]
    fn nuke_launches_damage_on_every_soldier() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        engine.add_test_entity(soldier(false));
        engine.add_test_entity(soldier(false));
        assert_eq!(engine.orders.sequence_manager.sequence_count(), 0);
        let resp =
            engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "NUKE");
        assert_eq!(
            resp,
            ConsoleResponse::Ok("Nuking ...\nNuked 2 soldiers".to_string())
        );
        assert_eq!(engine.orders.sequence_manager.sequence_count(), 2);
    }

    #[test]
    fn final_mode_accepts_unblip_alias() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        dev.console.use_final = true;
        engine.add_test_entity(soldier(true));
        let resp =
            engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "UNBLIP");
        assert!(matches!(resp, ConsoleResponse::Ok(_)));
    }

    #[test]
    fn final_mode_rejects_dev_only_commands() {
        let sim_context = crate::sim_rng::test_context();
        let sim = &sim_context;
        let mut dev = DevState::default();
        let mut engine = EngineInner::new();
        dev.console.use_final = true;
        // NUKE is a dev-only cheat — must not resolve in final mode.
        assert_eq!(
            engine.run_console_command(TickCtx::new(sim, &assets()), &mut dev, &mut None, "NUKE"),
            ConsoleResponse::Unknown
        );
    }

    #[test]
    fn actor_cheat_admission_marks_attempt_even_when_selection_is_missing() {
        let sim = crate::sim_rng::test_context();
        let assets = assets();
        for (command, expected) in [
            (ConsoleCommand::Honolulu, ""),
            (
                ConsoleCommand::Morpheus,
                "MORPHEUS\nPlease enable view cone of a NPC before using this command.",
            ),
            (
                ConsoleCommand::Hades,
                "HADES\nPlease enable view cone of a NPC before using this command.",
            ),
            (
                ConsoleCommand::LastManStanding,
                "Last man standing\nPlease enable view cone of a NPC before using this command.",
            ),
        ] {
            let mut engine = EngineInner::new();
            let mut selected = None;
            let response = engine.dispatch_sim_console_command(
                TickCtx::new(&sim, &assets),
                &mut selected,
                &command,
            );
            assert_eq!(response, ConsoleResponse::Ok(expected.to_owned()));
            assert_eq!(selected, None);
            assert_eq!(
                engine.mission_domain.cheat_used_flags,
                CHEAT_CONSOLE_COMMAND
            );
            assert_eq!(engine.orders.sequence_manager.sequence_count(), 0);
        }
    }

    #[test]
    fn honolulu_reports_a_missing_selected_entity_without_clearing_it() {
        let sim = crate::sim_rng::test_context();
        let mut engine = EngineInner::new();
        let id = EntityId::new(999, crate::entity_id::EntityIdKind::Soldier);
        let mut selected = Some(id);
        let response = engine.dispatch_sim_console_command(
            TickCtx::new(&sim, &assets()),
            &mut selected,
            &ConsoleCommand::Honolulu,
        );
        assert_eq!(
            response,
            ConsoleResponse::Ok(format!("Error: selected entity {id:?} no longer exists")),
        );
        assert_eq!(selected, Some(id));
    }

    #[test]
    fn honolulu_retains_host_latch_and_reactivates_resolved_npc_without_host_state() {
        let sim = crate::sim_rng::test_context();
        let assets = assets();
        let mut engine = EngineInner::new();
        let mut dev = DevState::default();
        let id = engine.add_test_entity(soldier(false));
        let mut selected = Some(id);
        assert_eq!(
            engine.dispatch_console_command(
                TickCtx::new(&sim, &assets),
                &mut dev,
                &mut selected,
                &ConsoleCommand::Honolulu,
            ),
            ConsoleResponse::Ok("Honolulu\nBye, I'm on holiday.".to_owned()),
        );
        assert_eq!(selected, None);
        assert_eq!(dev.last_actor_in_honolulu, Some(id));
        assert!(!engine.get_entity(id).unwrap().element_data().active);

        selected = Some(id);
        assert_eq!(
            engine.dispatch_sim_console_command(
                TickCtx::new(&sim, &assets),
                &mut selected,
                &ConsoleCommand::Honolulu,
            ),
            ConsoleResponse::Ok("Honolulu\nI'm back!".to_owned()),
        );
        assert_eq!(selected, Some(id));
        assert!(engine.get_entity(id).unwrap().element_data().active);
    }

    #[test]
    fn honolulu_resolution_follows_the_original_branches_plus_the_two_step_fallback() {
        let mut engine = EngineInner::new();
        let active = engine.add_test_entity(soldier(false));
        let away = engine.add_test_entity(soldier(false));
        let also_away = engine.add_test_entity(soldier(false));
        let pc = engine.add_test_entity(royalist_pc());
        for id in [away, also_away] {
            engine.get_entity_mut(id).unwrap().element_data_mut().active = false;
        }
        let missing = EntityId::new(999, crate::entity_id::EntityIdKind::Soldier);
        let resolve =
            |viewed, remembered| resolve_honolulu(viewed, remembered, |id| engine.get_entity(id));
        let admit = |target, sends_away| HonoluluResolution::Admit { target, sends_away };

        // Original branches with a viewed element.
        assert_eq!(resolve(Some(active), Some(away)), admit(Some(active), true));
        assert_eq!(
            resolve(Some(also_away), Some(away)),
            admit(Some(away), false)
        );
        assert_eq!(resolve(Some(away), Some(away)), admit(Some(away), false));
        assert_eq!(resolve(Some(also_away), None), HonoluluResolution::Usage);
        assert_eq!(
            resolve(Some(also_away), Some(active)),
            HonoluluResolution::Usage
        );
        assert_eq!(resolve(Some(pc), Some(away)), admit(Some(pc), false));
        assert_eq!(
            resolve(Some(missing), Some(away)),
            admit(Some(missing), false)
        );
        // No view: the original is silent; the remake brings the
        // remembered NPC back while it is still away.
        assert_eq!(resolve(None, Some(away)), admit(Some(away), false));
        assert_eq!(resolve(None, Some(active)), admit(None, false));
        assert_eq!(resolve(None, None), admit(None, false));
    }

    #[test]
    fn honolulu_two_step_flow_sends_away_and_brings_back_in_place() {
        let sim = crate::sim_rng::test_context();
        let assets = assets();
        let mut engine = EngineInner::new();
        let npc = engine.add_test_entity(soldier(false));
        let spot = crate::coordinates::MapPoint::new(40.0, 25.0);
        engine
            .get_entity_mut(npc)
            .unwrap()
            .element_data_mut()
            .set_position_map(spot);
        let mut remembered = None;
        let mut view = Some(npc);
        let mut expected = ["Honolulu\nBye, I'm on holiday.", "Honolulu\nI'm back!"].into_iter();
        for active_after in [false, true] {
            let HonoluluResolution::Admit { target, sends_away } =
                resolve_honolulu(view, remembered, |id| engine.get_entity(id))
            else {
                panic!("usage")
            };
            let mut selected = target;
            let response = engine.dispatch_sim_console_command(
                TickCtx::new(&sim, &assets),
                &mut selected,
                &ConsoleCommand::Honolulu,
            );
            assert_eq!(
                response,
                ConsoleResponse::Ok(expected.next().unwrap().to_owned())
            );
            if sends_away {
                remembered = target;
                view = selected;
                assert_eq!(view, None, "sending away clears the view cone");
            }
            let element = engine.get_entity(npc).unwrap().element_data();
            assert_eq!(element.active, active_after);
            assert_eq!(element.position_map(), spot);
        }
    }

    #[test]
    fn last_man_standing_keeps_only_the_viewed_actor_and_rejects_stale_views() {
        let sim = crate::sim_rng::test_context();
        let assets = assets();
        let mut engine = EngineInner::new();
        let hero = engine.add_test_entity(soldier(false));
        let others = [
            engine.add_test_entity(soldier(false)),
            engine.add_test_entity(soldier(true)),
        ];
        let stale = EntityId::new(999, crate::entity_id::EntityIdKind::Soldier);
        let mut selected = Some(stale);
        assert_eq!(
            engine.dispatch_sim_console_command(
                TickCtx::new(&sim, &assets),
                &mut selected,
                &ConsoleCommand::LastManStanding,
            ),
            ConsoleResponse::Ok(format!(
                "Last man standing\nError: selected entity {stale:?} no longer exists"
            ))
        );
        assert!(
            others
                .iter()
                .all(|&id| engine.get_entity(id).unwrap().element_data().active)
        );

        let mut selected = Some(hero);
        assert_eq!(
            engine.dispatch_sim_console_command(
                TickCtx::new(&sim, &assets),
                &mut selected,
                &ConsoleCommand::LastManStanding,
            ),
            ConsoleResponse::Ok("Last man standing\nLonely hero...".to_owned())
        );
        assert_eq!(selected, Some(hero));
        assert!(engine.get_entity(hero).unwrap().element_data().active);
        assert!(
            others
                .iter()
                .all(|&id| !engine.get_entity(id).unwrap().element_data().active)
        );
    }

    #[test]
    fn call_validates_actor_before_method_and_does_not_launch_work_on_error() {
        let sim = crate::sim_rng::test_context();
        let mut engine = EngineInner::new();
        for (actor, expected) in [
            ("RR", "CALL: expected single PC initial."),
            ("R", "CALL: no such PC."),
        ] {
            let response = engine.dispatch_sim_console_command(
                TickCtx::new(&sim, &assets()),
                &mut None,
                &ConsoleCommand::Call {
                    actor: actor.to_owned(),
                    method: "UNKNOWN".to_owned(),
                },
            );
            assert_eq!(response, ConsoleResponse::Ok(expected.to_owned()));
            assert_eq!(engine.orders.sequence_manager.sequence_count(), 0);
        }
    }
}
