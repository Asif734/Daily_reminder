import type { DashboardStats, MemberPage, ReminderPage, ReportPage, TokenPair } from "./types";

const ACCESS = "reminder_access";
const REFRESH = "reminder_refresh";
export const tokenStore = {
  access: () => typeof window === "undefined" ? null : sessionStorage.getItem(ACCESS),
  save: (pair:TokenPair) => { sessionStorage.setItem(ACCESS,pair.access_token); localStorage.setItem(REFRESH,pair.refresh_token); },
  clear: () => { sessionStorage.removeItem(ACCESS); localStorage.removeItem(REFRESH); },
};

export async function api<T>(path:string, init:RequestInit = {}):Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) headers.set("Content-Type","application/json");
  const token = tokenStore.access();
  if (token) headers.set("Authorization",`Bearer ${token}`);
  const response = await fetch(`/backend${path}`, {...init,headers});
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? payload?.error?.message ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export const queries = {
  members: (search="",active="") => api<MemberPage>(`/users?search=${encodeURIComponent(search)}${active ? `&active=${active}`:""}`),
  reminders: () => api<ReminderPage>("/reminders"),
  reports: () => api<ReportPage>("/reports/occurrences"),
  dashboardStats: () => api<DashboardStats>("/reports/dashboard"),
};
