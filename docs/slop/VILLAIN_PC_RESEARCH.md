# Villain PC mod: character research dossier

This document gathers the shipped evidence for the five principal named villains
before any playable abilities are designed for them:

- Prince John Lackland
- Guy of Gisbourne
- William/Guillaume de Longchamp(s)
- the Sheriff of Nottingham
- Lord Scathlock of Derby

It deliberately separates facts present in the game from later mod-design
inference. No three-ability kits are proposed here.

## Research scope and method

The following sources were checked:

1. Every preserved Robin Hood interview in `docs/interviews/`, including the
   interviews' direct descriptions of the villains and the enemy hierarchy.
2. Original-game character identities, dialogue portraits, VIP combat rules,
   projectile and distraction rules, and enemy-AI pride behaviour.
3. The English full-game data in `datadirs/fullgame_linux`.
4. The decoded data in `datadirs/fullgame_gog_hackable`, including character
   profiles, sprite manifests, `.red.json` dialogue descriptors, mission data,
   and `.scb.json` scripts.
5. Decompiled versions of every shipped full-game mission script, generated
   from the binary `.scb` files so that actor names, objectives, popup text, and
   mission staging could be inspected together.

### Dialogue coverage

The full English campaign contains **126 spoken dialogue lines in 24 dialogue
sequences across 13 missions**. The Linux binary resources and decoded GOG
hackable resources have exactly the same text and portrait assignments for all
126 lines. The only observed difference is that the Linux conversion refers to
`.ogg` audio and the decoded GOG resource manifest refers to `.wav` audio.

The dialogue portrait table identifies the five speakers at indices 2, 7, 8,
9, and 10. Every line directly assigned to one
of those portraits is reproduced in the appendix below:

| Character | Direct spoken lines |
| --- | ---: |
| Prince John | 12 |
| Guy of Gisbourne | 2 |
| Longchamp | 7 |
| Sheriff of Nottingham | 6 |
| Scathlock | 5 |
| **Total** | **32** |

The remaining 94 lines were also inspected for what other characters say about
the villains. Relevant indirect evidence is incorporated into the dossiers.

This count covers every text-backed, portrait-assigned campaign conversation.
The game also has generic situational voice-bark banks (warnings, refusals,
combat exclamations, and similar reactions). The decoded resource manifests
identify their event names and audio files, but do not provide English
transcripts for those recordings; they are therefore treated as mechanical
voice-bark evidence rather than silently counted as additional dialogue lines.
The villain-specific banks are noted under shared VIP behaviour below.

## High-level findings

### Narrative roles

| Character | Role established by shipped material | Dominant characterization |
| --- | --- | --- |
| Prince John | Regent, would-be usurper, supreme political commander | Lazy, entitled, avaricious, theatrical, and strategically ruthless; delegates violence |
| Guy of Gisbourne | John's right-hand man, occupier of Lincoln, Marian's forced bridegroom | Cruel, vain, class-conscious, cowardly when disadvantaged, but a lethal duellist when cornered |
| Longchamp | John's counsellor, envoy, and political advocate | Scheming, articulate, loyal to John's claim, diplomatic, composed, and knightly in manner |
| Sheriff | John's chief enforcer and Robin's most personal enemy | Cunning, corrupt, greedy, vindictive, oppressive, and a capable recurring duellist |
| Scathlock | Lord of Derby and one of John's best generals | Cruel, sadistic, proud, militaristic, gluttonous, and secretly ridiculous/vulnerable to humiliation |

### Shipped mechanical split

The game does **not** implement all five in the same way:

- Prince John is civilian profile 11, `PrinceJohn`, a `Vip` civilian with a
  technically `Friendly` AI attitude. This is staging data, not narrative
  allegiance: scripts lock, move, hide, and capture him as a noncombatant.
- Guy, Longchamp, Scathlock, and the Sheriff are soldier profiles 59–62. All
  four are hostile VIP knights with 250 life, 100 intelligence, 100 courage,
  100 pride, 100 fighting, 100 endurance, no shooting skill, no lure affinity,
  and melee weapon profile 19.
