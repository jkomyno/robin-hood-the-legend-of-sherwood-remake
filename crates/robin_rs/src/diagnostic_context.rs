//! Bounded native diagnostic breadcrumbs, independent of live engine state.
use serde::{Deserialize, Serialize};
use std::sync::{LazyLock, Mutex};
use std::time::Instant;

static STARTED: LazyLock<Instant> = LazyLock::new(Instant::now);
static CONTEXT: Mutex<Context> = Mutex::new(Context::new());

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Stage {
    Startup,
    DataInitialization,
    WindowInitialization,
    GameInitialization,
    MainMenu,
    MissionLoading,
    MissionFrame,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Launch {
    headless: bool,
    replay: bool,
    multiplayer: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Gpu {
    name: String,
    backend: String,
    device_type: String,
    driver: String,
    driver_info: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Context {
    stage: Stage,
    launch: Option<Launch>,
    mission: Option<String>,
    frame: Option<u32>,
    selected_datadir: Option<String>,
    core_overlay: Option<String>,
    mounted_mod_overlays: Vec<String>,
    omitted_mod_overlays: usize,
    gpu: Option<Gpu>,
}
impl Context {
    const fn new() -> Self {
        Self {
            stage: Stage::Startup,
            launch: None,
            mission: None,
            frame: None,
            selected_datadir: None,
            core_overlay: None,
            mounted_mod_overlays: Vec::new(),
            omitted_mod_overlays: 0,
            gpu: None,
        }
    }
    fn begin_mission(&mut self, name: &str) {
        self.mission = Some(bounded(name));
        self.frame = None;
        self.stage = Stage::MissionLoading;
    }
    fn main_menu(&mut self) {
        self.mission = None;
        self.frame = None;
        self.stage = Stage::MainMenu;
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct Snapshot {
    schema_version: u32,
    process_id: u32,
    uptime_ms: u128,
    capture_thread: Option<String>,
    context: Option<Context>,
    unavailable_reason: Option<String>,
}

fn bounded(value: &str) -> String {
    super::bug_report::bound_text(value.into(), 2048)
}
fn update(action: impl FnOnce(&mut Context)) {
    match CONTEXT.lock() {
        Ok(mut context) => action(&mut context),
        Err(error) => tracing::warn!("Diagnostic context update unavailable: {error}"),
    }
}
fn multiplayer(server: bool, client: bool) -> String {
    if server {
        "host"
    } else if client {
        "client"
    } else {
        "local"
    }
    .into()
}
/// Record only selected flags; raw arguments may contain invitation credentials.
pub fn initialize(args: &crate::main_entry::CliArgs) {
    LazyLock::force(&STARTED);
    update(|context| {
        context.launch = Some(Launch {
            headless: args.headless,
            replay: args.replay.is_some(),
            multiplayer: multiplayer(args.server, args.connect.is_some() || args.join.is_some()),
        });
    });
}
pub fn set_stage(stage: Stage) {
    update(|context| context.stage = stage);
}
pub(crate) fn selected_datadir(path: &str) {
    update(|context| context.selected_datadir = Some(bounded(path)));
}
pub(crate) fn core_overlay(path: &std::path::Path) {
    update(|context| context.core_overlay = Some(bounded(&path.to_string_lossy())));
}
pub(crate) fn mounted_mod_overlay(path: &std::path::Path) {
    update(|context| {
        if context.mounted_mod_overlays.len() < 64 {
            context
                .mounted_mod_overlays
                .push(bounded(&path.to_string_lossy()));
        } else {
            context.omitted_mod_overlays += 1;
        }
    });
}
pub(crate) fn gpu(info: &wgpu::AdapterInfo) {
    update(|context| {
        context.gpu = Some(Gpu {
            name: bounded(&info.name),
            backend: format!("{:?}", info.backend),
            device_type: format!("{:?}", info.device_type),
            driver: bounded(&info.driver),
            driver_info: bounded(&info.driver_info),
        })
    });
}
pub(crate) fn begin_mission(name: &str, args: &crate::main_entry::MissionRequest) {
    crate::bug_report::clear_replay();
    update(|context| {
        context.begin_mission(name);
        context.launch = Some(Launch {
            headless: args.config.cli.headless,
            replay: args.replay.is_some() || args.replay_data.is_some(),
            multiplayer: multiplayer(
                args.multiplayer.server,
                args.multiplayer.connect.is_some() || args.multiplayer.join.is_some(),
            ),
        });
    });
}
pub(crate) fn main_menu() {
    crate::bug_report::clear_replay();
    update(Context::main_menu);
}
pub(crate) fn frame(number: u32) {
    update(|context| {
        context.frame = Some(number);
        context.stage = Stage::MissionFrame;
    });
}
fn snapshot(context: &Mutex<Context>) -> Snapshot {
    // Panic hooks may run on the thread that already holds this lock.
    let (context, unavailable_reason) = match context.try_lock() {
        Ok(context) => (Some(context.clone()), None),
        Err(error) => (None, Some(error.to_string())),
    };
    Snapshot {
        schema_version: 1,
        process_id: std::process::id(),
        uptime_ms: STARTED.elapsed().as_millis(),
        capture_thread: std::thread::current().name().map(bounded),
        context,
        unavailable_reason,
    }
}
pub(crate) fn attachment()
-> serde_json::Result<robin_run_protocol::diagnostics::DiagnosticAttachmentV1> {
    Ok(robin_run_protocol::diagnostics::DiagnosticAttachmentV1 {
        filename: "native-context.json".into(),
        content: serde_json::to_string(&snapshot(&CONTEXT))?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn context_survives_roundtrip_and_clears_between_missions() {
        let mut context = Context::new();
        assert_eq!(context.stage, Stage::Startup);
        assert!(context.mission.is_none());
        context.begin_mission("Derby");
        context.frame = Some(123);
        let value = snapshot(&Mutex::new(context.clone()));
        let decoded: Snapshot =
            serde_json::from_str(&serde_json::to_string(&value).unwrap()).unwrap();
        assert_eq!(decoded.context.unwrap().frame, Some(123));
        context.main_menu();
        assert!(context.mission.is_none());
        assert!(context.frame.is_none());
        context.begin_mission("Lincoln");
        assert_eq!(context.mission.as_deref(), Some("Lincoln"));
        assert!(context.frame.is_none());
    }
    #[test]
    fn snapshot_does_not_wait_for_held_lock() {
        let context = Mutex::new(Context::new());
        let guard = context.lock().unwrap();
        let value = snapshot(&context);
        assert!(value.context.is_none());
        assert!(value.unavailable_reason.is_some());
        drop(guard);
    }
    #[test]
    fn strings_are_bounded_at_utf8_boundaries() {
        let text = bounded(&"界".repeat(4000));
        assert!(text.len() <= 2048);
        assert!(text.ends_with('界'));
    }
}
