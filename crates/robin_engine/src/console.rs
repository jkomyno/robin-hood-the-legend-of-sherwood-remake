//! In-game debug console.
//!
//! Processes text commands for cheating/debugging (give money, teleport,
//! win mission, toggle display overlays, etc.).
//!
//! This module owns the parser and the `ConsoleCommand` enum.  Actual
//! command dispatch lives on the engine side in
//! `engine::console_dispatch`, which mutates engine/campaign state and
//! returns a human-readable response.

// ─── Command enum ───────────────────────────────────────────────

/// Every console command recognized by the game.
///
/// Commands that take arguments carry them inline. Commands from the
/// "final" cheat list (CASH, GOODLUCK, etc.) are parsed as aliases to
/// the same variant as their dev-mode equivalents.
#[derive(
    Debug,
    Clone,
    PartialEq,
    serde::Serialize,
    serde::Deserialize,
    robin_state_hash_derive::StateHash,
    bitcode::Encode,
    bitcode::Decode,
)]
pub enum ConsoleCommand {
    // ── Campaign / mission flow ──
    GiveMoney {
        amount: u32,
        /// True when the user invoked `CASH`/`EZB` with no argument.
        /// In that case the dispatcher prints a four-line help listing
        /// (`Try also the following:`, `CASH CENT`, etc.) before
        /// applying the 1000-gold default.
        show_help: bool,
    },
    GiveBlazon {
        amount: u32,
    },
    GiveAmulets {
        amount: u32,
    },
    AddPeasant,
    WinMission,
    WinCampaign,
    LoseMission,
    CampaignReport,
    LoadCampaign {
        filename: String,
    },

    // ── Actor / AI operations ──
    Goldeneye,
    Elevation,
    BigBrother,
    BudSpencer,
    Nuke,
    Wakeup,
    Highlander,
    Highlander2,
    Honolulu,
    LastManStanding,
    DiesIrae,
    Freeze,
    StupidSoldiers,
    RoterAlarm,
    MisterSandman,
    Morpheus,
    Hades,
    Coma,
    Reinforcement,
    SanPetrus,
    WaspMaster,
    GiveArrows,
    GiveAmmo,
    Ubiquity,
    Lukas {
        pcs: Option<String>,
    },
    Call {
        actor: String,
        method: String,
    },
    /// `DIPLOMACY <first> <second> <allied|neutral|hostile>`.
    SetDiplomacy {
        first: u16,
        second: u16,
        relationship: crate::diplomacy::Relationship,
    },

    // ── Display toggles ──
    Ai,
    Anim,
    Babylon,
    CestLaZone,
    Companies,
    Einstein,
    EnergyDisplay,
    Euler,
    Fps,
    Light,
    LevelText {
        option: Option<String>,
    },
    Motion,
    Noise,
    PcSight,
    Projection,
    Railroad,
    SeekAndDestroy,
    Shadow,
    Sphere,
    SpriteMasks,
    Surface,
    StatusFramecache,
    StatusHardware,
    StatusShadow,
    StatusPc,

    // ── Misc ──
    Help,
    AssertFalse,
    Forget,
    Sarkozy,
    Optimize,

    /// A known keyword that was invoked with the wrong number of
    /// arguments.  Carries the in-body "USAGE: …" / "Verboten …"
    /// help text (e.g. campaign with < 2 args).  The dispatcher turns
    /// this into a plain `Ok(msg)` so
    /// the overlay shows the help text instead of a generic
    /// "Unknown command" error.
    UsageError(String),
}

impl ConsoleCommand {
    /// Whether this command only changes host-owned developer presentation.
    ///
    /// These commands are dispatched by the host before frame admission and
    /// must never be placed in the deterministic external-action journal.
    pub fn is_host_only(&self) -> bool {
        matches!(
            self,
            Self::Elevation
                | Self::BigBrother
                | Self::Einstein
                | Self::EnergyDisplay
                | Self::Euler
                | Self::Fps
                | Self::Light
                | Self::LevelText { .. }
                | Self::Motion
                | Self::Noise
                | Self::PcSight
                | Self::Projection
                | Self::Railroad
                | Self::SeekAndDestroy
                | Self::Shadow
                | Self::Sphere
                | Self::SpriteMasks
                | Self::Surface
                | Self::Anim
                | Self::Companies
                | Self::CestLaZone
                | Self::StatusFramecache
                | Self::StatusHardware
                | Self::StatusShadow
                | Self::StatusPc
                | Self::Help
                | Self::AssertFalse
                | Self::Forget
                | Self::Sarkozy
                | Self::Optimize
                | Self::UsageError(_)
        )
    }
}

// ─── Original registry ──────────────────────────────────────────

/// Which of the original console's two command vectors owns an entry.
///
/// The original console (`FUN_0045ad00`) fills a developer ("primary")
/// vector with 63 entries and a release vector with 9 entries. It starts
/// release-only; the GLOIRE token switches to the primary vector.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsoleRegistry {
    Primary,
    Release,
}

/// One original `FUN_0045b620`/`FUN_0045b900` registration call.
///
/// VAs refer to the SHA-matched original `Game.exe` (image base
/// `0x00400000`) and are kept as parity evidence.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ConsoleRegistration {
    pub registry: ConsoleRegistry,
    /// Exact registered name; multiword names are matched word by word.
    pub name: &'static str,
    pub name_va: u32,
    /// Verbatim description printed by HELP (empty for release entries).
    pub description: &'static str,
    pub description_va: u32,
    pub handler_va: u32,
}

const fn reg(
    registry: ConsoleRegistry,
    name: &'static str,
    name_va: u32,
    description: &'static str,
    description_va: u32,
    handler_va: u32,
) -> ConsoleRegistration {
    ConsoleRegistration {
        registry,
        name,
        name_va,
        description,
        description_va,
        handler_va,
    }
}

use ConsoleRegistry::{Primary, Release};

