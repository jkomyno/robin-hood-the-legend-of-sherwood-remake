use super::*;
use crate::element::{ActionState, Command, Entity, Posture};
use crate::engine::{Engine, EngineArgs, LevelLoadArgs, SimConfig};
use crate::sequence::SequenceElement;
use std::sync::Arc;

fn compiled_walkway(bytes: &[u8]) -> (EngineInner, LevelAssets) {
    let loaded = crate::level_data::LoadedLevel::hackable_from_json(bytes).unwrap();
    let mut assets = LevelAssets::new();
    let mut profiles = crate::profiles::ProfileManager::new();
    let mut campaign = crate::campaign::Campaign::new();
    let mission = campaign
        .force_next_mission_by_name(&mut profiles, "walkway", "walkway", true)
        .unwrap();
    campaign.current_mission_idx = Some(mission);
    assets.profile_manager = Arc::new(profiles);
    let engine = Engine::new(EngineArgs {
        campaign,
        level: LevelLoadArgs {
            assets: &mut assets,
            level_directory: "",
            progress: &mut |_| {},
            loaded,
            bg_pixel_dims: (2000., 2000.),
        },
        ground_mark_sprite: None,
        titbit_row_frame_counts: vec![],
        rng_seed: 0,
        original_rng_replay: None,
        sim_config: SimConfig {
            script_enabled: false,
            ..Default::default()
        },
    })
    .unwrap();
    ((*engine).clone(), assets)
}

#[test]
fn actor_ticks_cross_compiled_walkway_seams_and_update_height() {
    for (layer, sector_index, source, goal) in [
        (0, 0, MapPoint::new(396., 320.), MapPoint::new(404., 290.)),
        (0, 0, MapPoint::new(404., 290.), MapPoint::new(396., 320.)),
        (1, 1, MapPoint::new(510., 325.), MapPoint::new(510., 280.)),
        (1, 1, MapPoint::new(510., 280.), MapPoint::new(510., 325.)),
    ] {
        let (engine, assets) = compiled_walkway(include_bytes!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/fixtures/asset-navigation-copies.level.json"
        )));
        tick_walkway_crossing(engine, assets, layer, sector_index, source, goal);
    }
}

fn tick_walkway_crossing(
    mut engine: EngineInner,
    mut assets: LevelAssets,
    layer: u16,
    sector_index: usize,
    source: MapPoint,
    goal: MapPoint,
) -> (u32, f32) {
    let sector = &engine.world.fast_grid.level.sectors[sector_index];
    let handle = crate::position_interface::SectorHandle::new(u16::from(sector.sector_number))
        .unwrap()
        .with_arena_index(crate::fast_find_grid::SectorIndex::new(sector_index as u32).unwrap());
    let start_receiver = engine
        .get_projection_area_index(&assets, handle, layer, source)
        .unwrap();
    let end_receiver = engine
        .get_projection_area_index(&assets, handle, layer, goal)
        .unwrap();
    assert_ne!(start_receiver, end_receiver);
    let action = OrderType::WalkingUpright;
    let script = crate::sprite_script::SpriteScript {
        action_id: action as u16,
        action_done: 2,
        average_speed: 1.,
        hotspot: crate::coordinates::SpriteLocalPoint::ZERO,
        sum_distance: 3,
        frame_ids: vec![1, 2, 3],
        delays: vec![0; 3],
        distances: vec![1; 3],
        offsets: vec![crate::coordinates::SpriteFrameOffset::ZERO; 3],
        sound_ids: vec![0; 3],
    };
    let mut conversion = crate::engine::test_support::unmapped_conversion();
    conversion[action as usize] = 0;
    let mut pc = crate::engine::test_support::actors::unbound_pc(Posture::Upright);
    pc.element.sprite =
        crate::sprite::Sprite::new(Arc::new(vec![script; 16]), Arc::new(conversion));
    pc.element.active = true;
    pc.element.set_position_map(source);
    pc.element.set_sector(Some(handle));
    pc.element.set_layer(layer);
    pc.element
        .sprite
        .position_iface
        .set_move_box(crate::coordinates::MoveBox::from_corners(
            MapVec::new(-6., -4.),
            MapVec::new(6., 4.),
        ));
    pc.actor.action_state = ActionState::Moving;
    let owner = engine.add_test_entity(Entity::Pc(pc));
    crate::engine::complete_test_runtime_fixture(&mut engine, &mut assets);
    engine.set_obstacle_and_material(&assets, owner, Some(start_receiver));
    let mut movement = SequenceElement::new_movement(1, Command::MoveOk, Some(owner), action);
    let order_id = engine.orders.allocate_order_id();
    movement
        .orders
        .push_back(crate::order::Order::new(action, goal.x, goal.y, order_id));
    let sequence = engine.t_launch_in_progress(&assets, movement);
    engine.select_sequence_element(owner, Some((sequence, 0)));
    let mut samples = Vec::new();
    for _ in 0..200 {
        engine.t_tick_actor_owner_envelopes(&assets);
        let position = engine.ent(owner).element_data().position_map();
        samples.push(position);
        if (position - goal).length() < 0.01 {
            break;
        }
    }
    assert!(
        samples.iter().any(|p| *p != source),
        "actor never moved: {samples:?}"
    );
    let entity = engine.ent(owner);
    assert!(
        (entity.element_data().position_map() - goal).length() < 0.01,
        "actor did not arrive: {samples:?}"
    );
    assert_eq!(entity.position_iface().get_obstacle(), Some(end_receiver));
    let height = assets.environment.static_sight_obstacles[usize::from(end_receiver)]
        .compute_top_z_from_projection(goal.x, goal.y);
    assert!((entity.element_data().position().z - height).abs() < 0.001);
    assert!(
        samples.len() > 2,
        "movement must advance over multiple actor ticks"
    );
    (u32::from(end_receiver), height)
}

