use super::*;
use robin_engine::element::{
    ActorData, ActorSoldier, ElementBonus, ElementData, ElementKind, ElementTarget, FxData,
    HumanData, NpcData, ObjectData, SoldierData, TargetData, TargetFilter,
};

/// `PlayerCommand` intentionally has no `PartialEq` (it carries f32
/// payloads); command sequences are compared via their exhaustive
/// `Debug` form instead.
macro_rules! assert_cmds {
    ($left:expr, $right:expr) => {
        assert_eq!(format!("{:?}", $left), format!("{:?}", $right))
    };
}

#[test]
fn sword_seek_distance_distinguishes_simple_click_from_thrust_a_gesture() {
    let mut weapon = robin_engine::profiles::HtHWeaponProfile::default();
    weapon.distance[robin_engine::weapons::WeaponDistance::Maximal as usize] = 70;
    weapon.thrusts[robin_engine::weapons::SwordStrike::A as usize].maximal_distance = 60;

    assert_eq!(
        sword_seek_distance_for_weapon(&weapon, Command::SwordstrikeThrustA, true),
        63.0
    );
    assert_eq!(
        sword_seek_distance_for_weapon(&weapon, Command::SwordstrikeThrustA, false),
        54.0
    );
}

use crate::host::test_support::{add_pc_with_status, fixture};

const NO_MODS: ClickModifiers = ClickModifiers {
    shift: false,
    planning: false,
    control: false,
    double: false,
};
/// Physical Shift doubles as the planning modifier in these click tests.
const SHIFT: ClickModifiers = ClickModifiers {
    shift: true,
    planning: true,
    ..NO_MODS
};
const PLANNING: ClickModifiers = ClickModifiers {
    planning: true,
    ..NO_MODS
};
const CTRL: ClickModifiers = ClickModifiers {
    control: true,
    ..NO_MODS
};
const DOUBLE: ClickModifiers = ClickModifiers {
    double: true,
    ..NO_MODS
};

/// A live, selectable PC at `(x, y)`. Zero-size sprites hit-test as a
/// 20-unit radius around the entity position, so clicks at the exact
/// position always register.
fn add_pc(engine: &mut Engine, x: f32, y: f32, posture: Posture) -> EntityId {
    add_pc_with_status(engine, x, y, posture, true, 100)
}

fn add_soldier(engine: &mut Engine, x: f32, y: f32, life_points: i16) -> EntityId {
    let mut element = {
        let mut initial_element = ElementData::from_initial_posture(Posture::Upright);
        initial_element.kind = ElementKind::ActorSoldier;
        initial_element.active = true;
        initial_element
    };
    element.set_position_map(MapPoint::new(x, y));
    engine.test_add_entity(engine_element::Entity::Soldier(ActorSoldier {
        element,
        actor: ActorData::default(),
        human: HumanData::default(),
        npc: NpcData {
            life_points,
            ..Default::default()
        },
        soldier: SoldierData {
            cached_camp: robin_engine::element_kinds::Camp::Lacklandists,
            ..Default::default()
        },
    }))
}

fn add_bonus(engine: &mut Engine, x: f32, y: f32) -> EntityId {
    let mut element = {
        let mut initial_element = ElementData::default();
        initial_element.kind = ElementKind::ObjectBonus;
        initial_element.active = true;
        initial_element
    };
    element.set_position_map(MapPoint::new(x, y));
    engine.test_add_entity(engine_element::Entity::Bonus(ElementBonus {
        element,
        object: ObjectData::default(),
    }))
}

fn apply(engine: &mut Engine, assets: &LevelAssets, cmd: PlayerCommand) {
    engine
        .advance_frame(
            assets,
            robin_engine::engine::SimulationFrameInput::new(vec![cmd.into()]).with_hourglass(false),
        )
        .expect("test command admission");
}

fn select(engine: &mut Engine, assets: &LevelAssets, pc_id: EntityId) {
    apply(
        engine,
        assets,
        PlayerCommand::SelectPc {
            pc_id,
            append: false,
        },
    );
}

fn add_fighting_allied_soldier(
    engine: &mut Engine,
    x: f32,
    y: f32,
    opponent: EntityId,
) -> EntityId {
    let mut element = {
        let mut initial_element = ElementData::from_initial_posture(Posture::Upright);
        initial_element.kind = ElementKind::ActorSoldier;
        initial_element.active = true;
        initial_element
    };
    element.set_position_map(MapPoint::new(x, y));
    engine.test_add_entity(engine_element::Entity::Soldier(ActorSoldier {
        element,
        actor: ActorData::default(),
        human: HumanData {
            opponents: vec![opponent].into(),
            ..Default::default()
        },
        npc: NpcData {
            life_points: 100,
            ai: robin_engine::element::AiActorData {
                ai_brain: robin_engine::element::AiBrain::Enemy(Box::default()),
                ..Default::default()
            },
        },
        soldier: SoldierData {
            cached_camp: robin_engine::element_kinds::Camp::Royalists,
            command_interface: robin_engine::human_control::CommandInterface::TacticalOrders,
            ..Default::default()
        },
    }))
}

fn add_allied_soldier(engine: &mut Engine, x: f32, y: f32) -> EntityId {
    let mut element = {
        let mut initial_element = ElementData::from_initial_posture(Posture::Upright);
        initial_element.kind = ElementKind::ActorSoldier;
        initial_element.active = true;
        initial_element
    };
    element.set_position_map(MapPoint::new(x, y));
    engine.test_add_entity(engine_element::Entity::Soldier(ActorSoldier {
        element,
        actor: ActorData::default(),
        human: HumanData::default(),
        npc: NpcData {
            life_points: 100,
            ai: robin_engine::element::AiActorData {
                ai_brain: robin_engine::element::AiBrain::Enemy(Box::default()),
                ..Default::default()
            },
        },
        soldier: SoldierData {
            cached_camp: robin_engine::element_kinds::Camp::Royalists,
            command_interface: robin_engine::human_control::CommandInterface::TacticalOrders,
            ..Default::default()
        },
    }))
}

fn select_allied(engine: &mut Engine, assets: &LevelAssets, soldier: EntityId) {
    apply(
        engine,
        assets,
        PlayerCommand::SelectTacticalUnits {
            soldiers: vec![soldier],
            append: false,
        },
    );
}

fn arm_action(engine: &mut Engine, assets: &LevelAssets, pc_id: EntityId, action: Action) {
    apply(
        engine,
        assets,
        PlayerCommand::SelectResolvedAction { pc_id, action },
    );
}

// ── pattern_to_command ──

#[test]
fn portrait_heal_gate_requires_an_injured_pc() {
    let (mut engine, _, _) = fixture();
    let missing = EntityId::Pc(robin_engine::entity_id::PcId(999));
    assert!(!is_valid_heal_portrait_target(&engine, missing));
    for life in [i16::MIN, -1, 0, 1, 50, 99, 100, 101, i16::MAX] {
        // Activity is not part of this legacy portrait gate; callers
        // independently decide which portraits are interactive.
        for active in [false, true] {
            let pc = add_pc_with_status(&mut engine, 25.0, 25.0, Posture::Upright, active, life);
            assert_eq!(
                is_valid_heal_portrait_target(&engine, pc),
                (1..100).contains(&life)
            );
        }
        let soldier = add_soldier(&mut engine, 25.0, 25.0, life);
        assert!(!is_valid_heal_portrait_target(&engine, soldier));
    }
}