/// Every original registration in call order.
pub const ORIGINAL_REGISTRY: [ConsoleRegistration; 72] = [
    reg(
        Primary,
        "AI",
        0x006ac8cc,
        "Display AI information.",
        0x006ac8d0,
        0x0045e620,
    ),
    reg(
        Primary,
        "ALARM",
        0x006ac8a8,
        "Reinforcement arriving...",
        0x006ac8b0,
        0x0045eb40,
    ),
    reg(
        Primary,
        "AMOR",
        0x006ac85c,
        "Increase the number of available arrows for all the selected PCs.",
        0x006ac864,
        0x0045ee70,
    ),
    reg(
        Primary,
        "AMULETS",
        0x006ac834,
        "Add amulets to the campaign.",
        0x006ac83c,
        0x0045eaa0,
    ),
    reg(
        Primary,
        "ASSERTFALSE",
        0x006ac820,
        "Ok !",
        0x006ac82c,
        0x0045e510,
    ),
    reg(
        Primary,
        "BABYLON",
        0x006ac7f4,
        "Display all NPC remarks on screen.",
        0x006ac7fc,
        0x0045e6a0,
    ),
    reg(
        Primary,
        "BIG BROTHER",
        0x006ac7cc,
        "Display some actor infos.",
        0x006ac7d8,
        0x0045e530,
    ),
    reg(
        Primary,
        "BUD SPENCER",
        0x006ac7ac,
        "Stun all oponents.",
        0x006ac7b8,
        0x0045e2e0,
    ),
    reg(
        Primary,
        "CALL",
        0x006ac790,
        "Call a PC's method",
        0x006ac798,
        0x0045f590,
    ),
    reg(
        Primary,
        "COMA",
        0x006ac770,
        "Put a PC in the coma",
        0x006ac778,
        0x0045e8d0,
    ),
    reg(
        Primary,
        "COMPANIES",
        0x006ac748,
        "Display the company numbers",
        0x006ac754,
        0x0045e5d0,
    ),
    reg(
        Primary,
        "DIES IRAE",
        0x006ac714,
        "Divine intervention against enemies.",
        0x006ac720,
        0x0045db20,
    ),
    reg(
        Primary,
        "EINSTEIN",
        0x006ac6f0,
        "Show all 3D-obstacles !",
        0x006ac6fc,
        0x0045e290,
    ),
    reg(
        Primary,
        "ELEVATION",
        0x006ac67c,
        "Display bonds (yellow, red when crossed), character elevation (blue) and character movement (white).",
        0x006ac688,
        0x0045cc60,
    ),
    reg(
        Primary,
        "EULER",
        0x006ac650,
        "Show the graph of the pathfinder.",
        0x006ac658,
        0x0045e450,
    ),
    reg(
        Primary,
        "EZB",
        0x006ac640,
        "Gives money",
        0x006ac644,
        0x0045f0c0,
    ),
    reg(
        Primary,
        "FPS",
        0x006ac624,
        "Display the FPS rate",
        0x006ac628,
        0x0045e670,
    ),
    reg(
        Primary,
        "FORGET",
        0x006ac5f4,
        "Check the current state of the memory",
        0x006ac5fc,
        0x0045f4e0,
    ),
    reg(
        Primary,
        "FREEZE",
        0x006ac5c4,
        "Freeze / unfrost all NPCs in the level.",
        0x006ac5cc,
        0x0045dc80,
    ),
    reg(
        Primary,
        "FULLHOUSE",
        0x006ac58c,
        "Give all PCs ammunition for all actions.",
        0x006ac598,
        0x0045f050,
    ),
    reg(
        Primary,
        "GOLDENEYE",
        0x006ac550,
        "Make all PCs invisible for other characters.",
        0x006ac55c,
        0x0045cc20,
    ),
    reg(
        Primary,
        "HADES",
        0x006ac534,
        "Kill selected NPC",
        0x006ac53c,
        0x0045e7e0,
    ),
    reg(
        Primary,
        "HELP",
        0x006ac518,
        "Display this help.",
        0x006ac520,
        0x0045ccb0,
    ),
    reg(
        Primary,
        "HIGHLANDER",
        0x006ac4ec,
        "All PCs become invulnerable.",
        0x006ac4f8,
        0x0045d840,
    ),
    reg(
        Primary,
        "HIGHLANDER2",
        0x006ac4b8,
        "All adversaries become invulnerable.",
        0x006ac4c4,
        0x0045d8b0,
    ),
    reg(
        Primary,
        "HONOLULU",
        0x006ac488,
        "Beam the selected NPC to Honolulu",
        0x006ac494,
        0x0045d920,
    ),
    reg(
        Primary,
        "KOLKOZ",
        0x006ac460,
        "Add a new peasant to the gang.",
        0x006ac468,
        0x004600b0,
    ),
    reg(
        Primary,
        "LAST MAN STANDING",
        0x006ac420,
        "Beam all but the selected NPC to Honolulu",
        0x006ac434,
        0x0045da50,
    ),
    reg(
        Primary,
        "LEVEL TEXT",
        0x006ac3ec,
        "Display all texts for the current level",
        0x006ac3f8,
        0x00460140,
    ),
    reg(
        Primary,
        "LOOSE",
        0x006ac3cc,
        "Loose this mission !",
        0x006ac3d4,
        0x0045d5c0,
    ),
    reg(
        Primary,
        "MISTER SANDMAN",
        0x006ac3a0,
        "The PCs make a little nap.",
        0x006ac3b0,
        0x0045dd90,
    ),
    reg(
        Primary,
        "MORPHEUS",
        0x006ac37c,
        "Knock out selected NPC",
        0x006ac388,
        0x0045e6f0,
    ),
    reg(
        Primary,
        "MOTION",
        0x006ac350,
        "Show all motion obstacles & doors.",
        0x006ac358,
        0x0045e4b0,
    ),
    reg(
        Primary,
        "NOISE",
        0x006ac31c,
        "Display ranges of walk noise of the PCs.",
        0x006ac324,
        0x0045db80,
    ),
    reg(
        Primary,
        "NUKE",
        0x006ac2f4,
        "Kill all opponent in the level.",
        0x006ac2fc,
        0x0045d650,
    ),
    reg(
        Primary,
        "PAMELA ANDERSON",
        0x006ac2b8,
        "Make the soldiers stupid in close combat.",
        0x006ac2c8,
        0x0045dce0,
    ),
    reg(
        Primary,
        "PROJECTION",
        0x006ac28c,
        "Show all 3D-projection areas.",
        0x006ac298,
        0x0045e400,
    ),
    reg(
        Primary,
        "RAILROAD",
        0x006ac26c,
        "Display railroads.",
        0x006ac278,
        0x0045e240,
    ),
    reg(
        Primary,
        "ROTER ALARM",
        0x006ac244,
        "Alert all NPCs in the level",
        0x006ac250,
        0x0045dd40,
    ),
    reg(
        Primary,
        "SAN PETRUS",
        0x006ac210,
        "Make all selected PC go to paradise.",
        0x006ac21c,
        0x0045eb50,
    ),
    reg(
        Primary,
        "SHADOW",
        0x006ac1e4,
        "Display the free shadow polygon.",
        0x006ac1ec,
        0x0045d780,
    ),
    reg(
        Primary,
        "SPHERE",
        0x006ac1b8,
        "Display the shadow polygon sphere.",
        0x006ac1c0,
        0x0045f310,
    ),
    reg(
        Primary,
        "STATUS FRAMECACHE",
        0x006ac168,
        "Get information about the current sprite caching system.",
        0x006ac17c,
        0x0045df30,
    ),
    reg(
        Primary,
        "STATUS HARDWARE",
        0x006ac12c,
        "Get information about the hardware used.",
        0x006ac13c,
        0x0045df30,
    ),
    reg(
        Primary,
        "STATUS SHADOW",
        0x006ac0f4,
        "Get Information about the sprite cache.",
        0x006ac104,
        0x0045df30,
    ),
    reg(
        Primary,
        "STATUS PC",
        0x006ac0c0,
        "Display the current status of all PC",
        0x006ac0cc,
        0x0045f500,
    ),
    reg(
        Primary,
        "UBIQUITY",
        0x006ac0a0,
        "Unblip all actors.",
        0x006ac0ac,
        0x004600e0,
    ),
    reg(
        Primary,
        "WAKEUP",
        0x006ac05c,
        "When the currently selected NPC is sleeping, he wakes up.",
        0x006ac064,
        0x0045d7d0,
    ),
    reg(
        Primary,
        "WASP MASTER",
        0x006ac008,
        "Increases the number of available wasp nets for all the selected PCs.",
        0x006ac014,
        0x0045ec90,
    ),
    reg(
        Primary,
        "WIN",
        0x006abff0,
        "Win this mission !",
        0x006abff4,
        0x0045cda0,
    ),
    reg(
        Primary,
        "WAPPEN",
        0x006abfd8,
        "Give blazons",
        0x006abfe0,
        0x0045f2a0,
    ),
    reg(
        Primary,
        "LUKAS",
        0x006abfc0,
        "Knock out a PC.",
        0x006abfc8,
        0x0045f330,
    ),
    reg(
        Primary,
        "ANIM",
        0x006abf98,
        "Show all animation polylines.",
        0x006abfa0,
        0x00460350,
    ),
    reg(
        Primary,
        "SARKOZY",
        0x006abf68,
        "Securization of all memory allocation !",
        0x006abf70,
        0x00460370,
    ),
    reg(
        Primary,
        "SEEKANDDESTROY",
        0x006abf40,
        "Display all seek points",
        0x006abf50,
        0x0045d5f0,
    ),
    reg(
        Primary,
        "REPORT",
        0x006abf18,
        "Complete campaign state report",
        0x006abf20,
        0x004603b0,
    ),
    reg(
        Primary,
        "LIGHT",
        0x006abefc,
        "Display light zones",
        0x006abf04,
        0x004603e0,
    ),
    reg(
        Primary,
        "PCSIGHT",
        0x006abee0,
        "Enable PC view cone",
        0x006abee8,
        0x00460410,
    ),
    reg(
        Primary,
        "CAMPAIGN",
        0x006abea8,
        "Load campaign values (CAMPAIGN FILENAME)",
        0x006abeb4,
        0x00460460,
    ),
    reg(
        Primary,
        "I AM THE WINNER",
        0x006abe84,
        "Win the campaign !",
        0x006abe94,
        0x0045d580,
    ),
    reg(
        Primary,
        "CESTLAZONE",
        0x006abe60,
        "Display script zones.",
        0x006abe6c,
        0x0045dc20,
    ),
    reg(
        Primary,
        "OPTIMIZE",
        0x006abe28,
        "Try to optimize the custom memory manager.",
        0x006abe34,
        0x0045de60,
    ),
    reg(
        Primary,
        "CHROMA",
        0x006abdf8,
        "Change the color of one PC on the fly.",
        0x006abe00,
        0x00460620,
    ),
    reg(Release, "GOODLUCK", 0x006abdec, "", 0x006c0560, 0x0045eaa0),
    reg(Release, "EINSTEIN", 0x006ac6f0, "", 0x006c0560, 0x0045e290),
    reg(Release, "CASH", 0x006abde4, "", 0x006c0560, 0x0045f0c0),
    reg(Release, "IMMUNITY", 0x006abdd8, "", 0x006c0560, 0x0045d840),
    reg(Release, "MERRYMAN", 0x006abdcc, "", 0x006c0560, 0x004600b0),
    reg(Release, "PAM", 0x006abdc8, "", 0x006c0560, 0x0045dce0),
    reg(Release, "UNBLIP", 0x006abdc0, "", 0x006c0560, 0x004600e0),
    reg(Release, "WINNER", 0x006abdb8, "", 0x006c0560, 0x0045cda0),
    reg(Release, "BINGO", 0x006abdb0, "", 0x006c0560, 0x0045f050),
];

