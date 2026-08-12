"use client";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { Empty } from "@/components/status";
import { queries } from "@/lib/api";

export default function Reports(){const report=useQuery({queryKey:["occurrence-reports"],queryFn:queries.reports,refetchInterval:15000});return <AppShell title="Reports" subtitle="Review occurrence completion and snooze history.">{report.data?.items.length?<div className="card overflow-x-auto"><table className="w-full text-sm"><thead className="bg-[#f3f7f4] text-left"><tr>{["Reminder","Member","Status","Scheduled","Completed","Snoozed until"].map(x=><th key={x} className="px-5 py-3">{x}</th>)}</tr></thead><tbody>{report.data.items.map(item=><tr key={item.id} className="border-t border-slate-100"><td className="px-5 py-4 font-medium">{item.title}</td><td className="px-5 py-4 font-medium">{item.user_name}</td><td className="px-5 py-4 font-bold">{item.status}</td><td className="px-5 py-4">{new Date(item.scheduled_at).toLocaleString()}</td><td className="px-5 py-4">{item.completed_at?new Date(item.completed_at).toLocaleString():"—"}</td><td className="px-5 py-4">{item.snoozed_until?new Date(item.snoozed_until).toLocaleString():"—"}</td></tr>)}</tbody></table></div>:<Empty message={report.isLoading?"Loading occurrence history…":"No reminder occurrences found."}/>}</AppShell>}