#[test]
fn world_shield_clicks_select_protectee_then_require_danger_point() {
    let (mut engine, assets, mut host) = fixture();
    let actor = add_pc(&mut engine, 25.0, 25.0, Posture::Upright);
    let protected = add_pc(&mut engine, 125.0, 125.0, Posture::Upright);
    select(&mut engine, &assets, actor);
    arm_action(&mut engine, &assets, actor, Action::Shield);
    let seat = host.transport.local_seat();

    let first = resolve_action_left_click(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(125.0, 125.0),
        seat,
        Action::Shield,
        NO_MODS,
    );
    assert_cmds!(
        first,
        vec![PlayerCommand::ShieldSelectProtected {
            actor,
            protected_pc: protected,
        }]
    );
    apply(&mut engine, &assets, first[0].clone());
    assert!(!engine.shield().is_protected);
    assert_eq!(engine.shield().protected_pc, Some(protected));

    let second = resolve_action_left_click(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 275.0),
        seat,
        Action::Shield,
        NO_MODS,
    );
    assert!(matches!(
        second.as_slice(),
        [
            PlayerCommand::RaiseShieldWithDanger {
                actor: actual_actor,
                protected_pc: actual_protected,
                danger_point_layer: 0,
                ..
            },
            PlayerCommand::UnselectAllActions,
        ] if *actual_actor == actor && *actual_protected == protected
    ));
}

#[test]
fn portrait_shield_click_only_selects_protectee_before_danger_phase() {
    let (mut engine, assets, mut host) = fixture();
    let actor = add_pc(&mut engine, 25.0, 25.0, Posture::Upright);
    let protected = add_pc(&mut engine, 125.0, 125.0, Posture::Upright);
    select(&mut engine, &assets, actor);
    arm_action(&mut engine, &assets, actor, Action::BigShield);
    let seat = host.transport.local_seat();

    let first = resolve_shield_portrait_click(&engine, seat, actor, protected, false)
        .expect("armed shield must consume its protectee portrait");
    assert_cmds!(
        first,
        vec![PlayerCommand::ShieldSelectProtected {
            actor,
            protected_pc: protected,
        }]
    );
    apply(&mut engine, &assets, first[0].clone());

    assert!(
        resolve_shield_portrait_click(&engine, seat, actor, protected, false).is_none(),
        "a portrait cannot replace the required world danger-point click"
    );
    let danger = resolve_action_left_click(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(325.0, 250.0),
        seat,
        Action::BigShield,
        NO_MODS,
    );
    assert!(matches!(
        danger.first(),
        Some(PlayerCommand::RaiseShieldWithDanger {
            actor: actual_actor,
            protected_pc: actual_protected,
            ..
        }) if *actual_actor == actor && *actual_protected == protected
    ));
}

#[test]
fn planned_shield_portrait_uses_the_same_two_phase_protocol() {
    let (mut engine, assets, mut host) = fixture();
    let actor = add_pc(&mut engine, 25.0, 25.0, Posture::Upright);
    let protected = add_pc(&mut engine, 125.0, 125.0, Posture::Upright);
    select(&mut engine, &assets, actor);
    apply(
        &mut engine,
        &assets,
        PlayerCommand::SelectPlannedAction {
            pc_id: actor,
            action: Action::Shield,
        },
    );
    let seat = host.transport.local_seat();

    let first = resolve_shield_portrait_click(&engine, seat, actor, protected, true)
        .expect("planned shield must consume its protectee portrait");
    assert_cmds!(
        first,
        vec![PlayerCommand::SelectPlannedShieldProtected {
            actor,
            protected_pc: protected,
        }]
    );
    apply(&mut engine, &assets, first[0].clone());
    assert!(resolve_shield_portrait_click(&engine, seat, actor, protected, true).is_none());

    let danger_point = MapPoint::new(325.0, 250.0);
    let queued = queue_shift_click_commands(
        resolve_action_left_click(
            &mut host,
            &engine,
            &assets,
            danger_point,
            seat,
            Action::Shield,
            PLANNING,
        ),
        Action::Shield,
        true,
    );
    assert!(matches!(
        queued.as_slice(),
        [PlayerCommand::QueueQuickAction {
            action: Action::Shield,
            command: QueuedQuickActionCommand::RaiseShieldWithDanger {
                actor: actual_actor,
                protected_pc: actual_protected,
                danger_point: actual_danger,
                danger_point_layer: 0,
            },
        }] if *actual_actor == actor
            && *actual_protected == protected
            && actual_danger.x == danger_point.x
            && actual_danger.y == danger_point.y
    ));
}

#[test]
fn shield_portrait_gate_matches_world_focus_selection_rules() {
    let (mut engine, assets, host) = fixture();
    let actor = add_pc(&mut engine, 25.0, 25.0, Posture::Upright);
    let protected = add_pc(&mut engine, 125.0, 125.0, Posture::Upright);
    let second_selected = add_pc(&mut engine, 225.0, 225.0, Posture::Upright);
    let dead = add_pc_with_status(&mut engine, 325.0, 325.0, Posture::Dead, true, 0);
    let inactive = add_pc_with_status(&mut engine, 425.0, 425.0, Posture::Upright, false, 100);
    select(&mut engine, &assets, actor);
    let seat = host.transport.local_seat();

    assert!(is_valid_shield_portrait_protectee(&engine, seat, protected));
    assert!(!is_valid_shield_portrait_protectee(&engine, seat, actor));
    assert!(!is_valid_shield_portrait_protectee(&engine, seat, dead));
    assert!(!is_valid_shield_portrait_protectee(&engine, seat, inactive));

    apply(
        &mut engine,
        &assets,
        PlayerCommand::SelectPc {
            pc_id: second_selected,
            append: true,
        },
    );
    assert!(!is_valid_shield_portrait_protectee(
        &engine, seat, protected
    ));
}

#[test]
fn right_click_cancels_shield_targeting_without_launching_it() {
    let (mut engine, assets, host) = fixture();
    let actor = add_pc(&mut engine, 25.0, 25.0, Posture::Upright);
    let protected = add_pc(&mut engine, 125.0, 125.0, Posture::Upright);
    select(&mut engine, &assets, actor);
    arm_action(&mut engine, &assets, actor, Action::Shield);
    let seat = host.transport.local_seat();
    let first = resolve_shield_portrait_click(&engine, seat, actor, protected, false)
        .expect("shield protectee click");
    apply(&mut engine, &assets, first[0].clone());

    let cancel = resolve_right_click(&engine, seat);
    assert_cmds!(cancel, vec![PlayerCommand::UnselectAllActions]);
    apply(&mut engine, &assets, cancel[0].clone());
    assert_eq!(engine.selected_action_for_seat(seat), Action::NoAction);
    assert!(resolve_shield_portrait_click(&engine, seat, actor, protected, false).is_none());
}