- The four knight profiles use the same broad animation vocabulary, including
  full sword combat, parrying, charging, menacing, gathering soldiers,
  searching, leaning out, and a character-specific `Special` animation slot.
  Prince John's sprite set has civilian locomotion and gestures but no sword
  animation family.

The four duelists differ mechanically only in material presentation:

| Character | Weapon material | Armour material |
| --- | --- | --- |
| Guy | Steel | Plate |
| Longchamp | Steel | Leather |
| Sheriff | Steel | Leather |
| Scathlock | Cast iron | Chain mail |

These values are in `Data/Configuration/profile.cpf.json` in the hackable
datadir. Melee profile 19 is a sword-like weapon with straight, lateral,
semicircular, circular, and high-energy attacks; it has no shield and does not
support charge as a weapon property.

### Shared VIP behaviour in the original engine

The original game gives elite NPCs a strong common identity that matters when
turning them into PCs:

- Only Robin may initiate sword combat against a VIP. Other PCs are rejected
  and play the “VIPs are for Robin” remark.
- NPC VIPs cannot be targeted normally with the bow, and arrows do not hit them.
- Stones do no damage to VIPs.
- Nets fail to capture them.
- Wasps reject VIPs as victims.
- VIP soldiers cannot be strangled.
- Their profile values for beer, apples, money, and whistle are all zero. The
  AI supplies aristocratic refusal remarks for beer, apples, nets, wasps, and
  gold.
- Their pride score of 100 participates in a “too proud to attack” AI path:
  when lower-pride soldiers are available, lords stand back, observe, and only
  enter the fight later. This matches the developer's description that proud lords watch
  common soldiers fight and join only after the soldiers are gone.
- Each villain has a distinct VIP exclamation bank in the decoded
  `Data/Text/actors.res.d/manifest.json`: `PJ` (Prince John), `GG` (Guy), `GL`
  (Longchamp), `SN` (Sheriff), and `SK` (Scathlock). John has a reduced set;
  the four combat VIPs have the full 34-entry bank.

## Prince John Lackland

### Identity and position

- Also called John Lackland, Prince John, the Prince, the Regent, the usurper,
  and briefly “King John” by his supporters.
- He is King Richard's brother and governs England during Richard's captivity.
- The original game classifies him as a VIP enemy NPC.
- In actual mission data he is a civilian VIP rather than a soldier. He is the
  one member of this group with no combat stats or sword animations.
- Portrait resource 264 depicts a crowned, blond, bearded man in red/purple
  royal clothing.

### Personality

- The developers call him **evil** and **lazy**
  (`docs/interviews/06-haessig-devouassoux-homelan.md:72-74`).
- He is accustomed to power and actively enriches himself through oppressive
  taxation and unjust laws (`docs/interviews/07-haessig-devouassoux-action-vault.md:17`).
- His dialogue is self-important and legalistic. He repeatedly calls his acts
  “legitimate,” “just,” or necessary to his authority, even while accidentally
  calling himself King rather than Regent.
- He treats Richard's ransom as an opportunity to seize the crown. He is amused
  by Leopold's ultimatum, refuses to pay, and explicitly authorizes Leopold to
  dispose of Richard.
- He is not merely weak or manipulated. He personally plans to prevent the
  royalists from raising the ransom, orders heavier taxation, orders Scathlock
  to prepare force, gathers the Crown Jewels, confiscates Godwin's lands, hires
  a military engineer, calls reinforcements, and commands attacks on royalist
  castles.
- He delegates execution to capable subordinates: the Sheriff handles money
  and repression, Scathlock handles military force, Guy receives confiscated
  estates, and Longchamp handles counsel and diplomacy.
- He retains theatrical charm and humour: he mocks Leopold, proposes a toast,
  politely dismisses his lords for the night, and gives grand speeches even in
  defeat.
