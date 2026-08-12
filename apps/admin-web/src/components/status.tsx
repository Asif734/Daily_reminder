export function Status({active}:{active:boolean}){return <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-bold ${active?"bg-emerald-50 text-emerald-700":"bg-slate-100 text-slate-600"}`}>{active?"Active":"Inactive"}</span>}
export function Empty({message}:{message:string}){return <div className="card p-12 text-center muted">{message}</div>}