#[test]
fn planned_shield_queue_preserves_replay_geometry() {
    let actor = EntityId::Pc(robin_engine::entity_id::PcId(2));
    let protected = EntityId::Pc(robin_engine::entity_id::PcId(3));
    let danger_point = engine_coordinates::WorldPoint3D::new(125.0, 150.0, 25.0);
    let queued = queue_shift_click_commands(
        vec![PlayerCommand::RaiseShieldWithDanger {
            actor,
            protected_pc: protected,
            danger_point,
            danger_point_layer: 6,
        }],
        Action::Shield,
        true,
    );
    assert!(matches!(
        queued.as_slice(),
        [PlayerCommand::QueueQuickAction {
            action: Action::Shield,
            command: QueuedQuickActionCommand::RaiseShieldWithDanger {
                actor: actual_actor,
                protected_pc: actual_protected,
                danger_point: actual_point,
                danger_point_layer: 6,
            },
        }] if *actual_actor == actor
            && *actual_protected == protected
            && *actual_point == danger_point
    ));

    let encoded = serde_json::to_value(&queued).expect("serialize queued shield command");
    let decoded: Vec<PlayerCommand> =
        serde_json::from_value(encoded).expect("deserialize queued shield command");
    assert_cmds!(decoded, queued);
}

#[test]
fn pattern_to_command_maps_every_thrust() {
    let cases = [
        (MouseWayPattern::ThrustA, Command::SwordstrikeThrustA),
        (MouseWayPattern::ThrustB, Command::SwordstrikeThrustB),
        (MouseWayPattern::ThrustC, Command::SwordstrikeThrustC),
        (MouseWayPattern::ThrustD, Command::SwordstrikeThrustD),
        (MouseWayPattern::ThrustE, Command::SwordstrikeThrustE),
        (MouseWayPattern::ThrustF, Command::SwordstrikeThrustF),
        (MouseWayPattern::ThrustG, Command::SwordstrikeThrustG),
        (MouseWayPattern::ThrustH, Command::SwordstrikeThrustH),
        (MouseWayPattern::ThrustI, Command::SwordstrikeThrustI),
    ];
    for (pattern, expected) in cases {
        assert_eq!(pattern_to_command(pattern), Some(expected));
    }
}

#[test]
fn pattern_to_command_rejects_non_strikes() {
    assert_eq!(pattern_to_command(MouseWayPattern::None), None);
    assert_eq!(pattern_to_command(MouseWayPattern::Attempt), None);
}

#[test]
fn shift_wraps_world_actions_but_not_selection_or_live_action_cleanup() {
    let pc = EntityId::Pc(robin_engine::entity_id::PcId(2));
    let commands = vec![
        PlayerCommand::SelectPc {
            pc_id: pc,
            append: true,
        },
        PlayerCommand::LaunchSelfAbility {
            actor: pc,
            command: Command::WhistleCmd,
        },
        PlayerCommand::UnselectAllActions,
        PlayerCommand::CancelAction { pc_id: pc },
    ];

    let queued = queue_shift_click_commands(commands, Action::Whistle, true);
    assert!(matches!(queued[0], PlayerCommand::SelectPc { .. }));
    assert!(matches!(
        queued[1],
        PlayerCommand::QueueQuickAction {
            action: Action::Whistle,
            ..
        }
    ));
    assert_eq!(queued.len(), 2);
}

#[test]
fn shift_queues_resolved_untie_interaction_without_re_resolving_it() {
    let pc = EntityId::Pc(robin_engine::entity_id::PcId(2));
    let target = EntityId::Soldier(robin_engine::entity_id::SoldierId(7));
    let queued = queue_shift_click_commands(
        vec![PlayerCommand::LaunchInteraction {
            actor: pc,
            target,
            command: Command::Untie,
            running: false,
        }],
        Action::Tie,
        true,
    );

    assert!(matches!(
        queued.as_slice(),
        [PlayerCommand::QueueQuickAction {
            action: Action::Tie,
            command: QueuedQuickActionCommand::LaunchInteraction {
                actor,
                target: queued_target,
                command: Command::Untie,
                running: false,
            },
        }] if *actor == pc && *queued_target == target
    ));
}

#[test]
fn shift_suppresses_unclassified_live_simulation_commands() {
    let pc = EntityId::Pc(robin_engine::entity_id::PcId(2));
    let queued = queue_shift_click_commands(
        vec![PlayerCommand::HeroSpeak {
            pc_id: pc,
            expression: engine_api::melee::HERO_UNABLE_TO_DO_SOMETHING,
        }],
        Action::NoAction,
        true,
    );
    assert!(queued.is_empty());
}

// ── resolve_left_click ──

#[test]
fn left_click_empty_ground_without_selection_is_noop_and_clears_cache() {
    let (engine, assets, mut host) = fixture();
    host.frontend.input.gestures.element_old_click =
        Some(EntityId::Pc(robin_engine::entity_id::PcId(3)));

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(100.0, 100.0),
        NO_MODS,
    );

    assert!(cmds.is_empty());
    assert_eq!(host.frontend.input.gestures.element_old_click, None);
}

#[test]
fn left_click_on_pc_without_selection_selects_it() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 50.0, 50.0, Posture::Upright);
    host.frontend.presentation.draw_order.ids.push(pc);

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(50.0, 50.0),
        NO_MODS,
    );

    assert_cmds!(
        cmds,
        vec![PlayerCommand::SelectPc {
            pc_id: pc,
            append: false
        }]
    );
    assert_eq!(host.frontend.input.gestures.element_old_click, Some(pc));
}

#[test]
fn left_click_shift_appends_to_selection() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 50.0, 50.0, Posture::Upright);
    host.frontend.presentation.draw_order.ids.push(pc);

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(50.0, 50.0),
        SHIFT,
    );

    assert_cmds!(
        cmds,
        vec![PlayerCommand::SelectPc {
            pc_id: pc,
            append: true
        }]
    );
}

#[test]
fn left_click_ctrl_on_unselected_pc_toggles_selection() {
    let (mut engine, assets, mut host) = fixture();
    let selected = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let other = add_pc(&mut engine, 200.0, 200.0, Posture::Upright);
    host.frontend
        .presentation
        .draw_order
        .ids
        .extend([selected, other]);
    select(&mut engine, &assets, selected);

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(200.0, 200.0),
        CTRL,
    );

    assert_cmds!(
        cmds,
        vec![PlayerCommand::TogglePcSelection { pc_id: other }]
    );
    assert_eq!(host.frontend.input.gestures.element_old_click, Some(other));
}

#[test]
fn left_click_ground_with_selection_issues_group_move() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    host.frontend
        .input
        .publish_spatial_hit(robin_engine::engine::SpatialHit {
            valid_position_for_move: true,
            selected_sector_idx: Some(robin_engine::fast_find_grid::SectorIndex::new(0).unwrap()),
            ..Default::default()
        });

    let dest = MapPoint::new(300.0, 300.0);
    let cmds = resolve_left_click_with_planning(&mut host, &engine, &assets, dest, NO_MODS);

    assert_cmds!(
        cmds,
        vec![PlayerCommand::GroupMove {
            actors: vec![pc],
            destination: dest,
            running: false,
            show_marker: true,
            goal_override: None,
            goal_sector_index_override: None,
            door_route_override: None,
            recorded_gate_routes: Vec::new(),
            recorded_failed_gate_routes: Vec::new(),
        }]
    );
    assert_eq!(host.frontend.input.gestures.element_old_click, None);
}

