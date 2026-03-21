use serde::{Deserialize, Serialize};
use tauri::{command, AppHandle};
use tauri_plugin_store::StoreExt;

#[derive(Serialize, Deserialize)]
pub struct WindowState {
    pub width: f64,
    pub height: f64,
    pub x: i32,
    pub y: i32,
    pub maximized: bool,
}

#[command]
pub fn save_window_geometry(app: AppHandle, state: WindowState) {
    if let Ok(store) = app.store("window_state.json") {
        store.set("state", serde_json::to_value(state).unwrap());
        let _ = store.save();
    }
}

#[command]
pub fn load_window_geometry(app: AppHandle) -> Option<WindowState> {
    let store = app.store("window_state.json").ok()?;
    let val = store.get("state")?;
    serde_json::from_value(val).ok()
}