/// Remake-only commands accepted in developer mode, listed by HELP after
/// the original registry.
pub const REMAKE_EXTENSIONS: &[(&str, &str)] = &[
    (
        "IDS",
        "Toggle the numeric entity ID overlay (BIG BROTHER alias).",
    ),
    (
        "DIPLOMACY <first> <second> <allied|neutral|hostile>",
        "Set the relationship between two allegiances.",
    ),
    (
        "SPRITE MASKS",
        "Toggle the sprite mask overlay (also SPRITEMASKS).",
    ),
    ("SURFACE", "Toggle the surface overlay."),
];

/// Registry entries the given parser mode accepts under their original
/// name.
///
/// Final mode is the original release vector. Developer mode accepts the
/// primary vector plus the release aliases: the remake does not reproduce
/// the hidden unlock as a prerequisite for the player-facing names.
pub fn active_registrations(use_final: bool) -> impl Iterator<Item = &'static ConsoleRegistration> {
    ORIGINAL_REGISTRY
        .iter()
        .filter(move |entry| !use_final || entry.registry == ConsoleRegistry::Release)
}

/// Original HELP listing (`FUN_0045bff0`) for the given mode, one entry
/// per console line.
///
/// Every name word is followed by one space, then the verbatim
/// description, so release entries keep a trailing space. The listing
/// ends with one empty line. Developer mode then appends the release
/// aliases and remake extensions, which the original primary listing
/// does not contain.
pub fn help_lines(use_final: bool) -> Vec<String> {
    let registry = if use_final {
        ConsoleRegistry::Release
    } else {
        ConsoleRegistry::Primary
    };
    let mut lines = vec![
        "Robin Hood Console Help File.".to_owned(),
        "Available command in this release:".to_owned(),
    ];
    lines.extend(
        ORIGINAL_REGISTRY
            .iter()
            .filter(|entry| entry.registry == registry)
            .map(|entry| format!("{} {}", entry.name, entry.description)),
    );
    lines.push(String::new());
    if !use_final {
        lines.push("Release aliases also accepted:".to_owned());
        let aliases: Vec<&str> = ORIGINAL_REGISTRY
            .iter()
            .filter(|entry| entry.registry == ConsoleRegistry::Release)
            .map(|entry| entry.name)
            .collect();
        lines.push(aliases.join(" "));
        lines.push("Remake additions:".to_owned());
        lines.extend(
            REMAKE_EXTENSIONS
                .iter()
                .map(|(name, description)| format!("{name} {description}")),
        );
    }
    lines
}