#[test]
fn double_click_ground_not_recording_accelerates_instead_of_moving() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    host.frontend
        .input
        .publish_spatial_hit(robin_engine::engine::SpatialHit {
            valid_position_for_move: true,
            selected_sector_idx: Some(robin_engine::fast_find_grid::SectorIndex::new(0).unwrap()),
            ..Default::default()
        });

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        DOUBLE,
    );

    assert_cmds!(cmds, vec![PlayerCommand::MakePcFast { pc_id: pc }]);
}

#[test]
fn double_click_ground_runs_allies_in_mixed_selection() {
    let (mut engine, assets, mut host) = fixture();
    let preferences = host.frontend.preferences();
    crate::host::FrontendPreferences::new(
        preferences.key_config().clone(),
        preferences.custom_key_config().clone(),
        robin_engine::gameplay_config::GameplayConfig {
            control_tactical_units: true,
            ..preferences.gameplay_config()
        },
        &robin_engine::graphic_config::GraphicConfig::default(),
    )
    .apply(&mut host.frontend);
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let ally = add_allied_soldier(&mut engine, 20.0, 20.0);
    select(&mut engine, &assets, pc);
    apply(
        &mut engine,
        &assets,
        PlayerCommand::SelectTacticalUnits {
            soldiers: vec![ally],
            append: false,
        },
    );
    host.frontend
        .input
        .publish_spatial_hit(robin_engine::engine::SpatialHit {
            valid_position_for_move: true,
            selected_sector_idx: Some(robin_engine::fast_find_grid::SectorIndex::new(0).unwrap()),
            ..Default::default()
        });

    let destination = MapPoint::new(300.0, 300.0);
    let commands =
        resolve_left_click_with_planning(&mut host, &engine, &assets, destination, DOUBLE);

    assert_cmds!(
        commands,
        vec![
            PlayerCommand::MakePcFast { pc_id: pc },
            PlayerCommand::MoveTacticalUnits {
                soldiers: vec![ally],
                destination,
                running: true,
                formation: TacticalFormation::Line,
            },
        ]
    );
}

#[test]
fn left_click_ground_without_valid_move_position_is_noop() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    // valid_position_for_move stays false.

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        NO_MODS,
    );

    assert!(cmds.is_empty());
}

#[test]
fn double_click_with_unavailable_armed_action_is_swallowed() {
    // No character profiles exist in the fixture, so any armed
    // action fails the availability pre-check and the double-click
    // must be dropped before dispatch.
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Whistle);
    assert_eq!(
        engine.selected_action_for_seat(host.transport.local_seat()),
        Action::Whistle
    );

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        DOUBLE,
    );

    assert!(cmds.is_empty());
}

// ── resolve_action_left_click (via resolve_left_click) ──

#[test]
fn whistle_click_launches_and_disarms() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Whistle);

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        NO_MODS,
    );

    assert_cmds!(
        cmds,
        vec![
            PlayerCommand::LaunchSelfAbility {
                actor: pc,
                command: Command::WhistleCmd,
            },
            PlayerCommand::UnselectAllActions,
        ]
    );
}

#[test]
fn eat_click_launches_eat_ability() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Eat);

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        NO_MODS,
    );

    assert_cmds!(
        cmds,
        vec![
            PlayerCommand::LaunchSelfAbility {
                actor: pc,
                command: Command::EatCmd,
            },
            PlayerCommand::UnselectAllActions,
        ]
    );
}

#[test]
fn listen_click_launches_enter_listen() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Listen);

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        NO_MODS,
    );

    assert_cmds!(
        cmds,
        vec![
            PlayerCommand::LaunchSelfAbility {
                actor: pc,
                command: Command::EnterListen,
            },
            PlayerCommand::UnselectAllActions,
        ]
    );
}

#[test]
fn purse_click_is_gated_on_valid_trajectory() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Purse);
    host.frontend.reject_trajectory_hit();

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        NO_MODS,
    );

    assert!(cmds.is_empty());
}

#[test]
fn net_click_is_gated_on_valid_trajectory() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Net);
    host.frontend.reject_trajectory_hit();

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        NO_MODS,
    );

    assert!(cmds.is_empty());
}

#[test]
fn beggar_double_click_while_simulating_accelerates() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::SimulatingBeggar);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Beggar);
    // The double-click availability pre-check would swallow this
    // (no profiles), so call the action resolver directly.
    let seat = host.transport.local_seat();
    let cmds = resolve_action_left_click(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        seat,
        Action::Beggar,
        DOUBLE,
    );

    assert_cmds!(cmds, vec![PlayerCommand::MakePcFast { pc_id: pc }]);
}

#[test]
fn beggar_click_from_default_posture_enters_beggar() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    let seat = host.transport.local_seat();

    let cmds = resolve_action_left_click(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        seat,
        Action::Beggar,
        NO_MODS,
    );

    assert_cmds!(
        cmds,
        vec![
            PlayerCommand::LaunchSelfAbility {
                actor: pc,
                command: Command::EnterBeggar,
            },
            PlayerCommand::UnselectAllActions,
        ]
    );
}

#[test]
fn help_to_climb_click_from_default_posture_launches() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    let seat = host.transport.local_seat();

    let cmds = resolve_action_left_click(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        seat,
        Action::HelpToClimb,
        NO_MODS,
    );

    assert_cmds!(
        cmds,
        vec![
            PlayerCommand::LaunchSelfAbility {
                actor: pc,
                command: Command::EnterHelpingClimb,
            },
            PlayerCommand::UnselectAllActions,
        ]
    );
}

#[test]
fn help_to_climb_click_while_helping_falls_through_to_walk() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::HelpingToClimb);
    select(&mut engine, &assets, pc);
    let seat = host.transport.local_seat();

    let cmds = resolve_action_left_click(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(300.0, 300.0),
        seat,
        Action::HelpToClimb,
        NO_MODS,
    );

    assert!(cmds.is_empty());
}

// ── resolve_right_click / resolve_right_click_stop ──

#[test]
fn right_click_without_selection_is_noop() {
    let (engine, _assets, host) = fixture();
    assert!(resolve_right_click(&engine, host.transport.local_seat()).is_empty());
}

#[test]
fn right_click_stops_idle_upright_pc() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);

    let cmds = resolve_right_click(&engine, host.transport.local_seat());
    assert_cmds!(cmds, vec![PlayerCommand::StopPc { pc_id: pc }]);
}

#[test]
fn right_click_parries_only_engaged_units_without_stopping_idle_selection() {
    let (mut engine, assets, _) = fixture();
    let idle = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let opponent = add_soldier(&mut engine, 20.0, 20.0, 100);
    let first = add_fighting_allied_soldier(&mut engine, 10.0, 10.0, opponent);
    let second = add_fighting_allied_soldier(&mut engine, 12.0, 10.0, opponent);
    select(&mut engine, &assets, idle);
    apply(
        &mut engine,
        &assets,
        PlayerCommand::SelectTacticalUnits {
            soldiers: vec![first, second],
            append: true,
        },
    );
    assert_eq!(engine.hero_selection(PlayerId(0)), &[idle]);
    assert_eq!(engine.tactical_selection(PlayerId(0)), &[first, second]);
    assert_cmds!(
        resolve_right_click(&engine, PlayerId(0)),
        vec![
            PlayerCommand::LaunchSelfAbility {
                actor: first,
                command: Command::ParrySword
            },
            PlayerCommand::LaunchSelfAbility {
                actor: second,
                command: Command::ParrySword
            },
            PlayerCommand::ClearTacticalSelection,
        ]
    );
}

