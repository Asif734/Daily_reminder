"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { api, queries } from "@/lib/api";

export default function NewReminder() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const members = useQuery({
    queryKey: ["members", "active"],
    queryFn: () => queries.members("", "true"),
  });
  const [type, setType] = useState("DAILY");
  const [mode, setMode] = useState("ALL");
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const create = useMutation({
    mutationFn: (body: unknown) =>
      api("/reminders", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reminders"] });
      router.push("/reminders");
    },
    onError: (requestError) => setError(requestError.message),
  });

  function changeMode(nextMode: string) {
    setMode(nextMode);
    setSelectedMemberIds([]);
    setError("");
  }

  function toggleMember(id: string) {
    if (mode === "SINGLE") {
      setSelectedMemberIds([id]);
      return;
    }
    setSelectedMemberIds((current) =>
      current.includes(id)
        ? current.filter((memberId) => memberId !== id)
        : [...current, id],
    );
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode !== "ALL" && selectedMemberIds.length === 0) {
      setError("Select at least one member.");
      return;
    }

    setError("");
    const form = new FormData(event.currentTarget);
    const secondTime = form.get("secondary_reminder_time");
    create.mutate({
      title: form.get("title"),
      description: form.get("description") || null,
      type,
      assignment_mode: mode,
      user_ids: mode === "ALL" ? [] : selectedMemberIds,
      reminder_time: `${form.get("reminder_time")}:00`,
      secondary_reminder_time:
        type === "DAILY" && secondTime ? `${secondTime}:00` : null,
      monthly_due_day:
        type === "MONTHLY" ? Number(form.get("monthly_due_day")) : null,
      days_before:
        type === "MONTHLY" ? Number(form.get("days_before")) : 5,
      priority: form.get("priority"),
    });
  }

  const activeMembers = members.data?.items ?? [];
  const allSelected =
    activeMembers.length > 0 && selectedMemberIds.length === activeMembers.length;

  return (
    <AppShell
      title="Create reminder"
      subtitle="Set up a recurring reminder in under a minute."
    >
      <form onSubmit={submit} className="card p-6 max-w-3xl">
        <div className="grid md:grid-cols-2 gap-5">
          <label className="md:col-span-2">
            <span className="label">Title *</span>
            <input name="title" className="field" required maxLength={200} />
          </label>
          <label className="md:col-span-2">
            <span className="label">Description</span>
            <textarea name="description" className="field min-h-24" />
          </label>
          <label>
            <span className="label">Reminder type *</span>
            <select
              className="field"
              value={type}
              onChange={(event) => setType(event.target.value)}
            >
              <option>DAILY</option>
              <option>MONTHLY</option>
            </select>
          </label>
          <label>
            <span className="label">First reminder time *</span>
            <input name="reminder_time" type="time" className="field" required />
          </label>
          {type === "DAILY" && (
            <label>
              <span className="label">Second reminder time (optional)</span>
              <input name="secondary_reminder_time" type="time" className="field" />
            </label>
          )}
          {type === "MONTHLY" && (
            <>
              <label>
                <span className="label">Due day *</span>
                <input
                  name="monthly_due_day"
                  type="number"
                  min="1"
                  max="31"
                  defaultValue="15"
                  className="field"
                  required
                />
              </label>
              <label>
                <span className="label">Days before *</span>
                <input
                  name="days_before"
                  type="number"
                  min="0"
                  max="31"
                  defaultValue="5"
                  className="field"
                  required
                />
              </label>
            </>
          )}
          <label>
            <span className="label">Assign to *</span>
            <select
              className="field"
              value={mode}
              onChange={(event) => changeMode(event.target.value)}
            >
              <option value="ALL">All active members</option>
              <option value="SINGLE">Single member</option>
              <option value="MULTIPLE">Multiple members</option>
            </select>
          </label>
          <label>
            <span className="label">Priority</span>
            <select name="priority" className="field" defaultValue="NORMAL">
              <option>LOW</option>
              <option>NORMAL</option>
              <option>HIGH</option>
            </select>
          </label>
          {mode !== "ALL" && (
            <fieldset className="md:col-span-2">
              <div className="mb-2 flex items-center justify-between gap-3">
                <legend className="label mb-0">Members *</legend>
                <span className="text-xs muted">
                  {selectedMemberIds.length} selected
                </span>
              </div>
              <div className="member-picker">
                {mode === "MULTIPLE" && activeMembers.length > 0 && (
                  <label className="member-option member-option-all">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={() =>
                        setSelectedMemberIds(
                          allSelected ? [] : activeMembers.map((member) => member.id),
                        )
                      }
                    />
                    <span>Select all members</span>
                  </label>
                )}
                {members.isLoading && (
                  <p className="p-4 text-sm muted">Loading members…</p>
                )}
                {!members.isLoading && activeMembers.length === 0 && (
                  <p className="p-4 text-sm muted">No active members available.</p>
                )}
                {activeMembers.map((member) => (
                  <label className="member-option" key={member.id}>
                    <input
                      type={mode === "SINGLE" ? "radio" : "checkbox"}
                      name={mode === "SINGLE" ? "selected_member" : undefined}
                      checked={selectedMemberIds.includes(member.id)}
                      onChange={() => toggleMember(member.id)}
                    />
                    <span>
                      <strong>{member.name}</strong>
                      <span className="member-email">{member.email}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
        </div>
        {error && (
          <p role="alert" className="text-red-700 bg-red-50 p-3 rounded-lg mt-5">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-3 mt-7">
          <button type="button" onClick={() => router.back()} className="btn btn-secondary">
            Cancel
          </button>
          <button disabled={create.isPending} className="btn btn-primary">
            {create.isPending ? "Saving…" : "Save reminder"}
          </button>
        </div>
      </form>
    </AppShell>
  );
}
