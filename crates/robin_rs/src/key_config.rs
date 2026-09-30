//! Host-side keyboard binding configuration.
//!
//! Stores named action strings with primary and secondary key slots, and
//! provides hardcoded default presets. The original game owns the active and
//! custom bindings as part of each player profile and copies the active
//! profile's bindings into its input translator, so those live values are host
//! application state rather than deterministic engine state.
//!
//! The original preset definitions came from
//! `Data/Configuration/keyset1.cfg` and `keyset2.cfg`; the Rust port currently
//! preserves its existing hardcoded tables here.
//! TODO(architecture): load preset definitions through the asset layer while
//! keeping physical [`KeyCode`] values and per-profile selections host-owned.
//!
//! Bindings match physical [`KeyCode`]s so a held key keeps matching while
//! Shift or Caps Lock change the character it produces. [`KeyCode`] variants
//! are named after the US layout, though, so a captured binding also records
//! the character the player's layout produced ([`KeyBinding::primary_label`])
//! and the options screen shows that instead of the US name.
//!
//! This unpublished workspace API previously lived at
//! `robin_assets::keyconfig`; consumers must now import
//! `robin_rs::key_config`.

use winit::keyboard::{Key, KeyCode};

/// A single action‐to‐key mapping.
#[derive(Debug, Clone, Default, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct KeyBinding {
    pub action: String,
    pub primary_key: Option<KeyCode>,
    pub secondary_key: Option<KeyCode>,
    /// Display-only character the keyboard layout produced when
    /// `primary_key` was captured (see [`layout_label`]). Absent for presets,
    /// named keys and configurations saved before labels existed; those fall
    /// back to the US-layout name of `primary_key`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub primary_label: Option<String>,
}

/// Whether the character printed by `key` depends on the keyboard layout.
/// Named keys (arrows, F-keys, modifiers) and numpad keys keep their
/// localised names instead.
pub fn is_layout_dependent(key: KeyCode) -> bool {
    use KeyCode::*;
    matches!(
        key,
        Backquote
            | Backslash
            | BracketLeft
            | BracketRight
            | Comma
            | Digit0
            | Digit1
            | Digit2
            | Digit3
            | Digit4
            | Digit5
            | Digit6
            | Digit7
            | Digit8
            | Digit9
            | Equal
            | IntlBackslash
            | IntlRo
            | IntlYen
            | KeyA
            | KeyB
            | KeyC
            | KeyD
            | KeyE
            | KeyF
            | KeyG
            | KeyH
            | KeyI
            | KeyJ
            | KeyK
            | KeyL
            | KeyM
            | KeyN
            | KeyO
            | KeyP
            | KeyQ
            | KeyR
            | KeyS
            | KeyT
            | KeyU
            | KeyV
            | KeyW
            | KeyX
            | KeyY
            | KeyZ
            | Minus
            | Period
            | Quote
            | Semicolon
            | Slash
    )
}

/// Label to record for a captured `physical` key: the printable character
/// the active layout produced for it (`logical`), lowercased like the
/// built-in letter names. `None` when the key has a layout-independent name
/// or produced no printable character (e.g. a dead key).
pub fn layout_label(physical: KeyCode, logical: &Key) -> Option<String> {
    let Key::Character(text) = logical else {
        return None;
    };
    let printable = !text.is_empty() && !text.chars().any(|c| c.is_control() || c.is_whitespace());
    (is_layout_dependent(physical) && printable).then(|| text.to_lowercase())
}

/// The full set of key bindings.
#[derive(Debug, Clone, Default, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct KeyConfig {
    pub bindings: Vec<KeyBinding>,
    /// Config type: `0` = Unknown, `1` = UserDefined, `2+` = PresetBase+index.
    pub key_type: u16,
}

// ── Index‐to‐action‐name mapping ──

/// Action names indexed 0..29. Index 30 is `Dummy` (the sentinel — excluded
/// from [`REAL_KEY_COUNT`]).
const KEY_NAMES: &[&str] = &[
    "ZoomIn",
    "ZoomOut",
    "ScrollUp",
    "ScrollDown",
    "ScrollLeft",
    "ScrollRight",
    "Minimap",
    "Character1",
    "Character2",
    "Character3",
    "Character4",
    "Character5",
    "AllCharacters",
    "NoneCharacters",
    "Crouch",
    "StandUp",
    "GoBehindBuildings",
    "ToggleOutlineDisplay",
    "Action1",
    "Action2",
    "Action3",
    "MoveDuringAction",
    "RecordQuickAction",
    "StartQuickAction",
    "DeleteQuickAction",
    "ShowViewCone",
    "QuickSave1",
    "QuickLoad1",
    "PlanQuickActions",
    "ToggleCloak",
    "Dummy",
];