- In defeat he surrenders rather than fighting. He compliments Robin's loyalty
  to Richard and predicts that England will eventually need him. That last line
  leaves him vain and politically self-assured rather than broken.

### Actions and campaign footprint

- Central conspirator in **The Outlaw and the Prince** (`H03_Der_MK`), where
  Robin and Marian spy on his council.
- Orders Godwin declared a felon during **Save Tuck** (`S04_Der_EC`).
- Appears socially at the Silver Arrow tournament and Marian's wedding staging.
- Directs Longchamp's mission to Leopold in **Lackland's Plan** (`H10_Yor_VL`).
- Retreats to the Sheriff's fortress for **The Sheriff of Nottingham**
  (`H12_Not_MP`). The mission script locks him while the Sheriff duels Robin;
  after the Sheriff dies, John is turned toward Robin, speaks his surrender,
  and becomes the captured objective.
- In the Derby council script, Prince John is the hierarchy root: Longchamp,
  Scathlock, Guy, the Sheriff, and nearby soldiers are all registered as his
  subordinates.

### What other characters establish

- Marian initially believes he may listen to Robin's complaint, showing that
  his treachery is not universally obvious at the story's start.
- Ranulph says he had already doubted John's honesty.
- Robin calls him a criminal driven by appetite; Marian calls him a monster and
  traitor; Godwin calls him a villain and traitor.
- Campaign text repeatedly attributes John's strength to armies, convoys,
  taxation, recruitment, engineers, supplies, and subordinate barons—not to
  personal combat.

## Guy of Gisbourne

### Identity and position

- Spelled `Guisbourne` in most game data, and Gisborne/Guisbourne in interviews
  and localized text.
- The original game classifies him as a VIP enemy NPC.
- Soldier profile 59: hostile VIP knight, 250 life, perfect fighting/courage/
  endurance/intelligence/pride, steel weapon, and plate armour.
- Portrait resource 262 depicts a long-faced, black-haired armoured noble in
  dark plate/chain with red-and-gold clothing.

### Personality

- The developers call him **cruel**, **evil**, and **despicable**, with his
  desire to marry Marian as his defining plot trait
  (`docs/interviews/06-haessig-devouassoux-homelan.md:72-74` and
  `docs/interviews/07-haessig-devouassoux-action-vault.md:97`).
- He is described in campaign text as Prince John's “sly right-hand man.”
- He is intensely class-conscious: he calls Robin a pest, vile outlaw, yokel,
  and someone unworthy of his blade.
- At Lincoln, he refuses Robin's challenge, sends for guards, and escapes down
  a secret passage. The script explicitly stages his flight and deactivates him
  once he reaches safety.
- His cowardice is opportunistic rather than lack of ability. At the wedding,
  once isolated with Marian, he personally challenges Robin and fights the
  required duel.
- He turns Marian and Robin's death into status objects: he intends the forced
  marriage to establish possession of Marian and promises Robin's head as a
  “wedding gift.”
- His dialogue is terse, contemptuous, and aggressive; unlike Longchamp, he
  makes no ideological argument.

### Actions and campaign footprint

- Receives Godwin's confiscated lands and occupies Lincoln with his own men.
- Keeps Godwin imprisoned in Godwin's own dungeon.
- Flees the first confrontation in **Free Godwin** (`H05_Lin_EC`).
- Is the forced bridegroom in **Save Marian** (`S05_Yrk_EC`). The cathedral
  sequence clears the way for a dedicated duel with Robin.
- Appears with John's court at the Silver Arrow tournament and in council/
  wedding staging even when he has no spoken line.
- The developers identify stopping Marian's forced marriage as one of the
  campaign's signature missions
  (`docs/interviews/12-martin-kuppe-worthplaying.md:48-50`).

### What other characters establish

- Ranulph calls him the beneficiary of John's theft of Godwin's lands.
- Godwin calls his followers “Guisbourne roughnecks” and expects Guy to remain
  a continuing threat after being driven out.
