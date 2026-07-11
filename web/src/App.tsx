import { useEffect, useRef } from "react";
import { HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppProvider, useAppState } from "./context/AppContext";
import { api } from "./api/http";
import Layout from "./components/Layout";
import ChatPage from "./pages/ChatPage";
import HistoryPage from "./pages/HistoryPage";
import MemoryPage from "./pages/MemoryPage";
import SkillManagerPage from "./pages/SkillManagerPage";
import ToolsPage from "./pages/ToolsPage";
import SettingsLLMPage from "./pages/SettingsLLMPage";
import SettingsERPPage from "./pages/SettingsERPPage";
import SettingsAgentPage from "./pages/SettingsAgentPage";
import SettingsExtensionsPage from "./pages/SettingsExtensionsPage";
import CronJobPage from "./pages/CronJobPage";
import McpPage from "./pages/McpPage";
import type { ConfigResponse } from "./types";

function AppInit({ children }: { children: React.ReactNode }) {
  const { dispatch } = useAppState();
  const retries = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api.get<ConfigResponse>("/config")
        .then((config) => {
          if (!cancelled) {
            dispatch({ type: "SET_CONFIG", config });
          }
        })
        .catch(() => {
          if (!cancelled && retries.current < 10) {
            retries.current++;
            setTimeout(load, 1000 * retries.current);
          }
        });
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  return <>{children}</>;
}

export default function App() {
  return (
    <HashRouter>
      <AppProvider>
        <AppInit>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<ChatPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="/skills" element={<SkillManagerPage />} />
              <Route path="/tools" element={<ToolsPage />} />
              <Route path="/settings/llm" element={<SettingsLLMPage />} />
              <Route path="/settings/yonsuite" element={<Navigate to="/settings/erp?tab=yonsuite" replace />} />
              <Route path="/settings/erp" element={<SettingsERPPage />} />
              <Route path="/settings/agent" element={<SettingsAgentPage />} />
              <Route path="/settings/extensions" element={<SettingsExtensionsPage />} />
              <Route path="/cronjobs" element={<CronJobPage />} />
              <Route path="/mcp" element={<McpPage />} />
            </Route>
          </Routes>
        </AppInit>
      </AppProvider>
    </HashRouter>
  );
}
