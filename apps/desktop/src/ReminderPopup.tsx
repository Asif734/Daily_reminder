import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { BellRing, Check, Clock3 } from "lucide-react";
import { useEffect, useState } from "react";

import { native } from "./native";
import type { Occurrence } from "./types";
import type { Session } from "./types";

type ReminderDelivery = { occurrence: Occurrence; session: Session };

export function ReminderPopup() {
  const [queue, setQueue] = useState<ReminderDelivery[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = queue[0];

  useEffect(() => {
    const unlisten = listen<ReminderDelivery>("reminder-due", ({ payload }) => {
      setQueue((items) =>
        items.some((item) => item.occurrence.id === payload.occurrence.id)
          ? items
          : [...items, payload],
      );
      setError("");
    });
    const unlistenLogout = listen("logged-out", () => {
      setQueue([]);
      getCurrentWindow().hide();
    });
    return () => {
      unlisten.then((removeListener) => removeListener());
      unlistenLogout.then((removeListener) => removeListener());
    };
  }, []);

  async function act(action: "complete" | "later") {
    if (!current || busy) return;
    setBusy(true);
    setError("");
    try {
      if (action === "complete") {
        await native.complete(current.occurrence.id, current.session);
      } else {
        await native.snooze(current.occurrence.id, 10, current.session);
      }
      const remaining = queue.slice(1);
      if (remaining.length === 0) await native.dismissPopup();
      setQueue(remaining);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  if (!current) return <main className="popup-shell" aria-hidden="true" />;

  return (
    <main className="popup-shell">
      <section className="popup-card" role="alertdialog" aria-modal="true" aria-labelledby="reminder-title">
        <div className="popup-icon"><BellRing size={34} /></div>
        <p className="popup-eyebrow">REMINDER DUE</p>
        <h1 id="reminder-title">{current.occurrence.title}</h1>
        <p className="popup-description">
          {current.occurrence.description || "This reminder needs your attention."}
        </p>
        <div className="popup-meta">
          <span>{current.occurrence.type}</span>
          <span>{new Date(current.occurrence.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
          {queue.length > 1 && <span>{queue.length} reminders waiting</span>}
        </div>
        {error && <p className="popup-error" role="alert">{error}</p>}
        <div className="popup-actions">
          <button disabled={busy} className="btn popup-later" onClick={() => act("later")}>
            <Clock3 size={20} /> Remind me later
            <small>10 minutes</small>
          </button>
          <button disabled={busy} className="btn popup-done" onClick={() => act("complete")}>
            <Check size={21} /> Completed
          </button>
        </div>
      </section>
    </main>
  );
}
