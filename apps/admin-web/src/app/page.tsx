"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { restoreSession } from "@/lib/api";
export default function Home(){const router=useRouter();useEffect(()=>{restoreSession().then(user=>router.replace(user?"/dashboard":"/login"))},[router]);return <main className="min-h-screen grid place-items-center text-slate-500">Checking your session…</main>}
