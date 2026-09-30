# SCB native signature evidence

Audit of all 265 original native IDs (0..264), excluding Rust extensions.
Baseline: `3036a14725c8a150d9a125fd1129f6897da548b9` on `revival/m2-natives-crosscheck`.

Result: **0 arity fixes, 1 return-type fix, 264 unchanged entries confirmed
compatible with wrapper evidence, 0 unresolved ambiguous entries**. All 265
arities are verified. The corrected entry is ID 63, `RecordTakeCorpse` (`int`
to `bool`). No caller changes are needed: native dispatch already returns a
32-bit VM word, and typed consumers read the registry's ABI metadata.

## Sources and method

Source binary: GOG v1.1 `Game.exe`, image base `0x00400000`, SHA-256
`b0963242470d96cdd8021e2cb81ccbc5e26b4fb2cb122febdec50ad30774f08e`.

The source evidence was read in place from the separately supplied
`m2-evidence/decomp/` directory. No decompiled C, assembly exports, or raw JSON
are included in this repository. This document and the test fixture contain
only the comparison conclusions and address citations.

- `natives.md`: extraction provenance, dispatch interpretation and shared stub.
- `raw/dispatch.txt`: all 265 registry stores in initializer `0x004075c0`.
- `raw/native-map.json`: ID-to-wrapper and engine-target mapping. Its logical
  signatures are guesses, so its `args` and `ret` fields were not treated as proof.
- `raw/natives-bulk.txt`: each registered wrapper's parameter-stack used-byte
  decrement, divided by four, gives the arity. A combined decrement such as
  12 bytes consumes three arguments. No engine-call argument-count inference
  was needed.
- `raw/wrappers-asm.txt`: checked each wrapper through its first return or tail
  jump, confirming all argument pushes (excluding saved registers), engine
  targets and return conventions against the C. The 265 registry stores also
  agree with the machine-readable address map.

Return conventions: 83 wrappers clear EAX (`void`), 117 mask EAX to the low
byte (`bool`-like), 63 preserve the engine result as a 32-bit word, and two
logical entries share the zero sentinel stub. The table calls an existing
word return *compatible*, because a wrapper alone cannot distinguish an
integer from floating-point bits or a logical object/location handle. Likewise,
a one-byte mask establishes a byte-sized result, not a mathematical guarantee
that the engine only emits 0 and 1. `bool` is the registry's existing category
for these results. Parameter types and names remain logical annotations;
32-bit cells alone do not prove their semantics.

Several passthrough wrappers are decompiled as `void` with `return;`. Assembly
shows no EAX clear after the engine call, so those C declarations do not justify
changing an existing value-returning signature to `void`. This applies to all
word-return rows below. Zero-argument thunks likewise preserve the target's
return convention.

## Resolved qualifications and ambiguity

- ID 63: wrapper `0x004054a0` consumes 12 bytes, calls `0x00574a70`, then masks
  EAX at `0x004054c7`. Changed `RecordTakeCorpse` to `bool`, consistent with
  the other byte-result recording wrappers; all three parameters stay intact.
- IDs 111 (`God`) and 159 (`NoWhere`): both registry slots hold `0x00405d20`,
  which jumps to `0x00579a20`. The target returns zero without consuming
  parameters. These are typed zero sentinels, so their existing `Actor` and
  `Location` return types stay intact; they are not void adapters.
- IDs 70 and 71 consume 24 and 32 bytes respectively (six and eight cells).
  Their larger parameter lists are confirmed by assembly pushes.
- **ambiguous: none** for argument count or wrapper return convention after
  assembly cross-checking. “Confirmed” means ABI consistency, not recovery of
  all original source-language types.
- TODO: recover logical parameter and passthrough return types from engine
  semantics or original declarations if stronger type evidence becomes available.
  This audit deliberately retains those existing annotations.

## Gate repairs

The first required test gate exposed an existing failure in
`picture::tests::original_sixteen_accepts_only_the_stale_rgb24_export_length`.
For a two-pixel image, the decoder accepted five decompressed bytes even though
its documented contract and test permit only four RGB565 bytes or the known
six-byte legacy RGB24 export. `robin_assets/src/picture.rs` now rejects any
other decoded length before truncating the permitted legacy suffix. The
existing test covers zlib and bzip2 payloads, canonical re-export and stream
position; no new image behavior or test cases were added beyond that repair.
The next run exposed an architecture-specific test expectation in
`ai_enemy::util::step_back_direction_tests::zero_vector_normalization_preserves_original_nan_result`:
ARM returned positive NaN (`0x7fc00000`) where the test pinned the original x86
negative NaN (`0xffc00000`). The test now asserts NaN on every target and retains
the exact original bit check on x86/x86_64. Production vector arithmetic is
unchanged; the existing old/new helper bit-comparison suite also stays intact.
These gate repairs are separate from the native-signature counts above.

## Verification

Final gates passed in the requested order on macOS ARM64:

1. `env -u RUSTUP_TOOLCHAIN cargo test -p robin_script_types -p robin_assets -p robin_engine`
2. `env -u RUSTUP_TOOLCHAIN cargo check -p robin_rs --features desktop`

Formatting checks passed for the three changed crates. The new native evidence
test was first run against the unchanged signature and failed on ID 63's `int`
return; it passed after the correction. Existing fixture-dependent ignored
tests retain their normal ignored status. The raw evidence was not used as a
runtime test dependency.

## Full comparison

“Before” is the baseline Rust declaration. Every row received its wrapper VA
comment, including rows with no signature change. The test's static arity table
was derived from wrapper stack consumption independently of registry parameters.

