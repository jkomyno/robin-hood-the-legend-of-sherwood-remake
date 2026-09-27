# Villain PC mod: three-ability proposals

This document turns the evidence collected in
`docs/VILLAIN_PC_RESEARCH.md` into playable kits for Prince John, Guy of
Gisbourne, Longchamp, the Sheriff of Nottingham, and Scathlock.

These are design proposals, not claims about mechanics already present in the
shipped game. Each character has exactly three selectable actions, matching the
normal PC profiles.

## Baseline from the normal roster

The hackable profile data gives every principal PC three actions:

| PC | Action 1 | Action 2 | Action 3 |
| --- | --- | --- | --- |
| Robin | Bow | Hit | Purse |
| Little John | Whistle | Hit Hard | Help to Climb |
| Friar Tuck | Wasp Nest | Ale | Guzzle |
| Stuteley | Net | Apple | Beggar |
| Will Scarlet | Stone | Strangle | Big Shield |
| Marian | Bow | Heal | Listen |

The game mixes weapons, consumable distractions, combat stances, disguises,
support actions, and traversal tools in the same three slots. The villain kits
follow that model rather than giving everyone three combat powers.

For this proposal, ordinary movement and each character's basic melee attack
are baseline controls rather than additional abilities. Guy, Longchamp, the
Sheriff, and Scathlock retain their shipped sword fighting and 250-life elite
profile as their common chassis. Prince John retains the civilian, noncombatant
chassis established by his data. This prevents the four knight kits from all
spending one slot on an identical sword action.

## Recommended kits at a glance

| Character | Action 1 | Action 2 | Action 3 | Tactical identity |
| --- | --- | --- | --- | --- |
| Prince John | Royal Decree | Bleed Them Dry | Call Reinforcements | Noncombat commander and resource controller |
| Guy | On Guard, Yokel! | Call the Guard! | Plate Advance | Aggressive duellist who hides behind rank and armour |
| Longchamp | Join Us | Safe Conduct | Like True Knights | Infiltrator, converter, and counter-duellist |
| Sheriff | Writ of Arrest | Informer Network | Silver Arrow Trap | Hunter who reveals, marks, and captures targets |
| Scathlock | Crush Them! | Exemplary Punishment | Nettle, Honey, and Bees | Army leader who converts brutality into morale control |

## Prince John — command without personal courage

John should be the roster's most indirect character. His strength is the legal
fiction that he is the rightful ruler and the armed hierarchy willing to act
on it. If isolated, he should be markedly weaker than every other villain.

### 1. Royal Decree

Target a non-VIP soldier. The soldier stops, salutes, and temporarily changes
allegiance to John. John may control only one decreed soldier at a time;
decreeing another releases the first. Officers and named characters resist.

- **Use:** Steal a useful enemy from a patrol, open a guarded route, or acquire
  a temporary bodyguard.
- **Counterplay:** Requires John to approach within speaking range and complete
  the order without being interrupted. High-courage soldiers obey for less
  time; officers merely hesitate.
- **Evidence:** John is the hierarchy root in the Derby council, issues direct
  orders to every other villain, confiscates land by decree, and repeatedly
  insists on his legitimate authority.
- **Implementation:** New allegiance/command action, but it can reuse the AI's
  existing superior/subordinate relationships and salute/remark animations.

### 2. Bleed Them Dry

Throw a royal tax purse onto the ground. Greed-susceptible soldiers and
civilians abandon their current task to collect it. Unlike Robin's charitable
purse, the tax purse remains a contested pile for several seconds, bunching
targets together and slowing the eventual collector under its weight.

- **Use:** Break formations, empty a doorway, or prepare a clustered group for
  an ally's area effect.
- **Limit:** Six purses per mission, replenished by the existing purse bonus.
- **Evidence:** John's regime is funded by confiscation and oppressive tax;
  the Sheriff promises to “bleed these yokels dry.” The existing game already
  represents gold as a soldier lure.
- **Implementation:** A low-risk variant of the existing Purse projectile and
  money-seeking AI.

### 3. Call Reinforcements

Spend a royal seal to summon two ordinary soldiers from a valid map entrance.
They remain allied until defeated but cannot complete objectives or leave the
mission as rescued units.

- **Use:** Replace John's lack of direct combat, hold a chokepoint, or create a
  distraction elsewhere on the map.
