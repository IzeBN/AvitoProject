// src-tauri/src/lib.rs
mod commands;
use commands::{auth, window, notify};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_dialog::init())
        // updater требует конфигурацию pubkey — включить перед релизом
        //.plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            auth::get_token,
            auth::set_token,
            auth::clear_token,
            window::save_window_geometry,
            window::load_window_geometry,
            notify::send_notification,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
