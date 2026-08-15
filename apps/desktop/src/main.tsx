import React from "react";import ReactDOM from "react-dom/client";import {getCurrentWindow} from "@tauri-apps/api/window";import {QueryClient,QueryClientProvider} from "@tanstack/react-query";import App from "./App";import {ReminderPopup} from "./ReminderPopup";import "./styles.css";
const Root=getCurrentWindow().label==="reminder"?ReminderPopup:App;
ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><QueryClientProvider client={new QueryClient()}><Root/></QueryClientProvider></React.StrictMode>);