- **Limit:** Three seals per mission; no summon if the chosen entrance is
  visible to an enemy or cannot path to John.
- **Evidence:** John answers every setback with recruitment, troops, engineers,
  convoys, and reinforcements, and delegates all physical violence.
- **Implementation:** New action and UI resource. Actor creation and scripted
  reinforcement entry already exist in mission logic, so this should use the
  same spawn and path validation rather than inventing a second system.

### Intended rhythm

John converts one valuable soldier, scatters a formation with tax money, then
spends limited seals when he needs actual force. He is powerful with preparation
and vulnerable when rushed—the correct expression of a man who claims a crown
but never draws a sword in the campaign.

## Guy of Gisbourne — privileged bully in plate

Guy should be the most direct offensive knight, but his best play should still
involve singling out a victim and ensuring other men absorb the danger first.

### 1. On Guard, Yokel!

Challenge one upright human enemy. Guy closes rapidly and delivers a powerful
opening sword combination. If the target has no nearby allies, the combination
deals increased posture damage and is difficult to parry; it loses the bonus
when Guy tries it into a crowd.

- **Use:** Delete an isolated sentry or begin a boss duel on favourable terms.
- **Limit:** Unlimited, but only one challenge may be active and a missed or
  parried opener leaves Guy briefly exposed.
- **Evidence:** His cathedral line personally challenges Robin, promises
  Robin's head as a wedding gift, and contrasts with his refusal to duel when
  Robin confronts him amid the Lincoln garrison.
- **Implementation:** New targeted sword action built on Hit Hard, charge
  movement, and existing sword-combination orders.

### 2. Call the Guard!

Guy calls up to three nearby allied soldiers to converge on his current target.
While they respond, Guy may disengage without their target immediately
following him. The action creates no soldiers; it exploits forces already on
the map.

- **Use:** Turn a bad duel into a group fight, pull guards away from their
  posts, or screen a retreat.
- **Limit:** No effect without idle or lower-ranked allies in hearing range.
- **Evidence:** At Lincoln he refuses Robin's challenge, orders Parker to fetch
  the guard, and escapes through a secret passage. The campaign calls him
  John's sly right-hand man rather than a solitary warrior.
- **Implementation:** New command action using existing gather, hear-sound,
  attack-target, and subordinate AI paths. It should use Guy's `Special` or
  gathering animation rather than require a new sprite family.

### 3. Plate Advance

Adopt a slow, guarded advance. Guy becomes highly resistant to frontal arrows,
stones, and knockdown, but cannot sprint and remains vulnerable from behind.
Attacking or selecting the action again drops the stance.

- **Use:** Cross exposed streets, force an archer from position, or approach a
  challenge safely.
- **Limit:** Directional protection only; no blanket recreation of NPC VIP
  immunity.
- **Evidence:** Guy alone has Plate armour in the shipped profiles. His portrait
  and combat sprite present him as the heaviest of the four knights.
- **Implementation:** A character-specific Big Shield variant using armour
  facing instead of a carried shield.

### Intended rhythm

Guy advances through missiles, isolates and overwhelms one target, and calls
ordinary guards when the fight stops favouring him. He is formidable but never
honourable unless honour gives him an advantage.

## Longchamp — diplomat, infiltrator, and formal duellist

Longchamp should win by controlling allegiance and engagement rules. He is the
least brutish villain and the best suited to missions where open combat is a
failure rather than the goal.

### 1. Join Us

Attempt to persuade a non-VIP human target. A civilian becomes cooperative and
ignores alarms; a low-courage soldier temporarily changes allegiance; a target
that resists is left arguing and stationary for a shorter period. Named
characters and VIPs always resist conversion.

- **Use:** Neutralize a witness, borrow a guard, or hold one member of a patrol
  out of a fight.
- **Limit:** Three letters of patronage per mission. Success scales inversely
  with courage and fails if the target is already fighting Longchamp.
- **Evidence:** Longchamp first tries to persuade Robin that Richard has
  abandoned England and explicitly asks him to join John's cause. He is the
  court's political advocate and schemer.
- **Implementation:** Shares the core allegiance work required by Royal Decree,
  but uses a resistance check and consumable instead of rank-based authority.

### 2. Safe Conduct

Display John's safe-conduct and enter a diplomatic posture. Ordinary soldiers
treat Longchamp as neutral and allow him through guarded routes. Running,
drawing his sword, touching an objective, entering a restricted inner zone, or
being recognized by an officer breaks the posture and raises the alarm.