#[test]
fn right_click_clears_allies_from_a_mixed_selection() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let soldier = add_allied_soldier(&mut engine, 20.0, 20.0);
    select(&mut engine, &assets, pc);
    select_allied(&mut engine, &assets, soldier);

    assert_cmds!(
        resolve_right_click(&engine, host.transport.local_seat()),
        vec![
            PlayerCommand::StopPc { pc_id: pc },
            PlayerCommand::ClearTacticalSelection,
        ]
    );
}

#[test]
fn exclusive_portrait_commands_switch_between_heroes_and_allied_groups() {
    let (mut engine, assets, _host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let soldier = add_allied_soldier(&mut engine, 20.0, 20.0);
    select_allied(&mut engine, &assets, soldier);
    apply(&mut engine, &assets, PlayerCommand::PinTacticalSelection);

    select(&mut engine, &assets, pc);
    assert_eq!(engine.hero_selection(PlayerId(0)), &[pc]);
    assert!(engine.tactical_selection(PlayerId(0)).is_empty());

    apply(
        &mut engine,
        &assets,
        PlayerCommand::SelectTacticalGroup {
            group_id: 1,
            append: false,
        },
    );
    assert!(engine.hero_selection(PlayerId(0)).is_empty());
    assert_eq!(engine.tactical_selection(PlayerId(0)), &[soldier]);
}

#[test]
fn right_click_drops_carried_corpse_when_idle() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::CarryingCorpse);
    select(&mut engine, &assets, pc);

    let cmds = resolve_right_click(&engine, host.transport.local_seat());
    assert_cmds!(
        cmds,
        vec![PlayerCommand::LaunchSelfAbility {
            actor: pc,
            command: Command::DropCorpse,
        }]
    );
}

#[test]
fn right_click_climbs_down_from_shoulders_when_idle() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::OnShoulders);
    select(&mut engine, &assets, pc);

    let cmds = resolve_right_click(&engine, host.transport.local_seat());
    assert_cmds!(
        cmds,
        vec![PlayerCommand::LaunchSelfAbility {
            actor: pc,
            command: Command::ClimbDownFromShoulders,
        }]
    );
}

#[test]
fn right_click_ignores_idle_climb_helper() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::HelpingToClimb);
    select(&mut engine, &assets, pc);

    let cmds = resolve_right_click(&engine, host.transport.local_seat());
    assert!(cmds.is_empty());
}

#[test]
fn right_click_with_generic_action_armed_only_disarms() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Apple);

    let cmds = resolve_right_click(&engine, host.transport.local_seat());
    assert_cmds!(cmds, vec![PlayerCommand::UnselectAllActions]);
}

#[test]
fn right_click_with_hit_action_stops_then_disarms() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Hit);

    let cmds = resolve_right_click(&engine, host.transport.local_seat());
    assert_cmds!(
        cmds,
        vec![
            PlayerCommand::StopPc { pc_id: pc },
            PlayerCommand::UnselectAllActions,
        ]
    );
}

#[test]
fn right_click_with_bow_armed_and_empty_queue_disarms() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Bow);

    let cmds = resolve_right_click(&engine, host.transport.local_seat());
    assert_cmds!(cmds, vec![PlayerCommand::UnselectAllActions]);
}

// ── resolve_action_drag ──

#[test]
fn drag_interactions_preserve_launch_and_completion_policy_for_every_action() {
    let actor = EntityId::Pc(robin_engine::entity_id::PcId(2));
    let target = EntityId::Soldier(robin_engine::entity_id::SoldierId(7));
    for (action, command, regular_tail, recording_tail) in [
        (
            Action::Apple,
            Command::ThrowApple,
            None,
            Some(PlayerCommand::StopRecordingMacro),
        ),
        (
            Action::Stone,
            Command::ThrowStone,
            None,
            Some(PlayerCommand::StopRecordingMacro),
        ),
        (Action::Hit, Command::HitCmd, None, None),
        (Action::HitHard, Command::HitCmd, None, None),
        (Action::Strangle, Command::StrangleCmd, None, None),
        (
            Action::Heal,
            Command::HealCmd,
            Some(PlayerCommand::UnselectAllActions),
            Some(PlayerCommand::StopRecordingMacro),
        ),
        (
            Action::Lever,
            Command::UseLever,
            Some(PlayerCommand::UnselectAllActions),
            Some(PlayerCommand::StopRecordingMacro),
        ),
    ] {
        for (recording, tail) in [(false, regular_tail), (true, recording_tail)] {
            let mut expected = vec![PlayerCommand::LaunchInteraction {
                actor,
                target,
                command,
                running: false,
            }];
            expected.extend(tail);
            assert_cmds!(
                drag_interaction_commands(actor, target, action, recording),
                expected
            );
        }
    }
}

#[test]
fn action_drag_without_armed_action_is_noop() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);

    let cmds = resolve_action_drag(&mut host, &engine, &assets, MapPoint::new(50.0, 50.0));
    assert!(cmds.is_empty());
}

#[test]
fn action_drag_respects_ignore_latch() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Hit);
    host.frontend.input.ignore_mouse_event(false, true, false);

    let cmds = resolve_action_drag(&mut host, &engine, &assets, MapPoint::new(50.0, 50.0));
    assert!(cmds.is_empty());
}

#[test]
fn action_drag_clears_stale_target_when_focus_lost() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Hit);
    host.frontend.input.gestures.target_drag = Some(pc);

    // Nothing focusable under the cursor: the stale drag target
    // must be cleared so a later re-hover can re-fire.
    let cmds = resolve_action_drag(&mut host, &engine, &assets, MapPoint::new(700.0, 700.0));
    assert!(cmds.is_empty());
    assert_eq!(host.frontend.input.gestures.target_drag, None);
}

// ── resolve_swordfight ──

#[test]
fn swordfight_resolution_requires_engaged_selection() {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);

    let cmds = resolve_swordfight(&mut host, &engine, &assets, MapPoint::new(50.0, 50.0), true);
    assert!(cmds.is_empty());
}

#[test]
fn swordfighter_query_borrows_only_an_engaged_selected_entity() {
    let (mut engine, assets, _) = fixture();
    let idle = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let opponent = add_soldier(&mut engine, 20.0, 20.0, 100);
    let allied = add_fighting_allied_soldier(&mut engine, 10.0, 10.0, opponent);
    assert!(first_selected_swordfighter(&engine.presentation_view(), PlayerId(0)).is_none());
    select(&mut engine, &assets, idle);
    assert!(first_selected_swordfighter(&engine.presentation_view(), PlayerId(0)).is_none());
    select_allied(&mut engine, &assets, allied);
    assert!(std::ptr::eq(
        first_selected_swordfighter(&engine.presentation_view(), PlayerId(0)).unwrap(),
        engine.get_entity(allied).unwrap()
    ));
    apply(&mut engine, &assets, PlayerCommand::ClearTacticalSelection);
    assert!(!is_selected_unit_swordfighting(
        &engine.presentation_view(),
        PlayerId(0)
    ));
}

