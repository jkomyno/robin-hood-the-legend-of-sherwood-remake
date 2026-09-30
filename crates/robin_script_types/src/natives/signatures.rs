//! Declarative registry for native IDs, signatures, provenance, and Lua exposure.
//!
//! The original game's script API defines the fixed 0..=264 native ID range
//! and the corresponding script-visible signatures.

use super::NativeFn;

#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
pub enum NativeYieldPolicy {
    Never,
    Always,
    Conditional,
}

/// Engine word representation shared by native adapters. Historical type
/// spellings remain in the registry for documentation and ABI identity.
#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
pub enum NativeAbiType {
    Int,
    Float,
    Bool,
    Handle,
    Void,
}

impl NativeAbiType {
    /// Evaluated while constructing the static registry: unknown types cannot
    /// become a runtime-only bridge failure.
    pub const fn from_declared_type(name: &str) -> Self {
        match name.as_bytes() {
            b"int" => Self::Int,
            b"float" => Self::Float,
            b"bool" => Self::Bool,
            b"void" => Self::Void,
            b"Actor" | b"Door" | b"Patch" | b"Location" | b"SoundSource" | b"Building"
            | b"Scroll" | b"Way" => Self::Handle,
            _ => panic!("unsupported native ABI type"),
        }
    }

    pub const fn parameter_type(name: &str) -> Self {
        let kind = Self::from_declared_type(name);
        if matches!(kind, Self::Void) {
            panic!("void native parameter");
        }
        kind
    }

    pub const fn lua_name(self) -> &'static str {
        match self {
            Self::Int => "integer",
            Self::Float => "number",
            Self::Bool => "boolean",
            Self::Handle => "handle",
            Self::Void => "no value",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NativeParamSig {
    pub ty: &'static str,
    pub abi_type: NativeAbiType,
    pub name: &'static str,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NativeSignature {
    pub name: &'static str,
    pub return_type: &'static str,
    pub return_abi_type: NativeAbiType,
    pub params: &'static [NativeParamSig],
}

/// Namespace owning a native ID.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NativeNamespace {
    /// Fixed namespace used by shipped SCB bytecode.
    Original,
    /// Operations supplied by the Rust/Lua port, outside the original interface.
    RustExtension,
}

/// Complete metadata for one native function.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NativeDefinition {
    pub native: NativeFn,
    pub namespace: NativeNamespace,
    pub signature: NativeSignature,
    pub expose_to_lua: bool,
}

/// Spellforge-facing aliases for native ABI entries. Keeping this beside the
/// declarative registry gives every Lua implementation one canonical mapping.
pub const SPELLFORGE_NATIVE_ALIASES: &[(&str, NativeFn)] = &[
    ("StartSequence", NativeFn::Start),
    ("EndSequence", NativeFn::Thanx),
    ("SequenceScrollCameraTo", NativeFn::RecordScrollCameraTo),
    ("SequenceJumpCameraTo", NativeFn::RecordJumpCameraTo),
    ("SequenceSetZoomLevel", NativeFn::RecordSetZoom),
    ("SequenceMoveCameraTo", NativeFn::RecordMoveCameraTo),
    ("SequenceDisplayMap", NativeFn::RecordDisplayMap),
    ("SequenceMove", NativeFn::RecordMove),
    ("SequenceMoveIntoBuilding", NativeFn::RecordMoveIntoBuilding),
    ("SequenceMoveNear", NativeFn::RecordMoveNear),
    ("SequenceEnterLevel", NativeFn::RecordEnterGame),
    ("SequenceLeaveLevel", NativeFn::RecordLeaveGame),
    ("SequenceTurnTo", NativeFn::RecordTurnTo),
    ("SequencePlayAnim", NativeFn::RecordPlayAnim),
    ("SequencePlayAnimLoop", NativeFn::RecordPlayAnimLoop),
    ("SequencePlayAnimFreeze", NativeFn::RecordPlayAnimFreeze),
    ("SequencePlayDialog", NativeFn::RecordPlayDialog),
    ("SequenceReplaceAnim", NativeFn::RecordReplaceAnim),
    ("SequenceRestoreAnim", NativeFn::RecordRestoreAnim),
    ("SequenceLockAI", NativeFn::RecordLockAI),
    ("SequenceUnlockAI", NativeFn::RecordUnlockAI),
    ("SequenceLockUser", NativeFn::RecordLockUser),
    ("SequenceUnLockUser", NativeFn::RecordUnLockUser),
    ("SequenceLockCameraOn", NativeFn::RecordLockCameraOn),
    ("SequenceClearCameraLock", NativeFn::RecordClearCameraLock),
    ("SequenceTimer", NativeFn::RecordTimer),
    ("SequenceSpeak", NativeFn::RecordSpeak),
    ("SequenceSpeakPC", NativeFn::RecordSpeakPC),
    ("SequenceFreezeAll", NativeFn::RecordFreezeAll),
    ("SequenceDisplayPopupText", NativeFn::RecordDisplayPopupText),
    ("SequenceSendMessage", NativeFn::RecordSendMessage),
    (
        "SequenceSendMessageWithArguments",
        NativeFn::RecordSendMessageWithArguments,
    ),
    ("SequenceSeekActor", NativeFn::RecordSeekActor),
    ("SequenceSeekActorMessage", NativeFn::RecordSeekActorMessage),
    (
        "SequenceSeekActorMessageWithArguments",
        NativeFn::RecordSeekActorMessageWithArguments,
    ),
    (
        "SequenceActivateMobileElement",
        NativeFn::RecordActivateMobileElement,
    ),
    (
        "SequenceDeactivateMobileElement",
        NativeFn::RecordDeactivateMobileElement,
    ),
    (
        "SequenceStartMobileElement",
        NativeFn::RecordStartMobileElement,
    ),
    (
        "SequenceStopMobileElement",
        NativeFn::RecordStopMobileElement,
    ),
    ("SequenceTakeCorpse", NativeFn::RecordTakeCorpse),
    ("SequenceLeaveCorpse", NativeFn::RecordLeaveCorpse),
    ("SequenceAction", NativeFn::RecordAction),
    ("SequenceActionAvailable", NativeFn::RecordActionAvailable),
    (
        "SequenceCharacterAvailable",
        NativeFn::RecordCharacterAvailable,
    ),
    ("SequenceUnBlip", NativeFn::RecordUnBlip),
    ("AssignPatrol", NativeFn::AssignPath),
    ("AddAsSquadMember", NativeFn::AddAsSubordinate),
    ("RemoveAllSquadMembers", NativeFn::RemoveAllSubordinates),
    ("GetScrollState", NativeFn::GetScrollStatus),
    ("SetScrollState", NativeFn::SetScrollStatus),
    (
        "AreAllEnemiesInsideOutOfAction",
        NativeFn::AreAllEnemiesInsideHS,
    ),
];

