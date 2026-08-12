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

Copy the desktop environment file and set the backend URL before running or packaging:

```bash
cp .env.example .env
```

Both values should point to the same API gateway. Use an HTTPS address for production builds.

```bash
npm ci
npm test
npm run build
npm run tauri dev
```

Windows packaging should be performed on a Windows CI runner. macOS packaging requires an
Apple signing identity for distributable builds. Backend addresses are supplied through
`VITE_API_BASE_URL` and `DESKTOP_API_BASE_URL` in the desktop `.env` file.
