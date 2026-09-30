//! Host-owned color/depth composition for rendered map states.
use robin_engine::engine::level_loading::{BackgroundAppearanceRegion, PreDecodedBackground};
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub(crate) struct MapAppearance {
    pub width: u16,
    pub height: u16,
    pub color: Vec<u16>,
    pub depth: Vec<u16>,
    regions: Vec<BackgroundAppearanceRegion>,
    selected: Vec<usize>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::Engine as _;
    use robin_engine::sbfile::SbFileSystem;
    use std::sync::Arc;

    fn fixture() -> (tempfile::TempDir, SbFileSystem) {
        let root = tempfile::tempdir().unwrap();
        let files: std::collections::BTreeMap<String, String> =
            serde_json::from_str(include_str!("../tests/fixtures/map-appearance.json")).unwrap();
        for (path, encoded) in files {
            let path = root.path().join(path);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(
                path,
                base64::engine::general_purpose::STANDARD
                    .decode(encoded)
                    .unwrap(),
            )
            .unwrap();
        }
        let files = SbFileSystem::new(Arc::new(robin_util::asset_fs::AssetVfs::new()));
        files
            .lock_ranked_verifier_primary_path(root.path())
            .unwrap();
        (root, files)
    }

    fn decode(files: &SbFileSystem) -> Result<PreDecodedBackground, String> {
        crate::level_loading_host::pre_decode_background_map_with_files(
            "appearance-contract",
            "Day",
            "Data/Levels",
            None,
            &mut |_| {},
            files,
        )
        .map(|background| background.unwrap())
    }

    #[test]
    fn editor_state_pngs_apply_combinations_and_reset_both_fields() {
        let (_root, files) = fixture();
        let background = decode(&files).unwrap();
        assert_eq!(background.appearance_regions.len(), 2);
        assert_eq!(background.appearance_regions[0].patches, [1, 0]);
        assert!(
            MapAppearance::new(&background, 1)
                .err()
                .unwrap()
                .contains("missing map patch")
        );
        let mut appearance = MapAppearance::new(&background, 2).unwrap().unwrap();
        assert!(!appearance.sync(|_| false));
        for (gate, roof, color, depth) in [
            (
                true,
                false,
                [65535, 0x07e0, 0xffe0, 0x07e0],
                [5, 2000, 4000, 2001],
            ),
            (
                true,
                true,
                [65535, 0x001f, 0xffe0, 0x001f],
                [5, 3000, 4000, 3001],
            ),
            (
                false,
                true,
                [65535, 0xf800, 65535, 0xf800],
                [5, 1000, 15, 1001],
            ),
            (false, false, [65535; 4], [5, 10, 15, 20]),
            (
                false,
                true,
                [65535, 0xf800, 65535, 0xf800],
                [5, 1000, 15, 1001],
            ),
        ] {
            assert!(appearance.sync(|index| if index == 0 { gate } else { roof }));
            assert_eq!(appearance.color, color);
            assert_eq!(appearance.depth, depth);
            assert!(!appearance.sync(|index| if index == 0 { gate } else { roof }));
        }
    }

    #[test]
    fn malformed_appearance_tables_fail_loading() {
        for (case, expected) in [
            (0, "outside"),
            (1, "overlapping"),
            (2, "state combinations"),
            (3, "state combinations"),
            (4, "missing appearance state"),
            (5, "dimensions"),
        ] {
            let (root, files) = fixture();
            let path = root
                .path()
                .join("Data/Levels/Day/appearance-contract.appearance.json");
            let mut manifest: serde_json::Value =
                serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
            match case {
                0 => manifest["regions"][0]["bounds"][0] = 2.into(),
                1 => manifest["regions"][1]["bounds"][0] = 1.into(),
                2 => manifest["regions"][0]["patches"][1] = 1.into(),
                3 => {
                    manifest["regions"][0]["states"]
                        .as_array_mut()
                        .unwrap()
                        .pop();
                }
                4 => manifest["regions"][0]["states"][1] = serde_json::Value::Null,
                5 => {
                    manifest["regions"][0]["states"][1]["color"] =
                        "Data/Levels/Day/appearance-contract.map.png".into()
                }
                _ => unreachable!(),
            }
            std::fs::write(path, serde_json::to_vec(&manifest).unwrap()).unwrap();
            assert!(
                decode(&files).err().unwrap().contains(expected),
                "case {case}"
            );
        }
    }
}

impl MapAppearance {
    pub fn new(
        background: &PreDecodedBackground,
        patch_count: usize,
    ) -> Result<Option<Self>, String> {
        if background.appearance_regions.is_empty() {
            return Ok(None);
        }
        let depth = background
            .occlusion_depth
            .as_ref()
            .ok_or("appearance map has no depth field")?;
        let size = usize::from(background.width) * usize::from(background.height);
        if background.pixels.len() != size || depth.len() != size {
            return Err("appearance base dimensions are invalid".into());
        }
        for region in &background.appearance_regions {
            if region
                .patches
                .iter()
                .any(|&index| usize::from(index) >= patch_count)
            {
                return Err("appearance region references a missing map patch".into());
            }
        }
        Ok(Some(Self {
            width: background.width,
            height: background.height,
            color: background.pixels.clone(),
            depth: depth.clone(),
            regions: background.appearance_regions.clone(),
            selected: vec![0; background.appearance_regions.len()],
        }))
    }

    /// Recompute from current simulation state rather than consuming one-shot events;
    /// this also restores visuals after loading a save or seeking a replay.
    pub fn sync(&mut self, applied: impl Fn(u16) -> bool) -> bool {
        let mut changed = false;
        for (region, selected) in self.regions.iter().zip(&mut self.selected) {
            let state = region
                .patches
                .iter()
                .enumerate()
                .fold(0, |state, (bit, &patch)| {
                    state | (usize::from(applied(patch)) << bit)
                });
            if state == *selected {
                continue;
            }
            let pixels = &region.states[state];
            let [x, y, w, h] = region.bounds.map(usize::from);
            for row in 0..h {
                let destination = (y + row) * usize::from(self.width) + x;
                let source = row * w;
                self.color[destination..destination + w]
                    .copy_from_slice(&pixels.color[source..source + w]);
                self.depth[destination..destination + w]
                    .copy_from_slice(&pixels.depth[source..source + w]);
            }
            *selected = state;
            changed = true;
        }
        changed
    }
}
