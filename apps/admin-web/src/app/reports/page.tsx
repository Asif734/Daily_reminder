import { AppShell } from "@/components/app-shell";
import { Empty } from "@/components/status";
export default function Reports(){return <AppShell title="Reports" subtitle="Review occurrence completion and delivery history."><div className="card p-4 grid md:grid-cols-5 gap-3 mb-5">{["User","Reminder","Status","Date range","Type"].map(x=><select key={x} className="field"><option>{x}: All</option></select>)}</div><Empty message="Occurrence reporting endpoint will populate this table when report aggregation is enabled."/></AppShell>}