/// The single declaration of every native. Consumers expand this to generate
/// the ID enum and metadata tables, so order, signatures, and Lua enumeration
/// cannot drift independently.
macro_rules! native_registry {
    ($consumer:ident) => {
        $consumer! {
            original {
            // VA: 0x00404a80 wrapper
            InitGlobal => ("void", [("int", "iID"), ("int", "iValue")], lua, ScriptCore, Never);
            // VA: 0x00404ab0 wrapper
            SetGlobal => ("void", [("int", "iID"), ("int", "iValue")], lua, ScriptCore, Never);
            // VA: 0x00404ae0 wrapper
            GetGlobal => ("int", [("int", "iID")], lua, ScriptCore, Never);
            // VA: 0x00404b00 wrapper
            GetActorScript => ("Actor", [("int", "iPosition")], lua, ScriptCore, Never);
            // VA: 0x00404b20 wrapper
            GetDoorScript => ("Door", [("int", "iPosition")], lua, ScriptCore, Never);
            // VA: 0x00404b40 wrapper
            GetPatchScript => ("Patch", [("int", "iPosition")], lua, ScriptCore, Never);
            // VA: 0x00404b60 wrapper
            GetLocationScript => ("Location", [("int", "iPosition")], lua, ScriptCore, Never);
            // VA: 0x00404b80 wrapper
            GetSoundSourceScript => ("SoundSource", [("int", "iPosition")], lua, ScriptCore, Never);
            // VA: 0x00404ba0 wrapper
            GetBuildingScript => ("Building", [("int", "iPosition")], lua, ScriptCore, Never);
            // VA: 0x00404bc0 wrapper
            GetWayScript => ("Way", [("int", "iPosition")], lua, ScriptCore, Never);
            // VA: 0x00404be0 wrapper
            GetActorIndex => ("int", [("Actor", "actor")], lua, ScriptCore, Never);
            // VA: 0x00404c00 wrapper
            GetDoorIndex => ("int", [("Door", "door")], lua, ScriptCore, Never);
            // VA: 0x00404c20 wrapper
            GetPatchIndex => ("int", [("Patch", "patch")], lua, ScriptCore, Never);
            // VA: 0x00404c40 wrapper
            GetLocationIndex => ("int", [("Location", "location")], lua, ScriptCore, Never);
            // VA: 0x00404c60 wrapper
            GetSoundSourceIndex => ("int", [("SoundSource", "soundsource")], lua, ScriptCore, Never);
            // VA: 0x00404c80 wrapper
            GetBuildingIndex => ("int", [("Building", "building")], lua, ScriptCore, Never);
            // VA: 0x00404ca0 wrapper
            GetWayIndex => ("int", [("Way", "way")], lua, ScriptCore, Never);
            // VA: 0x00404cc0 wrapper
            StartDialog => ("void", [("int", "iDialogue")], lua, Sequences, Always);
            // VA: 0x00404cf0 wrapper
            ScrollCameraTo => ("bool", [("Location", "location")], lua, Sequences, Always);
            // VA: 0x00404d20 wrapper
            ScrollCameraSlowlyTo => ("bool", [("Location", "location"), ("float", "fSpeed")], lua, Sequences, Always);
            // VA: 0x00404d50 wrapper
            JumpCameraTo => ("bool", [("Location", "location")], lua, Sequences, Always);
            // VA: 0x00404d80 wrapper
            SetZoomLevel => ("bool", [("float", "fZoom")], lua, Sequences, Always);
            // VA: 0x00404db0 wrapper
            DisplayMap => ("bool", [("bool", "bDisplay")], lua, Sequences, Always);
            // VA: 0x00404de0 wrapper
            DisplayConsole => ("void", [], lua, Sequences, Always);
            // VA: 0x00404df0 wrapper
            CustomizeMinimapDisplay => ("void", [("Actor", "actor"), ("int", "iKindOfDot")], lua, Sequences, Always);
            // VA: 0x00404e20 wrapper
            DefineFlatTrajectoryZone => ("void", [("Location", "pLocation"), ("int", "iApex")], lua, Sequences, Always);
            // VA: 0x00404e50 wrapper
            AddShortBriefing => ("void", [("int", "iID"), ("bool", "bPrimary")], lua, Sequences, Never);
            // VA: 0x00404e80 wrapper
            DoneShortBriefing => ("void", [("int", "iID")], lua, Sequences, Never);
            // VA: 0x00404eb0 wrapper
            ChooseVictoryDefeatText => ("void", [("int", "iID")], lua, Sequences, Always);
            // VA: 0x00404ee0 wrapper
            ForceCheckVictory => ("void", [], lua, ScriptCore, Never);
            // VA: 0x00404ef0 wrapper
            Start => ("bool", [], lua, ScriptCore, Never);
            // VA: 0x00404f00 wrapper
            Thanx => ("bool", [], lua, ScriptCore, Always);
            // VA: 0x00404f10 wrapper
            Then => ("int", [], lua, ScriptCore, Never);
            // VA: 0x00404f20 wrapper
            RecordScrollCameraTo => ("bool", [("Location", "location")], lua, Sequences, Never);
            // VA: 0x00404f50 wrapper
            RecordJumpCameraTo => ("bool", [("Location", "location")], lua, Sequences, Never);
            // VA: 0x00404f80 wrapper
            RecordSetZoom => ("bool", [("float", "fZoomLevel")], lua, Sequences, Never);
            // VA: 0x00404fb0 wrapper
            RecordDisplayMap => ("bool", [("bool", "bDisplay")], lua, Sequences, Never);
            // VA: 0x00404fe0 wrapper
            RecordActionAvailable => ("bool", [("Actor", "actor"), ("int", "iAction"), ("bool", "bAvailable")], lua, Sequences, Never);
            // VA: 0x00405020 wrapper
            RecordCharacterAvailable => ("bool", [("Actor", "actor"), ("bool", "bAvailable")], lua, Sequences, Never);
            // VA: 0x00405050 wrapper
            RecordLockCameraOn => ("bool", [("Actor", "actor")], lua, Sequences, Never);
            // VA: 0x00405080 wrapper
            RecordClearCameraLock => ("bool", [], lua, Sequences, Never);
            // VA: 0x00405090 wrapper
            RecordPlayDialog => ("bool", [("int", "iDialogID")], lua, Sequences, Never);
            // VA: 0x004050c0 wrapper
            RecordMoveCameraTo => ("bool", [("Location", "destination"), ("int", "iSpeed")], lua, Sequences, Never);
            // VA: 0x004050f0 wrapper
            RecordSendMessage => ("void", [("Actor", "actReceiver"), ("int", "iMessageCode")], lua, Sequences, Never);
            // VA: 0x00405120 wrapper
            RecordSendMessageWithArguments => ("void", [("Actor", "actReceiver"), ("int", "iMessageCode"), ("int", "iArgument1"), ("int", "iArgument2")], lua, Sequences, Never);
            // VA: 0x00405150 wrapper
            RecordMove => ("bool", [("Actor", "actor"), ("Location", "location"), ("int", "iStyle")], lua, Sequences, Always);
            // VA: 0x00405180 wrapper
            RecordEnterGame => ("bool", [("Actor", "actor"), ("Location", "location"), ("int", "iDirection"), ("int", "iStyle")], lua, Sequences, Always);
            // VA: 0x004051c0 wrapper
            RecordLeaveGame => ("bool", [("Actor", "actor"), ("Location", "location"), ("int", "iDirection"), ("int", "iStyle")], lua, Sequences, Always);
            // VA: 0x00405200 wrapper
            RecordTurnTo => ("bool", [("Actor", "actor"), ("Location", "location")], lua, Sequences, Never);
            // VA: 0x00405230 wrapper
            RecordPlayAnim => ("bool", [("Actor", "actor"), ("int", "iId")], lua, Sequences, Never);
            // VA: 0x00405260 wrapper
            RecordPlayAnimLoop => ("bool", [("Actor", "actor"), ("int", "iId")], lua, Sequences, Never);
            // VA: 0x00405290 wrapper
            RecordPlayAnimFreeze => ("bool", [("Actor", "actor"), ("int", "iId")], lua, Sequences, Never);
            // VA: 0x004052c0 wrapper
            RecordLockAI => ("bool", [("Actor", "actor")], lua, Sequences, Never);
            // VA: 0x004052f0 wrapper
            RecordUnlockAI => ("bool", [("Actor", "actor")], lua, Sequences, Never);
            // VA: 0x00405320 wrapper
            RecordLockUser => ("bool", [], lua, Sequences, Never);
            // VA: 0x00405330 wrapper
            RecordUnLockUser => ("bool", [], lua, Sequences, Never);
            // VA: 0x00405340 wrapper
            RecordTimer => ("bool", [("int", "iFrames")], lua, Sequences, Never);
            // VA: 0x00405370 wrapper
            RecordSeekActor => ("bool", [("Actor", "actor"), ("Actor", "target"), ("int", "iStyle"), ("float", "fTolerance")], lua, Sequences, Never);
            // VA: 0x004053b0 wrapper
            RecordStopSeek => ("bool", [("Actor", "actor")], lua, Sequences, Never);
            // VA: 0x004053e0 wrapper
            RecordAction => ("bool", [("Actor", "actor"), ("int", "iID"), ("int", "iValue")], lua, Sequences, Never);
            // VA: 0x00405410 wrapper
            RecordReplaceAnim => ("bool", [("Actor", "actor"), ("int", "iOriginalAnim"), ("int", "iNewAnim")], lua, Sequences, Never);
            // VA: 0x00405440 wrapper
            RecordRestoreAnim => ("bool", [("Actor", "actor"), ("int", "iOriginalAnim")], lua, Sequences, Never);
            // VA: 0x00405470 wrapper
            RecordSpeakPC => ("bool", [("Actor", "actor"), ("int", "iRemarkID"), ("int", "iRemarkVariant")], lua, Sequences, Never);
            // VA: 0x004054a0 wrapper; masks EAX to the low byte (bool-like).
            RecordTakeCorpse => ("bool", [("Actor", "taker"), ("Actor", "corpse"), ("int", "iStyle")], lua, Sequences, Always);
            // VA: 0x004054d0 wrapper
            RecordMoveIntoBuilding => ("bool", [("Actor", "actor"), ("Location", "pointBeforeDoor"), ("int", "iStyle")], lua, Sequences, Always);
            // VA: 0x00405500 wrapper
            RecordLeaveCorpse => ("bool", [("Actor", "actor")], lua, Sequences, Never);
            // VA: 0x00405530 wrapper
            ResetAnim => ("bool", [("Actor", "actor")], lua, Sequences, Always);
            // VA: 0x00405560 wrapper
            RecordStartMobileElement => ("void", [("int", "iIndex")], lua, Sequences, Never);
            // VA: 0x00405590 wrapper
            RecordStopMobileElement => ("void", [("int", "iIndex")], lua, Sequences, Never);
            // VA: 0x004055c0 wrapper
            RecordSpeak => ("bool", [("Actor", "actor"), ("int", "iRemarkID")], lua, Sequences, Never);
            // VA: 0x004055f0 wrapper
            RecordSeekActorMessage => ("bool", [("Actor", "pActor"), ("Actor", "pTarget"), ("int", "iStyle"), ("float", "fDistance"), ("Actor", "pActorEvent"), ("int", "iID")], lua, Sequences, Never);
            // VA: 0x00405630 wrapper
            RecordSeekActorMessageWithArguments => ("bool", [("Actor", "pActor"), ("Actor", "pTarget"), ("int", "iStyle"), ("float", "fDistance"), ("Actor", "pActorEvent"), ("int", "iID"), ("int", "iArg1"), ("int", "iArg2")], lua, Sequences, Never);
            // VA: 0x00405680 wrapper
            RecordActivateMobileElement => ("void", [("int", "iIndex")], lua, Sequences, Never);
            // VA: 0x004056b0 wrapper
            RecordDeactivateMobileElement => ("void", [("int", "iIndex")], lua, Sequences, Never);
            // VA: 0x004056e0 wrapper
            ThisActor => ("Actor", [], lua, Actors, Never);
            // VA: 0x004056f0 wrapper
            GetNumberOfActorsInEngine => ("int", [], lua, Actors, Never);
            // VA: 0x00405700 wrapper
            IsActorAnimation => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405730 wrapper
            IsActorObject => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405760 wrapper
            IsActorCharacter => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405790 wrapper
            IsActorPC => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x004057c0 wrapper
            IsActorNPC => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x004057f0 wrapper
            IsActorSoldier => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405820 wrapper
            IsActorCivilian => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405850 wrapper
            IsActorAnimal => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405880 wrapper
            IsActorCart => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x004058b0 wrapper
            IsNull => ("bool", [("Actor", "actor")], lua, ScriptCore, Never);
            // VA: 0x004058e0 wrapper
            IsActorEqual => ("bool", [("Actor", "one"), ("Actor", "two")], lua, ScriptCore, Never);
            // VA: 0x00405910 wrapper
            IsActorDead => ("bool", [("Actor", "actor")], lua, ScriptCore, Never);
            // VA: 0x00405940 wrapper
            IsActorKO => ("bool", [("Actor", "actor")], lua, ScriptCore, Never);
            // VA: 0x00405970 wrapper
            IsActorTied => ("bool", [("Actor", "actor")], lua, ScriptCore, Never);
            // VA: 0x004059a0 wrapper
            IsActorHS => ("bool", [("Actor", "actor")], lua, ScriptCore, Never);
            // VA: 0x004059d0 wrapper
            GetActorPosture => ("int", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x004059f0 wrapper
            SetActorPosture => ("void", [("Actor", "actor"), ("int", "iPosture")], lua, Actors, Always);
            // VA: 0x00405a20 wrapper
            GetActorDirection => ("int", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405a40 wrapper
            SetActorDirection => ("bool", [("Actor", "actor"), ("int", "iDirection")], lua, Actors, Never);
            // VA: 0x00405a70 wrapper
            GetActorLocation => ("Location", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405a90 wrapper
            SetActorLocation => ("bool", [("Actor", "actor"), ("Location", "location")], lua, Actors, Always);
            // VA: 0x00405ac0 wrapper
            IsInside => ("bool", [("Actor", "actor"), ("Location", "location")], lua, Actors, Never);
            // VA: 0x00405af0 wrapper
            IsInsideBuilding => ("bool", [("Actor", "actor"), ("Building", "building")], lua, Actors, Never);
            // VA: 0x00405b20 wrapper
            UnBlip => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405b50 wrapper
            GetMovementStyle => ("int", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405b70 wrapper
            GetCurrentAction => ("int", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00405b90 wrapper
            InflictPain => ("void", [("Actor", "actor"), ("int", "iDamage"), ("bool", "bStun")], lua, Actors, Conditional);
            // VA: 0x00405bc0 wrapper
            StopActor => ("bool", [("Actor", "actor")], lua, ScriptCore, Always);
            // VA: 0x00405bf0 wrapper
            Sees => ("bool", [("Actor", "actorNPC"), ("Actor", "actorTarget")], lua, Actors, Never);
            // VA: 0x00405c20 wrapper
            EnableViewCone => ("void", [("Actor", "actor")], lua, Actors, Conditional);
            // VA: 0x00405c50 wrapper
            GetOutlineDisplay => ("bool", [], lua, Sequences, Never);
            // VA: 0x00405c60 wrapper
            SetOutlineDisplay => ("void", [("bool", "bDisplay")], lua, Sequences, Always);
            // VA: 0x00405c90 wrapper
            PrototypeFilterEvent => ("bool", [("Actor", "prototype"), ("Actor", "actorSource"), ("int", "iEvent")], lua, Actors, Always);
            // VA: 0x00405cc0 wrapper
            SendMessage => ("void", [("Actor", "actReceiver"), ("int", "iMessageCode")], lua, Actors, Always);
            // VA: 0x00405cf0 wrapper
            SendMessageWithArguments => ("void", [("Actor", "actReceiver"), ("int", "iMessageCode"), ("int", "iArgument1"), ("int", "iArgument2")], lua, Actors, Always);
            // VA: 0x00405d20 wrapper -> 0x00579a20; shared God/NoWhere zero sentinel.
            God => ("Actor", [], lua, ScriptCore, Never);
            // VA: 0x00405d30 wrapper
            Select => ("bool", [("int", "selectCode")], lua, ScriptCore, Always);
            // VA: 0x00405d60 wrapper
            Deactivate => ("bool", [("Actor", "actor")], lua, ScriptCore, Always);
            // VA: 0x00405d90 wrapper
            Activate => ("bool", [("Actor", "actor")], lua, ScriptCore, Always);
            // VA: 0x00405dc0 wrapper
            SetActionAvailable => ("bool", [("Actor", "actor"), ("int", "iAction"), ("bool", "bAvailable")], lua, Actors, Never);
            // VA: 0x00405e00 wrapper
            IsActionAvailable => ("bool", [("Actor", "actor"), ("int", "iAction")], lua, Actors, Never);
            // VA: 0x00405e30 wrapper
            SetPersistentProperty => ("bool", [("Actor", "actor"), ("int", "iProperty"), ("int", "iAmount")], lua, Actors, Conditional);
            // VA: 0x00405e60 wrapper
            GetPersistentProperty => ("int", [("Actor", "actor"), ("int", "iProperty")], lua, Actors, Never);
            // VA: 0x00405e90 wrapper
            IsAnyCivilianDead => ("bool", [], lua, Actors, Never);
            // VA: 0x00405ea0 wrapper
            IsAnyEnemyDead => ("bool", [], lua, Actors, Never);
            // VA: 0x00405eb0 wrapper
            GetOverallEnemyAlert => ("int", [], lua, Actors, Never);
            // VA: 0x00405ec0 wrapper
            GetOverallCivilianAlert => ("int", [], lua, Actors, Never);
            // VA: 0x00405ed0 wrapper
            SetAIAlertStatus => ("bool", [("Actor", "actor"), ("int", "iStatus")], lua, Ai, Conditional);
            // VA: 0x00405f00 wrapper
            GetAIAlertStatus => ("int", [("Actor", "actor")], lua, Ai, Never);
            // VA: 0x00405f20 wrapper
            SetAIState => ("bool", [("Actor", "actor"), ("int", "iState")], lua, Ai, Conditional);
            // VA: 0x00405f50 wrapper
            GetAIState => ("int", [("Actor", "actor")], lua, Ai, Never);
            // VA: 0x00405f70 wrapper
            SetAIAttitude => ("bool", [("Actor", "actor"), ("int", "iAttitude")], lua, Ai, Never);
            // VA: 0x00405fa0 wrapper
            GetAIAttitude => ("int", [("Actor", "actor")], lua, Ai, Never);
            // VA: 0x00405fc0 wrapper
            SetAILevel => ("bool", [("Actor", "actor"), ("int", "iProperty"), ("int", "iLevel")], lua, Ai, Never);
            // VA: 0x00405ff0 wrapper
            StareActor => ("void", [("Actor", "actor"), ("Actor", "actorTarget"), ("bool", "bTurnSprite")], lua, Ai, Always);
            // VA: 0x00406020 wrapper
            StareLocation => ("void", [("Actor", "actor"), ("Location", "locPoint"), ("bool", "bTurnSprite")], lua, Ai, Always);
            // VA: 0x00406050 wrapper
            AssignPath => ("void", [("Actor", "actor"), ("Way", "myWay")], lua, Ai, Always);
            // VA: 0x00406080 wrapper
            AssignPost => ("void", [("Actor", "actor"), ("Location", "location"), ("int", "iDirection")], lua, Ai, Always);
            // VA: 0x004060b0 wrapper
            LockAI => ("void", [("Actor", "actor"), ("bool", "bRememberEvents")], lua, ScriptCore, Always);
            // VA: 0x004060e0 wrapper
            UnlockAI => ("void", [("Actor", "actor")], lua, ScriptCore, Always);
            // VA: 0x00406110 wrapper
            ForceBattleDecision => ("void", [("Actor", "actor"), ("int", "iDecision")], lua, Ai, Never);
            // VA: 0x00406140 wrapper
            MakeNoise => ("void", [("Location", "location"), ("int", "iTypeID")], lua, Ai, Always);
            // VA: 0x00406170 wrapper
            Freeze => ("void", [("Actor", "actor"), ("bool", "bFrozen")], lua, ScriptCore, Never);
            // VA: 0x004061a0 wrapper
            FreezeAll => ("void", [("bool", "bFrozen")], lua, ScriptCore, Always);
            // VA: 0x004061d0 wrapper
            SetPathWalkingStyle => ("void", [("Actor", "NPC"), ("int", "i0Walking1Running2Backward")], lua, Ai, Always);
            // VA: 0x00406200 wrapper
            GetSoldierRank => ("int", [("Actor", "actor")], lua, Ai, Never);
            // VA: 0x00406220 wrapper
            IsAnimationActive => ("bool", [("Actor", "actor")], lua, World, Never);
            // VA: 0x00406250 wrapper
            SetAnimationState => ("bool", [("Actor", "actor"), ("bool", "bState")], lua, World, Never);
            // VA: 0x00406280 wrapper
            IsPatchApplied => ("bool", [("Patch", "patch")], lua, World, Never);
            // VA: 0x004062b0 wrapper
            ApplyPatch => ("bool", [("Patch", "patch")], lua, World, Always);
            // VA: 0x004062e0 wrapper
            ResetPatch => ("bool", [("Patch", "patch")], lua, World, Always);
            // VA: 0x00406310 wrapper
            SuspendAllSoundSources => ("bool", [], lua, World, Always);
            // VA: 0x00406320 wrapper
            ResumeAllSoundSources => ("bool", [], lua, World, Always);
            // VA: 0x00406330 wrapper
            ActivateSoundSource => ("bool", [("SoundSource", "source")], lua, World, Always);
            // VA: 0x00406360 wrapper
            DeactivateSoundSource => ("bool", [("SoundSource", "source")], lua, World, Always);
            // VA: 0x00406390 wrapper
            DestroySoundSource => ("bool", [("SoundSource", "source")], lua, World, Always);
            // VA: 0x004063c0 wrapper
            CleanFromHisBuildingBeforeTeleport => ("bool", [("Actor", "actor")], no_lua, World, Never);
            // VA: 0x004063f0 wrapper
            CleanFromScriptZoneBeforeTeleport => ("bool", [("Actor", "actor"), ("Location", "cestLaZone")], no_lua, World, Never);
            // VA: 0x00406420 wrapper
            AddToScriptZoneAfterTeleport => ("bool", [("Actor", "actor"), ("Location", "cestLaZone")], no_lua, World, Never);
            // VA: 0x00406450 wrapper
            SetCorpseExistsInBuilding => ("void", [("Actor", "pActor")], no_lua, World, Never);
            // TODO(original parity): available script API declarations
            // spell ID 156 as `PutActorInBulding`. Rust retains its established
            // corrected public spelling.
            // VA: 0x00406480 wrapper
            PutActorInBuilding => ("void", [("Actor", "actor"), ("Building", "building")], no_lua, World, Always);
            // VA: 0x004064b0 wrapper
            SetBuildingActive => ("void", [("Building", "building"), ("bool", "bActive")], lua, World, Never);
            // VA: 0x004064e0 wrapper
            GetAnyActorInsideBuilding => ("Actor", [("Building", "building")], lua, World, Never);
            // VA: 0x00405d20 wrapper -> 0x00579a20; shared God/NoWhere zero sentinel.
            NoWhere => ("Location", [], lua, ScriptCore, Never);
            // VA: 0x00406500 wrapper
            GetDistance => ("int", [("Location", "here"), ("Location", "there")], lua, ScriptCore, Never);
            // VA: 0x00406530 wrapper
            Rand => ("int", [("int", "iMaximum")], lua, ScriptCore, Never);
            // VA: 0x00406550 wrapper
            PrintConsole => ("void", [("int", "iValue")], lua, ScriptCore, Never);
            // VA: 0x00406580 wrapper
            GetSizeOfMissionTeam => ("int", [], lua, ScriptCore, Never);
            // VA: 0x00406590 wrapper
            GetPCFromMissionTeam => ("Actor", [("int", "ulPC")], lua, Campaign, Never);
            // VA: 0x004065b0 wrapper
            AddPCToMissionTeam => ("void", [("Actor", "actor")], lua, Campaign, Always);
            // VA: 0x004065e0 wrapper
            RemovePCFromMissionTeam => ("void", [("Actor", "actor")], lua, Campaign, Never);
            // VA: 0x00406610 wrapper
            GetNumberOfObligatoryPCsInMissionTeam => ("int", [], lua, Campaign, Never);
            // VA: 0x00406620 wrapper
            GetObligatoryPCFromMissionTeam => ("Actor", [("int", "ulPC")], lua, Campaign, Never);
            // VA: 0x00406640 wrapper
            IsPCObligatoryInMissionTeam => ("bool", [("Actor", "actor")], lua, Campaign, Never);
            // VA: 0x00406670 wrapper
            IsMissionTeamValid => ("bool", [], lua, ScriptCore, Never);
            // VA: 0x00406680 wrapper
            GetLastPlayedMission => ("int", [], lua, ScriptCore, Never);
            // VA: 0x00406690 wrapper
            GetNextPlayedMission => ("int", [], lua, ScriptCore, Never);
            // VA: 0x004066a0 wrapper
            IsMenToBlazonConversionMode => ("bool", [], no_lua, Campaign, Never);
            // VA: 0x004066b0 wrapper
            GetNumberOfBeamMes => ("int", [], no_lua, Campaign, Never);
            // VA: 0x004066c0 wrapper
            MoveBeamMe => ("void", [("int", "iIndex"), ("Location", "pLocation")], no_lua, Campaign, Never);
            // VA: 0x004066f0 wrapper
            SetCompanyNumber => ("void", [("Actor", "pActor"), ("int", "iNumber")], lua, Actors, Never);
            // VA: 0x00406720 wrapper
            SetAlwaysAttentive => ("void", [("Actor", "actor"), ("bool", "bYes")], lua, Actors, Conditional);
            // VA: 0x00406750 wrapper
            WinBlazon => ("void", [("Actor", "blazon")], lua, Campaign, Always);
            // VA: 0x00406780 wrapper
            LoseBlazon => ("void", [("Actor", "blazon")], lua, Campaign, Never);
            // VA: 0x004067b0 wrapper
            SetInvisible => ("void", [("Actor", "actor"), ("bool", "bHollow")], lua, Actors, Never);
            // VA: 0x004067e0 wrapper
            IsInvisible => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x00406810 wrapper
            IsDoorLockedPC => ("bool", [("Door", "door")], lua, World, Never);
            // VA: 0x00406840 wrapper
            IsDoorUnlockable => ("bool", [("Door", "door")], lua, World, Never);
            // VA: 0x00406870 wrapper
            IsDoorLockedNPCCivilian => ("bool", [("Door", "door")], lua, World, Never);
            // VA: 0x004068a0 wrapper
            IsDoorLockedNPCVillain => ("bool", [("Door", "door")], lua, World, Never);
            // VA: 0x004068d0 wrapper
            SetDoorLockedPC => ("void", [("Door", "door"), ("bool", "bState")], lua, World, Never);
            // VA: 0x00406900 wrapper
            SetDoorUnlockable => ("void", [("Door", "door"), ("bool", "bState")], lua, World, Never);
            // VA: 0x00406930 wrapper
            SetDoorLockedNPCCivilian => ("void", [("Door", "door"), ("bool", "bState")], lua, World, Never);
            // VA: 0x00406960 wrapper
            SetDoorLockedNPCVillain => ("void", [("Door", "door"), ("bool", "bState")], lua, World, Never);
            // VA: 0x00406990 wrapper
            SetDoorSpecialAutorisation => ("void", [("Door", "door"), ("Actor", "actor"), ("bool", "bDirect")], lua, World, Never);
            // VA: 0x004069c0 wrapper
            ActivateDoorMouseSector => ("void", [("bool", "bActive"), ("Door", "door")], lua, World, Never);
            // VA: 0x004069f0 wrapper
            ThisScroll => ("Actor", [], lua, World, Never);
            // VA: 0x00406a00 wrapper
            GetScrollStatus => ("int", [("Actor", "scroll")], lua, World, Never);
            // VA: 0x00406a20 wrapper
            SetScrollStatus => ("void", [("Actor", "scroll"), ("int", "iStatus")], lua, World, Always);
            // VA: 0x00406a50 wrapper
            GetCustomCampaignValue => ("int", [("int", "iIndex")], lua, ScriptCore, Never);
            // VA: 0x00406a70 wrapper
            SetCustomCampaignValue => ("void", [("int", "iIndex"), ("int", "iValue")], lua, ScriptCore, Never);
            // VA: 0x00406aa0 wrapper
            GetCustomNPCValue => ("int", [("Actor", "actor"), ("int", "iIndex")], lua, ScriptCore, Never);
            // VA: 0x00406ad0 wrapper
            SetCustomNPCValue => ("void", [("Actor", "actor"), ("int", "iIndex"), ("int", "iValue")], lua, ScriptCore, Never);
            // VA: 0x00406b00 wrapper
            RegisterAsProductionSector => ("void", [("int", "iType"), ("Location", "sector"), ("int", "iProductionSpeed")], lua, Campaign, Never);
            // VA: 0x00406b30 wrapper
            AddProductionPoint => ("void", [("int", "iType"), ("Location", "point")], lua, Campaign, Never);
            // VA: 0x00406b60 wrapper
            GetActorForBeamMe => ("Actor", [("int", "iIndex")], lua, Campaign, Never);
            // VA: 0x00406b80 wrapper
            DisplayPopupText => ("void", [("int", "iPopupTextID")], lua, Sequences, Always);
            // VA: 0x00406bb0 wrapper
            RecordDisplayPopupText => ("void", [("int", "iPopupTextID")], lua, Sequences, Never);
            // VA: 0x00406be0 wrapper
            GetNumberOfActorsInSector => ("int", [("Location", "loc")], lua, Campaign, Never);
            // VA: 0x00406c00 wrapper
            GetActorInSector => ("Actor", [("Location", "loc"), ("int", "iIndex")], lua, Campaign, Never);
            // VA: 0x00406c30 wrapper
            BitwiseAnd => ("int", [("int", "i"), ("int", "j")], lua, ScriptCore, Never);
            // VA: 0x00406c60 wrapper
            BitwiseOr => ("int", [("int", "i"), ("int", "j")], lua, ScriptCore, Never);
            // VA: 0x00406c90 wrapper
            BitwiseXor => ("int", [("int", "i"), ("int", "j")], lua, ScriptCore, Never);
            // VA: 0x00406cc0 wrapper
            HasPCAction => ("bool", [("Actor", "actPC"), ("int", "iActionCode")], lua, Actors, Never);
            // VA: 0x00406cf0 wrapper
            HasAnyPCAction => ("bool", [("int", "iActionCode")], lua, Actors, Never);
            // VA: 0x00406d20 wrapper
            GetRobin => ("Actor", [], lua, Campaign, Never);
            // VA: 0x00406d30 wrapper
            RecordMoveNear => ("bool", [("Actor", "actor"), ("Location", "location"), ("int", "iStyle"), ("int", "iTolerance")], lua, Sequences, Always);
            // VA: 0x00406d70 wrapper
            ComputeLocationBetween => ("Location", [("Location", "locA"), ("Location", "locB"), ("float", "fLambdaBetweenZeroAndOne")], lua, Campaign, Never);
            // VA: 0x00406da0 wrapper
            DeclareAsCombatTrainer => ("void", [("Actor", "actor")], lua, Ai, Never);
            // VA: 0x00406dd0 wrapper
            GetRelic => ("Actor", [("int", "iID")], lua, Campaign, Never);
            // VA: 0x00406df0 wrapper
            GetNumberOfPCs => ("int", [], lua, ScriptCore, Never);
            // VA: 0x00406e00 wrapper
            GetPC => ("Actor", [("int", "i")], lua, ScriptCore, Never);
            // VA: 0x00406e20 wrapper
            AddAsSubordinate => ("void", [("Actor", "actChief"), ("Actor", "actSubordinate")], lua, Ai, Always);
            // VA: 0x00406e50 wrapper
            RemoveAllSubordinates => ("void", [("Actor", "actChief")], lua, Ai, Always);
            // VA: 0x00406e80 wrapper
            SwitchToAlertPath => ("void", [("Actor", "actSoldier")], lua, Ai, Always);
            // VA: 0x00406eb0 wrapper
            IsActorRider => ("bool", [("Actor", "actWhoever")], lua, Actors, Never);
            // VA: 0x00406ee0 wrapper
            IsUnblipped => ("bool", [("Actor", "actWhoever")], lua, Actors, Never);
            // VA: 0x00406f10 wrapper
            IsBlazonWon => ("bool", [("Actor", "blazon")], lua, Campaign, Never);
            // VA: 0x00406f40 wrapper
            AddRepulsivePoint => ("int", [("Location", "location"), ("float", "fRadius"), ("float", "fActionRadius"), ("int", "iFlags")], lua, Ai, Never);
            // VA: 0x00406f70 wrapper
            SetViewRadius => ("void", [("int", "iRadius")], lua, Sequences, Never);
            // VA: 0x00406fa0 wrapper
            RecordFreezeAll => ("void", [("bool", "bFreeze")], lua, Sequences, Never);
            // VA: 0x00406fd0 wrapper
            DeleteRepulsivePoint => ("void", [("int", "iID")], lua, Ai, Never);
            // VA: 0x00407000 wrapper
            SetNPCEmoticon => ("void", [("Actor", "actNPC"), ("int", "iEmoticonType"), ("int", "iTime")], lua, Ai, Never);
            // VA: 0x00407030 wrapper
            ConfiscateMoney => ("void", [("Actor", "actCapitalist")], lua, Campaign, Always);
            // VA: 0x00407060 wrapper
            AreAllPCsInside => ("bool", [("Location", "location")], lua, World, Never);
            // VA: 0x00407090 wrapper
            AreAllEnemiesInsideHS => ("bool", [("Location", "locZone")], lua, World, Never);
            // VA: 0x004070c0 wrapper
            AddPCToGang => ("void", [("Actor", "actor")], lua, Campaign, Never);
            // VA: 0x004070f0 wrapper
            AttachScrollToNPC => ("void", [("Actor", "actNPC"), ("Actor", "scroll")], lua, World, Never);
            // VA: 0x00407120 wrapper
            AreAllBlazonsWon => ("bool", [], lua, ScriptCore, Never);
            // VA: 0x00407130 wrapper
            IsBonusItemPickedUp => ("bool", [("Actor", "actItem")], lua, Campaign, Never);
            // VA: 0x00407160 wrapper
            GetRansomMoney => ("int", [], lua, ScriptCore, Never);
            // VA: 0x00407170 wrapper
            SetRansomMoney => ("void", [("int", "iRansomMoneyAmount")], lua, ScriptCore, Always);
            // VA: 0x004071a0 wrapper
            GetDifficultyLevel => ("int", [], lua, ScriptCore, Never);
            // VA: 0x004071b0 wrapper
            DisplaySherwoodReport => ("void", [], lua, Sequences, Always);
            // VA: 0x004071c0 wrapper
            IsActorActive => ("bool", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x004071f0 wrapper
            AddFarmerToGang => ("void", [("int", "iType"), ("int", "iExperienceSword"), ("int", "iExperienceBow")], lua, Campaign, Never);
            // VA: 0x00407220 wrapper
            SetExperiences => ("void", [("Actor", "actor"), ("int", "iExperienceSword"), ("int", "iExperienceBow")], lua, Campaign, Never);
            // VA: 0x00407250 wrapper
            RecordUnBlip => ("bool", [("Actor", "pActor")], lua, Sequences, Never);
            // VA: 0x00407280 wrapper
            SetPatchAnimationActive => ("void", [("Patch", "patch"), ("bool", "bActive")], lua, World, Never);
            // VA: 0x004072b0 wrapper
            GetNumberOfPCsAlive => ("int", [], lua, ScriptCore, Never);
            // VA: 0x004072c0 wrapper
            AreAllPCsAliveInside => ("bool", [("Location", "location")], lua, World, Never);
            // VA: 0x004072f0 wrapper
            TransformHandleTargetToTakeTarget => ("void", [("Actor", "actTarget")], lua, Campaign, Never);
            // VA: 0x00407320 wrapper
            IsPCSelected => ("bool", [("Actor", "actPC")], lua, Campaign, Never);
            // VA: 0x00407350 wrapper
            GetNumberOfSelectedPCs => ("int", [], lua, Campaign, Never);
            // VA: 0x00407360 wrapper
            GetSelectedPC => ("Actor", [("int", "iIndex")], lua, Campaign, Never);
            // VA: 0x00407380 wrapper
            PlayTrapJingle => ("void", [], lua, Sequences, Always);
            // VA: 0x00407390 wrapper
            MakePCCrouched => ("void", [("Actor", "actPC")], lua, Actors, Always);
            // VA: 0x004073c0 wrapper
            HasAnyPCActionWhoIsInThisLevelOrCouldMaybeComeFromSherwood => ("bool", [("int", "iActionCode")], lua, ScriptCore, Never);
            // VA: 0x004073f0 wrapper
            LockPatch => ("void", [("Patch", "patch"), ("bool", "bLocked")], lua, World, Never);
            // VA: 0x00407420 wrapper
            HasAnyActivePCAction => ("bool", [("int", "iActionCode")], lua, Actors, Never);
            // VA: 0x00407450 wrapper
            GetPCType => ("int", [("Actor", "actPC")], lua, Campaign, Never);
            // VA: 0x00407470 wrapper
            SelectActorPC => ("void", [("Actor", "actPCOrGodForAllPCs"), ("bool", "bSelectOrUnselect")], lua, Campaign, Always);
            // VA: 0x004074a0 wrapper
            HasAnyActionSelected => ("bool", [("Actor", "actPC")], lua, Actors, Never);
            // VA: 0x004074d0 wrapper
            GetActorActionState => ("int", [("Actor", "actor")], lua, Actors, Never);
            // VA: 0x004074f0 wrapper
            SetActorActionState => ("void", [("Actor", "actor"), ("int", "iActionState")], lua, Actors, Always);
            // VA: 0x00407520 wrapper
            SecretAgentsAreBackInSherwood => ("bool", [], lua, ScriptCore, Never);
            // VA: 0x00407530 wrapper
            FadeToBlack => ("void", [("int", "iSpeed")], lua, Sequences, Always);
            // VA: 0x00407560 wrapper
            LinkTargetToFX => ("void", [("Actor", "actTarget"), ("Actor", "actFX")], lua, World, Never);
            // VA: 0x00407590 wrapper
            ForbidNPCRemark => ("void", [("Actor", "actNPC"), ("int", "iRemark"), ("bool", "bTrueMeansForbidFalseMeansAllow")], lua, Ai, Never);
            }
            rust_extensions {
            Reveal => ("int", [("Actor", "actActor")], lua, Campaign, Never);
            AddObjective => ("int", [("int", "iObjectiveID"), ("bool", "bIsMainObjective")], lua, Campaign, Never);
            CompleteObjective => ("int", [("int", "iObjectiveID")], lua, Campaign, Never);
            IsActorOutOfAction => ("bool", [("Actor", "actActor")], lua, Campaign, Never);
            SetPatrolShouldRun => ("void", [("Actor", "actPatrolLeader"), ("bool", "bShouldRun")], lua, Campaign, Never);
            SequenceReveal => ("int", [("Actor", "actActor")], lua, Campaign, Never);
            GetActorAllegiance => ("int", [("Actor", "actActor")], lua, ScriptCore, Never);
            GetDiplomacyRelationship => ("int", [("int", "iFirst"), ("int", "iSecond")], lua, ScriptCore, Never);
            SetDiplomacyRelationship => ("void", [("int", "iFirst"), ("int", "iSecond"), ("int", "iRelationship")], lua, ScriptCore, Never);
            }
        }
    };
}

pub(crate) use native_registry;

macro_rules! lua_exposure {
    (lua) => {
        true
    };
    (no_lua) => {
        false
    };
}

macro_rules! signature {
    ($name:ident, $return_type:literal, [$(($param_type:literal, $param_name:literal)),* $(,)?]) => {
        NativeSignature {
            name: stringify!($name),
            return_type: $return_type,
            return_abi_type: NativeAbiType::from_declared_type($return_type),
            params: &[
                $(NativeParamSig { ty: $param_type, abi_type: NativeAbiType::parameter_type($param_type), name: $param_name }),*
            ],
        }
    };
}

macro_rules! define_native_metadata {
    (
        original {
            $( $original:ident => ($original_return:literal, $original_params:tt, $original_lua:ident, $original_domain:ident, $original_yield:ident); )*
        }
        rust_extensions {
            $( $extension:ident => ($extension_return:literal, $extension_params:tt, $extension_lua:ident, $extension_domain:ident, $extension_yield:ident); )*
        }
    ) => {
        impl NativeFn {
            pub fn domain(self) -> super::NativeDomain {
                match self {
                    $(Self::$original => super::NativeDomain::$original_domain,)*
                    $(Self::$extension => super::NativeDomain::$extension_domain,)*
                }
            }

            pub fn yield_policy(self) -> NativeYieldPolicy {
                match self {
                    $(Self::$original => NativeYieldPolicy::$original_yield,)*
                    $(Self::$extension => NativeYieldPolicy::$extension_yield,)*
                }
            }

            /// Whether any valid call can suspend into the engine driver.
            pub fn may_yield(self) -> bool {
                !matches!(self.yield_policy(), NativeYieldPolicy::Never)
            }
        }

        /// Complete registry in numeric ID order.
        pub const NATIVE_REGISTRY: &[NativeDefinition] = &[
            $(
                NativeDefinition {
                    native: NativeFn::$original,
                    namespace: NativeNamespace::Original,
                    signature: signature!($original, $original_return, $original_params),
                    expose_to_lua: lua_exposure!($original_lua),
                },
            )*
            $(
                NativeDefinition {
                    native: NativeFn::$extension,
                    namespace: NativeNamespace::RustExtension,
                    signature: signature!($extension, $extension_return, $extension_params),
                    expose_to_lua: lua_exposure!($extension_lua),
                },
            )*
        ];

        /// Compatibility view of all signatures in numeric ID order.
        pub const NATIVE_SIGNATURES: &[NativeSignature] = &[
            $(signature!($original, $original_return, $original_params),)*
            $(signature!($extension, $extension_return, $extension_params),)*
        ];
    };
}

native_registry!(define_native_metadata);

pub fn native_definition_by_index(index: u32) -> Option<&'static NativeDefinition> {
    let position = if index < super::ORIGINAL_NATIVE_COUNT {
        index
    } else {
        index
            .checked_sub(super::RUST_EXTENSION_NATIVE_START)?
            .checked_add(super::ORIGINAL_NATIVE_COUNT)?
    };
    NATIVE_REGISTRY
        .get(usize::try_from(position).ok()?)
        .filter(|definition| definition.native as u32 == index)
}

pub fn native_definition_by_name(name: &str) -> Option<&'static NativeDefinition> {
    NATIVE_REGISTRY
        .iter()
        .find(|definition| definition.signature.name == name)
}

pub fn native_signature_by_index(index: u32) -> Option<&'static NativeSignature> {
    native_definition_by_index(index).map(|definition| &definition.signature)
}

pub fn native_signature_by_name(name: &str) -> Option<&'static NativeSignature> {
    native_definition_by_name(name).map(|definition| &definition.signature)
}

#[cfg(test)]
mod tests {
    use std::collections::HashSet;

    use super::*;
    use crate::natives::{ORIGINAL_NATIVE_COUNT, RUST_EXTENSION_NATIVE_START, native_name};

    // GOG v1.1 Game.exe, registry initializer 0x004075c0.
    // Independent wrapper evidence: (native ID/name, wrapper VA, 32-bit cells popped).
    // See docs/natives-evidence.md; raw decompilation stays outside the repository.
    const WRAPPER_ARITIES: [(NativeFn, u32, usize); 265] = [
        (NativeFn::InitGlobal, 0x00404a80, 2),
        (NativeFn::SetGlobal, 0x00404ab0, 2),
        (NativeFn::GetGlobal, 0x00404ae0, 1),
        (NativeFn::GetActorScript, 0x00404b00, 1),
        (NativeFn::GetDoorScript, 0x00404b20, 1),
        (NativeFn::GetPatchScript, 0x00404b40, 1),
        (NativeFn::GetLocationScript, 0x00404b60, 1),
        (NativeFn::GetSoundSourceScript, 0x00404b80, 1),
        (NativeFn::GetBuildingScript, 0x00404ba0, 1),
        (NativeFn::GetWayScript, 0x00404bc0, 1),
        (NativeFn::GetActorIndex, 0x00404be0, 1),
        (NativeFn::GetDoorIndex, 0x00404c00, 1),
        (NativeFn::GetPatchIndex, 0x00404c20, 1),
        (NativeFn::GetLocationIndex, 0x00404c40, 1),
        (NativeFn::GetSoundSourceIndex, 0x00404c60, 1),
        (NativeFn::GetBuildingIndex, 0x00404c80, 1),
        (NativeFn::GetWayIndex, 0x00404ca0, 1),
        (NativeFn::StartDialog, 0x00404cc0, 1),
        (NativeFn::ScrollCameraTo, 0x00404cf0, 1),
        (NativeFn::ScrollCameraSlowlyTo, 0x00404d20, 2),
        (NativeFn::JumpCameraTo, 0x00404d50, 1),
        (NativeFn::SetZoomLevel, 0x00404d80, 1),
        (NativeFn::DisplayMap, 0x00404db0, 1),
        (NativeFn::DisplayConsole, 0x00404de0, 0),
        (NativeFn::CustomizeMinimapDisplay, 0x00404df0, 2),
        (NativeFn::DefineFlatTrajectoryZone, 0x00404e20, 2),
        (NativeFn::AddShortBriefing, 0x00404e50, 2),
        (NativeFn::DoneShortBriefing, 0x00404e80, 1),
        (NativeFn::ChooseVictoryDefeatText, 0x00404eb0, 1),
        (NativeFn::ForceCheckVictory, 0x00404ee0, 0),
        (NativeFn::Start, 0x00404ef0, 0),
        (NativeFn::Thanx, 0x00404f00, 0),
        (NativeFn::Then, 0x00404f10, 0),
        (NativeFn::RecordScrollCameraTo, 0x00404f20, 1),
        (NativeFn::RecordJumpCameraTo, 0x00404f50, 1),
        (NativeFn::RecordSetZoom, 0x00404f80, 1),
        (NativeFn::RecordDisplayMap, 0x00404fb0, 1),
        (NativeFn::RecordActionAvailable, 0x00404fe0, 3),
        (NativeFn::RecordCharacterAvailable, 0x00405020, 2),
        (NativeFn::RecordLockCameraOn, 0x00405050, 1),
        (NativeFn::RecordClearCameraLock, 0x00405080, 0),
        (NativeFn::RecordPlayDialog, 0x00405090, 1),
        (NativeFn::RecordMoveCameraTo, 0x004050c0, 2),
        (NativeFn::RecordSendMessage, 0x004050f0, 2),
        (NativeFn::RecordSendMessageWithArguments, 0x00405120, 4),
        (NativeFn::RecordMove, 0x00405150, 3),
        (NativeFn::RecordEnterGame, 0x00405180, 4),
        (NativeFn::RecordLeaveGame, 0x004051c0, 4),
        (NativeFn::RecordTurnTo, 0x00405200, 2),
        (NativeFn::RecordPlayAnim, 0x00405230, 2),
        (NativeFn::RecordPlayAnimLoop, 0x00405260, 2),
        (NativeFn::RecordPlayAnimFreeze, 0x00405290, 2),
        (NativeFn::RecordLockAI, 0x004052c0, 1),
        (NativeFn::RecordUnlockAI, 0x004052f0, 1),
        (NativeFn::RecordLockUser, 0x00405320, 0),
        (NativeFn::RecordUnLockUser, 0x00405330, 0),
        (NativeFn::RecordTimer, 0x00405340, 1),
        (NativeFn::RecordSeekActor, 0x00405370, 4),
        (NativeFn::RecordStopSeek, 0x004053b0, 1),
        (NativeFn::RecordAction, 0x004053e0, 3),
        (NativeFn::RecordReplaceAnim, 0x00405410, 3),
        (NativeFn::RecordRestoreAnim, 0x00405440, 2),
        (NativeFn::RecordSpeakPC, 0x00405470, 3),
        (NativeFn::RecordTakeCorpse, 0x004054a0, 3),
        (NativeFn::RecordMoveIntoBuilding, 0x004054d0, 3),
        (NativeFn::RecordLeaveCorpse, 0x00405500, 1),
        (NativeFn::ResetAnim, 0x00405530, 1),
        (NativeFn::RecordStartMobileElement, 0x00405560, 1),
        (NativeFn::RecordStopMobileElement, 0x00405590, 1),
        (NativeFn::RecordSpeak, 0x004055c0, 2),
        (NativeFn::RecordSeekActorMessage, 0x004055f0, 6),
        (NativeFn::RecordSeekActorMessageWithArguments, 0x00405630, 8),
        (NativeFn::RecordActivateMobileElement, 0x00405680, 1),
        (NativeFn::RecordDeactivateMobileElement, 0x004056b0, 1),
        (NativeFn::ThisActor, 0x004056e0, 0),
        (NativeFn::GetNumberOfActorsInEngine, 0x004056f0, 0),
        (NativeFn::IsActorAnimation, 0x00405700, 1),
        (NativeFn::IsActorObject, 0x00405730, 1),
        (NativeFn::IsActorCharacter, 0x00405760, 1),
        (NativeFn::IsActorPC, 0x00405790, 1),
        (NativeFn::IsActorNPC, 0x004057c0, 1),
        (NativeFn::IsActorSoldier, 0x004057f0, 1),
        (NativeFn::IsActorCivilian, 0x00405820, 1),
        (NativeFn::IsActorAnimal, 0x00405850, 1),
        (NativeFn::IsActorCart, 0x00405880, 1),
        (NativeFn::IsNull, 0x004058b0, 1),
        (NativeFn::IsActorEqual, 0x004058e0, 2),
        (NativeFn::IsActorDead, 0x00405910, 1),
        (NativeFn::IsActorKO, 0x00405940, 1),
        (NativeFn::IsActorTied, 0x00405970, 1),
        (NativeFn::IsActorHS, 0x004059a0, 1),
        (NativeFn::GetActorPosture, 0x004059d0, 1),
        (NativeFn::SetActorPosture, 0x004059f0, 2),
        (NativeFn::GetActorDirection, 0x00405a20, 1),
        (NativeFn::SetActorDirection, 0x00405a40, 2),
        (NativeFn::GetActorLocation, 0x00405a70, 1),
        (NativeFn::SetActorLocation, 0x00405a90, 2),
        (NativeFn::IsInside, 0x00405ac0, 2),
        (NativeFn::IsInsideBuilding, 0x00405af0, 2),
        (NativeFn::UnBlip, 0x00405b20, 1),
        (NativeFn::GetMovementStyle, 0x00405b50, 1),
        (NativeFn::GetCurrentAction, 0x00405b70, 1),
        (NativeFn::InflictPain, 0x00405b90, 3),
        (NativeFn::StopActor, 0x00405bc0, 1),
        (NativeFn::Sees, 0x00405bf0, 2),
        (NativeFn::EnableViewCone, 0x00405c20, 1),
        (NativeFn::GetOutlineDisplay, 0x00405c50, 0),
        (NativeFn::SetOutlineDisplay, 0x00405c60, 1),
        (NativeFn::PrototypeFilterEvent, 0x00405c90, 3),
        (NativeFn::SendMessage, 0x00405cc0, 2),
        (NativeFn::SendMessageWithArguments, 0x00405cf0, 4),
        (NativeFn::God, 0x00405d20, 0),
        (NativeFn::Select, 0x00405d30, 1),
        (NativeFn::Deactivate, 0x00405d60, 1),
        (NativeFn::Activate, 0x00405d90, 1),
        (NativeFn::SetActionAvailable, 0x00405dc0, 3),
        (NativeFn::IsActionAvailable, 0x00405e00, 2),
        (NativeFn::SetPersistentProperty, 0x00405e30, 3),
        (NativeFn::GetPersistentProperty, 0x00405e60, 2),
        (NativeFn::IsAnyCivilianDead, 0x00405e90, 0),
        (NativeFn::IsAnyEnemyDead, 0x00405ea0, 0),
        (NativeFn::GetOverallEnemyAlert, 0x00405eb0, 0),
        (NativeFn::GetOverallCivilianAlert, 0x00405ec0, 0),
        (NativeFn::SetAIAlertStatus, 0x00405ed0, 2),
        (NativeFn::GetAIAlertStatus, 0x00405f00, 1),
        (NativeFn::SetAIState, 0x00405f20, 2),
        (NativeFn::GetAIState, 0x00405f50, 1),
        (NativeFn::SetAIAttitude, 0x00405f70, 2),
        (NativeFn::GetAIAttitude, 0x00405fa0, 1),
        (NativeFn::SetAILevel, 0x00405fc0, 3),
        (NativeFn::StareActor, 0x00405ff0, 3),
        (NativeFn::StareLocation, 0x00406020, 3),
        (NativeFn::AssignPath, 0x00406050, 2),
        (NativeFn::AssignPost, 0x00406080, 3),
        (NativeFn::LockAI, 0x004060b0, 2),
        (NativeFn::UnlockAI, 0x004060e0, 1),
        (NativeFn::ForceBattleDecision, 0x00406110, 2),
        (NativeFn::MakeNoise, 0x00406140, 2),
        (NativeFn::Freeze, 0x00406170, 2),
        (NativeFn::FreezeAll, 0x004061a0, 1),
        (NativeFn::SetPathWalkingStyle, 0x004061d0, 2),
        (NativeFn::GetSoldierRank, 0x00406200, 1),
        (NativeFn::IsAnimationActive, 0x00406220, 1),
        (NativeFn::SetAnimationState, 0x00406250, 2),
        (NativeFn::IsPatchApplied, 0x00406280, 1),
        (NativeFn::ApplyPatch, 0x004062b0, 1),
        (NativeFn::ResetPatch, 0x004062e0, 1),
        (NativeFn::SuspendAllSoundSources, 0x00406310, 0),
        (NativeFn::ResumeAllSoundSources, 0x00406320, 0),
        (NativeFn::ActivateSoundSource, 0x00406330, 1),
        (NativeFn::DeactivateSoundSource, 0x00406360, 1),
        (NativeFn::DestroySoundSource, 0x00406390, 1),
        (NativeFn::CleanFromHisBuildingBeforeTeleport, 0x004063c0, 1),
        (NativeFn::CleanFromScriptZoneBeforeTeleport, 0x004063f0, 2),
        (NativeFn::AddToScriptZoneAfterTeleport, 0x00406420, 2),
        (NativeFn::SetCorpseExistsInBuilding, 0x00406450, 1),
        (NativeFn::PutActorInBuilding, 0x00406480, 2),
        (NativeFn::SetBuildingActive, 0x004064b0, 2),
        (NativeFn::GetAnyActorInsideBuilding, 0x004064e0, 1),
        (NativeFn::NoWhere, 0x00405d20, 0),
        (NativeFn::GetDistance, 0x00406500, 2),
        (NativeFn::Rand, 0x00406530, 1),
        (NativeFn::PrintConsole, 0x00406550, 1),
        (NativeFn::GetSizeOfMissionTeam, 0x00406580, 0),
        (NativeFn::GetPCFromMissionTeam, 0x00406590, 1),
        (NativeFn::AddPCToMissionTeam, 0x004065b0, 1),
        (NativeFn::RemovePCFromMissionTeam, 0x004065e0, 1),
        (
            NativeFn::GetNumberOfObligatoryPCsInMissionTeam,
            0x00406610,
            0,
        ),
        (NativeFn::GetObligatoryPCFromMissionTeam, 0x00406620, 1),
        (NativeFn::IsPCObligatoryInMissionTeam, 0x00406640, 1),
        (NativeFn::IsMissionTeamValid, 0x00406670, 0),
        (NativeFn::GetLastPlayedMission, 0x00406680, 0),
        (NativeFn::GetNextPlayedMission, 0x00406690, 0),
        (NativeFn::IsMenToBlazonConversionMode, 0x004066a0, 0),
        (NativeFn::GetNumberOfBeamMes, 0x004066b0, 0),
        (NativeFn::MoveBeamMe, 0x004066c0, 2),
        (NativeFn::SetCompanyNumber, 0x004066f0, 2),
        (NativeFn::SetAlwaysAttentive, 0x00406720, 2),
        (NativeFn::WinBlazon, 0x00406750, 1),
        (NativeFn::LoseBlazon, 0x00406780, 1),
        (NativeFn::SetInvisible, 0x004067b0, 2),
        (NativeFn::IsInvisible, 0x004067e0, 1),
        (NativeFn::IsDoorLockedPC, 0x00406810, 1),
        (NativeFn::IsDoorUnlockable, 0x00406840, 1),
        (NativeFn::IsDoorLockedNPCCivilian, 0x00406870, 1),
        (NativeFn::IsDoorLockedNPCVillain, 0x004068a0, 1),
        (NativeFn::SetDoorLockedPC, 0x004068d0, 2),
        (NativeFn::SetDoorUnlockable, 0x00406900, 2),
        (NativeFn::SetDoorLockedNPCCivilian, 0x00406930, 2),
        (NativeFn::SetDoorLockedNPCVillain, 0x00406960, 2),
        (NativeFn::SetDoorSpecialAutorisation, 0x00406990, 3),
        (NativeFn::ActivateDoorMouseSector, 0x004069c0, 2),
        (NativeFn::ThisScroll, 0x004069f0, 0),
        (NativeFn::GetScrollStatus, 0x00406a00, 1),
        (NativeFn::SetScrollStatus, 0x00406a20, 2),
        (NativeFn::GetCustomCampaignValue, 0x00406a50, 1),
        (NativeFn::SetCustomCampaignValue, 0x00406a70, 2),
        (NativeFn::GetCustomNPCValue, 0x00406aa0, 2),
        (NativeFn::SetCustomNPCValue, 0x00406ad0, 3),
        (NativeFn::RegisterAsProductionSector, 0x00406b00, 3),
        (NativeFn::AddProductionPoint, 0x00406b30, 2),
        (NativeFn::GetActorForBeamMe, 0x00406b60, 1),
        (NativeFn::DisplayPopupText, 0x00406b80, 1),
        (NativeFn::RecordDisplayPopupText, 0x00406bb0, 1),
        (NativeFn::GetNumberOfActorsInSector, 0x00406be0, 1),
        (NativeFn::GetActorInSector, 0x00406c00, 2),
        (NativeFn::BitwiseAnd, 0x00406c30, 2),
        (NativeFn::BitwiseOr, 0x00406c60, 2),
        (NativeFn::BitwiseXor, 0x00406c90, 2),
        (NativeFn::HasPCAction, 0x00406cc0, 2),
        (NativeFn::HasAnyPCAction, 0x00406cf0, 1),
        (NativeFn::GetRobin, 0x00406d20, 0),
        (NativeFn::RecordMoveNear, 0x00406d30, 4),
        (NativeFn::ComputeLocationBetween, 0x00406d70, 3),
        (NativeFn::DeclareAsCombatTrainer, 0x00406da0, 1),
        (NativeFn::GetRelic, 0x00406dd0, 1),
        (NativeFn::GetNumberOfPCs, 0x00406df0, 0),
        (NativeFn::GetPC, 0x00406e00, 1),
        (NativeFn::AddAsSubordinate, 0x00406e20, 2),
        (NativeFn::RemoveAllSubordinates, 0x00406e50, 1),
        (NativeFn::SwitchToAlertPath, 0x00406e80, 1),
        (NativeFn::IsActorRider, 0x00406eb0, 1),
        (NativeFn::IsUnblipped, 0x00406ee0, 1),
        (NativeFn::IsBlazonWon, 0x00406f10, 1),
        (NativeFn::AddRepulsivePoint, 0x00406f40, 4),
        (NativeFn::SetViewRadius, 0x00406f70, 1),
        (NativeFn::RecordFreezeAll, 0x00406fa0, 1),
        (NativeFn::DeleteRepulsivePoint, 0x00406fd0, 1),
        (NativeFn::SetNPCEmoticon, 0x00407000, 3),
        (NativeFn::ConfiscateMoney, 0x00407030, 1),
        (NativeFn::AreAllPCsInside, 0x00407060, 1),
        (NativeFn::AreAllEnemiesInsideHS, 0x00407090, 1),
        (NativeFn::AddPCToGang, 0x004070c0, 1),
        (NativeFn::AttachScrollToNPC, 0x004070f0, 2),
        (NativeFn::AreAllBlazonsWon, 0x00407120, 0),
        (NativeFn::IsBonusItemPickedUp, 0x00407130, 1),
        (NativeFn::GetRansomMoney, 0x00407160, 0),
        (NativeFn::SetRansomMoney, 0x00407170, 1),
        (NativeFn::GetDifficultyLevel, 0x004071a0, 0),
        (NativeFn::DisplaySherwoodReport, 0x004071b0, 0),
        (NativeFn::IsActorActive, 0x004071c0, 1),
        (NativeFn::AddFarmerToGang, 0x004071f0, 3),
        (NativeFn::SetExperiences, 0x00407220, 3),
        (NativeFn::RecordUnBlip, 0x00407250, 1),
        (NativeFn::SetPatchAnimationActive, 0x00407280, 2),
        (NativeFn::GetNumberOfPCsAlive, 0x004072b0, 0),
        (NativeFn::AreAllPCsAliveInside, 0x004072c0, 1),
        (NativeFn::TransformHandleTargetToTakeTarget, 0x004072f0, 1),
        (NativeFn::IsPCSelected, 0x00407320, 1),
        (NativeFn::GetNumberOfSelectedPCs, 0x00407350, 0),
        (NativeFn::GetSelectedPC, 0x00407360, 1),
        (NativeFn::PlayTrapJingle, 0x00407380, 0),
        (NativeFn::MakePCCrouched, 0x00407390, 1),
        (
            NativeFn::HasAnyPCActionWhoIsInThisLevelOrCouldMaybeComeFromSherwood,
            0x004073c0,
            1,
        ),
        (NativeFn::LockPatch, 0x004073f0, 2),
        (NativeFn::HasAnyActivePCAction, 0x00407420, 1),
        (NativeFn::GetPCType, 0x00407450, 1),
        (NativeFn::SelectActorPC, 0x00407470, 2),
        (NativeFn::HasAnyActionSelected, 0x004074a0, 1),
        (NativeFn::GetActorActionState, 0x004074d0, 1),
        (NativeFn::SetActorActionState, 0x004074f0, 2),
        (NativeFn::SecretAgentsAreBackInSherwood, 0x00407520, 0),
        (NativeFn::FadeToBlack, 0x00407530, 1),
        (NativeFn::LinkTargetToFX, 0x00407560, 2),
        (NativeFn::ForbidNPCRemark, 0x00407590, 3),
    ];

    #[test]
    fn original_signatures_match_wrapper_evidence() {
        let original: Vec<_> = NATIVE_REGISTRY
            .iter()
            .filter(|definition| definition.namespace == NativeNamespace::Original)
            .collect();
        assert_eq!(original.len(), 265);
        assert_eq!(ORIGINAL_NATIVE_COUNT, 265);
        for (id, &(native, wrapper_va, arity)) in WRAPPER_ARITIES.iter().enumerate() {
            assert_eq!(native as usize, id, "wrapper 0x{wrapper_va:08x}");
            assert_eq!(original[id].native, native);
            assert_eq!(
                original[id].signature.params.len(),
                arity,
                "{native}: wrapper 0x{wrapper_va:08x}"
            );
        }

        // IDs 111 (God) and 159 (NoWhere) share the zero-return sentinel stub:
        // 0x00405d20 -> 0x00579a20. Preserve their distinct logical handle types.
        for (id, native, return_type) in [
            (111, NativeFn::God, "Actor"),
            (159, NativeFn::NoWhere, "Location"),
        ] {
            assert_eq!(WRAPPER_ARITIES[id], (native, 0x00405d20, 0));
            assert_eq!(original[id].signature.return_type, return_type);
            assert_eq!(
                original[id].signature.return_abi_type,
                NativeAbiType::Handle
            );
        }

        // 0x004054a0 calls 0x00574a70, then AND EAX,0xff at 0x004054c7.
        let take_corpse = native_signature_by_index(63).unwrap();
        assert_eq!(take_corpse.name, "RecordTakeCorpse");
        assert_eq!(take_corpse.return_type, "bool");
        assert_eq!(take_corpse.return_abi_type, NativeAbiType::Bool);
    }

    #[test]
    fn synchronous_ai_natives_are_rejected_before_direct_host_mutation() {
        for native in [
            NativeFn::StareActor,
            NativeFn::StareLocation,
            NativeFn::AssignPath,
            NativeFn::AssignPost,
            NativeFn::SetPathWalkingStyle,
            NativeFn::SwitchToAlertPath,
            NativeFn::RemoveAllSubordinates,
            NativeFn::StopActor,
            NativeFn::LockAI,
            NativeFn::UnlockAI,
        ] {
            assert_eq!(native.yield_policy(), NativeYieldPolicy::Always, "{native}");
            assert!(native.may_yield(), "{native}");
        }
        assert!(!NativeFn::GetGlobal.may_yield());
        assert_eq!(
            NativeFn::SetAIState.yield_policy(),
            NativeYieldPolicy::Conditional
        );
    }

    #[test]
    fn native_lookup_rejects_out_of_range_ids() {
        assert!(native_definition_by_index(NATIVE_REGISTRY.len() as u32).is_none());
        assert!(native_definition_by_index(u32::MAX).is_none());
        for definition in NATIVE_REGISTRY {
            assert_eq!(
                native_definition_by_index(definition.native as u32),
                Some(definition)
            );
        }
    }

    #[test]
    fn registry_has_exhaustive_unique_ids_names_and_signatures() {
        assert_eq!(NATIVE_REGISTRY.len(), NATIVE_SIGNATURES.len());

        let mut ids = HashSet::new();
        let mut names = HashSet::new();
        for (position, definition) in NATIVE_REGISTRY.iter().enumerate() {
            let id = definition.native as u32;
            assert!(ids.insert(id), "duplicate native ID {id}");
            assert!(
                names.insert(definition.signature.name),
                "duplicate native name {}",
                definition.signature.name
            );
            assert_eq!(native_name(id), definition.signature.name);
            let signature = &definition.signature;
            assert_eq!(
                signature.return_abi_type,
                NativeAbiType::from_declared_type(signature.return_type)
            );
            for parameter in signature.params {
                assert_eq!(
                    parameter.abi_type,
                    NativeAbiType::from_declared_type(parameter.ty)
                );
                assert_ne!(
                    parameter.abi_type,
                    NativeAbiType::Void,
                    "void parameter in {}",
                    signature.name
                );
            }
            assert_eq!(
                native_signature_by_index(id),
                Some(&definition.signature),
                "missing signature for registry position {position}"
            );
            assert_eq!(
                native_signature_by_name(definition.signature.name),
                Some(&definition.signature)
            );
            assert_eq!(NATIVE_SIGNATURES[position], definition.signature);
        }
    }

    #[test]
    fn namespaces_are_contiguous_and_ordered() {
        assert_eq!(ORIGINAL_NATIVE_COUNT, 265);
        assert_eq!(RUST_EXTENSION_NATIVE_START, ORIGINAL_NATIVE_COUNT);

        for (expected_id, definition) in NATIVE_REGISTRY
            .iter()
            .take(ORIGINAL_NATIVE_COUNT as usize)
            .enumerate()
        {
            assert_eq!(definition.namespace, NativeNamespace::Original);
            assert_eq!(definition.native as usize, expected_id);
        }

        let extensions = &NATIVE_REGISTRY[ORIGINAL_NATIVE_COUNT as usize..];
        assert!(!extensions.is_empty());
        for (offset, definition) in extensions.iter().enumerate() {
            assert_eq!(definition.namespace, NativeNamespace::RustExtension);
            assert_eq!(
                definition.native as u32,
                RUST_EXTENSION_NATIVE_START + offset as u32
            );
        }
    }

    #[test]
    fn lua_enumeration_is_unique_and_follows_registry_order() {
        let exposed: Vec<_> = NATIVE_REGISTRY
            .iter()
            .filter(|definition| definition.expose_to_lua)
            .collect();
        assert!(!exposed.is_empty());
        assert!(
            exposed
                .windows(2)
                .all(|pair| (pair[0].native as u32) < pair[1].native as u32)
        );

        let names: HashSet<_> = exposed
            .iter()
            .map(|definition| definition.signature.name)
            .collect();
        assert_eq!(names.len(), exposed.len());
    }
}