#[test]
fn allied_soldier_swordfight_participates_in_gesture_input_and_parry() {
    let (mut engine, assets, mut host) = fixture();
    let opponent = add_soldier(&mut engine, 20.0, 20.0, 100);
    let soldier = add_fighting_allied_soldier(&mut engine, 10.0, 10.0, opponent);
    select_allied(&mut engine, &assets, soldier);

    assert!(is_selected_unit_swordfighting(
        &engine.presentation_view(),
        PlayerId(0)
    ));
    assert_cmds!(
        resolve_right_click(&engine, PlayerId(0)),
        vec![
            PlayerCommand::LaunchSelfAbility {
                actor: soldier,
                command: Command::ParrySword,
            },
            PlayerCommand::ClearTacticalSelection,
        ]
    );

    // A full circle is the game's Thrust-H gesture. It exercises the
    // gesture path without needing a seek-distance profile fixture.
    apply(
        &mut engine,
        &assets,
        PlayerCommand::SetCombatGestureRules {
            more_combat_gestures: false,
            gesture_quality_damage: false,
        },
    );
    for (x, y) in [
        (320.0, 280.0),
        (360.0, 320.0),
        (360.0, 340.0),
        (320.0, 350.0),
        (300.0, 340.0),
        (280.0, 340.0),
        (280.0, 320.0),
        (320.0, 290.0),
    ] {
        host.frontend
            .add_gesture_point(engine_coordinates::ScreenPoint::new(x, y));
    }
    assert_cmds!(
        resolve_swordfight(&mut host, &engine, &assets, MapPoint::new(0.0, 0.0), true,),
        vec![PlayerCommand::SwordStrikeCmd {
            actor: soldier,
            target: opponent,
            command: Command::SwordstrikeThrustH,
            composite: None,
            gesture_quality: GestureQuality::PERFECT,
            with_seek: false,
            seek_distance: None,
        }]
    );

    host.frontend.clear_gesture();
    apply(
        &mut engine,
        &assets,
        PlayerCommand::SetCombatGestureRules {
            more_combat_gestures: true,
            gesture_quality_damage: true,
        },
    );
    for &(x, y) in crate::mouse_way::composite_template(CompositeSwordTechnique::Vortex) {
        host.frontend
            .add_gesture_point(engine_coordinates::ScreenPoint::new(
                320.0 + x * 90.0,
                320.0 + y * 90.0,
            ));
    }
    assert_cmds!(
        resolve_swordfight(&mut host, &engine, &assets, MapPoint::new(0.0, 0.0), true,),
        vec![PlayerCommand::SwordStrikeCmd {
            actor: soldier,
            target: opponent,
            command: Command::SwordstrikeThrustH,
            composite: Some(CompositeSwordTechnique::Vortex),
            gesture_quality: GestureQuality::PERFECT,
            with_seek: false,
            seek_distance: None,
        }]
    );
}

#[test]
fn allied_box_selection_uses_ground_points_not_sprite_bounds() {
    let (mut engine, assets, _host) = fixture();
    let opponent = add_soldier(&mut engine, 100.0, 100.0, 100);
    let inside = add_fighting_allied_soldier(&mut engine, 10.0, 10.0, opponent);
    let outside = add_fighting_allied_soldier(&mut engine, -1.0, -1.0, opponent);

    apply(
        &mut engine,
        &assets,
        PlayerCommand::BoxSelectTacticalUnits {
            pt1: MapPoint::new(0.0, 0.0),
            pt2: MapPoint::new(20.0, 20.0),
            shift: false,
        },
    );

    assert_eq!(engine.tactical_selection(PlayerId(0)), &[inside]);
    assert_ne!(inside, outside);
}

// ── determine_use_command ──

