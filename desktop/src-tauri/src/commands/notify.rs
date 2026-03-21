use tauri::command;
use tauri_plugin_notification::NotificationExt;

#[command]
pub fn send_notification(app: tauri::AppHandle, title: String, body: String) {
    let _ = app
        .notification()
        .builder()
        .title(&title)
        .body(&body)
        .show();
}
