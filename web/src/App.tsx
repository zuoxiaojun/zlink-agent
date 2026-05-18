import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppProvider, useAppState } from "./context/AppContext";
import { api } from "./api/http";
import Layout from "./components/Layout";
import ChatPage from "./pages/ChatPage";
import HistoryPage from "./pages/HistoryPage";
import MemoryPage from "./pages/MemoryPage";
import SkillManagerPage from "./pages/SkillManagerPage";
import ToolsPage from "./pages/ToolsPage";
import SettingsLLMPage from "./pages/SettingsLLMPage";
import SettingsYSPage from "./pages/SettingsYSPage";
import SettingsAgentPage from "./pages/SettingsAgentPage";
import McpPage from "./pages/McpPage";
import type { ConfigResponse } from "./types";

function AppInit({ children }: { children: React.ReactNode }) {
  const { dispatch } = useAppState();

  useEffect(() => {
    api.get<ConfigResponse>("/config")
      .then((config) => dispatch({ type: "SET_CONFIG", config }))
      .catch(() => {});
  }, [dispatch]);

  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
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
              <Route path="/settings/yonsuite" element={<SettingsYSPage />} />
              <Route path="/settings/agent" element={<SettingsAgentPage />} />
              <Route path="/mcp" element={<McpPage />} />
            </Route>
          </Routes>
        </AppInit>
      </AppProvider>
    </BrowserRouter>
  );
}