- Mission narration explicitly calls his first escape cowardly.

## William/Guillaume de Longchamp(s)

### Identity and position

- Also known as William of Longchamps.
- The dialogue uses “Longchamps” and gives his death name as **Guillaume de
  Longchamps**; profiles use `Longchamp` without the final s.
- The developers call him **the schemer**
  (`docs/interviews/12-martin-kuppe-worthplaying.md:84-86`).
- Soldier profile 60: hostile VIP knight, 250 life, perfect fighting/courage/
  endurance/intelligence/pride, steel weapon, and leather armour.
- Portrait resource 263 depicts a clean-shaven, dark-haired courtier in green
  and purple rather than visibly heavy armour.

### Personality

- Longchamp is the most articulate and politically minded of the four duelists.
- He is the councillor who identifies Ranulph as the likely centre of loyalist
  resistance.
- He initiates the toast to “King John,” signalling active commitment rather
  than passive obedience.
- He accepts the mission to carry John's safe-conduct and letter to Leopold,
  giving himself until dawn to prepare.
- When Robin confronts him, he tries persuasion before violence. He argues that
  Richard neglects his subjects by fighting abroad and that John has a rightful
  claim. He even invites Robin to join them.
- He calls Robin young, remains verbally composed, refuses surrender, and
  proposes resolving the dispute “like true knights.” His final “on guard” is
  formal rather than insulting.
- The contrast between “schemer” and courteous knight is important: he is a
  political operator, diplomat, and ideologue who is also fully capable in a
  duel.

### Actions and campaign footprint

- Counsels John in **The Outlaw and the Prince** (`H03_Der_MK`).
- Serves as John's courier to Leopold in **Lackland's Plan** (`H10_Yor_VL`). If
  he leaves, Richard's rescue is lost.
- The mission enforces a Robin-only duel zone, marks his death as the main
  objective, and preserves a separate Longchamp corpse actor.
- After his death, Allan-a-Dale wears his clothes, uses John's safe-conduct,
  impersonates him, and carries the ransom to Leopold. This establishes that
  Longchamp's recognizable appearance and official credentials are as
  important as his sword.
- He also appears in court staging at the Silver Arrow tournament and Marian's
  wedding.

### What other characters establish

- Robin calls him a rascal but still offers him safe surrender and wishes him
  peace after killing him.
- The campaign describes him as one of John's henchmen with a personal
  entourage and an embedded informant, implying a courtly network of his own.

## The Sheriff of Nottingham

### Identity and position

- The original game classifies the Sheriff of Nottingham as a VIP enemy NPC.
- Soldier profile 62: hostile VIP knight, 250 life, perfect fighting/courage/
  endurance/intelligence/pride, steel weapon, and leather armour.
- Portrait resource 266 depicts a severe, greying dark-haired man with a pointed
  beard, dark clothing, and a purple collar.
- Developers variously call him **evil**, **cunning**, **tyrannical**, and the
  final/personal adversary. The game's story was designed to end with Robin's
  duel against him (`docs/interviews/06-haessig-devouassoux-homelan.md:42-44`).

### Personality

- He is avaricious and sadistic: his response to the ransom problem is to
  “bleed these yokels dry,” using hunger to crush resistance.
- He is deceitful and corrupt. He falsifies Robin's death to seize Locksley,
  bribes local figures, protects a tax-gouging brother-in-law, and uses office
  to enrich himself.
- He is a hands-on administrator of oppression: taxes, tolls, pillaging,
  extortion, recruitment, humiliating punishments, executions, body display,
  arrests, informants, staged bandit atrocities, convoy guards, and searches of
  Sherwood are all associated with him in mission text.
- He is cunning enough to set the Silver Arrow tournament as a trap and to
  capture Robin with an informer.
- He has dry humour—he calls Leopold deluded—and enjoys humiliating Robin.
- He recognizes genuine skill. At the tournament he acknowledges Robin as
  England's finest archer; after losing the first duel, he admits Robin is
  stronger than expected.
