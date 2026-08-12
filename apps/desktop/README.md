# Reminder Desktop

Tauri 2 member client with a React UI and Rust-owned SQLite cache/outbox.

## Features

- Member login with session data stored in the operating-system credential store
- Startup, login, two-minute periodic, reconnect, and manual synchronization
- SQLite occurrence cache and retryable local action outbox
- Offline due detection and native notifications
- Today, upcoming, overdue, and completed sections
- One-click completion and 10/30/60/120-minute snooze
- Official Tauri notification and autostart plugins
- System tray with Open Reminders, Sync Now, Logout, and Exit
- Closing the window hides it; only Exit terminates the process
- Autostart launches with a minimized argument

## Development

Install Rust using `rustup`, plus the platform prerequisites from the Tauri 2 documentation.

```bash
npm ci
npm test
npm run build
npm run tauri dev
```

Windows packaging should be performed on a Windows CI runner. macOS packaging requires an
Apple signing identity for distributable builds. The backend base URL currently defaults to
`http://localhost:8000` for local development; production builds should inject a managed HTTPS
endpoint through a compile-time configuration module.