/// Number of real key bindings (excludes the Dummy sentinel).
pub const REAL_KEY_COUNT: u16 = (KEY_NAMES.len() - 1) as u16;
/// Stable row/index of the building/door movement modifier.
pub const GO_BEHIND_BUILDINGS_INDEX: u16 = 16;
/// Stable row/index of the rebindable planned-action modifier.
pub const PLAN_QUICK_ACTIONS_INDEX: u16 = 28;
/// Stable row/index of the reusable-cloak action.
pub const TOGGLE_CLOAK_INDEX: u16 = 29;

impl KeyConfig {
    /// Add the reusable-cloak action to a key profile written before the
    /// action existed. Preserve all user bindings; V is used only when it is
    /// still free, otherwise the new action starts unbound.
    fn ensure_reusable_cloak_binding(&mut self) {
        if self.get_binding("ToggleCloak").is_some() {
            return;
        }
        let default_key =
            (self.get_action_for_key(KeyCode::KeyV).is_none()).then_some(KeyCode::KeyV);
        self.set_binding("ToggleCloak", default_key, None);
    }

    /// Insert or update a binding for `action`.
    pub fn set_binding(
        &mut self,
        action: &str,
        primary: Option<KeyCode>,
        secondary: Option<KeyCode>,
    ) {
        if let Some(b) = self.bindings.iter_mut().find(|b| b.action == action) {
            if b.primary_key != primary {
                b.primary_label = None;
            }
            b.primary_key = primary;
            b.secondary_key = secondary;
        } else {
            self.bindings.push(KeyBinding {
                action: action.to_owned(),
                primary_key: primary,
                secondary_key: secondary,
                primary_label: None,
            });
        }
    }

    /// Look up a binding by action name.
    pub fn get_binding(&self, action: &str) -> Option<&KeyBinding> {
        self.bindings.iter().find(|b| b.action == action)
    }

    /// Return the action name whose primary *or* secondary key matches `key`.
    fn get_action_for_key(&self, key: KeyCode) -> Option<&str> {
        self.bindings
            .iter()
            .find(|b| b.primary_key == Some(key) || b.secondary_key == Some(key))
            .map(|b| b.action.as_str())
    }

    // ── Index-based access ──

    /// Get the primary key for the binding at the given action index.
    /// Returns `None` if the index is out of range or the binding doesn't exist.
    pub fn get_key_by_index(&self, index: u16) -> Option<KeyCode> {
        KEY_NAMES
            .get(index as usize)
            .and_then(|name| self.get_binding(name))
            .and_then(|b| b.primary_key)
    }

    /// Display label captured with the primary key at the given action index.
    pub fn get_label_by_index(&self, index: u16) -> Option<&str> {
        KEY_NAMES
            .get(index as usize)
            .and_then(|name| self.get_binding(name))
            .and_then(|b| b.primary_label.as_deref())
    }

    /// Record the display label for the primary key at the given action
    /// index. Does nothing when the binding does not exist.
    pub fn set_label_by_index(&mut self, index: u16, label: Option<String>) {
        if let Some(&name) = KEY_NAMES.get(index as usize)
            && let Some(binding) = self.bindings.iter_mut().find(|b| b.action == name)
        {
            binding.primary_label = label;
        }
    }

    /// Set the primary key for the binding at the given action index.
    /// Preserves the existing secondary key if a binding already exists.
    /// A changed key drops the previous key's display label.
    pub fn set_key_by_index(&mut self, index: u16, key: Option<KeyCode>) {
        if let Some(&name) = KEY_NAMES.get(index as usize) {
            if let Some(binding) = self
                .bindings
                .iter_mut()
                .find(|binding| binding.action == name)
            {
                if binding.primary_key != key {
                    binding.primary_label = None;
                }
                binding.primary_key = key;
            } else {
                self.set_binding(name, key, None);
            }
        }
    }

    /// Copy all primary keys into a flat array, indexed by action.
    /// Fills up to `len` entries; missing bindings produce `None`.
    pub fn get_keys_array(&self, out: &mut [Option<KeyCode>]) {
        for (i, slot) in out.iter_mut().enumerate() {
            *slot = KEY_NAMES
                .get(i)
                .and_then(|name| self.get_binding(name))
                .and_then(|b| b.primary_key);
        }
    }

