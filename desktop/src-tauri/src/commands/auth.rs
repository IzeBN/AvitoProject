use keyring::Entry;

#[tauri::command]
pub fn get_token(service: &str, account: &str) -> Result<String, String> {
    let entry = Entry::new(service, account).map_err(|e| e.to_string())?;
    entry.get_password().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn set_token(service: &str, account: &str, token: &str) -> Result<(), String> {
    let entry = Entry::new(service, account).map_err(|e| e.to_string())?;
    entry.set_password(token).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn clear_token(service: &str, account: &str) -> Result<(), String> {
    let entry = Entry::new(service, account).map_err(|e| e.to_string())?;
    entry.delete_credential().map_err(|e| e.to_string())
}