/// First words the parser accepts in the given mode, sorted and
/// deduplicated, for Tab completion.
///
/// The original completes only the first registered word as well.
pub fn completion_keywords(use_final: bool) -> Vec<&'static str> {
    let mut words: Vec<&'static str> = active_registrations(use_final).map(first_word).collect();
    if !use_final {
        words.extend(
            REMAKE_EXTENSIONS
                .iter()
                .map(|(name, _)| first_word_of(name)),
        );
    }
    words.sort_unstable();
    words.dedup();
    words
}

fn first_word(entry: &'static ConsoleRegistration) -> &'static str {
    first_word_of(entry.name)
}

fn first_word_of(name: &'static str) -> &'static str {
    name.split(' ')
        .next()
        .expect("registered names are nonempty")
}

// ─── Console struct ─────────────────────────────────────────────

const HISTORY_SIZE: usize = 10;

#[derive(Debug, Clone)]
pub struct Console {
    pub history: Vec<String>,
    pub enabled: bool,
    /// When true, only the "final" (release) cheat set is available.
    /// Exposed as a runtime flag so developer tooling (HTTP API, debug
    /// overlays) can force-enable the dev cheat set even in a shipping
    /// build.  The parser, tab completion, and help text all honour
    /// this flag.
    pub use_final: bool,
    /// Extra output lines emitted by cheats during dispatch.  The
    /// overlay drains this every frame and appends each entry to the
    /// scrollback.  Cheat handlers use this side channel to emit
    /// multi-line diagnostics (e.g. `STATUS PC`, `STATUS HARDWARE`,
    /// `SAN PETRUS` epitaphs).
    pub pending_output: Vec<String>,
}

impl Default for Console {
    fn default() -> Self {
        Console {
            history: Vec::with_capacity(HISTORY_SIZE),
            enabled: false,
            use_final: false,
            pending_output: Vec::new(),
        }
    }
}

// ─── Parsing ────────────────────────────────────────────────────

/// Parse a console input string into a `ConsoleCommand`.
///
/// Input is case-insensitive (uppercased before matching).
/// Multi-word commands like "BIG BROTHER" are matched by checking the
/// first N tokens.
pub fn parse(input: &str) -> Option<ConsoleCommand> {
    parse_with_final(input, false)
}

/// Parse with the "final" flag controlling which command set is used.
///
/// Final mode accepts only the 9 original release names. Developer mode
/// accepts the original primary names, the release names, and the
/// remake extensions. Unlike the original matcher, which compares only
/// as many input words as a name has and lets `I` reach `I AM THE
/// WINNER`, every word of a multiword name is required.
pub fn parse_with_final(input: &str, use_final: bool) -> Option<ConsoleCommand> {
    let upper = input.trim().to_ascii_uppercase();
    let tokens: Vec<&str> = upper.split_whitespace().collect();
    if tokens.is_empty() {
        return None;
    }

    // Final (release) cheats — a smaller set with different command strings
    if use_final {
        return parse_final(&tokens);
    }

    // Dev cheats — the full set
    parse_dev(&tokens)
}

fn parse_final(tokens: &[&str]) -> Option<ConsoleCommand> {
    match tokens[0] {
        "CASH" => Some(parse_money_args(&tokens[1..])),
        "GOODLUCK" => Some(parse_amulets_args(&tokens[1..])),
        "EINSTEIN" => Some(ConsoleCommand::Einstein),
        "IMMUNITY" => Some(ConsoleCommand::Highlander),
        "MERRYMAN" => Some(ConsoleCommand::AddPeasant),
        "PAM" => Some(ConsoleCommand::StupidSoldiers),
        "UNBLIP" => Some(ConsoleCommand::Ubiquity),
        "WINNER" => Some(ConsoleCommand::WinMission),
        "BINGO" => Some(ConsoleCommand::GiveAmmo),
        _ => None,
    }
}

fn parse_dev(tokens: &[&str]) -> Option<ConsoleCommand> {
    match tokens[0] {
        "AI" => Some(ConsoleCommand::Ai),
        "ALARM" => Some(ConsoleCommand::Reinforcement),
        "AMOR" => Some(ConsoleCommand::GiveArrows),
        "AMULETS" => Some(parse_amulets_args(&tokens[1..])),
        "ASSERTFALSE" => Some(ConsoleCommand::AssertFalse),
        "BABYLON" => Some(ConsoleCommand::Babylon),
        "BIG" if tokens.get(1) == Some(&"BROTHER") => Some(ConsoleCommand::BigBrother),
        "IDS" => Some(ConsoleCommand::BigBrother),
        "BUD" if tokens.get(1) == Some(&"SPENCER") => Some(ConsoleCommand::BudSpencer),
        "CALL" if tokens.len() >= 3 => Some(ConsoleCommand::Call {
            actor: tokens[1].to_string(),
            method: tokens[2].to_string(),
        }),
        "COMA" => Some(ConsoleCommand::Coma),
        "COMPANIES" => Some(ConsoleCommand::Companies),
        "CESTLAZONE" => Some(ConsoleCommand::CestLaZone),
        "CAMPAIGN" if tokens.len() >= 2 => Some(ConsoleCommand::LoadCampaign {
            filename: tokens[1].to_string(),
        }),
        "CAMPAIGN" => Some(ConsoleCommand::UsageError(
            "Verboten : Please enter a valid filename !".to_owned(),
        )),
        "DIES" if tokens.get(1) == Some(&"IRAE") => Some(ConsoleCommand::DiesIrae),
        "DIPLOMACY" if tokens.len() == 4 => Some(parse_diplomacy_args(tokens)),
        "DIPLOMACY" => Some(ConsoleCommand::UsageError(
            "USAGE: DIPLOMACY <first> <second> <allied|neutral|hostile>".to_owned(),
        )),
        "EINSTEIN" => Some(ConsoleCommand::Einstein),
        "ELEVATION" => Some(ConsoleCommand::Elevation),
        "EULER" => Some(ConsoleCommand::Euler),
        "EZB" => Some(parse_money_args(&tokens[1..])),
        "FPS" => Some(ConsoleCommand::Fps),
        "FORGET" => Some(ConsoleCommand::Forget),
        "FREEZE" => Some(ConsoleCommand::Freeze),
        "FULLHOUSE" => Some(ConsoleCommand::GiveAmmo),
        "GOLDENEYE" => Some(ConsoleCommand::Goldeneye),
        "HADES" => Some(ConsoleCommand::Hades),
        "HELP" => Some(ConsoleCommand::Help),
        "HIGHLANDER" => Some(ConsoleCommand::Highlander),
        "HIGHLANDER2" => Some(ConsoleCommand::Highlander2),
        "HONOLULU" => Some(ConsoleCommand::Honolulu),
        "I" if tokens.len() >= 4
            && tokens[1] == "AM"
            && tokens[2] == "THE"
            && tokens[3] == "WINNER" =>
        {
            Some(ConsoleCommand::WinCampaign)
        }
        "KOLKOZ" => Some(ConsoleCommand::AddPeasant),
        "LAST" if tokens.get(1) == Some(&"MAN") && tokens.get(2) == Some(&"STANDING") => {
            Some(ConsoleCommand::LastManStanding)
        }
        "LEVEL" if tokens.get(1) == Some(&"TEXT") => Some(ConsoleCommand::LevelText {
            option: tokens.get(2).map(|s| s.to_string()),
        }),
        "LIGHT" => Some(ConsoleCommand::Light),
        "LOOSE" => Some(ConsoleCommand::LoseMission),
        "LUKAS" => Some(ConsoleCommand::Lukas {
            pcs: tokens.get(1).map(|s| s.to_string()),
        }),
        "MISTER" if tokens.get(1) == Some(&"SANDMAN") => Some(ConsoleCommand::MisterSandman),
        "MORPHEUS" => Some(ConsoleCommand::Morpheus),
        "MOTION" => Some(ConsoleCommand::Motion),
        "NOISE" => Some(ConsoleCommand::Noise),
        "NUKE" => Some(ConsoleCommand::Nuke),
        "OPTIMIZE" => Some(ConsoleCommand::Optimize),
        "PAMELA" if tokens.get(1) == Some(&"ANDERSON") => Some(ConsoleCommand::StupidSoldiers),
        "PCSIGHT" => Some(ConsoleCommand::PcSight),
        "PROJECTION" => Some(ConsoleCommand::Projection),
        "RAILROAD" => Some(ConsoleCommand::Railroad),
        "REPORT" => Some(ConsoleCommand::CampaignReport),
        "ROTER" if tokens.get(1) == Some(&"ALARM") => Some(ConsoleCommand::RoterAlarm),
        "SAN" if tokens.get(1) == Some(&"PETRUS") => Some(ConsoleCommand::SanPetrus),
        "SARKOZY" => Some(ConsoleCommand::Sarkozy),
        "SEEKANDDESTROY" => Some(ConsoleCommand::SeekAndDestroy),
        "SHADOW" => Some(ConsoleCommand::Shadow),
        "SPHERE" => Some(ConsoleCommand::Sphere),
        "SPRITEMASKS" | "SPRITE_MASKS" => Some(ConsoleCommand::SpriteMasks),
        "SPRITE" if tokens.get(1) == Some(&"MASKS") => Some(ConsoleCommand::SpriteMasks),
        "SURFACE" => Some(ConsoleCommand::Surface),
        "STATUS" => match tokens.get(1).copied() {
            Some("FRAMECACHE") => Some(ConsoleCommand::StatusFramecache),
            Some("HARDWARE") => Some(ConsoleCommand::StatusHardware),
            Some("SHADOW") => Some(ConsoleCommand::StatusShadow),
            Some("PC") => Some(ConsoleCommand::StatusPc),
            _ => None,
        },
        "UBIQUITY" => Some(ConsoleCommand::Ubiquity),
        "ANIM" => Some(ConsoleCommand::Anim),
        "WAKEUP" => Some(ConsoleCommand::Wakeup),
        "WASP" if tokens.get(1) == Some(&"MASTER") => Some(ConsoleCommand::WaspMaster),
        "WAPPEN" => Some(parse_blazon_args(&tokens[1..])),
        "WIN" => Some(ConsoleCommand::WinMission),
        // TODO: CHROMA (original 0x00460620) patches the selected PC's
        // dictionary sprite in place; the remake has no per-sprite
        // recoloring route yet.
        "CHROMA" => Some(ConsoleCommand::UsageError(
            "CHROMA is not supported yet.".to_owned(),
        )),
        // Release names are accepted alongside the developer names.
        _ => parse_final(tokens),
    }
}

fn parse_diplomacy_args(tokens: &[&str]) -> ConsoleCommand {
    const USAGE: &str = "USAGE: DIPLOMACY <first> <second> <allied|neutral|hostile>";
    let Ok(first) = tokens[1].parse::<u16>() else {
        return ConsoleCommand::UsageError(USAGE.to_owned());
    };
    let Ok(second) = tokens[2].parse::<u16>() else {
        return ConsoleCommand::UsageError(USAGE.to_owned());
    };
    let relationship = match tokens[3] {
        "ALLIED" => crate::diplomacy::Relationship::Allied,
        "NEUTRAL" => crate::diplomacy::Relationship::Neutral,
        "HOSTILE" => crate::diplomacy::Relationship::Hostile,
        _ => return ConsoleCommand::UsageError(USAGE.to_owned()),
    };
    ConsoleCommand::SetDiplomacy {
        first,
        second,
        relationship,
    }
}

fn parse_money_args(args: &[&str]) -> ConsoleCommand {
    let (amount, show_help) = if let Some(&arg) = args.first() {
        let amount = match arg {
            "HUNDRED" => 100,
            "THOUSAND" => 1000,
            "TENTHOUSAND" => 10_000,
            "HUNDREDTHOUSAND" => 100_000,
            _ => arg.parse::<u32>().unwrap_or(1000),
        };
        (amount, false)
    } else {
        // No-arg default + help-text-emitting branch.
        (1000, true)
    };
    ConsoleCommand::GiveMoney { amount, show_help }
}

fn parse_amulets_args(args: &[&str]) -> ConsoleCommand {
    let amount = args
        .first()
        .and_then(|s| s.parse::<u32>().ok())
        .unwrap_or(100);
    ConsoleCommand::GiveAmulets { amount }
}

fn parse_blazon_args(args: &[&str]) -> ConsoleCommand {
    let amount = args
        .first()
        .and_then(|s| s.parse::<u32>().ok())
        .unwrap_or(1);
    ConsoleCommand::GiveBlazon { amount }
}

impl Console {
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a line to the command history (ring buffer, max HISTORY_SIZE).
    pub fn push_history(&mut self, line: &str) {
        if self.history.len() >= HISTORY_SIZE {
            self.history.remove(0);
        }
        self.history.push(line.to_string());
    }

    /// Append a line to the pending output queue.  Dispatchers use this
    /// when a single cheat needs to emit many lines.  The overlay
    /// drains the queue every frame and appends each entry to its
    /// scrollback.
    pub fn push_output(&mut self, line: impl Into<String>) {
        self.pending_output.push(line.into());
    }

    /// Take ownership of every queued output line, leaving the queue
    /// empty.  Callers (the overlay renderer, the HTTP snapshot) are
    /// responsible for presenting the drained lines.
    pub fn drain_output(&mut self) -> Vec<String> {
        std::mem::take(&mut self.pending_output)
    }
}

// ─── Tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Original HELP output after unlocking (primary registry), including
    /// the closing empty message.
    const ORIGINAL_PRIMARY_HELP: &[&str] = &[
        "Robin Hood Console Help File.",
        "Available command in this release:",
        "AI Display AI information.",
        "ALARM Reinforcement arriving...",
        "AMOR Increase the number of available arrows for all the selected PCs.",
        "AMULETS Add amulets to the campaign.",
        "ASSERTFALSE Ok !",
        "BABYLON Display all NPC remarks on screen.",
        "BIG BROTHER Display some actor infos.",
        "BUD SPENCER Stun all oponents.",
        "CALL Call a PC's method",
        "COMA Put a PC in the coma",
        "COMPANIES Display the company numbers",
        "DIES IRAE Divine intervention against enemies.",
        "EINSTEIN Show all 3D-obstacles !",
        "ELEVATION Display bonds (yellow, red when crossed), character elevation (blue) and character movement (white).",
        "EULER Show the graph of the pathfinder.",
        "EZB Gives money",
        "FPS Display the FPS rate",
        "FORGET Check the current state of the memory",
        "FREEZE Freeze / unfrost all NPCs in the level.",
        "FULLHOUSE Give all PCs ammunition for all actions.",
        "GOLDENEYE Make all PCs invisible for other characters.",
        "HADES Kill selected NPC",
        "HELP Display this help.",
        "HIGHLANDER All PCs become invulnerable.",
        "HIGHLANDER2 All adversaries become invulnerable.",
        "HONOLULU Beam the selected NPC to Honolulu",
        "KOLKOZ Add a new peasant to the gang.",
        "LAST MAN STANDING Beam all but the selected NPC to Honolulu",
        "LEVEL TEXT Display all texts for the current level",
        "LOOSE Loose this mission !",
        "MISTER SANDMAN The PCs make a little nap.",
        "MORPHEUS Knock out selected NPC",
        "MOTION Show all motion obstacles & doors.",
        "NOISE Display ranges of walk noise of the PCs.",
        "NUKE Kill all opponent in the level.",
        "PAMELA ANDERSON Make the soldiers stupid in close combat.",
        "PROJECTION Show all 3D-projection areas.",
        "RAILROAD Display railroads.",
        "ROTER ALARM Alert all NPCs in the level",
        "SAN PETRUS Make all selected PC go to paradise.",
        "SHADOW Display the free shadow polygon.",
        "SPHERE Display the shadow polygon sphere.",
        "STATUS FRAMECACHE Get information about the current sprite caching system.",
        "STATUS HARDWARE Get information about the hardware used.",
        "STATUS SHADOW Get Information about the sprite cache.",
        "STATUS PC Display the current status of all PC",
        "UBIQUITY Unblip all actors.",
        "WAKEUP When the currently selected NPC is sleeping, he wakes up.",
        "WASP MASTER Increases the number of available wasp nets for all the selected PCs.",
        "WIN Win this mission !",
        "WAPPEN Give blazons",
        "LUKAS Knock out a PC.",
        "ANIM Show all animation polylines.",
        "SARKOZY Securization of all memory allocation !",
        "SEEKANDDESTROY Display all seek points",
        "REPORT Complete campaign state report",
        "LIGHT Display light zones",
        "PCSIGHT Enable PC view cone",
        "CAMPAIGN Load campaign values (CAMPAIGN FILENAME)",
        "I AM THE WINNER Win the campaign !",
        "CESTLAZONE Display script zones.",
        "OPTIMIZE Try to optimize the custom memory manager.",
        "CHROMA Change the color of one PC on the fly.",
        "",
    ];

    /// Original release-registry HELP listing; every line keeps the
    /// separator space appended after the name.
    const ORIGINAL_RELEASE_HELP: &[&str] = &[
        "Robin Hood Console Help File.",
        "Available command in this release:",
        "GOODLUCK ",
        "EINSTEIN ",
        "CASH ",
        "IMMUNITY ",
        "MERRYMAN ",
        "PAM ",
        "UNBLIP ",
        "WINNER ",
        "BINGO ",
        "",
    ];

    fn sample_input(entry: &ConsoleRegistration) -> String {
        match entry.name {
            "CALL" => "CALL R HIDEINTERFACE".to_owned(),
            "CAMPAIGN" => "CAMPAIGN SAVE.SAV".to_owned(),
            name => name.to_owned(),
        }
    }

    #[test]
    fn registry_inventory_matches_original_registration_calls() {
        use std::collections::HashSet;
        let primary = ORIGINAL_REGISTRY
            .iter()
            .filter(|entry| entry.registry == ConsoleRegistry::Primary)
            .count();
        let names: HashSet<_> = ORIGINAL_REGISTRY.iter().map(|entry| entry.name).collect();
        let handlers: HashSet<_> = ORIGINAL_REGISTRY
            .iter()
            .map(|entry| entry.handler_va)
            .collect();
        assert_eq!(primary, 63);
        assert_eq!(ORIGINAL_REGISTRY.len() - primary, 9);
        assert_eq!(names.len(), 71, "EINSTEIN is registered in both vectors");
        assert_eq!(handlers.len(), 61);
        assert!(
            ORIGINAL_REGISTRY
                .iter()
                .filter(|entry| entry.registry == ConsoleRegistry::Release)
                .all(|entry| entry.description.is_empty() && entry.description_va == 0x006c_0560)
        );
    }

    #[test]
    fn every_registration_parses_in_its_own_mode() {
        for entry in &ORIGINAL_REGISTRY {
            let use_final = entry.registry == ConsoleRegistry::Release;
            let parsed = parse_with_final(&sample_input(entry), use_final);
            match entry.name {
                "CHROMA" => assert_eq!(
                    parsed,
                    Some(ConsoleCommand::UsageError(
                        "CHROMA is not supported yet.".to_owned()
                    ))
                ),
                _ => assert!(
                    !matches!(parsed, None | Some(ConsoleCommand::UsageError(_))),
                    "{} parsed to {parsed:?}",
                    entry.name
                ),
            }
        }
    }

    #[test]
    fn release_names_are_developer_aliases_of_their_shared_handler() {
        for release in active_registrations(true) {
            let primary = ORIGINAL_REGISTRY
                .iter()
                .find(|entry| {
                    entry.registry == ConsoleRegistry::Primary
                        && entry.handler_va == release.handler_va
                })
                .expect("every release handler is also a primary handler");
            assert_eq!(
                parse_with_final(release.name, false),
                parse_with_final(primary.name, false),
                "{} shares handler {:#x} with {}",
                release.name,
                release.handler_va,
                primary.name
            );
            assert_eq!(
                parse_with_final(release.name, true),
                parse_with_final(release.name, false)
            );
        }
    }

    #[test]
    fn final_mode_rejects_primary_only_names() {
        for entry in active_registrations(false)
            .filter(|entry| entry.registry == ConsoleRegistry::Primary && entry.name != "EINSTEIN")
        {
            assert_eq!(
                parse_with_final(&sample_input(entry), true),
                None,
                "{}",
                entry.name
            );
        }
    }

    #[test]
    fn partial_multiword_names_do_not_dispatch() {
        // The original matcher lets `I` reach `I AM THE WINNER` and
        // `STATUS` reach `STATUS FRAMECACHE`; the remake requires every word.
        for input in [
            "I", "I AM", "BIG", "STATUS", "LAST MAN", "LEVEL", "WASP", "SAN",
        ] {
            assert_eq!(parse(input), None, "{input}");
        }
    }

    #[test]
    fn help_reproduces_original_listing_then_remake_additions() {
        let developer = help_lines(false);
        assert_eq!(
            &developer[..ORIGINAL_PRIMARY_HELP.len()],
            ORIGINAL_PRIMARY_HELP
        );
        assert_eq!(
            &developer[ORIGINAL_PRIMARY_HELP.len()..],
            [
                "Release aliases also accepted:",
                "GOODLUCK EINSTEIN CASH IMMUNITY MERRYMAN PAM UNBLIP WINNER BINGO",
                "Remake additions:",
                "IDS Toggle the numeric entity ID overlay (BIG BROTHER alias).",
                "DIPLOMACY <first> <second> <allied|neutral|hostile> Set the relationship between two allegiances.",
                "SPRITE MASKS Toggle the sprite mask overlay (also SPRITEMASKS).",
                "SURFACE Toggle the surface overlay.",
            ]
        );
        assert_eq!(help_lines(true), ORIGINAL_RELEASE_HELP);
    }

    #[test]
    fn completion_offers_first_words_of_accepted_names() {
        assert_eq!(
            completion_keywords(true),
            [
                "BINGO", "CASH", "EINSTEIN", "GOODLUCK", "IMMUNITY", "MERRYMAN", "PAM", "UNBLIP",
                "WINNER"
            ]
        );
        let developer = completion_keywords(false);
        for word in developer.iter().copied() {
            assert!(
                ORIGINAL_REGISTRY
                    .iter()
                    .map(|entry| entry.name)
                    .chain(REMAKE_EXTENSIONS.iter().map(|(name, _)| *name))
                    .any(|name| name.split(' ').next() == Some(word)),
                "{word}"
            );
        }
        for word in [
            "CASH",
            "CHROMA",
            "I",
            "STATUS",
            "IDS",
            "DIPLOMACY",
            "SPRITE",
        ] {
            assert!(developer.contains(&word), "{word}");
        }
        assert!(!developer.contains(&"ENERGYDISPLAY"));
    }

    #[test]
    fn parse_known_commands() {
        assert_eq!(
            parse("EZB THOUSAND"),
            Some(ConsoleCommand::GiveMoney {
                amount: 1000,
                show_help: false
            })
        );
        assert_eq!(
            parse("ezb thousand"),
            Some(ConsoleCommand::GiveMoney {
                amount: 1000,
                show_help: false
            })
        );
        assert_eq!(
            parse("EZB 500"),
            Some(ConsoleCommand::GiveMoney {
                amount: 500,
                show_help: false
            })
        );
        assert_eq!(
            parse("EZB"),
            Some(ConsoleCommand::GiveMoney {
                amount: 1000,
                show_help: true
            })
        );
        assert_eq!(parse("HELP"), Some(ConsoleCommand::Help));
        assert_eq!(parse("WIN"), Some(ConsoleCommand::WinMission));
        assert_eq!(parse("LOOSE"), Some(ConsoleCommand::LoseMission));
        assert_eq!(parse("NUKE"), Some(ConsoleCommand::Nuke));
        assert_eq!(parse("HIGHLANDER"), Some(ConsoleCommand::Highlander));
        assert_eq!(parse("HIGHLANDER2"), Some(ConsoleCommand::Highlander2));
        assert_eq!(parse("GOLDENEYE"), Some(ConsoleCommand::Goldeneye));
        assert_eq!(parse("FREEZE"), Some(ConsoleCommand::Freeze));
        assert_eq!(parse("FULLHOUSE"), Some(ConsoleCommand::GiveAmmo));
        assert_eq!(parse("IDS"), Some(ConsoleCommand::BigBrother));
        assert_eq!(
            parse("DIPLOMACY 2 9 NEUTRAL"),
            Some(ConsoleCommand::SetDiplomacy {
                first: 2,
                second: 9,
                relationship: crate::diplomacy::Relationship::Neutral,
            })
        );
        assert!(matches!(
            parse("DIPLOMACY two 9 HOSTILE"),
            Some(ConsoleCommand::UsageError(_))
        ));
    }

    #[test]
    fn parse_multi_word_commands() {
        assert_eq!(parse("BIG BROTHER"), Some(ConsoleCommand::BigBrother));
        assert_eq!(parse("BUD SPENCER"), Some(ConsoleCommand::BudSpencer));
        assert_eq!(parse("DIES IRAE"), Some(ConsoleCommand::DiesIrae));
        assert_eq!(
            parse("LAST MAN STANDING"),
            Some(ConsoleCommand::LastManStanding)
        );
        assert_eq!(parse("I AM THE WINNER"), Some(ConsoleCommand::WinCampaign));
        assert_eq!(parse("ROTER ALARM"), Some(ConsoleCommand::RoterAlarm));
        assert_eq!(parse("SAN PETRUS"), Some(ConsoleCommand::SanPetrus));
        assert_eq!(parse("SPRITE MASKS"), Some(ConsoleCommand::SpriteMasks));
        assert_eq!(parse("WASP MASTER"), Some(ConsoleCommand::WaspMaster));
        assert_eq!(parse("MISTER SANDMAN"), Some(ConsoleCommand::MisterSandman));
        assert_eq!(
            parse("PAMELA ANDERSON"),
            Some(ConsoleCommand::StupidSoldiers)
        );
        assert_eq!(
            parse("STATUS FRAMECACHE"),
            Some(ConsoleCommand::StatusFramecache)
        );
        assert_eq!(
            parse("STATUS HARDWARE"),
            Some(ConsoleCommand::StatusHardware)
        );
        assert_eq!(
            parse("LEVEL TEXT"),
            Some(ConsoleCommand::LevelText { option: None })
        );
        assert_eq!(
            parse("LEVEL TEXT DG"),
            Some(ConsoleCommand::LevelText {
                option: Some("DG".to_string())
            })
        );
    }

    #[test]
    fn parse_final_cheats() {
        assert_eq!(
            parse_with_final("CASH", true),
            Some(ConsoleCommand::GiveMoney {
                amount: 1000,
                show_help: true
            })
        );
        assert_eq!(
            parse_with_final("CASH THOUSAND", true),
            Some(ConsoleCommand::GiveMoney {
                amount: 1000,
                show_help: false
            })
        );
        assert_eq!(
            parse_with_final("GOODLUCK", true),
            Some(ConsoleCommand::GiveAmulets { amount: 100 })
        );
        assert_eq!(
            parse_with_final("IMMUNITY", true),
            Some(ConsoleCommand::Highlander)
        );
        assert_eq!(
            parse_with_final("WINNER", true),
            Some(ConsoleCommand::WinMission)
        );
        assert_eq!(
            parse_with_final("BINGO", true),
            Some(ConsoleCommand::GiveAmmo)
        );
        assert_eq!(
            parse_with_final("MERRYMAN", true),
            Some(ConsoleCommand::AddPeasant)
        );
        assert_eq!(
            parse_with_final("PAM", true),
            Some(ConsoleCommand::StupidSoldiers)
        );
        assert_eq!(
            parse_with_final("UNBLIP", true),
            Some(ConsoleCommand::Ubiquity)
        );
    }

    #[test]
    fn parse_unknown_returns_none() {
        assert_eq!(parse("XYZZY"), None);
        assert_eq!(parse(""), None);
        assert_eq!(parse("   "), None);
    }

    #[test]
    fn parse_amulets_with_amount() {
        assert_eq!(
            parse("AMULETS 50"),
            Some(ConsoleCommand::GiveAmulets { amount: 50 })
        );
        assert_eq!(
            parse("AMULETS"),
            Some(ConsoleCommand::GiveAmulets { amount: 100 })
        );
    }

    #[test]
    fn parse_blazon() {
        assert_eq!(
            parse("WAPPEN 5"),
            Some(ConsoleCommand::GiveBlazon { amount: 5 })
        );
        assert_eq!(
            parse("WAPPEN"),
            Some(ConsoleCommand::GiveBlazon { amount: 1 })
        );
    }

    #[test]
    fn console_history_ring_buffer() {
        let mut console = Console::new();
        for i in 0..15 {
            console.push_history(&format!("EZB {}", i));
        }
        assert_eq!(console.history.len(), HISTORY_SIZE);
        // Oldest entries should have been dropped
        assert_eq!(console.history[0], "EZB 5");
    }

    #[test]
    fn parse_call_command() {
        assert_eq!(
            parse("CALL ABC123 HIDEINTERFACE"),
            Some(ConsoleCommand::Call {
                actor: "ABC123".to_string(),
                method: "HIDEINTERFACE".to_string(),
            })
        );
    }

    #[test]
    fn parse_campaign_missing_filename_emits_verboten() {
        // CAMPAIGN with no filename emits the "Verboten : …" usage string.
        assert_eq!(
            parse("CAMPAIGN"),
            Some(ConsoleCommand::UsageError(
                "Verboten : Please enter a valid filename !".to_owned()
            ))
        );
    }

    #[test]
    fn parse_lukas() {
        assert_eq!(parse("LUKAS"), Some(ConsoleCommand::Lukas { pcs: None }));
        assert_eq!(
            parse("LUKAS RJTS"),
            Some(ConsoleCommand::Lukas {
                pcs: Some("RJTS".to_string())
            })
        );
    }
}