- **Use:** Reconnoitre, cross a checkpoint, or reach the correct target before
  beginning a fight.
- **Limit:** Unlimited toggle, but scrutiny increases each time the same patrol
  sees him use it.
- **Evidence:** John entrusts Longchamp with a safe-conduct for reaching Leopold;
  after Longchamp dies, Allan's disguise and those credentials allow the plan
  to continue.
- **Implementation:** Reuse the Beggar disguise state's detection suppression,
  with officer proximity and hostile-action break conditions.

### 3. Like True Knights

Enter a formal guard against one selected melee opponent. Longchamp automatically
attempts one strong parry; a successful parry enables an immediate riposte and
briefly prevents other ordinary soldiers from joining the duel. A feint,
missile, or attack from another direction bypasses the effect.

- **Use:** Defeat a superior melee fighter through timing rather than raw
  aggression.
- **Limit:** Unlimited but commits Longchamp to the selected opponent until the
  parry resolves or he cancels it.
- **Evidence:** He refuses surrender and asks Robin to settle their disagreement
  “like true knights,” followed by the formal “on guard.”
- **Implementation:** New counter stance using existing parry, swordfight, and
  Robin-only duel-zone behaviour as references.

### Intended rhythm

Longchamp enters under papers, talks one obstacle out of the way, and only then
accepts a controlled duel. His kit should reward composure and route planning,
not charging into groups.

## Sheriff of Nottingham — law as a hunting weapon

The Sheriff should feel like the campaign's persistent antagonist: he knows
where people are, declares whom the law should seize, and turns obvious prizes
into traps.

### 1. Writ of Arrest

Mark one visible human as wanted. Nearby allied soldiers prioritize that target,
gain detection persistence against it, and try to knock it unconscious rather
than execute it. The first soldier to reach a downed target automatically ties
and arrests it.

- **Use:** Focus a dangerous opponent, stop an escaping objective, or capture a
  useful prisoner without personally entering the fight.
- **Limit:** Only one active writ. Named VIPs can be marked for tracking and
  focus fire but not automatically tied.
- **Evidence:** Arrests, public executions, informants, prisoner display, and
  the capture of Robin and his companions recur throughout the Sheriff's plot.
- **Implementation:** New target mark layered over existing AI focus-target,
  nonlethal knockdown, Tie, and prisoner states.

### 2. Informer Network

Place a paid informer at a clicked accessible position. After a short delay,
the informer reveals nearby human actors, their facing, and their immediate
patrol routes through fog of war. The informer disappears if approached by an
enemy.

- **Use:** Inspect a courtyard before entry, locate a mission target, or watch
  a patrol intersection while operating elsewhere.
- **Limit:** Six payments per mission; one active informer at a time.
- **Evidence:** The Sheriff repeatedly uses informers, bribery, planted bandits,
  searches, and intelligence to find and trap the outlaws.
- **Implementation:** A remote, localized Listen variant. It can reuse Listen's
  information overlay and the Beggar civilian presentation, but needs placement
  and remote ownership logic.

### 3. Silver Arrow Trap

Place a conspicuous prize on the ground. The first eligible enemy who approaches
is briefly held by a hidden net while nearby allied soldiers receive an attack
order against the trapped target. Cautious/high-intelligence actors may notice
the trap before triggering it.

- **Use:** Protect a passage, split a patrol, or prepare an arrest.
- **Limit:** Three prizes per mission. The trap may be disarmed from behind or
  destroyed by a projectile.
- **Evidence:** The Silver Arrow tournament is an attractive public prize built
  specifically to expose and capture Robin. The Sheriff also relies on traps
  and prepared ambushes throughout the campaign.
- **Implementation:** Compose the existing lure-seeking, Net, trap-detection,
  and allied alert behaviours around a new prize object.

### Intended rhythm

The Sheriff buys information, chooses one quarry, then prepares the place of
capture. He remains a capable sword fighter, but his actions are about making
sure a supposedly fair fight was decided before it started.

## Scathlock — fear, discipline, and grotesque punishment

Scathlock should be the strongest group-combat leader. His individual sword
skill is substantial, but his distinctive contribution is keeping common
soldiers aggressive and breaking the other side's nerve.

### 1. Crush Them!

