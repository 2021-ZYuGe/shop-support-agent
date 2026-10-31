import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { AdminLayout } from "./components/AdminLayout";
import { RequireAuth } from "./components/RequireAuth";
import { AdminConversationDetailPage } from "./pages/AdminConversationDetailPage";
import { AdminConversationsPage } from "./pages/AdminConversationsPage";
import { AdminInsightsPage } from "./pages/AdminInsightsPage";
import { AdminTicketsPage } from "./pages/AdminTicketsPage";
import { ChatPage } from "./pages/ChatPage";
import { DashboardPage } from "./pages/DashboardPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OrdersPage } from "./pages/OrdersPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/admin/login" element={<LoginPage />} />
          <Route
            path="/admin"
            element={
              <RequireAuth>
                <AdminLayout />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="conversations" element={<AdminConversationsPage />} />
            <Route
              path="conversations/:publicId"
              element={<AdminConversationDetailPage />}
            />
            <Route path="tickets" element={<AdminTicketsPage />} />
            <Route path="insights" element={<AdminInsightsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
