use super::{decode_hackable_terrain_png, decode_occlusion_depth_png, decode_rgb565_words};
use robin_engine::engine::level_loading::{BackgroundAppearancePixels, BackgroundAppearanceRegion};
use robin_engine::sbfile::SbFileSystem;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest {
    version: u32,
    regions: Vec<Region>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Region {
    bounds: [u16; 4],
    patches: Vec<u16>,
    states: Vec<Option<Images>>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Images {
    color: String,
    depth: String,
}

pub(super) fn decode(
    files: &SbFileSystem,
    path: &str,
    width: u16,
    height: u16,
    base_color: &[u16],
    base_depth: Option<&[u16]>,
) -> Result<Vec<BackgroundAppearanceRegion>, String> {
    let bytes = files
        .read_shared(path)
        .map_err(|e| format!("appearance manifest '{path}': {e}"))?;
    let manifest: Manifest =
        serde_json::from_slice(&bytes).map_err(|e| format!("appearance manifest '{path}': {e}"))?;
    if manifest.version != 1 || manifest.regions.is_empty() {
        return Err("invalid map appearance version or empty region table".into());
    }
    let base_depth = base_depth.ok_or("map appearances require a base occlusion-depth image")?;
    let mut output = Vec::<BackgroundAppearanceRegion>::new();
    for region in manifest.regions {
        let [x, y, w, h] = region.bounds.map(usize::from);
        if w == 0 || h == 0 || x + w > usize::from(width) || y + h > usize::from(height) {
            return Err("appearance region is outside the map".into());
        }
        if output.iter().any(|other| {
            let [px, py, pw, ph] = other.bounds.map(usize::from);
            x < px + pw && px < x + w && y < py + ph && py < y + h
        }) {
            return Err("overlapping appearance regions need a combined state table".into());
        }
        if region.patches.is_empty()
            || region.patches.len() > 16
            || region
                .patches
                .iter()
                .enumerate()
                .any(|(i, patch)| region.patches[..i].contains(patch))
            || region.states.len() != 1usize << region.patches.len()
            || region.states[0].is_some()
        {
            return Err("invalid appearance patch bindings or state combinations".into());
        }
        let mut states = Vec::with_capacity(region.states.len());
        let mut initial = BackgroundAppearancePixels {
            color: Vec::with_capacity(w * h),
            depth: Vec::with_capacity(w * h),
        };
        for row in y..y + h {
            let start = row * usize::from(width) + x;
            initial
                .color
                .extend_from_slice(&base_color[start..start + w]);
            initial
                .depth
                .extend_from_slice(&base_depth[start..start + w]);
        }
        states.push(initial);
        for images in region.states.into_iter().skip(1) {
            let images = images.ok_or("missing appearance state images")?;
            let color_bytes = files
                .read_shared(&images.color)
                .map_err(|e| format!("appearance color '{}': {e}", images.color))?;
            let picture = decode_hackable_terrain_png(&color_bytes, &images.color)?;
            if usize::from(picture.width) != w || usize::from(picture.height) != h {
                return Err("appearance color dimensions differ from its region".into());
            }
            let depth_bytes = files
                .read_shared(&images.depth)
                .map_err(|e| format!("appearance depth '{}': {e}", images.depth))?;
            states.push(BackgroundAppearancePixels {
                color: decode_rgb565_words(&picture.data),
                depth: decode_occlusion_depth_png(
                    &depth_bytes,
                    &images.depth,
                    picture.width,
                    picture.height,
                )?,
            });
        }
        output.push(BackgroundAppearanceRegion {
            bounds: region.bounds,
            patches: region.patches,
            states,
        });
    }
    Ok(output)
}