- He is persistent rather than suicidal. In the tournament script his first
  duel is deliberately stopped when his life drops to 150 or below; his life is
  reset upward and he retreats, promising a rematch.
- He finally stands between Robin and John in Nottingham, insists on settling
  their account, and fights to the death.

### Actions and campaign footprint

- Seizes Robin's inheritance and makes the conflict personal before the main
  conspiracy is known.
- Captures or threatens Stuteley, Will Scarlet, Little John, Allan-a-Dale,
  Robin, villagers, and assorted dissenters.
- Oversees the Silver Arrow trap in **The Silver Arrow** (`H07_Not_MK`).
- Attends both of John's conspiracy councils.
- Serves as John's last protector and final duellist in
  **The Sheriff of Nottingham** (`H12_Not_MP`). The mission forces non-Robin
  actors out of the duel space and makes the Sheriff's death trigger John's
  surrender.
- His soldiers and wealth drive many repeatable forest ambush missions, making
  his influence more continuously present in gameplay than any other named
  villain.

### What other characters establish

- Marian calls him deceitful and cruel and says he will never voluntarily
  restore Robin's land.
- Will Scarlet calls him a coward who understands only force.
- The campaign presents him both as John's pawn and as an independently corrupt
  power who exploits John's weak rule.
- Stuteley specifically builds traps for attacks on his convoys, tying the
  Sheriff to the game's trap/ambush economy.

## Lord Scathlock of Derby

### Identity and position

- Called `Scatlock` in profiles/scripts and **Scathlock** in English text.
- He has a dialogue portrait and hostile VIP soldier profile, and appears as
  a named lord and major duel target.
- Soldier profile 61: hostile VIP knight, 250 life, perfect fighting/courage/
  endurance/intelligence/pride, cast-iron weapon, and chain-mail armour.
- Portrait resource 265 depicts a broad-faced dark-haired lord with enormous
  eyebrows, a heavy moustache and beard, chain mail, and blue clothing.
- The developers call him **cruel** and identify him as one of the noble enemies
  who may only be killed in a duel with Robin
  (`docs/interviews/12-martin-kuppe-worthplaying.md:84-86`).

### Personality

- He is John's overt military strongman. He immediately volunteers his men to
  crush Ranulph and later offers to lead troops against Godwin.
- Campaign text calls him one of John's best generals and says removing him
  significantly damages enemy organization and morale.
- He enjoys cruelty personally. He imprisons Tuck on bread and water while
  ostentatiously eating in front of him.
- His decree threatens anyone who mispronounces or disrespects his name with a
  slow nettle whipping followed by honey and exposure to his beehives.
- He threatens a rescued prisoner with something the prisoner will not repeat
  and boasts about his executioner.
- He is lewd and sadistic in his duel taunt, promising to leave enough of Robin
  for his men.
- He is proud and theatrical, calling Derby the lion's den and treating Robin's
  challenge as a spectacle.
- He also has a comic secret: an unspecified treasured possession called
  **“Winnie.”** Robin may ransom it back for considerable money or reveal the
  secret, causing Scathlock's soldiers to mock him and lose morale. This is his
  clearest noncombat vulnerability.
- He is gluttonous, touchy about status, and extremely sensitive to ridicule.

### Actions and campaign footprint

- Rules Derby and imprisons Tuck in **Save Tuck** (`S04_Der_EC`).
- Hosts John's war council and agrees to attack Godwin.
- His secret possession drives the optional convoy mission **Scathlock's
  Secret**.
- Is the general defending Derby in **Attack Derby** (`Str02_Der_MP`). Mission
  text explicitly requires Robin to eliminate him honourably in a duel.
- His death sets a persistent campaign flag; later Derby attacks substitute a
  newly appointed general. If he survives the first assault, campaign text says
  he flees and will try to retake the castle.
- His death produces a serious strategic blow: without their leader, his troops
  put up only slight resistance to Ranulph and Godwin.