#[test]
fn actor_crosses_receivers_independently_of_switch_visibility() {
    for replacement in [false, true] {
        let mut descriptor: serde_json::Value = serde_json::from_slice(include_bytes!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/tests/fixtures/asset-navigation-copies.level.json"
        )))
        .unwrap();
        let geometry = &mut descriptor["asset_geometry"];
        let (initial, applied, expected_receiver) = if replacement {
            let mut higher = geometry["sight_obstacles"][0].clone();
            for point in higher["points"].as_array_mut().unwrap() {
                for axis in ["y", "z_top", "z_bottom"] {
                    point[axis] = serde_json::json!(point[axis].as_f64().unwrap() + 10.);
                }
            }
            geometry["sight_obstacles"]
                .as_array_mut()
                .unwrap()
                .push(higher);
            (vec![0], vec![4], 4)
        } else {
            (vec![], vec![0], 0)
        };
        geometry["movement_transitions"] = serde_json::json!([{
            "id":"receiver-visibility", "waypoint":[396,320], "sector":0, "layer":0,
            "active":true, "definitive":false, "apply_polygon":{"points":[]},
            "no_apply_polygon":{"points":[]}, "motion_changes":[],
            "initial_sight":initial, "applied_sight":applied
        }]);
        let bytes = serde_json::to_vec(&descriptor).unwrap();
        let mut heights = Vec::new();
        for state in 0..3 {
            let (mut engine, assets) = compiled_walkway(&bytes);
            let sim = crate::sim_rng::test_context();
            let patch = crate::patch::PatchIndex::new(0).unwrap();
            if state >= 1 {
                engine.apply_patch(TickCtx::new(&sim, &assets), patch);
            }
            if state == 2 {
                engine.reset_patch(TickCtx::new(&sim, &assets), patch);
            }
            assert_eq!(
                engine.world.static_sight_obstacle_active[expected_receiver],
                state == 1
            );
            let (receiver, height) = tick_walkway_crossing(
                engine,
                assets,
                0,
                0,
                MapPoint::new(396., 320.),
                MapPoint::new(404., 290.),
            );
            assert_eq!(receiver, expected_receiver as u32);
            heights.push(height);
        }
        assert!(
            heights
                .iter()
                .all(|height| (*height - heights[0]).abs() < 0.001)
        );
        assert!((heights[0] - if replacement { 74. } else { 64. }).abs() < 0.001);
    }
}