    /// Load all primary keys from a flat array. Clears existing bindings and
    /// recreates them from the array.
    fn load_keys_array(&mut self, keys: &[Option<KeyCode>]) {
        self.bindings.clear();
        for (&name, &key) in KEY_NAMES.iter().zip(keys) {
            self.bindings.push(KeyBinding {
                action: name.to_owned(),
                primary_key: key,
                secondary_key: None,
                primary_label: None,
            });
        }
    }

    /// Returns the Default1 preset used as the seed for new profiles.
    pub fn default_preset() -> Self {
        use KeyCode::*;
        const DEFAULT_KEYS: [Option<KeyCode>; REAL_KEY_COUNT as usize] = [
            Some(NumpadAdd),      // ZoomIn
            Some(NumpadSubtract), // ZoomOut
            Some(ArrowUp),        // ScrollUp
            Some(ArrowDown),      // ScrollDown
            Some(ArrowLeft),      // ScrollLeft
            Some(ArrowRight),     // ScrollRight
            Some(Semicolon),      // Minimap
            Some(Digit1),         // Character1
            Some(Digit2),         // Character2
            Some(Digit3),         // Character3
            Some(Digit4),         // Character4
            Some(Digit5),         // Character5
            Some(KeyQ),           // AllCharacters
            Some(KeyD),           // NoneCharacters
            Some(KeyC),           // Crouch
            Some(KeyS),           // StandUp
            Some(ShiftLeft),      // GoBehindBuildings
            Some(CapsLock),       // ToggleOutlineDisplay
            Some(KeyG),           // Action1
            Some(KeyH),           // Action2
            Some(KeyJ),           // Action3
            Some(ControlLeft),    // MoveDuringAction
            Some(KeyA),           // RecordQuickAction
            Some(Space),          // StartQuickAction
            Some(Backspace),      // DeleteQuickAction
            Some(AltLeft),        // ShowViewCone
            Some(F1),             // QuickSave1
            Some(F5),             // QuickLoad1
            Some(ShiftLeft),      // PlanQuickActions
            Some(KeyV),           // ToggleCloak
        ];

        let mut cfg = Self::default();
        cfg.load_keys_array(&DEFAULT_KEYS);
        cfg.key_type = 2; // PresetBase + 0
        cfg
    }

    /// Returns the "numpad-centric" Default2 preset.
    pub fn alternate_preset() -> Self {
        use KeyCode::*;
        const ALTERNATE_KEYS: [Option<KeyCode>; REAL_KEY_COUNT as usize] = [
            Some(NumpadAdd),      // ZoomIn
            Some(NumpadSubtract), // ZoomOut
            Some(ArrowUp),        // ScrollUp
            Some(ArrowDown),      // ScrollDown
            Some(ArrowLeft),      // ScrollLeft
            Some(ArrowRight),     // ScrollRight
            Some(NumpadMultiply), // Minimap
            Some(Numpad1),        // Character1
            Some(Numpad2),        // Character2
            Some(Numpad3),        // Character3
            Some(Numpad4),        // Character4
            Some(Numpad5),        // Character5
            Some(Numpad6),        // AllCharacters
            Some(Numpad0),        // NoneCharacters
            Some(PageDown),       // Crouch
            Some(PageUp),         // StandUp
            Some(ShiftRight),     // GoBehindBuildings
            Some(CapsLock),       // ToggleOutlineDisplay
            Some(Numpad7),        // Action1
            Some(Numpad8),        // Action2
            Some(Numpad9),        // Action3
            Some(ControlRight),   // MoveDuringAction
            Some(Enter),          // RecordQuickAction
            Some(Space),          // StartQuickAction
            Some(Backspace),      // DeleteQuickAction
            Some(AltRight),       // ShowViewCone
            Some(F1),             // QuickSave1
            Some(F5),             // QuickLoad1
            Some(ShiftRight),     // PlanQuickActions
            Some(KeyV),           // ToggleCloak
        ];

        let mut cfg = Self::default();
        cfg.load_keys_array(&ALTERNATE_KEYS);
        cfg.key_type = 3; // PresetBase + 1
        cfg
    }

