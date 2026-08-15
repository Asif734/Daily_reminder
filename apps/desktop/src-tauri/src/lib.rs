use chrono::Utc;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Emitter, Manager, State, WindowEvent,
};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_notification::NotificationExt;

const API_BASE_URL: &str = env!("DESKTOP_API_BASE_URL");
fn api(path: &str) -> String {
    format!("{}/api/v1/{path}", API_BASE_URL.trim_end_matches('/'))
}
#[derive(Debug, Serialize, Deserialize, Clone)]
struct Session {
    access_token: String,
    refresh_token: String,
    expires_at: i64,
}
#[derive(Debug, Deserialize)]
struct TokenPair {
    access_token: String,
    refresh_token: String,
}
#[derive(Debug, Serialize, Deserialize, Clone)]
struct Occurrence {
    id: String,
    reminder_id: String,
    title: String,
    description: Option<String>,
    #[serde(rename = "type")]
    kind: String,
    priority: String,
    scheduled_date: String,
    scheduled_at: String,
    due_at: String,
    status: String,
    snoozed_until: Option<String>,
    completed_at: Option<String>,
    updated_at: String,
}
#[derive(Debug, Serialize, Deserialize)]
struct Page {
    items: Vec<Occurrence>,
    next_cursor: Option<String>,
}
#[derive(Debug, Serialize, Clone)]
struct ReminderDelivery {
    occurrence: Occurrence,
    session: Session,
}
struct Db(Mutex<Connection>);
struct ActiveSession(Mutex<Option<Session>>);
fn migrate(c: &Connection) -> rusqlite::Result<()> {
    c.execute_batch("CREATE TABLE IF NOT EXISTS occurrences(id TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at TEXT NOT NULL,notified_trigger TEXT);CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY,kind TEXT NOT NULL,occurrence_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0);CREATE TABLE IF NOT EXISTS sync_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);")?;
    let _ = c.execute(
        "ALTER TABLE occurrences ADD COLUMN notified_trigger TEXT",
        [],
    );
    Ok(())
}
fn cache(c: &Connection, items: &[Occurrence]) -> Result<(), String> {
    let tx = c.unchecked_transaction().map_err(|e| e.to_string())?;
    for item in items {
        tx.execute("INSERT INTO occurrences(id,payload,updated_at) VALUES(?1,?2,?3) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",params![item.id,serde_json::to_string(item).unwrap(),item.updated_at]).map_err(|e|e.to_string())?;
    }
    tx.commit().map_err(|e| e.to_string())
}
fn replace_cache(c: &Connection, items: &[Occurrence]) -> Result<(), String> {
    let active_ids = items
        .iter()
        .map(|item| item.id.as_str())
        .collect::<HashSet<_>>();
    let existing_ids = {
        let mut statement = c
            .prepare("SELECT id FROM occurrences")
            .map_err(|error| error.to_string())?;
        let ids = statement
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(|error| error.to_string())?
            .filter_map(Result::ok)
            .collect::<Vec<_>>();
        ids
    };
    let tx = c
        .unchecked_transaction()
        .map_err(|error| error.to_string())?;
    for id in existing_ids {
        if !active_ids.contains(id.as_str()) {
            tx.execute("DELETE FROM occurrences WHERE id=?1", [id])
                .map_err(|error| error.to_string())?;
        }
    }
    for item in items {
        tx.execute("INSERT INTO occurrences(id,payload,updated_at) VALUES(?1,?2,?3) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",params![item.id,serde_json::to_string(item).unwrap(),item.updated_at]).map_err(|error|error.to_string())?;
    }
    tx.commit().map_err(|error| error.to_string())
}
fn due_for_notification(
    c: &Connection,
    now: chrono::DateTime<Utc>,
) -> Result<Vec<(Occurrence, String)>, String> {
    let mut statement = c
        .prepare("SELECT payload,notified_trigger FROM occurrences")
        .map_err(|e| e.to_string())?;
    let rows = statement
        .query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, Option<String>>(1)?))
        })
        .map_err(|e| e.to_string())?;
    Ok(rows
        .filter_map(Result::ok)
        .filter_map(|(payload, notified)| {
            let item: Occurrence = serde_json::from_str(&payload).ok()?;
            if item.status == "COMPLETED" {
                return None;
            }
            let trigger = item
                .snoozed_until
                .clone()
                .unwrap_or_else(|| item.scheduled_at.clone());
            let due = chrono::DateTime::parse_from_rfc3339(&trigger)
                .ok()?
                .with_timezone(&Utc)
                <= now;
            (due && notified.as_deref() != Some(trigger.as_str())).then_some((item, trigger))
        })
        .collect())
}
fn deliver_due_reminders(app: &tauri::AppHandle, session: &Session) {
    let due = {
        let db = app.state::<Db>();
        db.0.lock()
            .ok()
            .and_then(|c| due_for_notification(&c, Utc::now()).ok())
            .unwrap_or_default()
    };
    for (item, trigger) in due {
        let popup_shown = app
            .get_webview_window("reminder")
            .map(|window| {
                let emitted = app
                    .emit_to(
                        "reminder",
                        "reminder-due",
                        ReminderDelivery {
                            occurrence: item.clone(),
                            session: session.clone(),
                        },
                    )
                    .is_ok();
                let shown = window.show().is_ok();
                let _ = window.set_focus();
                emitted && shown
            })
            .unwrap_or(false);
        let delivered = if popup_shown {
            true
        } else {
            let body = item
                .description
                .as_deref()
                .unwrap_or("Open Reminder to mark this task done or snooze it.");
            app.notification()
                .builder()
                .title(&item.title)
                .body(body)
                .show()
                .is_ok()
        };
        if delivered {
            let db = app.state::<Db>();
            if let Ok(c) = db.0.lock() {
                let _ = c.execute(
                    "UPDATE occurrences SET notified_trigger=?1 WHERE id=?2",
                    params![trigger, item.id],
                );
            };
        }
    }
}
fn start_notification_scheduler(app: tauri::AppHandle) {
    std::thread::spawn(move || {
        // Give the hidden popup webview time to register its event listener at startup.
        std::thread::sleep(std::time::Duration::from_secs(2));
        loop {
            let session = app
                .state::<ActiveSession>()
                .0
                .lock()
                .ok()
                .and_then(|session| session.clone());
            if let Some(session) = session {
                deliver_due_reminders(&app, &session);
            }
            std::thread::sleep(std::time::Duration::from_secs(60));
        }
    });
}
#[tauri::command]
fn save_session(value: Session, active: State<'_, ActiveSession>) -> Result<(), String> {
    keyring::Entry::new("reminder-desktop", "session")
        .map_err(|e| e.to_string())?
        .set_password(&serde_json::to_string(&value).unwrap())
        .map_err(|e| e.to_string())?;
    *active.0.lock().map_err(|error| error.to_string())? = Some(value);
    Ok(())
}
#[tauri::command]
fn load_session() -> Result<Option<Session>, String> {
    match keyring::Entry::new("reminder-desktop", "session")
        .map_err(|e| e.to_string())?
        .get_password()
    {
        Ok(v) => Ok(serde_json::from_str(&v).ok()),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}
fn clear_stored_session() -> Result<(), String> {
    keyring::Entry::new("reminder-desktop", "session")
        .map_err(|e| e.to_string())?
        .delete_credential()
        .map_err(|e| e.to_string())
}
#[tauri::command]
fn clear_session(active: State<'_, ActiveSession>) -> Result<(), String> {
    let result = clear_stored_session();
    *active.0.lock().map_err(|error| error.to_string())? = None;
    result
}
#[tauri::command]
fn list_cached(db: State<Db>) -> Result<Vec<Occurrence>, String> {
    let c = db.0.lock().unwrap();
    let mut s = c
        .prepare("SELECT payload FROM occurrences ORDER BY updated_at")
        .map_err(|e| e.to_string())?;
    let rows = s
        .query_map([], |r| r.get::<_, String>(0))
        .map_err(|e| e.to_string())?;
    Ok(rows
        .filter_map(|x| x.ok().and_then(|v| serde_json::from_str(&v).ok()))
        .collect())
}
async fn send_action(
    id: &str,
    path: &str,
    body: serde_json::Value,
    s: &Session,
) -> Result<Occurrence, String> {
    reqwest::Client::new()
        .post(api(&format!("reminder-occurrences/{id}/{path}")))
        .bearer_auth(&s.access_token)
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())
}
fn persist_active_session(app: &tauri::AppHandle, session: Session) -> Result<(), String> {
    keyring::Entry::new("reminder-desktop", "session")
        .map_err(|error| error.to_string())?
        .set_password(&serde_json::to_string(&session).unwrap())
        .map_err(|error| error.to_string())?;
    *app.state::<ActiveSession>()
        .0
        .lock()
        .map_err(|error| error.to_string())? = Some(session);
    Ok(())
}
async fn active_session(app: &tauri::AppHandle) -> Result<Session, String> {
    let current = app
        .state::<ActiveSession>()
        .0
        .lock()
        .map_err(|error| error.to_string())?
        .clone()
        .ok_or_else(|| "Authentication is no longer valid".to_string())?;
    if current.expires_at > Utc::now().timestamp_millis() + 30_000 {
        return Ok(current);
    }
    let pair: TokenPair = reqwest::Client::new()
        .post(api("auth/refresh"))
        .json(&serde_json::json!({"refresh_token": current.refresh_token}))
        .send()
        .await
        .map_err(|error| error.to_string())?
        .error_for_status()
        .map_err(|error| error.to_string())?
        .json()
        .await
        .map_err(|error| error.to_string())?;
    let refreshed = Session {
        access_token: pair.access_token,
        refresh_token: pair.refresh_token,
        expires_at: Utc::now().timestamp_millis() + 14 * 60 * 1000,
    };
    persist_active_session(app, refreshed.clone())?;
    Ok(refreshed)
}
fn enqueue(
    c: &Connection,
    kind: &str,
    id: &str,
    payload: &serde_json::Value,
) -> Result<(), String> {
    c.execute(
        "INSERT INTO outbox(id,kind,occurrence_id,payload,created_at) VALUES(?1,?2,?3,?4,?5)",
        params![
            uuid::Uuid::new_v4().to_string(),
            kind,
            id,
            payload.to_string(),
            Utc::now().to_rfc3339()
        ],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}
async fn flush_outbox(db: &Db, s: &Session) -> Result<(), String> {
    let pending = {
        let c = db.0.lock().map_err(|e| e.to_string())?;
        let mut q = c
            .prepare(
                "SELECT id,kind,occurrence_id,payload,attempts FROM outbox ORDER BY created_at",
            )
            .map_err(|e| e.to_string())?;
        let rows = q
            .query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, String>(3)?,
                    r.get::<_, i64>(4)?,
                ))
            })
            .map_err(|e| e.to_string())?
            .filter_map(Result::ok)
            .collect::<Vec<_>>();
        rows
    };
    for (row_id, kind, id, payload, attempts) in pending {
        let value: serde_json::Value = serde_json::from_str(&payload).unwrap_or_default();
        match send_action(&id, &kind, value, s).await {
            Ok(item) => {
                let c = db.0.lock().map_err(|e| e.to_string())?;
                cache(&c, &[item])?;
                c.execute("DELETE FROM outbox WHERE id=?1", [row_id])
                    .map_err(|e| e.to_string())?;
            }
            Err(_) => {
                let c = db.0.lock().map_err(|e| e.to_string())?;
                if attempts >= 10 {
                    c.execute("DELETE FROM outbox WHERE id=?1", [row_id])
                        .map_err(|e| e.to_string())?;
                } else {
                    c.execute(
                        "UPDATE outbox SET attempts=attempts+1 WHERE id=?1",
                        [row_id],
                    )
                    .map_err(|e| e.to_string())?;
                    break;
                }
            }
        }
    }
    Ok(())
}
#[tauri::command]
async fn sync_now(db: State<'_, Db>, app: tauri::AppHandle) -> Result<Vec<Occurrence>, String> {
    let session = active_session(&app).await?;
    flush_outbox(db.inner(), &session).await?;
    let page: Page = reqwest::Client::new()
        .get(api("me/reminders"))
        .bearer_auth(&session.access_token)
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())?;
    {
        let c = db.0.lock().map_err(|e| e.to_string())?;
        replace_cache(&c, &page.items)?;
    }
    deliver_due_reminders(&app, &session);
    Ok(page.items)
}
#[tauri::command]
async fn complete_occurrence(
    id: String,
    db: State<'_, Db>,
    app: tauri::AppHandle,
) -> Result<(), String> {
    let session = active_session(&app).await?;
    match send_action(&id, "complete", serde_json::json!({}), &session).await {
        Ok(item) => cache(&db.0.lock().unwrap(), &[item]),
        Err(_) => enqueue(
            &db.0.lock().unwrap(),
            "complete",
            &id,
            &serde_json::json!({}),
        ),
    }
}
#[tauri::command]
async fn snooze_occurrence(
    id: String,
    minutes: i32,
    db: State<'_, Db>,
    app: tauri::AppHandle,
) -> Result<(), String> {
    let session = active_session(&app).await?;
    let body = serde_json::json!({"minutes":minutes});
    match send_action(&id, "snooze", body.clone(), &session).await {
        Ok(item) => cache(&db.0.lock().unwrap(), &[item]),
        Err(_) => enqueue(&db.0.lock().unwrap(), "snooze", &id, &body),
    }
}
#[tauri::command]
fn hide_main_window(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.hide();
    }
}
#[tauri::command]
fn dismiss_reminder_popup(app: tauri::AppHandle) -> Result<(), String> {
    app.get_webview_window("reminder")
        .ok_or_else(|| "Reminder window is unavailable".to_string())?
        .hide()
        .map_err(|error| error.to_string())
}
#[tauri::command]
fn enable_autostart(app: tauri::AppHandle) -> Result<(), String> {
    use tauri_plugin_autostart::ManagerExt;
    app.autolaunch().enable().map_err(|e| e.to_string())
}
#[tauri::command]
fn logout(app: tauri::AppHandle) -> Result<(), String> {
    let _ = clear_stored_session();
    if let Ok(mut active) = app.state::<ActiveSession>().0.lock() {
        *active = None;
    }
    let _ = app.emit("logged-out", ());
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
    }
    Ok(())
}
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .setup(|app| {
            let data = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data)?;
            let c = Connection::open(data.join("cache.sqlite3"))?;
            migrate(&c)?;
            app.manage(Db(Mutex::new(c)));
            app.manage(ActiveSession(Mutex::new(load_session().ok().flatten())));
            start_notification_scheduler(app.handle().clone());
            let open = MenuItem::with_id(app, "open", "Open Reminders", true, None::<&str>)?;
            let sync = MenuItem::with_id(app, "sync", "Sync Now", true, None::<&str>)?;
            let logout = MenuItem::with_id(app, "logout", "Logout", true, None::<&str>)?;
            let exit = MenuItem::with_id(app, "exit", "Exit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &sync, &logout, &exit])?;
            TrayIconBuilder::new()
                .menu(&menu)
                .on_menu_event(|app, e| match e.id.as_ref() {
                    "open" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "sync" => {
                        let _ = app.emit("sync-requested", ());
                    }
                    "logout" => {
                        let _ = clear_stored_session();
                        if let Ok(mut active) = app.state::<ActiveSession>().0.lock() {
                            *active = None;
                        }
                        let _ = app.emit("logged-out", ());
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                        }
                    }
                    "exit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;
            if !std::env::args().any(|a| a == "--minimized") {
                app.get_webview_window("main").unwrap().show()?;
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                if window.label() != "reminder" {
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            save_session,
            load_session,
            clear_session,
            list_cached,
            sync_now,
            complete_occurrence,
            snooze_occurrence,
            hide_main_window,
            dismiss_reminder_popup,
            enable_autostart,
            logout
        ])
        .run(tauri::generate_context!())
        .expect("desktop runtime failed")
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn migrations_are_idempotent() {
        let c = Connection::open_in_memory().unwrap();
        migrate(&c).unwrap();
        migrate(&c).unwrap();
        let n: i64 = c
            .query_row(
                "SELECT count(*) FROM sqlite_master WHERE type='table'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert!(n >= 3);
    }
}
