use crate::level_data::{
    MASK_CHARACTER, MASK_OBSTACLE, MASK_PROJECTILE, MASK_VIEW, MaskRef, RawMask, RawMotionData,
};

/// Validate compiler output before runtime decoding can skip an invalid mask
/// and change the per-layer indices used by state transitions.
pub(crate) fn validate_compiled_masks(
    masks: &[RawMask],
    motion: &RawMotionData,
    obstacle_count: usize,
) -> Result<Vec<MaskRef>, String> {
    if masks.len() > 65536 {
        return Err("too many compiled masks".into());
    }
    let mut counts = vec![0usize; motion.layers.len()];
    masks
        .iter()
        .enumerate()
        .map(|(index, mask)| {
            validate_mask(mask, obstacle_count)
                .map_err(|reason| format!("invalid compiled mask {index}: {reason}"))?;
            let layer = usize::from(mask.layer);
            if motion.layers.get(layer).is_none_or(Vec::is_empty) {
                return Err(format!("compiled mask {index} references a missing layer"));
            }
            let reference = MaskRef {
                layer: mask.layer,
                index: u16::try_from(counts[layer]).map_err(|_| "too many masks in one layer")?,
            };
            counts[layer] += 1;
            Ok(reference)
        })
        .collect()
}

fn validate_mask(mask: &RawMask, obstacle_count: usize) -> Result<(), &'static str> {
    if mask.mask_type == 0
        || mask.mask_type & !(MASK_CHARACTER | MASK_PROJECTILE | MASK_VIEW | MASK_OBSTACLE) != 0
    {
        return Err("unsupported mask type");
    }
    let obstacle = mask.mask_type & MASK_OBSTACLE != 0;
    if obstacle && (mask.mask_type & MASK_PROJECTILE == 0 || mask.obstacle_indices.is_empty())
        || !obstacle && !mask.obstacle_indices.is_empty()
        || mask
            .obstacle_indices
            .iter()
            .any(|&index| usize::from(index) >= obstacle_count)
    {
        return Err("invalid obstacle links");
    }
    for (flag, polyline) in [
        (MASK_CHARACTER, &mask.character_polyline),
        (MASK_PROJECTILE, &mask.projectile_polyline),
    ] {
        if mask.mask_type & flag == 0 {
            if polyline.is_some() {
                return Err("polyline without its mask type");
            }
            continue;
        }
        let points = polyline.as_ref().ok_or("missing masking polyline")?;
        // Obstacle-backed projectile masks may rely exclusively on their
        // altitude test, with an explicitly empty projectile polyline.
        if points.is_empty() && flag == MASK_PROJECTILE && obstacle {
            continue;
        }
        if points.len() < 2
            || points.windows(2).any(|pair| pair[0].0 > pair[1].0)
            || points.first().unwrap().0 == points.last().unwrap().0
        {
            return Err("masking polyline must span increasing X coordinates");
        }
    }
    let (width, height) = mask.box_size;
    if width <= 0
        || height <= 0
        || i16::try_from(i32::from(mask.box_top_left.0) + i32::from(width)).is_err()
        || i16::try_from(i32::from(mask.box_top_left.1) + i32::from(height)).is_err()
    {
        return Err("invalid mask bounds");
    }
    validate_bitmap(&mask.mask_data, width as usize, height as usize)
}

fn validate_bitmap(bytes: &[u8], width: usize, height: usize) -> Result<(), &'static str> {
    let mut offset = 0;
    for _ in 0..height {
        let length = usize::from(*bytes.get(offset).ok_or("missing bitmap row")?);
        offset += 1;
        let end = offset + length;
        if end > bytes.len() {
            return Err("truncated bitmap row");
        }
        let mut blocks = 0;
        while offset < end {
            let control = bytes[offset];
            offset += 1;
            let count = usize::from(control & 0x7f);
            if count == 0 {
                return Err("empty bitmap run");
            }
            blocks += count;
            offset += if control & 0x80 != 0 { 1 } else { count };
            if offset > end || blocks > width.div_ceil(8) {
                return Err("bitmap run exceeds its row");
            }
        }
        // Missing trailing blocks are transparent, including a zero-length row.
    }
    if offset != bytes.len() {
        return Err("unexpected trailing bitmap bytes");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bitmap_rows_accept_compressed_raw_and_transparent_tails() {
        for bytes in [
            vec![2, 0x82, 0xaa],
            vec![3, 2, 0xaa, 0x80],
            vec![2, 1, 0xaa],
            vec![0],
        ] {
            assert_eq!(validate_bitmap(&bytes, 9, 1), Ok(()));
        }
    }

    #[test]
    fn bitmap_rows_reject_truncation_overflow_and_ignored_bytes() {
        for bytes in [
            vec![],
            vec![2, 0x81],
            vec![2, 2, 0xff],
            vec![2, 0x83, 0xff],
            vec![1, 0],
            vec![0, 0],
        ] {
            assert!(validate_bitmap(&bytes, 9, 1).is_err(), "{bytes:?}");
        }
    }
}