    /// Add post-port bindings to a configuration written by an older build.
    pub fn migrate_post_port_bindings(&mut self) {
        if self.get_binding("PlanQuickActions").is_none() {
            let shift_is_available = self.bindings.iter().all(|binding| {
                let owns_shift = binding.primary_key == Some(KeyCode::ShiftLeft)
                    || binding.secondary_key == Some(KeyCode::ShiftLeft);
                !owns_shift || binding.action == "GoBehindBuildings"
            });
            let default_key = shift_is_available.then_some(KeyCode::ShiftLeft);
            self.set_binding("PlanQuickActions", default_key, None);
        }
        self.ensure_reusable_cloak_binding();
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn named_action_indices_match_persisted_action_names() {
        for (index, name) in [
            (super::GO_BEHIND_BUILDINGS_INDEX, "GoBehindBuildings"),
            (super::PLAN_QUICK_ACTIONS_INDEX, "PlanQuickActions"),
            (super::TOGGLE_CLOAK_INDEX, "ToggleCloak"),
        ] {
            assert!(index < super::REAL_KEY_COUNT);
            assert_eq!(super::KEY_NAMES[index as usize], name);
        }
    }

    use super::*;
    use winit::keyboard::KeyCode;

    #[test]
    fn indexed_edits_preserve_secondary_keys_and_first_duplicate_semantics() {
        let mut config = KeyConfig::default();
        config.set_binding("ZoomIn", Some(KeyCode::PageUp), Some(KeyCode::Home));
        config.bindings.push(config.bindings[0].clone());
        config.set_key_by_index(0, Some(KeyCode::PageDown));
        assert_eq!(config.bindings[0].primary_key, Some(KeyCode::PageDown));
        assert_eq!(config.bindings[0].secondary_key, Some(KeyCode::Home));
        assert_eq!(config.bindings[1].primary_key, Some(KeyCode::PageUp));
        config.set_key_by_index(1, None);
        assert_eq!(config.bindings.len(), 3);
        assert_eq!(config.get_binding("ZoomOut").unwrap().secondary_key, None);
        config.set_key_by_index(u16::MAX, Some(KeyCode::End));
        assert_eq!(config.bindings.len(), 3);
    }

    #[test]
    fn array_import_stops_at_the_action_table_and_clears_old_bindings() {
        let mut config = KeyConfig::default_preset();
        config.load_keys_array(&vec![Some(KeyCode::Home); KEY_NAMES.len() + 100]);
        assert_eq!(config.bindings.len(), KEY_NAMES.len());
        for (binding, name) in config.bindings.iter().zip(KEY_NAMES) {
            assert_eq!(&binding.action, name);
            assert_eq!(binding.primary_key, Some(KeyCode::Home));
            assert_eq!(binding.secondary_key, None);
        }
        config.load_keys_array(&[]);
        assert!(config.bindings.is_empty());
    }

    #[test]
    fn set_and_get_binding() {
        let mut cfg = KeyConfig::default();
        cfg.set_binding("ZoomIn", Some(KeyCode::PageUp), None);
        let b = cfg.get_binding("ZoomIn").unwrap();
        assert_eq!(b.primary_key, Some(KeyCode::PageUp));
        assert_eq!(b.secondary_key, None);
    }

    #[test]
    fn update_existing_binding() {
        let mut cfg = KeyConfig::default();
        cfg.set_binding("ZoomIn", Some(KeyCode::PageUp), None);
        cfg.set_binding("ZoomIn", Some(KeyCode::PageDown), Some(KeyCode::Home));
        assert_eq!(cfg.bindings.len(), 1);
        let b = cfg.get_binding("ZoomIn").unwrap();
        assert_eq!(b.primary_key, Some(KeyCode::PageDown));
        assert_eq!(b.secondary_key, Some(KeyCode::Home));
    }

    #[test]
    fn get_binding_missing() {
        let cfg = KeyConfig::default();
        assert!(cfg.get_binding("NonExistent").is_none());
    }

    #[test]
    fn get_action_for_primary_key() {
        let mut cfg = KeyConfig::default();
        cfg.set_binding("ScrollUp", Some(KeyCode::ArrowUp), None);
        assert_eq!(cfg.get_action_for_key(KeyCode::ArrowUp), Some("ScrollUp"));
    }

    #[test]
    fn get_action_for_secondary_key() {
        let mut cfg = KeyConfig::default();
        cfg.set_binding("ScrollUp", Some(KeyCode::ArrowUp), Some(KeyCode::F11));
        assert_eq!(cfg.get_action_for_key(KeyCode::F11), Some("ScrollUp"));
    }

    #[test]
    fn get_action_for_key_missing() {
        let cfg = KeyConfig::default();
        assert!(cfg.get_action_for_key(KeyCode::F24).is_none());
    }

    #[test]
    fn default_and_alternate_presets_differ() {
        let default = KeyConfig::default_preset();
        let alternate = KeyConfig::alternate_preset();

        let mut default_keys = vec![None; REAL_KEY_COUNT as usize];
        let mut alt_keys = vec![None; REAL_KEY_COUNT as usize];
        default.get_keys_array(&mut default_keys);
        alternate.get_keys_array(&mut alt_keys);

        assert_ne!(
            default_keys, alt_keys,
            "Default1 and Default2 must produce different bindings"
        );
        assert_eq!(
            default.key_type, 2,
            "default_preset key_type = PresetBase+0"
        );
        assert_eq!(
            alternate.key_type, 3,
            "alternate_preset key_type = PresetBase+1"
        );
    }

    #[test]
    fn serde_round_trip() {
        let mut cfg = KeyConfig::default();
        cfg.set_binding(
            "Crouch",
            Some(KeyCode::ShiftLeft),
            Some(KeyCode::ShiftRight),
        );
        cfg.set_binding("Minimap", Some(KeyCode::KeyM), None);

        let json = serde_json::to_string(&cfg).unwrap();
        let restored: KeyConfig = serde_json::from_str(&json).unwrap();

        assert_eq!(restored.bindings.len(), 2);
        let b = restored.get_binding("Crouch").unwrap();
        assert_eq!(b.primary_key, Some(KeyCode::ShiftLeft));
        assert_eq!(b.secondary_key, Some(KeyCode::ShiftRight));
    }

    #[test]
    fn serialized_shape_remains_compatible_with_existing_keyconfigs() {
        let json = r#"{"bindings":[{"action":"Crouch","primary_key":"ShiftLeft","secondary_key":"ShiftRight"},{"action":"Minimap","primary_key":"KeyM","secondary_key":null}],"key_type":1}"#;

        let cfg: KeyConfig = serde_json::from_str(json).unwrap();
        assert_eq!(cfg.key_type, 1);
        assert_eq!(
            cfg.get_binding("Crouch").unwrap().primary_key,
            Some(KeyCode::ShiftLeft)
        );
        assert_eq!(serde_json::to_string(&cfg).unwrap(), json);
    }

    #[test]
    fn legacy_key_profile_gains_non_destructive_cloak_binding() {
        let mut free_v = KeyConfig::default();
        free_v.set_binding("Crouch", Some(KeyCode::KeyC), None);
        free_v.ensure_reusable_cloak_binding();
        assert_eq!(
            free_v.get_binding("ToggleCloak").unwrap().primary_key,
            Some(KeyCode::KeyV)
        );

        let mut occupied_v = KeyConfig::default();
        occupied_v.set_binding("Crouch", Some(KeyCode::KeyV), None);
        occupied_v.ensure_reusable_cloak_binding();
        assert_eq!(
            occupied_v.get_binding("ToggleCloak").unwrap().primary_key,
            None
        );
        assert_eq!(
            occupied_v.get_binding("Crouch").unwrap().primary_key,
            Some(KeyCode::KeyV)
        );
    }

    #[test]
    fn legacy_planning_binding_only_shares_the_intentional_shift_action() {
        let mut intentional = KeyConfig::default();
        intentional.set_binding("GoBehindBuildings", Some(KeyCode::ShiftLeft), None);
        intentional.migrate_post_port_bindings();
        assert_eq!(
            intentional
                .get_binding("PlanQuickActions")
                .unwrap()
                .primary_key,
            Some(KeyCode::ShiftLeft)
        );

        let mut ambiguous = KeyConfig::default();
        ambiguous.set_binding("Crouch", Some(KeyCode::ShiftLeft), None);
        ambiguous.migrate_post_port_bindings();
        assert_eq!(
            ambiguous
                .get_binding("PlanQuickActions")
                .unwrap()
                .primary_key,
            None
        );
        assert_eq!(
            ambiguous.get_binding("Crouch").unwrap().primary_key,
            Some(KeyCode::ShiftLeft)
        );
    }

    #[test]
    fn captured_character_key_records_the_layout_character() {
        // Italian layout: the key in the US `]` position produces `+`.
        let plus = Key::Character("+".into());
        assert_eq!(
            layout_label(KeyCode::BracketRight, &plus).as_deref(),
            Some("+")
        );
        // AZERTY: the US `q` position produces `a`; caps lock is ignored.
        assert_eq!(
            layout_label(KeyCode::KeyQ, &Key::Character("A".into())).as_deref(),
            Some("a")
        );
        // Numpad keys keep their localised names even though they print.
        assert_eq!(layout_label(KeyCode::NumpadAdd, &plus), None);
        // Dead keys produce no printable character.
        assert_eq!(
            layout_label(KeyCode::BracketLeft, &Key::Dead(Some('^'))),
            None
        );
    }

    #[test]
    fn captured_named_key_records_no_label() {
        use winit::keyboard::NamedKey;
        assert_eq!(
            layout_label(KeyCode::ShiftLeft, &Key::Named(NamedKey::Shift)),
            None
        );
        assert_eq!(
            layout_label(KeyCode::Space, &Key::Named(NamedKey::Space)),
            None
        );
    }

    #[test]
    fn rebinding_a_row_drops_the_previous_keys_label() {
        let mut config = KeyConfig::default_preset();
        config.set_key_by_index(0, Some(KeyCode::BracketRight));
        config.set_label_by_index(0, Some("+".to_owned()));
        assert_eq!(config.get_label_by_index(0), Some("+"));
        // Re-assigning the same key keeps its label.
        config.set_key_by_index(0, Some(KeyCode::BracketRight));
        assert_eq!(config.get_label_by_index(0), Some("+"));
        config.set_key_by_index(0, Some(KeyCode::F3));
        assert_eq!(config.get_label_by_index(0), None);
        config.set_label_by_index(0, Some("x".to_owned()));
        config.set_binding("ZoomIn", None, None);
        assert_eq!(config.get_label_by_index(0), None);
    }

    #[test]
    fn labels_round_trip_and_unlabelled_configs_keep_their_shape() {
        let mut config = KeyConfig::default();
        config.set_binding("ZoomIn", Some(KeyCode::BracketRight), None);
        config.set_label_by_index(0, Some("+".to_owned()));
        let json = serde_json::to_string(&config).unwrap();
        assert_eq!(
            json,
            r#"{"bindings":[{"action":"ZoomIn","primary_key":"BracketRight","secondary_key":null,"primary_label":"+"}],"key_type":0}"#
        );
        assert_eq!(serde_json::from_str::<KeyConfig>(&json).unwrap(), config);
    }

    #[test]
    fn preset_bindings_remain_exact() {
        use KeyCode::*;

        let mut default_keys = vec![None; REAL_KEY_COUNT as usize];
        KeyConfig::default_preset().get_keys_array(&mut default_keys);
        assert_eq!(
            default_keys,
            vec![
                Some(NumpadAdd),
                Some(NumpadSubtract),
                Some(ArrowUp),
                Some(ArrowDown),
                Some(ArrowLeft),
                Some(ArrowRight),
                Some(Semicolon),
                Some(Digit1),
                Some(Digit2),
                Some(Digit3),
                Some(Digit4),
                Some(Digit5),
                Some(KeyQ),
                Some(KeyD),
                Some(KeyC),
                Some(KeyS),
                Some(ShiftLeft),
                Some(CapsLock),
                Some(KeyG),
                Some(KeyH),
                Some(KeyJ),
                Some(ControlLeft),
                Some(KeyA),
                Some(Space),
                Some(Backspace),
                Some(AltLeft),
                Some(F1),
                Some(F5),
                Some(ShiftLeft),
                Some(KeyV),
            ]
        );

        let mut alternate_keys = vec![None; REAL_KEY_COUNT as usize];
        KeyConfig::alternate_preset().get_keys_array(&mut alternate_keys);
        assert_eq!(
            alternate_keys,
            vec![
                Some(NumpadAdd),
                Some(NumpadSubtract),
                Some(ArrowUp),
                Some(ArrowDown),
                Some(ArrowLeft),
                Some(ArrowRight),
                Some(NumpadMultiply),
                Some(Numpad1),
                Some(Numpad2),
                Some(Numpad3),
                Some(Numpad4),
                Some(Numpad5),
                Some(Numpad6),
                Some(Numpad0),
                Some(PageDown),
                Some(PageUp),
                Some(ShiftRight),
                Some(CapsLock),
                Some(Numpad7),
                Some(Numpad8),
                Some(Numpad9),
                Some(ControlRight),
                Some(Enter),
                Some(Space),
                Some(Backspace),
                Some(AltRight),
                Some(F1),
                Some(F5),
                Some(ShiftRight),
                Some(KeyV),
            ]
        );
    }
}
