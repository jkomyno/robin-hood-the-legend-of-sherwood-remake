//! Sticky touch control for automatic quick-action planning.

use crate::renderer::Renderer;

pub const WIDTH: i32 = 118;
pub const HEIGHT: i32 = 34;

/// One browser build serves both mouse and touch devices, so the web HUD
/// follows the session's input rather than the compile target. It is sticky:
/// once a session is known to use touch, it keeps the control.
#[cfg(target_arch = "wasm32")]
static BROWSER_TOUCH_SESSION: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);

/// Whether the sticky plan/cancel control is shown and accepts presses.
/// Mobile builds always have it; desktop builds never do; browsers only for
/// touch sessions (see [`detect_browser_touch_session`] and
/// [`note_touch_input`]).
pub fn touch_planning_hud_active() -> bool {
    cfg!(any(target_os = "android", target_os = "ios")) || browser_touch_session()
}

#[cfg(target_arch = "wasm32")]
fn browser_touch_session() -> bool {
    BROWSER_TOUCH_SESSION.load(std::sync::atomic::Ordering::Relaxed)
}

#[cfg(not(target_arch = "wasm32"))]
fn browser_touch_session() -> bool {
    false
}

/// Show the control from the start when the primary pointer is coarse
/// (phones, tablets). Must run on the browser main thread.
#[cfg(target_arch = "wasm32")]
pub fn detect_browser_touch_session() {
    let window = web_sys::window().expect("browser window");
    let coarse = match window.match_media("(pointer: coarse)") {
        Ok(Some(query)) => query.matches(),
        Ok(None) => false,
        Err(error) => {
            tracing::warn!(
                ?error,
                "pointer media query failed; waiting for touch input"
            );
            false
        }
    };
    if coarse {
        BROWSER_TOUCH_SESSION.store(true, std::sync::atomic::Ordering::Relaxed);
    }
}

/// Record actual touch input, covering touchscreen laptops whose primary
/// pointer is a mouse or trackpad. The press that reveals the control is
/// still delivered to the world as usual.
pub fn note_touch_input() {
    #[cfg(target_arch = "wasm32")]
    BROWSER_TOUCH_SESSION.store(true, std::sync::atomic::Ordering::Relaxed);
}

/// The original's top-right cluster starts at `width - 100`: Sight (or the
/// Sherwood campaign-map button), the parchment ornament, and the zoom buttons
/// at `width - 26`. The control sits just left of it so none of those widgets
/// lose presses to it.
const TOP_RIGHT_CLUSTER_INSET: i32 = 100;
const CLUSTER_GAP: i32 = 8;

pub fn rect(screen_width: u16) -> (i32, i32, i32, i32) {
    let right = i32::from(screen_width).saturating_sub(TOP_RIGHT_CLUSTER_INSET + CLUSTER_GAP);
    (right - WIDTH, 46, right, 46 + HEIGHT)
}

pub fn hit_test(screen_width: u16, x: i32, y: i32) -> bool {
    let (left, top, right, bottom) = rect(screen_width);
    (left..=right).contains(&x) && (top..=bottom).contains(&y)
}

pub fn render(renderer: &mut Renderer, fonts: Option<&crate::hud_text::HudFonts>, active: bool) {
    if !touch_planning_hud_active() {
        return;
    }
    let (left, top, right, bottom) = rect(renderer.screen_width());
    let border = if active {
        Renderer::create_color_16(238, 192, 55)
    } else {
        Renderer::create_color_16(224, 211, 157)
    };
    renderer.draw_rect_outline_screen(left, top, right, bottom, border);
    renderer.draw_rect_outline_screen(left + 2, top + 2, right - 2, bottom - 2, border);
    if let Some(fonts) = fonts {
        let label = if active {
            "CANCEL PLAN"
        } else {
            "PLAN ACTIONS"
        };
        let width = fonts.tooltip_font.text_width(label);
        crate::ingame_menu::layout::render_text_screen_font(
            renderer,
            &fonts.tooltip_font,
            label,
            left + (WIDTH - width) / 2,
            top + (HEIGHT - fonts.tooltip_font.height() as i32) / 2,
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hit_box_tracks_right_edge_and_includes_boundary() {
        let (left, top, right, bottom) = rect(1024);
        assert!(hit_test(1024, left, top));
        assert!(hit_test(1024, right, bottom));
        assert!(!hit_test(1024, left - 1, top));
    }

    #[test]
    fn control_leaves_original_top_right_widgets_reachable() {
        for screen_width in [640u16, 800, 1024, 1264, 1920] {
            let (left, top, right, bottom) = rect(screen_width);
            let sw = i32::from(screen_width);
            assert!(left >= 0 && right < sw - TOP_RIGHT_CLUSTER_INSET);
            let zoom = crate::zoom_hud::ZoomHudLayout::for_screen_width(
                u32::from(screen_width),
                &crate::zoom_hud::ZoomButtonSprites::default(),
            );
            for button in [zoom.zoom_up, zoom.zoom_down] {
                for (x, y) in [
                    (button.left(), button.top()),
                    (button.left(), button.bottom() - 1),
                ] {
                    assert!(!hit_test(screen_width, x, y), "{screen_width}: ({x}, {y})");
                }
            }
            assert!(bottom > top);
        }
    }

    #[test]
    fn desktop_builds_never_show_the_control() {
        note_touch_input();
        assert_eq!(
            touch_planning_hud_active(),
            cfg!(any(target_os = "android", target_os = "ios"))
        );
    }
}
