export type Role = "ADMIN" | "MEMBER";
export type Member = { id:string; name:string; email:string; role:Role; is_active:boolean; timezone:string; last_login_at:string|null; created_at:string; updated_at:string };
export type MemberPage = { items:Member[]; total:number; limit:number; offset:number };
export type ReminderType = "DAILY" | "MONTHLY";
export type Reminder = { id:string; title:string; description:string|null; type:ReminderType; reminder_time:string; monthly_due_day:number|null; days_before:number; priority:"LOW"|"NORMAL"|"HIGH"; is_active:boolean; created_by:string; assigned_user_ids:string[]; created_at:string; updated_at:string };
export type ReminderPage = { items:Reminder[]; total:number; limit:number; offset:number };
export type TokenPair = { access_token:string; refresh_token:string; token_type:string };