### What other characters establish

- Tuck calls him unholy, a coward, and a glutton.
- Prisoners call him a monster and fear that he kills or tortures people over
  trivial disrespect.
- Mission narration calls him terrible, loathsome, and an excellent general.

## Comparisons that should constrain later ability design

These are evidence constraints, not ability proposals:

1. **John should not simply become a fifth sword knight.** The shipped game
   defines him through command, law, money, credentials, armies, and delegation,
   and gives him no combat animation family.
2. **The four duelists need differentiation beyond their shipped stats.** Their
   numerical profiles are nearly clones, so personality, plot actions, armour,
   mission scripting, and dialogue must carry the differentiation.
3. **Guy's identity is pursuit/escape and possessive aggression.** His plate
   armour and first-flight/second-duel arc distinguish him from Longchamp.
4. **Longchamp's identity is persuasion, disguise, credentials, and political
   planning.** He is the least brutish and most verbally sophisticated duelist.
5. **The Sheriff combines wealth, traps, informants, law enforcement, and
   recurring tactical pressure.** He is more than a sword boss.
6. **Scathlock combines army command with fear and ridicule.** His “Winnie”
   secret is uniquely suitable evidence for morale or humiliation mechanics.
7. **Aristocratic pride is systemic.** The original AI makes high-pride lords
   hold back while inferiors fight, then enter personally. Any playable version
   should decide consciously whether to preserve, invert, or reinterpret this.
8. **VIP immunity is part of their fantasy but cannot transfer unmodified to a
   PC kit.** Arrow, stone, net, wasp, strangling, and lure immunity would erase
   too much counterplay if copied wholesale.

## Appendix A: complete direct villain dialogue transcript

Wording and punctuation below follow the English resource text; line-wrapping
whitespace and the character headings are normalized for readability.

### Prince John — all 12 lines

**H03_Der_MK, dialogue 0 — The Outlaw and the Prince**

1. “… I won't let myself be had. But dear friends, this is the opportunity we
   have been waiting for. This letter from Leopold tells me that he will only
   release Richard in return for a ransom! And what a ransom! No less than One
   Hundred Thousand Pounds! Does he really think I'm going to pay? No, my
   brother left me his Kingdom, and I mean to keep it!”
2. “So we must make sure there is no way they can get the ransom together. I
   count on you, my good Sheriff, I trust you are up to the task!”
3. “That sounds good! If that isn't enough, I order you, Lord Scathlock, to
   reinforce your troops. We must be ready to use force if necessary.”
4. “I have issued an order that the Crown Jewels be assembled in order to
   proceed with my own coronation. The Royal Sceptre is already in my
   possession, and will soon be safe in my castle. As soon as Leopold has had
   enough of waiting for the ransom, I must be ready to ascend the throne.”

**H10_Yor_VL, dialogue 0 — Lackland's Plan**

5. “\"I, Duke Leopold, demand that King Richard's ransom be paid within one
   month, otherwise I shall be obliged to inconvenience your sovereign.\" Ha!
   Now you know the happy content of this ultimatum!”
6. “Not half! And it's time to put his feet back on the ground. Longchamps,
   here is a safe conduct, which will enable you to join Leopold on the
   continent. You will give him this letter, in which I explain that he can
   dispose of Richard as he sees fit, I will never pay! It's time that I was
   crowned in my brother's place.”
7. “Very well. I wish you good night, my lords.”

**H12_Not_MP — The Sheriff of Nottingham**

8. “Vile pest! The outlaw!”
9. “Well said, Sheriff. Finish him off!”
10. “So, I'm vanquished! So be it, Robin of Locksley, I am your prisoner. Be
    proud of your victory! My brother can count himself fortunate to have
    subjects as loyal as you. But I tell you, sooner or later, England will
    need me!”

**S04_Der_EC, dialogue 1 — Save Tuck**