Plant Scathlock's standard and issue an attack order. Allied ordinary soldiers
within its radius temporarily gain courage, faster attack commitment, and
resistance to fear or retreat. They converge on Scathlock's selected target if
one exists.

- **Use:** Turn a hesitant garrison into an assault force or stabilize allies
  after casualties.
- **Limit:** Three standards per mission; only one may be active, and enemies
  can tear it down.
- **Evidence:** Scathlock repeatedly volunteers his men to crush royalist
  opposition, is called one of John's best generals, and his death causes a
  major loss of organization and morale.
- **Implementation:** New destructible aura object using existing courage,
  pride, gather, and attack scheduling.

### 2. Exemplary Punishment

Perform a contextual execution on an unconscious or tied enemy. Nearby enemies
lose courage and may recoil or flee, while nearby allied soldiers immediately
rally. Named characters suffer the morale shock but cannot be executed by the
shortcut.

- **Use:** Convert a defeated sentry into area control during a larger fight.
- **Limit:** Requires a helpless target and a long, interruptible animation;
  using it is loud and destroys any stealth state.
- **Evidence:** Scathlock promises exemplary punishment, boasts about his
  executioner, tortures prisoners over trivial slights, and rules through
  highly theatrical cruelty.
- **Implementation:** Reuse Execute and witness-event plumbing, adding opposing
  courage effects. The full sequence should never defensively succeed without
  a valid victim.

### 3. Nettle, Honey, and Bees

Throw a beehive that releases a broad but short-lived swarm. Ordinary targets
panic and scatter; anyone already affected by Exemplary Punishment suffers a
longer fear response. Armoured or exceptionally courageous targets recover
quickly.

- **Use:** Break up formations before Scathlock and his troops charge.
- **Limit:** Six hives per mission, replenished by Wasp Nest bonuses.
- **Evidence:** Scathlock's own decree specifies nettle whipping, honey, and
  exposure to his beehives as punishment for disrespecting his name.
- **Implementation:** A Scathlock-specific Wasp Nest variant with a wider,
  shorter panic effect. It deliberately does not reproduce blanket VIP wasp
  immunity for playable characters.

### Intended rhythm

Scathlock opens by scattering the opposition, plants his standard to drive his
men forward, and turns a fallen enemy into a fear cascade. He is dangerous in a
crowd and much less flexible when separated from troops.

## Why “Winnie” is not one of Scathlock's buttons

Winnie is excellent characterization but poor as a voluntary ability: in the
campaign it is leverage *against* Scathlock, and revealing it makes his own men
mock him and lose morale. Turning it into a beneficial button would reverse the
evidence.

It should instead be a character-specific vulnerability or mission modifier.
If an enemy discovers Winnie, Scathlock's standard is disabled and nearby allies
lose courage until he recovers the possession or silences the witness. This is
not counted as a fourth ability.

## Balance relationships

- **John** has the best access to expendable bodies and the weakest personal
  defence.
- **Guy** has the strongest immediate single-target pressure and the least
  utility when no guards or isolated targets are available.
- **Longchamp** has the best infiltration and soft control but limited answers
  to groups after his cover breaks.
- **The Sheriff** has the best information and capture setup but needs time and
  map control.
- **Scathlock** dominates group engagements but depends heavily on nearby
  soldiers and highly visible preparations.

No playable villain should inherit the original NPC VIP package wholesale.
Complete immunity to arrows, stones, nets, wasps, strangling, and distractions
would flatten the roster and remove counterplay. Guy's directional plate guard,
Longchamp's formal parry, and the others' indirect protections translate the
elite fantasy into narrower, readable mechanics.

## Alternate ability pool

The recommended trios above are the most cohesive kits, not the only defensible
ones. The following researched alternatives give each villain a pool of seven
candidate actions in total. Each may replace one recommended action; the
suggested swap identifies the cleanest substitution without leaving a major
hole in the kit.

### Prince John alternatives

#### Crown Jewels

Place a piece of the royal treasure as an exceptionally powerful lure. Several
greed-susceptible actors compete over it, and John may reclaim it if nobody has
escaped with it. If it is stolen, that charge is lost for the mission.

- **Best swap:** Bleed Them Dry, for a riskier and more theatrical lure.
- **Evidence:** John assembles the Crown Jewels for his planned coronation and
  specifically secures the Royal Sceptre.
- **Mechanical direction:** Reusable purse object with a retrieval state and a
  much larger attraction value.

