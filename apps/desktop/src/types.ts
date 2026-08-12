export type Status="PENDING"|"SNOOZED"|"COMPLETED"|"OVERDUE";
export type Occurrence={id:string;reminder_id:string;title:string;description:string|null;type:"DAILY"|"MONTHLY";priority:"LOW"|"NORMAL"|"HIGH";scheduled_date:string;scheduled_at:string;due_at:string;status:Status;snoozed_until:string|null;completed_at:string|null;updated_at:string};
export type Session={access_token:string;refresh_token:string;expires_at:number};