11. “My lords, I cannot tolerate the insubordination of that scoundrel Godwin.
    He has dared to rebel against my legitimate decision to confiscate his
    lands to give them to my good Guisbourne! I cannot accept such a
    questioning of my just authority. I therefore declare Sir Godwin a felon
    and traitor, enemy of his King ... I mean Regent.”
12. “So be it! If it's war he wants, it's war he'll get!”

### Guy of Gisbourne — both lines

**H05_Lin_EC, dialogue 1 — Free Godwin**

1. “Pest! So you think you can come and threaten me on my land, vile outlaw!
   Do you think I would dishonour my blade by taking you on myself? Parker, go
   and get the guard! As for us, we'll meet again!”

**S05_Yrk_EC, dialogue 0 — Save Marian**

2. “Robin Hood! We meet again, at last! On guard, yokel, I have offered your
   head as a wedding gift to the noble Marian!”

### Longchamp — all 7 lines

**H03_Der_MK, dialogue 0 — The Outlaw and the Prince**

1. “It is possible that some vassals will refuse to accept your government with
   good grace. Sir Ranulph in particular has always been loyal to Richard.”
2. “Let's drink, my lords, let's drink to our King! Long Live King John!”

**H10_Yor_VL — Lackland's Plan**

3. “At your service, my lord. I need some time to prepare. I will leave at
   dawn.”
4. “Robin Hood! What? Never mind, you can't stop me carrying out my mission.”
5. “Legitimate? What good is a King who spends his time scrapping far away from
   his subjects? No Robin, it's you who must recognise Prince John's rights to
   the crown! Join us!”
6. “Ah, Robin, you are still very young… But I see there's no point in trying
   to convince you… and I can't meet your demands… Shall we settle this
   difference like true knights?”
7. “Right then, on guard!”

### Sheriff of Nottingham — all 6 lines

**H03_Der_MK, dialogue 0 — The Outlaw and the Prince**

1. “I will bleed these yokels dry. Hunger will shut them up, and crush them to
   their knees!”
2. “Long live the King!”

**H07_Not_MK — The Silver Arrow**

3. “So what they say is true! You indeed seem to be the most skilful archer in
   England, Robin Hood! But one thing is certain, you are definitely the most
   stupid! Come on, we've played enough. On guard! Let's see if you handle the
   sword as well as the bow!”
4. “Bah! You're stronger than I thought! We'll meet again, brigand, I promise!”

**H10_Yor_VL, dialogue 0 — Lackland's Plan**

5. “I think the poor Leopold is quite deluded.”

**H12_Not_MP, dialogue 0 — The Sheriff of Nottingham**

6. “Not so fast, presumptuous youth! We have an account to settle, you and I,
   on guard, and prepare to die!”

### Scathlock — all 5 lines

**H03_Der_MK, dialogue 0 — The Outlaw and the Prince**

1. “My men are awaiting only a word from you, my Lord! It would be a pleasure
   to crush this wretched Ranulph!”
2. “King John!”

**S04_Der_EC, dialogue 1 — Save Tuck**

3. “I will lead my troops against his lands, and seize him so that his
   punishment is exemplary, your lordship!”

**Str02_Der_MP, dialogue 0 — Attack Derby**

4. “Robin the brigand! So, you've decided to throw yourself into the lion's
   den? Have you come to give yourself up? My executioner will be delighted to
   meet you.”
5. “Don't worry, little one, I'll leave enough of you for my men to enjoy
   themselves!”

## Appendix B: dialogue-sequence inventory

This is the complete campaign dialogue inventory used for the review. It is
included to make the “all dialogues” claim auditable.