#### Act of Confiscation

Target a civilian, tied prisoner, or unconscious enemy and seize one compatible
consumable from them. If they carry nothing, John takes money that contributes
toward replenishing a royal seal.

- **Best swap:** Bleed Them Dry, for an economy action with less crowd control.
- **Evidence:** John confiscates Godwin's estates, extracts wealth through tax,
  and treats other people's property as his to redistribute.
- **Mechanical direction:** Search/loot interaction with a character-specific
  resource conversion table.

#### The Regent Is Untouchable

Adopt a surrender posture. Ordinary enemies hesitate and attempt to arrest John
instead of attacking him, buying time for allies to intervene. Any command,
theft, or attempted escape immediately ends the protection; named enemies and
VIPs are not fooled.

- **Best swap:** Royal Decree, for defensive control instead of conversion.
- **Evidence:** John survives defeat by surrendering and invoking his status;
  his shipped actor is a civilian VIP protected by staging rather than combat.
- **Mechanical direction:** A constrained Beggar-like posture that changes
  hostile response from damage to capture.

#### Levy the County

Choose a map entrance and requisition a mixed patrol—one officer and two common
soldiers—which arrives after a long warning delay. Unlike Call Reinforcements,
the levy is stronger but can be used only once and raises the entire map's
alertness when it enters.

- **Best swap:** Call Reinforcements, for one strategic commitment instead of
  several small summons.
- **Evidence:** John repeatedly responds to resistance with county-wide
  recruitment, new taxes, troop musters, and military campaigns.
- **Mechanical direction:** Existing scripted reinforcement entry plus a global
  alert cost.

### Guy alternatives

#### Secret Passage

Mark an out-of-sight safe position while Guy is unobserved. Once later in the
mission, activate the action to make Guy automatically disengage and sprint
toward that position along a valid path. He gains knockdown resistance while
retreating but cannot attack, and the action fails rather than teleporting him
through blocked geometry.

- **Best swap:** Call the Guard!, for a self-contained escape tool.
- **Evidence:** Guy refuses the first duel at Lincoln, calls the guard, and
  escapes through a secret passage staged explicitly by the mission script.
- **Mechanical direction:** Stored navigation target, forced movement, and a
  temporary disengage rule—never an unexplained teleport.

#### Sly Right-Hand

Guy's next sword attack from outside the target's view becomes a vicious
opening strike with increased knockdown. It provides no bonus in an announced
duel or against an actor already focused on him.

- **Best swap:** On Guard, Yokel!, exchanging honourable isolation pressure for
  an ambush opener.
- **Evidence:** Campaign text calls Guy John's sly right-hand man, while his
  behaviour consistently favours advantage over fairness.
- **Mechanical direction:** Hit Hard gated by target facing and detection state.

#### Wedding Gift

Mark one enemy as Guy's promised trophy. Defeating that target restores some of
Guy's posture and briefly improves allied morale, but failure to finish the
target before the mark expires lowers Guy's own attack commitment.

- **Best swap:** On Guard, Yokel!, for a longer hunt rather than an opening
  combination.
- **Evidence:** Guy promises Robin's head to Marian as a wedding gift and turns
  the duel into a public claim of possession and status.
- **Mechanical direction:** Timed target mark with on-defeat reward and on-expiry
  penalty.

#### Rank Has Its Privileges

Redirect the next non-area projectile or melee engagement aimed at Guy onto a
nearby ordinary allied soldier. The soldier must stand between Guy and the
threat and have time to react; the action cannot redirect explosions, traps, or
attacks from behind.

- **Best swap:** Plate Advance, for cowardly protection rather than personal
  toughness.
- **Evidence:** Guy refuses to risk himself when guards are available and uses
  subordinates to cover his escape.
- **Mechanical direction:** Limited bodyguard interception using the existing
  subordinate hierarchy and collision paths.

### Longchamp alternatives

#### Countermand

Issue forged orders to an unaware ordinary patrol. Select a valid patrol point
or guard post; the group walks there and resumes duty unless it encounters an
alarm or an officer who exposes the order.

- **Best swap:** Join Us, for spatial manipulation without changing allegiance.
- **Evidence:** Longchamp is John's counsellor, accredited envoy, and schemer;
  his official papers and perceived authority are central to his mission.
- **Mechanical direction:** Reuse patrol routes and temporary superior orders.