| ID | Name | signatures.rs before | Evidence verdict | Change made |
|---:|---|---|---|---|
| 0 | `InitGlobal` | `void InitGlobal(int iID, int iValue)` | `0x00404a80` -> `0x00577090`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 1 | `SetGlobal` | `void SetGlobal(int iID, int iValue)` | `0x00404ab0` -> `0x005770b0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 2 | `GetGlobal` | `int GetGlobal(int iID)` | `0x00404ae0` -> `0x00577100`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 3 | `GetActorScript` | `Actor GetActorScript(int iPosition)` | `0x00404b00` -> `0x00571590`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 4 | `GetDoorScript` | `Door GetDoorScript(int iPosition)` | `0x00404b20` -> `0x005716a0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 5 | `GetPatchScript` | `Patch GetPatchScript(int iPosition)` | `0x00404b40` -> `0x00571700`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 6 | `GetLocationScript` | `Location GetLocationScript(int iPosition)` | `0x00404b60` -> `0x005714f0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 7 | `GetSoundSourceScript` | `SoundSource GetSoundSourceScript(int iPosition)` | `0x00404b80` -> `0x005755f0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 8 | `GetBuildingScript` | `Building GetBuildingScript(int iPosition)` | `0x00404ba0` -> `0x00571760`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 9 | `GetWayScript` | `Way GetWayScript(int iPosition)` | `0x00404bc0` -> `0x00571780`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 10 | `GetActorIndex` | `int GetActorIndex(Actor actor)` | `0x00404be0` -> `0x00579bd0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 11 | `GetDoorIndex` | `int GetDoorIndex(Door door)` | `0x00404c00` -> `0x00579c90`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 12 | `GetPatchIndex` | `int GetPatchIndex(Patch patch)` | `0x00404c20` -> `0x00579d00`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 13 | `GetLocationIndex` | `int GetLocationIndex(Location location)` | `0x00404c40` -> `0x00579d70`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 14 | `GetSoundSourceIndex` | `int GetSoundSourceIndex(SoundSource soundsource)` | `0x00404c60` -> `0x00579de0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 15 | `GetBuildingIndex` | `int GetBuildingIndex(Building building)` | `0x00404c80` -> `0x00579e80`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 16 | `GetWayIndex` | `int GetWayIndex(Way way)` | `0x00404ca0` -> `0x00579ef0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 17 | `StartDialog` | `void StartDialog(int iDialogue)` | `0x00404cc0` -> `0x005714a0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 18 | `ScrollCameraTo` | `bool ScrollCameraTo(Location location)` | `0x00404cf0` -> `0x00571270`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 19 | `ScrollCameraSlowlyTo` | `bool ScrollCameraSlowlyTo(Location location, float fSpeed)` | `0x00404d20` -> `0x00571330`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 20 | `JumpCameraTo` | `bool JumpCameraTo(Location location)` | `0x00404d50` -> `0x005713f0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 21 | `SetZoomLevel` | `bool SetZoomLevel(float fZoom)` | `0x00404d80` -> `0x00571200`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 22 | `DisplayMap` | `bool DisplayMap(bool bDisplay)` | `0x00404db0` -> `0x005714b0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 23 | `DisplayConsole` | `void DisplayConsole()` | `0x00404de0` -> `0x00576170`; 0 bytes / 0 args; EAX cleared: void confirmed | VA comment only |
| 24 | `CustomizeMinimapDisplay` | `void CustomizeMinimapDisplay(Actor actor, int iKindOfDot)` | `0x00404df0` -> `0x005788a0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 25 | `DefineFlatTrajectoryZone` | `void DefineFlatTrajectoryZone(Location pLocation, int iApex)` | `0x00404e20` -> `0x00578c70`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 26 | `AddShortBriefing` | `void AddShortBriefing(int iID, bool bPrimary)` | `0x00404e50` -> `0x005785b0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 27 | `DoneShortBriefing` | `void DoneShortBriefing(int iID)` | `0x00404e80` -> `0x005785d0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 28 | `ChooseVictoryDefeatText` | `void ChooseVictoryDefeatText(int iID)` | `0x00404eb0` -> `0x00570a30`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 29 | `ForceCheckVictory` | `void ForceCheckVictory()` | `0x00404ee0` -> `0x00578c60`; 0 bytes / 0 args; EAX cleared: void confirmed | VA comment only |
| 30 | `Start` | `bool Start()` | `0x00404ef0` -> `0x00570f00`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 31 | `Thanx` | `bool Thanx()` | `0x00404f00` -> `0x00571020`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 32 | `Then` | `int Then()` | `0x00404f10` -> `0x00571100`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 33 | `RecordScrollCameraTo` | `bool RecordScrollCameraTo(Location location)` | `0x00404f20` -> `0x00572ab0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 34 | `RecordJumpCameraTo` | `bool RecordJumpCameraTo(Location location)` | `0x00404f50` -> `0x00572ba0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 35 | `RecordSetZoom` | `bool RecordSetZoom(float fZoomLevel)` | `0x00404f80` -> `0x00572d50`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 36 | `RecordDisplayMap` | `bool RecordDisplayMap(bool bDisplay)` | `0x00404fb0` -> `0x00572e40`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 37 | `RecordActionAvailable` | `bool RecordActionAvailable(Actor actor, int iAction, bool bAvailable)` | `0x00404fe0` -> `0x00577d30`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 38 | `RecordCharacterAvailable` | `bool RecordCharacterAvailable(Actor actor, bool bAvailable)` | `0x00405020` -> `0x00577e70`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 39 | `RecordLockCameraOn` | `bool RecordLockCameraOn(Actor actor)` | `0x00405050` -> `0x00577f30`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 40 | `RecordClearCameraLock` | `bool RecordClearCameraLock()` | `0x00405080` -> `0x00577fe0`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 41 | `RecordPlayDialog` | `bool RecordPlayDialog(int iDialogID)` | `0x00405090` -> `0x00572a20`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 42 | `RecordMoveCameraTo` | `bool RecordMoveCameraTo(Location destination, int iSpeed)` | `0x004050c0` -> `0x00572c70`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 43 | `RecordSendMessage` | `void RecordSendMessage(Actor actReceiver, int iMessageCode)` | `0x004050f0` -> `0x00578cb0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 44 | `RecordSendMessageWithArguments` | `void RecordSendMessageWithArguments(Actor actReceiver, int iMessageCode, int iArgument1, int iArgument2)` | `0x00405120` -> `0x00578e50`; 16 bytes / 4 args; EAX cleared: void confirmed | VA comment only |
| 45 | `RecordMove` | `bool RecordMove(Actor actor, Location location, int iStyle)` | `0x00405150` -> `0x005740b0`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 46 | `RecordEnterGame` | `bool RecordEnterGame(Actor actor, Location location, int iDirection, int iStyle)` | `0x00405180` -> `0x00577650`; 16 bytes / 4 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 47 | `RecordLeaveGame` | `bool RecordLeaveGame(Actor actor, Location location, int iDirection, int iStyle)` | `0x004051c0` -> `0x005779a0`; 16 bytes / 4 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 48 | `RecordTurnTo` | `bool RecordTurnTo(Actor actor, Location location)` | `0x00405200` -> `0x00574e70`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 49 | `RecordPlayAnim` | `bool RecordPlayAnim(Actor actor, int iId)` | `0x00405230` -> `0x00573190`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 50 | `RecordPlayAnimLoop` | `bool RecordPlayAnimLoop(Actor actor, int iId)` | `0x00405260` -> `0x00573280`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 51 | `RecordPlayAnimFreeze` | `bool RecordPlayAnimFreeze(Actor actor, int iId)` | `0x00405290` -> `0x00573370`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 52 | `RecordLockAI` | `bool RecordLockAI(Actor actor)` | `0x004052c0` -> `0x00575120`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 53 | `RecordUnlockAI` | `bool RecordUnlockAI(Actor actor)` | `0x004052f0` -> `0x005751d0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 54 | `RecordLockUser` | `bool RecordLockUser()` | `0x00405320` -> `0x005753d0`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 55 | `RecordUnLockUser` | `bool RecordUnLockUser()` | `0x00405330` -> `0x00575470`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 56 | `RecordTimer` | `bool RecordTimer(int iFrames)` | `0x00405340` -> `0x00575350`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 57 | `RecordSeekActor` | `bool RecordSeekActor(Actor actor, Actor target, int iStyle, float fTolerance)` | `0x00405370` -> `0x00573d10`; 16 bytes / 4 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 58 | `RecordStopSeek` | `bool RecordStopSeek(Actor actor)` | `0x004053b0` -> `0x006390a0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 59 | `RecordAction` | `bool RecordAction(Actor actor, int iID, int iValue)` | `0x004053e0` -> `0x00573450`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 60 | `RecordReplaceAnim` | `bool RecordReplaceAnim(Actor actor, int iOriginalAnim, int iNewAnim)` | `0x00405410` -> `0x00574f80`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 61 | `RecordRestoreAnim` | `bool RecordRestoreAnim(Actor actor, int iOriginalAnim)` | `0x00405440` -> `0x00575050`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 62 | `RecordSpeakPC` | `bool RecordSpeakPC(Actor actor, int iRemarkID, int iRemarkVariant)` | `0x00405470` -> `0x005730b0`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 63 | `RecordTakeCorpse` | `int RecordTakeCorpse(Actor taker, Actor corpse, int iStyle)` | `0x004054a0` -> `0x00574a70`; 12 bytes / 3 args; EAX masked to low byte: bool-like (mismatch) | `int` -> `bool`; VA comment |
| 64 | `RecordMoveIntoBuilding` | `bool RecordMoveIntoBuilding(Actor actor, Location pointBeforeDoor, int iStyle)` | `0x004054d0` -> `0x00574860`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 65 | `RecordLeaveCorpse` | `bool RecordLeaveCorpse(Actor actor)` | `0x00405500` -> `0x00574db0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 66 | `ResetAnim` | `bool ResetAnim(Actor actor)` | `0x00405530` -> `0x00570dd0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 67 | `RecordStartMobileElement` | `void RecordStartMobileElement(int iIndex)` | `0x00405560` -> `0x005783b0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 68 | `RecordStopMobileElement` | `void RecordStopMobileElement(int iIndex)` | `0x00405590` -> `0x00578430`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 69 | `RecordSpeak` | `bool RecordSpeak(Actor actor, int iRemarkID)` | `0x004055c0` -> `0x00572ef0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 70 | `RecordSeekActorMessage` | `bool RecordSeekActorMessage(Actor pActor, Actor pTarget, int iStyle, float fDistance, Actor pActorEvent, int iID)` | `0x004055f0` -> `0x00573da0`; 24 bytes / 6 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 71 | `RecordSeekActorMessageWithArguments` | `bool RecordSeekActorMessageWithArguments(Actor pActor, Actor pTarget, int iStyle, float fDistance, Actor pActorEvent, int iID, int iArg1, int iArg2)` | `0x00405630` -> `0x00573f00`; 32 bytes / 8 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 72 | `RecordActivateMobileElement` | `void RecordActivateMobileElement(int iIndex)` | `0x00405680` -> `0x005784b0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 73 | `RecordDeactivateMobileElement` | `void RecordDeactivateMobileElement(int iIndex)` | `0x004056b0` -> `0x00578530`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 74 | `ThisActor` | `Actor ThisActor()` | `0x004056e0` -> `0x00578050`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 75 | `GetNumberOfActorsInEngine` | `int GetNumberOfActorsInEngine()` | `0x004056f0` -> `0x005714d0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 76 | `IsActorAnimation` | `bool IsActorAnimation(Actor actor)` | `0x00405700` -> `0x00570a70`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 77 | `IsActorObject` | `bool IsActorObject(Actor actor)` | `0x00405730` -> `0x00570ae0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 78 | `IsActorCharacter` | `bool IsActorCharacter(Actor actor)` | `0x00405760` -> `0x00570a90`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 79 | `IsActorPC` | `bool IsActorPC(Actor actor)` | `0x00405790` -> `0x00570b80`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 80 | `IsActorNPC` | `bool IsActorNPC(Actor actor)` | `0x004057c0` -> `0x00570c10`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 81 | `IsActorSoldier` | `bool IsActorSoldier(Actor actor)` | `0x004057f0` -> `0x00570c60`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 82 | `IsActorCivilian` | `bool IsActorCivilian(Actor actor)` | `0x00405820` -> `0x00570cb0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 83 | `IsActorAnimal` | `bool IsActorAnimal(Actor actor)` | `0x00405850` -> `0x00570bd0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 84 | `IsActorCart` | `bool IsActorCart(Actor actor)` | `0x00405880` -> `0x00570b30`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 85 | `IsNull` | `bool IsNull(Actor actor)` | `0x004058b0` -> `0x00570a50`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 86 | `IsActorEqual` | `bool IsActorEqual(Actor one, Actor two)` | `0x004058e0` -> `0x00570a60`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 87 | `IsActorDead` | `bool IsActorDead(Actor actor)` | `0x00405910` -> `0x00579a70`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 88 | `IsActorKO` | `bool IsActorKO(Actor actor)` | `0x00405940` -> `0x00579ac0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 89 | `IsActorTied` | `bool IsActorTied(Actor actor)` | `0x00405970` -> `0x00579b10`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 90 | `IsActorHS` | `bool IsActorHS(Actor actor)` | `0x004059a0` -> `0x00579b60`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 91 | `GetActorPosture` | `int GetActorPosture(Actor actor)` | `0x004059d0` -> `0x005762d0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 92 | `SetActorPosture` | `void SetActorPosture(Actor actor, int iPosture)` | `0x004059f0` -> `0x005763e0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 93 | `GetActorDirection` | `int GetActorDirection(Actor actor)` | `0x00405a20` -> `0x00571a70`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 94 | `SetActorDirection` | `bool SetActorDirection(Actor actor, int iDirection)` | `0x00405a40` -> `0x00571ab0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 95 | `GetActorLocation` | `Location GetActorLocation(Actor actor)` | `0x00405a70` -> `0x005717a0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 96 | `SetActorLocation` | `bool SetActorLocation(Actor actor, Location location)` | `0x00405a90` -> `0x005718d0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 97 | `IsInside` | `bool IsInside(Actor actor, Location location)` | `0x00405ac0` -> `0x00571de0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 98 | `IsInsideBuilding` | `bool IsInsideBuilding(Actor actor, Building building)` | `0x00405af0` -> `0x00577cf0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 99 | `UnBlip` | `bool UnBlip(Actor actor)` | `0x00405b20` -> `0x00570e70`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 100 | `GetMovementStyle` | `int GetMovementStyle(Actor actor)` | `0x00405b50` -> `0x00571550`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 101 | `GetCurrentAction` | `int GetCurrentAction(Actor actor)` | `0x00405b70` -> `0x00578060`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 102 | `InflictPain` | `void InflictPain(Actor actor, int iDamage, bool bStun)` | `0x00405b90` -> `0x00577500`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 103 | `StopActor` | `bool StopActor(Actor actor)` | `0x00405bc0` -> `0x00571b30`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 104 | `Sees` | `bool Sees(Actor actorNPC, Actor actorTarget)` | `0x00405bf0` -> `0x00578160`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 105 | `EnableViewCone` | `void EnableViewCone(Actor actor)` | `0x00405c20` -> `0x005786b0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 106 | `GetOutlineDisplay` | `bool GetOutlineDisplay()` | `0x00405c50` -> `0x00578820`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 107 | `SetOutlineDisplay` | `void SetOutlineDisplay(bool bDisplay)` | `0x00405c60` -> `0x00578830`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 108 | `PrototypeFilterEvent` | `bool PrototypeFilterEvent(Actor prototype, Actor actorSource, int iEvent)` | `0x00405c90` -> `0x00578690`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 109 | `SendMessage` | `void SendMessage(Actor actReceiver, int iMessageCode)` | `0x00405cc0` -> `0x00578d80`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 110 | `SendMessageWithArguments` | `void SendMessageWithArguments(Actor actReceiver, int iMessageCode, int iArgument1, int iArgument2)` | `0x00405cf0` -> `0x00578f20`; 16 bytes / 4 args; EAX cleared: void confirmed | VA comment only |
| 111 | `God` | `Actor God()` | `0x00405d20` -> `0x00579a20`; 0 bytes / 0 args; shared zero sentinel; logical handle retained | VA comment only |
| 112 | `Select` | `bool Select(int selectCode)` | `0x00405d30` -> `0x00578710`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 113 | `Deactivate` | `bool Deactivate(Actor actor)` | `0x00405d60` -> `0x00575640`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 114 | `Activate` | `bool Activate(Actor actor)` | `0x00405d90` -> `0x005756f0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 115 | `SetActionAvailable` | `bool SetActionAvailable(Actor actor, int iAction, bool bAvailable)` | `0x00405dc0` -> `0x00575760`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 116 | `IsActionAvailable` | `bool IsActionAvailable(Actor actor, int iAction)` | `0x00405e00` -> `0x00575870`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 117 | `SetPersistentProperty` | `bool SetPersistentProperty(Actor actor, int iProperty, int iAmount)` | `0x00405e30` -> `0x00572300`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 118 | `GetPersistentProperty` | `int GetPersistentProperty(Actor actor, int iProperty)` | `0x00405e60` -> `0x00571fb0`; 8 bytes / 2 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 119 | `IsAnyCivilianDead` | `bool IsAnyCivilianDead()` | `0x00405e90` -> `0x005761f0`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 120 | `IsAnyEnemyDead` | `bool IsAnyEnemyDead()` | `0x00405ea0` -> `0x00576260`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 121 | `GetOverallEnemyAlert` | `int GetOverallEnemyAlert()` | `0x00405eb0` -> `0x00576a30`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 122 | `GetOverallCivilianAlert` | `int GetOverallCivilianAlert()` | `0x00405ec0` -> `0x00576af0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 123 | `SetAIAlertStatus` | `bool SetAIAlertStatus(Actor actor, int iStatus)` | `0x00405ed0` -> `0x00575af0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 124 | `GetAIAlertStatus` | `int GetAIAlertStatus(Actor actor)` | `0x00405f00` -> `0x00575bf0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 125 | `SetAIState` | `bool SetAIState(Actor actor, int iState)` | `0x00405f20` -> `0x00575c80`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 126 | `GetAIState` | `int GetAIState(Actor actor)` | `0x00405f50` -> `0x00575e20`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 127 | `SetAIAttitude` | `bool SetAIAttitude(Actor actor, int iAttitude)` | `0x00405f70` -> `0x00575ee0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 128 | `GetAIAttitude` | `int GetAIAttitude(Actor actor)` | `0x00405fa0` -> `0x00575f00`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 129 | `SetAILevel` | `bool SetAILevel(Actor actor, int iProperty, int iLevel)` | `0x00405fc0` -> `0x00575f70`; 12 bytes / 3 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 130 | `StareActor` | `void StareActor(Actor actor, Actor actorTarget, bool bTurnSprite)` | `0x00405ff0` -> `0x00575fc0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 131 | `StareLocation` | `void StareLocation(Actor actor, Location locPoint, bool bTurnSprite)` | `0x00406020` -> `0x005760b0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 132 | `AssignPath` | `void AssignPath(Actor actor, Way myWay)` | `0x00406050` -> `0x00576c50`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 133 | `AssignPost` | `void AssignPost(Actor actor, Location location, int iDirection)` | `0x00406080` -> `0x00576cc0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 134 | `LockAI` | `void LockAI(Actor actor, bool bRememberEvents)` | `0x004060b0` -> `0x00576d80`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 135 | `UnlockAI` | `void UnlockAI(Actor actor)` | `0x004060e0` -> `0x00576e00`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 136 | `ForceBattleDecision` | `void ForceBattleDecision(Actor actor, int iDecision)` | `0x00406110` -> `0x00576eb0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 137 | `MakeNoise` | `void MakeNoise(Location location, int iTypeID)` | `0x00406140` -> `0x00571160`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 138 | `Freeze` | `void Freeze(Actor actor, bool bFrozen)` | `0x00406170` -> `0x00576bb0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 139 | `FreezeAll` | `void FreezeAll(bool bFrozen)` | `0x004061a0` -> `0x00576c30`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 140 | `SetPathWalkingStyle` | `void SetPathWalkingStyle(Actor NPC, int i0Walking1Running2Backward)` | `0x004061d0` -> `0x005780d0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 141 | `GetSoldierRank` | `int GetSoldierRank(Actor actor)` | `0x00406200` -> `0x00579a30`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 142 | `IsAnimationActive` | `bool IsAnimationActive(Actor actor)` | `0x00406220` -> `0x00570d00`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 143 | `SetAnimationState` | `bool SetAnimationState(Actor actor, bool bState)` | `0x00406250` -> `0x00570d80`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 144 | `IsPatchApplied` | `bool IsPatchApplied(Patch patch)` | `0x00406280` -> `0x00570e20`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 145 | `ApplyPatch` | `bool ApplyPatch(Patch patch)` | `0x004062b0` -> `0x00570e30`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 146 | `ResetPatch` | `bool ResetPatch(Patch patch)` | `0x004062e0` -> `0x00570e50`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 147 | `SuspendAllSoundSources` | `bool SuspendAllSoundSources()` | `0x00406310` -> `0x00575510`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 148 | `ResumeAllSoundSources` | `bool ResumeAllSoundSources()` | `0x00406320` -> `0x00575530`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 149 | `ActivateSoundSource` | `bool ActivateSoundSource(SoundSource source)` | `0x00406330` -> `0x00575560`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 150 | `DeactivateSoundSource` | `bool DeactivateSoundSource(SoundSource source)` | `0x00406360` -> `0x00575590`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 151 | `DestroySoundSource` | `bool DestroySoundSource(SoundSource source)` | `0x00406390` -> `0x005755c0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 152 | `CleanFromHisBuildingBeforeTeleport` | `bool CleanFromHisBuildingBeforeTeleport(Actor actor)` | `0x004063c0` -> `0x00577150`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 153 | `CleanFromScriptZoneBeforeTeleport` | `bool CleanFromScriptZoneBeforeTeleport(Actor actor, Location cestLaZone)` | `0x004063f0` -> `0x00577220`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 154 | `AddToScriptZoneAfterTeleport` | `bool AddToScriptZoneAfterTeleport(Actor actor, Location cestLaZone)` | `0x00406420` -> `0x00577390`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 155 | `SetCorpseExistsInBuilding` | `void SetCorpseExistsInBuilding(Actor pActor)` | `0x00406450` -> `0x00578c50`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 156 | `PutActorInBuilding` | `void PutActorInBuilding(Actor actor, Building building)` | `0x00406480` -> `0x005781f0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 157 | `SetBuildingActive` | `void SetBuildingActive(Building building, bool bActive)` | `0x004064b0` -> `0x005782a0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 158 | `GetAnyActorInsideBuilding` | `Actor GetAnyActorInsideBuilding(Building building)` | `0x004064e0` -> `0x00571ea0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 159 | `NoWhere` | `Location NoWhere()` | `0x00405d20` -> `0x00579a20`; 0 bytes / 0 args; shared zero sentinel; logical handle retained | VA comment only |
| 160 | `GetDistance` | `int GetDistance(Location here, Location there)` | `0x00406500` -> `0x00571b80`; 8 bytes / 2 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 161 | `Rand` | `int Rand(int iMaximum)` | `0x00406530` -> `0x00578680`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 162 | `PrintConsole` | `void PrintConsole(int iValue)` | `0x00406550` -> `0x00579f10`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 163 | `GetSizeOfMissionTeam` | `int GetSizeOfMissionTeam()` | `0x00406580` -> `0x005791d0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 164 | `GetPCFromMissionTeam` | `Actor GetPCFromMissionTeam(int ulPC)` | `0x00406590` -> `0x005791f0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 165 | `AddPCToMissionTeam` | `void AddPCToMissionTeam(Actor actor)` | `0x004065b0` -> `0x00579210`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 166 | `RemovePCFromMissionTeam` | `void RemovePCFromMissionTeam(Actor actor)` | `0x004065e0` -> `0x00579280`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 167 | `GetNumberOfObligatoryPCsInMissionTeam` | `int GetNumberOfObligatoryPCsInMissionTeam()` | `0x00406610` -> `0x005792d0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 168 | `GetObligatoryPCFromMissionTeam` | `Actor GetObligatoryPCFromMissionTeam(int ulPC)` | `0x00406620` -> `0x00579350`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 169 | `IsPCObligatoryInMissionTeam` | `bool IsPCObligatoryInMissionTeam(Actor actor)` | `0x00406640` -> `0x005793a0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 170 | `IsMissionTeamValid` | `bool IsMissionTeamValid()` | `0x00406670` -> `0x005793e0`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 171 | `GetLastPlayedMission` | `int GetLastPlayedMission()` | `0x00406680` -> `0x005793f0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 172 | `GetNextPlayedMission` | `int GetNextPlayedMission()` | `0x00406690` -> `0x00579410`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 173 | `IsMenToBlazonConversionMode` | `bool IsMenToBlazonConversionMode()` | `0x004066a0` -> `0x005795b0`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 174 | `GetNumberOfBeamMes` | `int GetNumberOfBeamMes()` | `0x004066b0` -> `0x00579300`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 175 | `MoveBeamMe` | `void MoveBeamMe(int iIndex, Location pLocation)` | `0x004066c0` -> `0x00579000`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 176 | `SetCompanyNumber` | `void SetCompanyNumber(Actor pActor, int iNumber)` | `0x004066f0` -> `0x005790b0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 177 | `SetAlwaysAttentive` | `void SetAlwaysAttentive(Actor actor, bool bYes)` | `0x00406720` -> `0x005790f0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 178 | `WinBlazon` | `void WinBlazon(Actor blazon)` | `0x00406750` -> `0x005795c0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 179 | `LoseBlazon` | `void LoseBlazon(Actor blazon)` | `0x00406780` -> `0x005796d0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 180 | `SetInvisible` | `void SetInvisible(Actor actor, bool bHollow)` | `0x004067b0` -> `0x00579760`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 181 | `IsInvisible` | `bool IsInvisible(Actor actor)` | `0x004067e0` -> `0x005797c0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 182 | `IsDoorLockedPC` | `bool IsDoorLockedPC(Door door)` | `0x00406810` -> `0x00579810`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 183 | `IsDoorUnlockable` | `bool IsDoorUnlockable(Door door)` | `0x00406840` -> `0x00579820`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 184 | `IsDoorLockedNPCCivilian` | `bool IsDoorLockedNPCCivilian(Door door)` | `0x00406870` -> `0x00579830`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 185 | `IsDoorLockedNPCVillain` | `bool IsDoorLockedNPCVillain(Door door)` | `0x004068a0` -> `0x00579840`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 186 | `SetDoorLockedPC` | `void SetDoorLockedPC(Door door, bool bState)` | `0x004068d0` -> `0x00579850`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 187 | `SetDoorUnlockable` | `void SetDoorUnlockable(Door door, bool bState)` | `0x00406900` -> `0x00579870`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 188 | `SetDoorLockedNPCCivilian` | `void SetDoorLockedNPCCivilian(Door door, bool bState)` | `0x00406930` -> `0x00579880`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 189 | `SetDoorLockedNPCVillain` | `void SetDoorLockedNPCVillain(Door door, bool bState)` | `0x00406960` -> `0x005798a0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 190 | `SetDoorSpecialAutorisation` | `void SetDoorSpecialAutorisation(Door door, Actor actor, bool bDirect)` | `0x00406990` -> `0x005786f0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 191 | `ActivateDoorMouseSector` | `void ActivateDoorMouseSector(bool bActive, Door door)` | `0x004069c0` -> `0x005787f0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 192 | `ThisScroll` | `Actor ThisScroll()` | `0x004069f0` -> `0x005798c0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 193 | `GetScrollStatus` | `int GetScrollStatus(Actor scroll)` | `0x00406a00` -> `0x005798f0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 194 | `SetScrollStatus` | `void SetScrollStatus(Actor scroll, int iStatus)` | `0x00406a20` -> `0x00579950`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 195 | `GetCustomCampaignValue` | `int GetCustomCampaignValue(int iIndex)` | `0x00406a50` -> `0x00579430`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 196 | `SetCustomCampaignValue` | `void SetCustomCampaignValue(int iIndex, int iValue)` | `0x00406a70` -> `0x00579470`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 197 | `GetCustomNPCValue` | `int GetCustomNPCValue(Actor actor, int iIndex)` | `0x00406aa0` -> `0x005794b0`; 8 bytes / 2 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 198 | `SetCustomNPCValue` | `void SetCustomNPCValue(Actor actor, int iIndex, int iValue)` | `0x00406ad0` -> `0x00579520`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 199 | `RegisterAsProductionSector` | `void RegisterAsProductionSector(int iType, Location sector, int iProductionSpeed)` | `0x00406b00` -> `0x005799d0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 200 | `AddProductionPoint` | `void AddProductionPoint(int iType, Location point)` | `0x00406b30` -> `0x00579a00`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 201 | `GetActorForBeamMe` | `Actor GetActorForBeamMe(int iIndex)` | `0x00406b60` -> `0x00571610`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 202 | `DisplayPopupText` | `void DisplayPopupText(int iPopupTextID)` | `0x00406b80` -> `0x00579f30`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 203 | `RecordDisplayPopupText` | `void RecordDisplayPopupText(int iPopupTextID)` | `0x00406bb0` -> `0x00579fa0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 204 | `GetNumberOfActorsInSector` | `int GetNumberOfActorsInSector(Location loc)` | `0x00406be0` -> `0x0057a060`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 205 | `GetActorInSector` | `Actor GetActorInSector(Location loc, int iIndex)` | `0x00406c00` -> `0x0057a0a0`; 8 bytes / 2 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 206 | `BitwiseAnd` | `int BitwiseAnd(int i, int j)` | `0x00406c30` -> `0x0057a280`; 8 bytes / 2 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 207 | `BitwiseOr` | `int BitwiseOr(int i, int j)` | `0x00406c60` -> `0x0057a290`; 8 bytes / 2 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 208 | `BitwiseXor` | `int BitwiseXor(int i, int j)` | `0x00406c90` -> `0x0057a2a0`; 8 bytes / 2 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 209 | `HasPCAction` | `bool HasPCAction(Actor actPC, int iActionCode)` | `0x00406cc0` -> `0x0057a2b0`; 8 bytes / 2 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 210 | `HasAnyPCAction` | `bool HasAnyPCAction(int iActionCode)` | `0x00406cf0` -> `0x0057a4c0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 211 | `GetRobin` | `Actor GetRobin()` | `0x00406d20` -> `0x0057a8e0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 212 | `RecordMoveNear` | `bool RecordMoveNear(Actor actor, Location location, int iStyle, int iTolerance)` | `0x00406d30` -> `0x005743a0`; 16 bytes / 4 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 213 | `ComputeLocationBetween` | `Location ComputeLocationBetween(Location locA, Location locB, float fLambdaBetweenZeroAndOne)` | `0x00406d70` -> `0x00571c60`; 12 bytes / 3 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 214 | `DeclareAsCombatTrainer` | `void DeclareAsCombatTrainer(Actor actor)` | `0x00406da0` -> `0x00579160`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 215 | `GetRelic` | `Actor GetRelic(int iID)` | `0x00406dd0` -> `0x0057a950`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 216 | `GetNumberOfPCs` | `int GetNumberOfPCs()` | `0x00406df0` -> `0x0057aa20`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 217 | `GetPC` | `Actor GetPC(int i)` | `0x00406e00` -> `0x0057aa50`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 218 | `AddAsSubordinate` | `void AddAsSubordinate(Actor actChief, Actor actSubordinate)` | `0x00406e20` -> `0x0057aa70`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 219 | `RemoveAllSubordinates` | `void RemoveAllSubordinates(Actor actChief)` | `0x00406e50` -> `0x0057acc0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 220 | `SwitchToAlertPath` | `void SwitchToAlertPath(Actor actSoldier)` | `0x00406e80` -> `0x0057ad30`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 221 | `IsActorRider` | `bool IsActorRider(Actor actWhoever)` | `0x00406eb0` -> `0x0057ad90`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 222 | `IsUnblipped` | `bool IsUnblipped(Actor actWhoever)` | `0x00406ee0` -> `0x00570ec0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 223 | `IsBlazonWon` | `bool IsBlazonWon(Actor blazon)` | `0x00406f10` -> `0x00579730`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 224 | `AddRepulsivePoint` | `int AddRepulsivePoint(Location location, float fRadius, float fActionRadius, int iFlags)` | `0x00406f40` -> `0x0057adf0`; 16 bytes / 4 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 225 | `SetViewRadius` | `void SetViewRadius(int iRadius)` | `0x00406f70` -> `0x0057ae60`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 226 | `RecordFreezeAll` | `void RecordFreezeAll(bool bFreeze)` | `0x00406fa0` -> `0x00577df0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 227 | `DeleteRepulsivePoint` | `void DeleteRepulsivePoint(int iID)` | `0x00406fd0` -> `0x0057ae40`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 228 | `SetNPCEmoticon` | `void SetNPCEmoticon(Actor actNPC, int iEmoticonType, int iTime)` | `0x00407000` -> `0x0057aed0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 229 | `ConfiscateMoney` | `void ConfiscateMoney(Actor actCapitalist)` | `0x00407030` -> `0x005729a0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 230 | `AreAllPCsInside` | `bool AreAllPCsInside(Location location)` | `0x00407060` -> `0x00571e30`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 231 | `AreAllEnemiesInsideHS` | `bool AreAllEnemiesInsideHS(Location locZone)` | `0x00407090` -> `0x00571ef0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 232 | `AddPCToGang` | `void AddPCToGang(Actor actor)` | `0x004070c0` -> `0x0057afe0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 233 | `AttachScrollToNPC` | `void AttachScrollToNPC(Actor actNPC, Actor scroll)` | `0x004070f0` -> `0x005785f0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 234 | `AreAllBlazonsWon` | `bool AreAllBlazonsWon()` | `0x00407120` -> `0x00579690`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 235 | `IsBonusItemPickedUp` | `bool IsBonusItemPickedUp(Actor actItem)` | `0x00407130` -> `0x0057b080`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 236 | `GetRansomMoney` | `int GetRansomMoney()` | `0x00407160` -> `0x0057b0f0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 237 | `SetRansomMoney` | `void SetRansomMoney(int iRansomMoneyAmount)` | `0x00407170` -> `0x0057b120`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 238 | `GetDifficultyLevel` | `int GetDifficultyLevel()` | `0x004071a0` -> `0x0057b150`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 239 | `DisplaySherwoodReport` | `void DisplaySherwoodReport()` | `0x004071b0` -> `0x0057b160`; 0 bytes / 0 args; EAX cleared: void confirmed | VA comment only |
| 240 | `IsActorActive` | `bool IsActorActive(Actor actor)` | `0x004071c0` -> `0x00570d40`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 241 | `AddFarmerToGang` | `void AddFarmerToGang(int iType, int iExperienceSword, int iExperienceBow)` | `0x004071f0` -> `0x0057b2b0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 242 | `SetExperiences` | `void SetExperiences(Actor actor, int iExperienceSword, int iExperienceBow)` | `0x00407220` -> `0x0057b2f0`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
| 243 | `RecordUnBlip` | `bool RecordUnBlip(Actor pActor)` | `0x00407250` -> `0x00575290`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 244 | `SetPatchAnimationActive` | `void SetPatchAnimationActive(Patch patch, bool bActive)` | `0x00407280` -> `0x0057b350`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 245 | `GetNumberOfPCsAlive` | `int GetNumberOfPCsAlive()` | `0x004072b0` -> `0x0057b370`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 246 | `AreAllPCsAliveInside` | `bool AreAllPCsAliveInside(Location location)` | `0x004072c0` -> `0x0057b3d0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 247 | `TransformHandleTargetToTakeTarget` | `void TransformHandleTargetToTakeTarget(Actor actTarget)` | `0x004072f0` -> `0x0057b450`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 248 | `IsPCSelected` | `bool IsPCSelected(Actor actPC)` | `0x00407320` -> `0x0057b4f0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 249 | `GetNumberOfSelectedPCs` | `int GetNumberOfSelectedPCs()` | `0x00407350` -> `0x0057b5e0`; 0 bytes / 0 args; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 250 | `GetSelectedPC` | `Actor GetSelectedPC(int iIndex)` | `0x00407360` -> `0x0057b5f0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 251 | `PlayTrapJingle` | `void PlayTrapJingle()` | `0x00407380` -> `0x0057b780`; 0 bytes / 0 args; EAX cleared: void confirmed | VA comment only |
| 252 | `MakePCCrouched` | `void MakePCCrouched(Actor actPC)` | `0x00407390` -> `0x0057b7a0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 253 | `HasAnyPCActionWhoIsInThisLevelOrCouldMaybeComeFromSherwood` | `bool HasAnyPCActionWhoIsInThisLevelOrCouldMaybeComeFromSherwood(int iActionCode)` | `0x004073c0` -> `0x0057b800`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 254 | `LockPatch` | `void LockPatch(Patch patch, bool bLocked)` | `0x004073f0` -> `0x0057ba50`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 255 | `HasAnyActivePCAction` | `bool HasAnyActivePCAction(int iActionCode)` | `0x00407420` -> `0x0057a6d0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 256 | `GetPCType` | `int GetPCType(Actor actPC)` | `0x00407450` -> `0x0057ba60`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 257 | `SelectActorPC` | `void SelectActorPC(Actor actPCOrGodForAllPCs, bool bSelectOrUnselect)` | `0x00407470` -> `0x0057bdb0`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 258 | `HasAnyActionSelected` | `bool HasAnyActionSelected(Actor actPC)` | `0x004074a0` -> `0x0057bed0`; 4 bytes / 1 arg; EAX masked to low byte: bool-like confirmed | VA comment only |
| 259 | `GetActorActionState` | `int GetActorActionState(Actor actor)` | `0x004074d0` -> `0x005766f0`; 4 bytes / 1 arg; EAX passthrough: word return compatible; logical type retained | VA comment only |
| 260 | `SetActorActionState` | `void SetActorActionState(Actor actor, int iActionState)` | `0x004074f0` -> `0x00576830`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 261 | `SecretAgentsAreBackInSherwood` | `bool SecretAgentsAreBackInSherwood()` | `0x00407520` -> `0x0057bfe0`; 0 bytes / 0 args; EAX masked to low byte: bool-like confirmed | VA comment only |
| 262 | `FadeToBlack` | `void FadeToBlack(int iSpeed)` | `0x00407530` -> `0x0057bff0`; 4 bytes / 1 arg; EAX cleared: void confirmed | VA comment only |
| 263 | `LinkTargetToFX` | `void LinkTargetToFX(Actor actTarget, Actor actFX)` | `0x00407560` -> `0x0057c500`; 8 bytes / 2 args; EAX cleared: void confirmed | VA comment only |
| 264 | `ForbidNPCRemark` | `void ForbidNPCRemark(Actor actNPC, int iRemark, bool bTrueMeansForbidFalseMeansAllow)` | `0x00407590` -> `0x00573010`; 12 bytes / 3 args; EAX cleared: void confirmed | VA comment only |