#[test]
fn use_command_on_missing_target_is_none() {
    let (mut engine, assets, _host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let ghost = EntityId::Soldier(robin_engine::entity_id::SoldierId(99));

    assert_eq!(determine_use_command(&engine, &assets, pc, ghost), None);
}

#[test]
fn use_command_on_target_resolves_its_action_filter_before_dead_fallback() {
    let (mut engine, mut assets, _host) = fixture();
    // The target-use path classifies the selected PC's VIP flag, which
    // requires its character profile.
    std::sync::Arc::make_mut(&mut assets.profile_manager)
        .characters
        .push(engine_profiles::CharacterProfile::default());
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let target = engine.test_add_entity(Entity::Target(ElementTarget {
        element: {
            let mut initial_element = ElementData::default();
            initial_element.kind = ElementKind::Target;
            initial_element.active = true;
            initial_element
        },
        fx: FxData::default(),
        target: TargetData {
            action_filter: TargetFilter::CUT,
            ..Default::default()
        },
    }));

    assert_eq!(
        determine_use_command(&engine, &assets, pc, target),
        Some(Command::HitTarget)
    );
}

/// Selected PC at (10, 10) with `pc_profile`, and a lying soldier body at
/// (200, 200) carrying `money`, either dead or knocked out with positive
/// life. Both are in draw order and the campaign treasury holds 100.
fn body_search_fixture(
    pc_profile: engine_profiles::CharacterProfile,
    dead: bool,
    money: u32,
) -> (Engine, LevelAssets, Host, EntityId, EntityId) {
    body_search_fixture_with_vip(pc_profile, dead, money, false, false)
}

/// [`body_search_fixture`] with a VIP soldier profile and/or a Robin selector.
fn body_search_fixture_with_vip(
    pc_profile: engine_profiles::CharacterProfile,
    dead: bool,
    money: u32,
    vip_body: bool,
    pc_is_robin: bool,
) -> (Engine, LevelAssets, Host, EntityId, EntityId) {
    let mut campaign = engine_campaign::Campaign::default();
    campaign.set_value(engine_campaign::CampaignValue::Ransom, 100);
    let mut assets = LevelAssets::new();
    let mut engine =
        Engine::new_for_test(800.0, 600.0, campaign, &mut assets).expect("test engine");
    let profiles = std::sync::Arc::make_mut(&mut assets.profile_manager);
    profiles.characters.push(pc_profile);
    profiles.soldiers.push(engine_profiles::SoldierProfile {
        vip: vip_body,
        ..Default::default()
    });
    let mut host = Host::scratch(800.0, 600.0);

    let mut pc_element = ElementData::from_initial_posture(Posture::Upright);
    pc_element.kind = ElementKind::ActorPc;
    pc_element.active = true;
    pc_element.set_position_map(MapPoint::new(10.0, 10.0));
    pc_element.sprite.position_iface.settle_current_position();
    let pc = engine.test_add_entity(engine_element::Entity::Pc(engine_element::ActorPc {
        element: pc_element,
        actor: ActorData::default(),
        human: HumanData::default(),
        pc: engine_element::PcData {
            life_points: 100,
            playable: true,
            robin: pc_is_robin,
            ..Default::default()
        },
    }));
    let mut element = ElementData::from_initial_posture(Posture::Lying);
    element.kind = ElementKind::ActorSoldier;
    element.active = true;
    element.set_position_map(MapPoint::new(200.0, 200.0));
    element.sprite.position_iface.settle_current_position();
    let body = engine.test_add_entity(engine_element::Entity::Soldier(ActorSoldier {
        element,
        actor: ActorData::default(),
        human: HumanData {
            unconscious: !dead,
            ..Default::default()
        },
        npc: NpcData {
            life_points: if dead { 0 } else { 50 },
            ai: robin_engine::element::AiActorData {
                money,
                ..Default::default()
            },
        },
        soldier: SoldierData {
            cached_camp: robin_engine::element_kinds::Camp::Lacklandists,
            ..Default::default()
        },
    }));
    host.frontend.presentation.draw_order.ids.extend([pc, body]);
    select(&mut engine, &assets, pc);
    (engine, assets, host, pc, body)
}

fn searcher_profile(extra: &[Action]) -> engine_profiles::CharacterProfile {
    let mut contextual_actions =
        [Action::NoAction; engine_profiles::NUMBER_OF_PC_CONTEXTUAL_ACTIONS];
    contextual_actions[0] = Action::Search;
    contextual_actions[1..=extra.len()].copy_from_slice(extra);
    engine_profiles::CharacterProfile {
        contextual_actions,
        ..Default::default()
    }
}

fn click_body(host: &mut Host, engine: &Engine, assets: &LevelAssets) -> Vec<PlayerCommand> {
    resolve_left_click_with_planning(host, engine, assets, MapPoint::new(200.0, 200.0), NO_MODS)
}

fn body_use_focus(host: &Host, engine: &Engine, assets: &LevelAssets) -> Option<EntityId> {
    engine.find_focusable_entity(
        assets,
        &host.frontend.presentation.draw_order.ids,
        MapPoint::new(200.0, 200.0),
        Focus::Use,
    )
}

#[test]
fn click_on_rich_dead_or_unconscious_body_launches_search() {
    for dead in [true, false] {
        for money in [1, 49, 50, 125] {
            // Tie and Carry give the wrong-priority arms a chance to win.
            let (engine, assets, mut host, pc, body) = body_search_fixture(
                searcher_profile(&[Action::Tie, Action::LittleJohnCarry]),
                dead,
                money,
            );
            assert_eq!(body_use_focus(&host, &engine, &assets), Some(body));
            assert_eq!(
                engine.choose_use_cursor(&assets, body, Some(pc)),
                robin_engine::resource_ids::RHMOUSE_SEARCH,
                "dead={dead} money={money}"
            );
            assert_cmds!(
                click_body(&mut host, &engine, &assets),
                vec![PlayerCommand::LaunchInteraction {
                    actor: pc,
                    target: body,
                    command: Command::SearchCmd,
                    running: false,
                }]
            );
        }
    }
}

#[test]
fn use_command_on_empty_dead_body_carries_instead_of_searching() {
    let (engine, assets, _host, pc, body) =
        body_search_fixture(searcher_profile(&[Action::LittleJohnCarry]), true, 0);
    assert_eq!(
        determine_use_command(&engine, &assets, pc, body),
        Some(Command::TakeCorpse)
    );
}

#[test]
fn use_command_on_empty_unconscious_body_keeps_tie_fallback() {
    let (engine, assets, _host, pc, body) =
        body_search_fixture(searcher_profile(&[Action::Tie]), false, 0);
    assert_eq!(
        determine_use_command(&engine, &assets, pc, body),
        Some(Command::TieCmd)
    );
}

#[test]
fn use_command_on_rich_body_without_search_ability_is_not_search() {
    for dead in [true, false] {
        let (engine, assets, _host, pc, body) =
            body_search_fixture(engine_profiles::CharacterProfile::default(), dead, 125);
        assert_eq!(determine_use_command(&engine, &assets, pc, body), None);
    }
}

#[test]
fn only_robin_searches_a_rich_vip_body() {
    for robin in [false, true] {
        let (engine, assets, _host, pc, body) =
            body_search_fixture_with_vip(searcher_profile(&[]), false, 125, true, robin);
        assert_eq!(
            determine_use_command(&engine, &assets, pc, body),
            robin.then_some(Command::SearchCmd),
            "robin={robin}"
        );
    }
}

#[test]
fn use_command_on_bonus_is_take() {
    let (mut engine, assets, _host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let bonus = add_bonus(&mut engine, 60.0, 60.0);

    assert_eq!(
        determine_use_command(&engine, &assets, pc, bonus),
        Some(Command::Take)
    );
}

// ── resolve_double_click_repeat ──

#[test]
fn double_click_repeat_on_soldier_accelerates_when_not_recording() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    let soldier = add_soldier(&mut engine, 60.0, 60.0, 10);

    let cmds = resolve_double_click_repeat(&engine, &assets, soldier, host.transport.local_seat());
    assert_cmds!(cmds, vec![PlayerCommand::MakePcFast { pc_id: pc }]);
}

#[test]
fn double_click_repeat_preserves_hero_then_ally_order() {
    let (mut engine, assets, host) = fixture();
    let hero = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let ally = add_allied_soldier(&mut engine, 20.0, 20.0);
    let enemy = add_soldier(&mut engine, 60.0, 60.0, 100);
    select(&mut engine, &assets, hero);
    select_allied(&mut engine, &assets, ally);

    assert_cmds!(
        resolve_double_click_repeat(&engine, &assets, enemy, host.transport.local_seat()),
        vec![
            PlayerCommand::MakePcFast { pc_id: hero },
            PlayerCommand::MakePcFast { pc_id: ally },
        ]
    );
}

#[test]
fn allied_only_repeat_click_requires_a_hero_for_noncombat_interactions() {
    let (mut engine, assets, host) = fixture();
    let ally = add_allied_soldier(&mut engine, 20.0, 20.0);
    let enemy = add_soldier(&mut engine, 60.0, 60.0, 100);
    let bonus = add_bonus(&mut engine, 40.0, 40.0);
    let civilian = engine.test_add_entity(Entity::Civilian(robin_engine::element::ActorCivilian {
        element: ElementData::from_initial_posture(Posture::Upright),
        actor: ActorData::default(),
        human: HumanData::default(),
        npc: NpcData::default(),
        civilian: robin_engine::element::CivilianData::default(),
    }));
    select_allied(&mut engine, &assets, ally);
    let seat = host.transport.local_seat();
    assert!(engine.hero_selection(seat).is_empty());
    assert_eq!(engine.tactical_selection(seat), &[ally]);

    for target in [civilian, bonus] {
        assert!(resolve_double_click_repeat(&engine, &assets, target, seat).is_empty());
    }
    assert_cmds!(
        resolve_double_click_repeat(&engine, &assets, enemy, seat),
        vec![PlayerCommand::MakePcFast { pc_id: ally }]
    );
}

#[test]
fn double_click_repeat_on_missing_target_is_noop() {
    let (mut engine, assets, host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    select(&mut engine, &assets, pc);
    let ghost = EntityId::Soldier(robin_engine::entity_id::SoldierId(99));

    let cmds = resolve_double_click_repeat(&engine, &assets, ghost, host.transport.local_seat());
    assert!(cmds.is_empty());
}

/// Selected PC at (10, 10) whose character profile has the given VIP flag,
/// an idle beggar at (200, 200), both in draw order, and `ransom` in the
/// campaign treasury.
fn beggar_payment_fixture(
    pc_is_vip: bool,
    ransom: i32,
) -> (Engine, LevelAssets, Host, EntityId, EntityId) {
    let mut campaign = engine_campaign::Campaign::default();
    campaign.set_value(engine_campaign::CampaignValue::Ransom, ransom);
    let mut assets = LevelAssets::new();
    let mut engine =
        Engine::new_for_test(800.0, 600.0, campaign, &mut assets).expect("test engine");
    std::sync::Arc::make_mut(&mut assets.profile_manager)
        .characters
        .push(engine_profiles::CharacterProfile {
            vip: pc_is_vip,
            ..Default::default()
        });
    let mut host = Host::scratch(800.0, 600.0);

    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let mut element = ElementData::from_initial_posture(Posture::Upright);
    element.kind = ElementKind::ActorCivilian;
    element.active = true;
    element.set_position_map(MapPoint::new(200.0, 200.0));
    element.sprite.position_iface.settle_current_position();
    let beggar = engine.test_add_entity(engine_element::Entity::Civilian(
        engine_element::ActorCivilian {
            element,
            actor: ActorData::default(),
            human: HumanData::default(),
            npc: NpcData {
                life_points: 100,
                ..Default::default()
            },
            civilian: engine_element::CivilianData {
                // A non-hostile authored civilian loads as Royalist.
                cached_camp: robin_engine::element_kinds::Camp::Royalists,
                cached_civilian_type: engine_profiles::CivilianType::Beggar,
                beggar_scroll_sets: Some(vec![Vec::new(); 10]),
                ..Default::default()
            },
        },
    ));
    host.frontend
        .presentation
        .draw_order
        .ids
        .extend([pc, beggar]);
    select(&mut engine, &assets, pc);
    (engine, assets, host, pc, beggar)
}

fn click_beggar(host: &mut Host, engine: &Engine, assets: &LevelAssets) -> Vec<PlayerCommand> {
    resolve_left_click_with_planning(host, engine, assets, MapPoint::new(200.0, 200.0), NO_MODS)
}

fn is_pay(cmd: &PlayerCommand) -> bool {
    matches!(
        cmd,
        PlayerCommand::LaunchInteraction {
            command: Command::Pay,
            ..
        }
    )
}

#[test]
fn vip_pc_click_on_beggar_launches_pay() {
    let (engine, assets, mut host, pc, beggar) =
        beggar_payment_fixture(true, 2 * engine_api::BEGGAR_SALARY);
    let pc_entity = engine.get_entity(pc).expect("selected PC");
    assert!(engine.is_entity_vip(&assets, pc_entity));
    assert_eq!(
        engine.find_focusable_entity(
            &assets,
            &host.frontend.presentation.draw_order.ids,
            MapPoint::new(200.0, 200.0),
            Focus::Use,
        ),
        Some(beggar)
    );
    assert_eq!(
        engine.choose_use_cursor(&assets, beggar, Some(pc)),
        robin_engine::resource_ids::RHMOUSE_PAY_YES
    );

    let cmds = click_beggar(&mut host, &engine, &assets);
    assert_cmds!(
        cmds,
        vec![PlayerCommand::LaunchInteraction {
            actor: pc,
            target: beggar,
            command: Command::Pay,
            running: false,
        }]
    );
}

#[test]
fn vip_pc_below_beggar_salary_gets_pay_no_and_no_payment() {
    let (engine, assets, mut host, pc, beggar) =
        beggar_payment_fixture(true, engine_api::BEGGAR_SALARY - 1);
    assert_eq!(
        engine.choose_use_cursor(&assets, beggar, Some(pc)),
        robin_engine::resource_ids::RHMOUSE_PAY_NO
    );
    let cmds = click_beggar(&mut host, &engine, &assets);
    assert!(!cmds.iter().any(is_pay), "unexpected payment: {cmds:?}");
}

#[test]
fn non_vip_pc_cannot_pay_beggar() {
    let (engine, assets, mut host, pc, beggar) =
        beggar_payment_fixture(false, 2 * engine_api::BEGGAR_SALARY);
    let pc_entity = engine.get_entity(pc).expect("selected PC");
    assert!(!engine.is_entity_vip(&assets, pc_entity));
    assert_ne!(
        engine.choose_use_cursor(&assets, beggar, Some(pc)),
        robin_engine::resource_ids::RHMOUSE_PAY_YES
    );
    let cmds = click_beggar(&mut host, &engine, &assets);
    assert!(!cmds.iter().any(is_pay), "unexpected payment: {cmds:?}");
}

/// Selected PC at (10, 10) with Hit armed and a living civilian at
/// (200, 200) in the given camp (hostile profile attitude loads as
/// Lacklandists, friendly as Royalists).
fn punch_civilian_fixture(
    camp: robin_engine::element_kinds::Camp,
) -> (Engine, LevelAssets, Host, EntityId, EntityId) {
    let (mut engine, assets, mut host) = fixture();
    let pc = add_pc(&mut engine, 10.0, 10.0, Posture::Upright);
    let mut element = ElementData::from_initial_posture(Posture::Upright);
    element.kind = ElementKind::ActorCivilian;
    element.active = true;
    element.set_position_map(MapPoint::new(200.0, 200.0));
    element.sprite.position_iface.settle_current_position();
    let civilian = engine.test_add_entity(engine_element::Entity::Civilian(
        engine_element::ActorCivilian {
            element,
            actor: ActorData::default(),
            human: HumanData::default(),
            npc: NpcData {
                life_points: 100,
                ..Default::default()
            },
            civilian: engine_element::CivilianData {
                cached_camp: camp,
                cached_civilian_type: engine_profiles::CivilianType::Man,
                ..Default::default()
            },
        },
    ));
    host.frontend
        .presentation
        .draw_order
        .ids
        .extend([pc, civilian]);
    select(&mut engine, &assets, pc);
    arm_action(&mut engine, &assets, pc, Action::Hit);
    (engine, assets, host, pc, civilian)
}

#[test]
fn hit_click_on_hostile_noble_civilian_launches_punch() {
    let (engine, assets, mut host, pc, noble) =
        punch_civilian_fixture(robin_engine::element_kinds::Camp::Lacklandists);
    assert_eq!(
        engine.find_focusable_entity(
            &assets,
            &host.frontend.presentation.draw_order.ids,
            MapPoint::new(200.0, 200.0),
            Focus::Hit,
        ),
        Some(noble)
    );

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(200.0, 200.0),
        NO_MODS,
    );
    assert_cmds!(
        cmds,
        vec![PlayerCommand::LaunchInteraction {
            actor: pc,
            target: noble,
            command: Command::HitCmd,
            running: false,
        }]
    );
}

#[test]
fn hit_click_on_friendly_civilian_is_not_a_punch() {
    let (engine, assets, mut host, _pc, _civilian) =
        punch_civilian_fixture(robin_engine::element_kinds::Camp::Royalists);
    assert_eq!(
        engine.find_focusable_entity(
            &assets,
            &host.frontend.presentation.draw_order.ids,
            MapPoint::new(200.0, 200.0),
            Focus::Hit,
        ),
        None
    );

    let cmds = resolve_left_click_with_planning(
        &mut host,
        &engine,
        &assets,
        MapPoint::new(200.0, 200.0),
        NO_MODS,
    );
    assert!(
        !cmds.iter().any(|cmd| matches!(
            cmd,
            PlayerCommand::LaunchInteraction {
                command: Command::HitCmd,
                ..
            }
        )),
        "friendly civilian must not be punched: {cmds:?}"
    );
}