#### Diplomatic Escort

While Safe Conduct is active, extend its neutral treatment to one nearby allied
character. The escort must remain close and cannot carry an exposed weapon.
Recognition of either character exposes both.

- **Best swap:** Join Us, turning Longchamp from converter into party
  infiltrator.
- **Evidence:** Longchamp travels as an official envoy with an entourage, and
  his credentials—not just his face—permit passage toward Leopold.
- **Mechanical direction:** Safe Conduct aura with strict proximity and posture
  validation.

#### Ultimatum

Present a formal demand to an isolated, lower-courage enemy. After a short
countdown the target surrenders, retreats to fetch an officer, or attacks,
depending on courage and nearby support. The response is visible before the
countdown completes, allowing Longchamp to prepare.

- **Best swap:** Join Us, for predictable displacement and surrender rather
  than temporary recruitment.
- **Evidence:** Longchamp carries John's reply to Leopold's ultimatum and uses
  argument before drawing his sword against Robin.
- **Mechanical direction:** Courage check leading to existing tied/surrender,
  seek-superior, or attack states.

#### Dawn Departure

Choose an exit and begin a timed courier run. Longchamp gains movement and
interruption resistance while carrying the dispatch, but cannot use Safe
Conduct or attack until he reaches the destination. Success reveals objectives
and patrol routes near that exit; interruption drops the dispatch for enemies
to inspect.

- **Best swap:** Like True Knights, producing a pure mission/infiltration kit.
- **Evidence:** Longchamp gives himself until dawn to prepare, and preventing
  his departure with the letter is the central objective of Lackland's Plan.
- **Mechanical direction:** Carry-object and reach-exit sequence with a scouting
  reward, most appropriate for objective-heavy maps.

### Sheriff alternatives

#### Bleed the Yokels Dry

Designate a civilian cluster or building as taxable. A collector walks there
and extracts money over time. Successful collection replenishes payments for
Informer Network; abuse witnessed by hostile civilians increases local alarm
and resistance.

- **Best swap:** Informer Network, replacing immediate intelligence with an
  economy engine that can fund other systems.
- **Evidence:** Tax, tolls, pillage, extortion, and deliberate starvation are
  the Sheriff's most repeated activities.
- **Mechanical direction:** Escort/collection objective using civilian fear and
  witness events.

#### False Outlaws

Deploy two disguised bandits who stage a noisy theft at the selected location.
Nearby guards and civilians respond to the apparent crime, allowing the Sheriff
to redirect attention or manufacture an excuse for arrests. Inspection by a
high-intelligence officer exposes the deception.

- **Best swap:** Silver Arrow Trap, for an active false-flag distraction rather
  than a static ambush.
- **Evidence:** Mission text associates the Sheriff with planted or protected
  bandit atrocities used to terrorize the population and discredit resistance.
- **Mechanical direction:** Scripted civilian crime event plus disguise and
  investigation states.

#### Toll Gate

Place a temporary barricade across a valid narrow passage. Civilians stop to
pay, ordinary enemies pause to challenge it, and allied soldiers may guard it.
The obstacle can be dismantled, jumped where geometry permits, or destroyed.

- **Best swap:** Silver Arrow Trap, for persistent area denial.
- **Evidence:** The Sheriff imposes illegal tolls and controls roads, gates,
  convoys, and movement through Nottinghamshire.
- **Mechanical direction:** Placeable obstacle using gate/path blocking and a
  short interaction state.

#### Settle Our Account

Mark one visible enemy for a personal duel. The Sheriff gains detection
persistence and modest parry strength against that target, but allied soldiers
temporarily stop assisting him. Defeating the target refreshes Writ of Arrest;
breaking off the duel costs allied morale.

- **Best swap:** Writ of Arrest, trading command utility for a personal combat
  action.
- **Evidence:** He twice fights Robin personally, retreats from their first
  duel, and insists on settling their account in the final mission.
- **Mechanical direction:** A lighter variant of Longchamp's duel framework,
  emphasizing pursuit rather than a single riposte.

### Scathlock alternatives

#### The Lion's Den

Claim a room or courtyard around Scathlock's position. While he remains inside,
allies resist displacement and Scathlock gains faster attack commitment; leaving
the area ends the effect. Enemies can erase the claim by holding its centre
without Scathlock present.

