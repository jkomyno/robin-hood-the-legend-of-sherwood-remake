//! The fixture is produced by the editor's browser bake acceptance test.
//! It exercises the same archive discovery and terrain decoders as installed mods.

use std::sync::Arc;

use robin_engine::level_data::LoadedLevel;
use robin_engine::sbfile::SbFileSystem;
use robin_rs::level_loading_host::{
    pre_decode_background_map_with_files, pre_decode_minimap_with_files,
};
use robin_rs::mod_pack::{enumerate_missions, mount_mod_overlay, scan_mods_dir};
use robin_util::asset_fs::AssetVfs;

#[test]
fn browser_compiled_map_loads_geometry_without_mission_spawns() {
    let directory = tempfile::tempdir().unwrap();
    let archive = directory.path().join("editor-bake-contract.zip");
    std::fs::write(
        &archive,
        include_bytes!("fixtures/editor-bake-contract.zip"),
    )
    .unwrap();
    let mods = scan_mods_dir(directory.path());
    assert_eq!(mods.len(), 1);
    assert_eq!(mods[0].details.hackable_missions, ["editor-bake-contract"]);
    let files = SbFileSystem::new(Arc::new(AssetVfs::new()));
    mount_mod_overlay(&files, &archive).unwrap();
    let missions = enumerate_missions(&mods, &files);
    assert_eq!(missions.len(), 1);
    assert!(missions[0].hackable);

    let bytes = files
        .read_shared("Data/Levels/editor-bake-contract.level.json")
        .unwrap();
    let level = LoadedLevel::hackable_from_json(&bytes).unwrap();
    assert_eq!(level.mission.header.map_filename, "editor-bake-contract");
    assert!(level.mission.beam_mes.is_empty());
    assert_eq!(level.proto.sight_obstacles.len(), 1);
    let point = &level.proto.sight_obstacles[0].points[0];
    assert_eq!((point.x, point.y, point.z_top), (20.0, 40.0, 20.0));
    let motion = level.proto.motion_data.as_ref().unwrap();
    assert_eq!(motion.layers[0][0].obstacles.len(), 1);
    assert!(motion.layers[1].is_empty());

    let background = pre_decode_background_map_with_files(
        "editor-bake-contract",
        "Day",
        "Data/Levels",
        None,
        &mut |_| {},
        &files,
    )
    .unwrap()
    .unwrap();
    assert_eq!((background.width, background.height), (1100, 128));
    assert_eq!(background.pixels[30 * 1100 + 30], 0xf800);
    assert_eq!(background.pixels[30 * 1100 + 1023], 0x07e0);
    assert_eq!(background.pixels[30 * 1100 + 1024], 0x07e0);
    let depth = background.occlusion_depth.unwrap();
    let expected = ((50.5_f32 / 128.0) * 65535.0).round() as u16;
    assert!(depth[30 * 1100 + 30].abs_diff(expected) <= 2);
    let minimap = pre_decode_minimap_with_files(
        "editor-bake-contract",
        "Day",
        "Data/Levels",
        None,
        &mut |_| {},
        &files,
    )
    .unwrap();
    assert_eq!((minimap.width, minimap.height), (79, 9));
}