| Mission | Sequence | Lines | Speakers |
| --- | ---: | ---: | --- |
| Contact Marian (`H02_Not_EC`) | 0 | 20 | Robin, Marian |
| The Outlaw and the Prince (`H03_Der_MK`) | 0 | 11 | John, Longchamp, Sheriff, Scathlock, Marian |
| The Outlaw and the Prince (`H03_Der_MK`) | 1 | 2 | Marian, Robin |
| Contact Ranulph (`H04_Lei_VL`) | 0 | 6 | Robin, Marian, Ranulph |
| Contact Ranulph (`H04_Lei_VL`) | 1 | 11 | Robin, Marian, Ranulph |
| Free Godwin (`H05_Lin_EC`) | 0 | 4 | Robin, Godwin |
| Free Godwin (`H05_Lin_EC`) | 1 | 1 | Guy |
| The Silver Arrow (`H07_Not_MK`) | 0 | 1 | Sheriff |
| The Silver Arrow (`H07_Not_MK`) | 1 | 5 | Robin, Marian |
| The Silver Arrow (`H07_Not_MK`) | 2 | 1 | Sheriff |
| Lackland's Plan (`H10_Yor_VL`) | 0 | 6 | John, Sheriff, Longchamp, Robin |
| Lackland's Plan (`H10_Yor_VL`) | 1 | 8 | Robin, Longchamp |
| Lackland's Plan (`H10_Yor_VL`) | 2 | 5 | Robin, Allan-a-Dale |
| The Sheriff of Nottingham (`H12_Not_MP`) | 0 | 5 | Robin, John, Sheriff |
| The Sheriff of Nottingham (`H12_Not_MP`) | 1 | 2 | Robin, John |
| Save Stuteley (`S01_Not_VL`) | 0 | 3 | Stuteley, Robin |
| Save Scarlett (`S02_Lei_MP`) | 0 | 8 | Will Scarlet, Robin |
| Save Little John (`S03_FoB_MP`) | 0 | 3 | Soldier, Robin |
| Save Little John (`S03_FoB_MP`) | 1 | 5 | Little John, Robin |
| Save Tuck (`S04_Der_EC`) | 0 | 5 | Tuck, Robin |
| Save Tuck (`S04_Der_EC`) | 1 | 3 | John, Scathlock |
| Save Marian (`S05_Yrk_EC`) | 0 | 2 | Guy, Robin |
| Save Marian (`S05_Yrk_EC`) | 1 | 6 | Marian, Robin |
| Attack Derby (`Str02_Der_MP`) | 0 | 3 | Scathlock, Robin |

## Primary source index

### Interviews

- `docs/interviews/04-mischa-strecker-freelancer.md:48-50` — Sheriff, John,
  and Guy named as major bad guys.
- `docs/interviews/06-haessig-devouassoux-homelan.md:42-44` — plot arc ends
  with the Sheriff's duel and includes Marian/Guy.
- `docs/interviews/06-haessig-devouassoux-homelan.md:72-74` — concise traits:
  evil Sheriff, lazy John, cruel Guy, plus Longchamp and Scathlock.
- `docs/interviews/07-haessig-devouassoux-action-vault.md:85-89` — enemy
  hierarchy and proud lords' battlefield behaviour.
- `docs/interviews/08-martin-kuppe-xgr.md:22-24` — John, Sheriff, ransom,
  oppression, and royalist war overview.
- `docs/interviews/12-martin-kuppe-worthplaying.md:84-86` — Guy, cruel
  Scathlock, scheming Longchamp, and Sheriff as Robin-only noble duels.

### Hackable game data

- `datadirs/fullgame_gog_hackable/Data/Configuration/profile.cpf.json` — all
  civilian, soldier, character, weapon, and mission profiles.
- `datadirs/fullgame_gog_hackable/Data/Characters/{PrinceJohn,Guisbourne,Longchamp,Scatlock,sherif}.rhs.d/manifest.json`
  — decoded animation sets.
- `datadirs/fullgame_gog_hackable/Data/Text/RHLevel*.red.json` — dialogue
  descriptors and portrait assignments.
- `datadirs/fullgame_gog_hackable/neutral/Data/Text/Level.res.d/manifest.json`
  — all English campaign text and dialogue lines.
- `datadirs/fullgame_gog_hackable/Data/Levels/*.scb.json` and `*.rhm.json` —
  decoded mission logic and placements.