- **Best swap:** Crush Them!, for defensive command rather than an advancing
  standard.
- **Evidence:** Scathlock calls Derby the lion's den and is the general whose
  presence organizes the castle's defence.
- **Mechanical direction:** Temporary ownership zone with courage and posture
  modifiers.

#### Glutton's Feast

Scathlock stops to consume an extravagant meal, restoring substantial life and
posture. The long animation is interruptible; being struck spills the meal and
wastes the charge.

- **Best swap:** Exemplary Punishment, for sustain instead of fear control.
- **Evidence:** He starves Tuck on bread and water while eating ostentatiously
  in front of him, and Tuck repeatedly characterizes him as a glutton.
- **Mechanical direction:** A slower, stronger Guzzle variant with limited food
  charges.

#### Mind My Name

Scathlock bellows his full title. Enemies who can hear him turn toward him;
low-courage enemies hesitate, while proud or high-courage enemies become angry
and rush him. This deliberately produces different results by personality.

- **Best swap:** Nettle, Honey, and Bees, for reusable taunt/control rather than
  consumable panic.
- **Evidence:** His grotesque decree punishes anyone who mispronounces or
  disrespects his name, making status sensitivity one of his defining traits.
- **Mechanical direction:** Whistle-like sound event followed by courage/pride
  response branches.

#### Chain-Mail Bulwark

Brace in place to reduce lateral sword damage and resist knockdown. Scathlock
cannot chase or turn quickly while braced, so opponents can disengage or attack
from the rear.

- **Best swap:** Exemplary Punishment, producing a durable frontline general
  rather than an executioner.
- **Evidence:** His shipped profile uniquely combines chain-mail armour with a
  cast-iron weapon, visually and mechanically distinguishing him from Guy's
  plate and the leather-armoured knights.
- **Mechanical direction:** Stationary Big Shield analogue driven by armour
  facing, with no projectile immunity.

## Example alternate trios

These combinations show how the larger pool can support substantially different
versions of the same character without mixing abilities arbitrarily.

| Character | Alternate trio | Resulting emphasis |
| --- | --- | --- |
| Prince John | Crown Jewels, The Regent Is Untouchable, Levy the County | High-risk royal treasure and one decisive army call |
| Guy | Sly Right-Hand, Secret Passage, Rank Has Its Privileges | Pure opportunist who ambushes and escapes behind guards |
| Longchamp | Countermand, Diplomatic Escort, Ultimatum | Noncombat officer and social infiltrator |
| Sheriff | Settle Our Account, False Outlaws, Toll Gate | More personal and territorial antagonist |
| Scathlock | The Lion's Den, Glutton's Feast, Mind My Name | Defensive boss built around provocation and sustain |

## Prototype path

The ideal kits require several new actions, but they can be tested in stages.

### Stage 1: existing-action stand-ins

| Villain action | Existing mechanic suitable for an early prototype |
| --- | --- |
| Bleed Them Dry | Purse |
| Plate Advance | Big Shield |
| Safe Conduct | Beggar posture/detection suppression |
| Like True Knights | Big Shield plus a scripted sword riposte |
| Informer Network | Listen reveal overlay |
| Silver Arrow Trap | Apple lure followed by Net |
| Exemplary Punishment | Execute |
| Nettle, Honey, and Bees | Wasp Nest |

This stage validates whether each tactical role is enjoyable before bespoke
icons, animations, AI orders, and serialized action variants are added.

### Stage 2: shared systems

Implement the reusable foundations once:

1. A temporary allegiance effect shared by Royal Decree and Join Us.
2. A marked-target order shared by Call the Guard, Writ of Arrest, and Crush
   Them.
3. A rule-driven neutral/disguise posture for Safe Conduct.
4. Placeable owned objects for informers, traps, and standards.
5. Courage modifiers for standards, executions, and Winnie.

### Stage 3: presentation and tuning

Add final icons, localized action descriptions, remarks, sound cues, and any
missing animations. Tune durations and ammunition against full campaign maps,
especially narrow entrances where reinforcements or arrest focus could bypass
the intended challenge.

## Evidence trail

The narrative, dialogue, interview, original-game, and hackable-data evidence
behind each proposal is indexed in `docs/VILLAIN_PC_RESEARCH.md`. The normal PC
action matrix and the villain chassis values come from
`datadirs/fullgame_gog_hackable/Data/Configuration/profile.cpf.json`.
