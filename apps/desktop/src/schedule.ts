import type {Occurrence} from "./types";
export function dueOccurrences(items:Occurrence[],now=new Date()){return items.filter(item=>item.status!=="COMPLETED"&&new Date(item.snoozed_until??item.scheduled_at)<=now)}
export function sections(items:Occurrence[],today=new Date().toISOString().slice(0,10)){return {today:items.filter(x=>x.scheduled_date===today&&x.status!=="COMPLETED"&&x.status!=="OVERDUE"),upcoming:items.filter(x=>x.scheduled_date>today&&x.status!=="COMPLETED"),overdue:items.filter(x=>x.status==="OVERDUE"),completed:items.filter(x=>x.status==="COMPLETED")}}
