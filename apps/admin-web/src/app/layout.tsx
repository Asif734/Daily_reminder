import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata:Metadata = {title:"Reminder Admin",description:"Internal reminder management"};
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body><Providers>{children}</Providers></body></html>;
}
