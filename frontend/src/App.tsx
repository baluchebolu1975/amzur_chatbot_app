import { type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useMe } from "./hooks/useAuth";
import LoginPage from "./pages/LoginPage";
import MainLayout from "./pages/MainLayout";
import TicTacToePage from "./pages/TicTacToePage";

function ProtectedRoute({ children }: Readonly<{ children: ReactNode }>) {
  const { data, isLoading, isError } = useMe();

  if (isLoading) {
    return (
      <div className="grid min-h-screen place-items-center">Loading...</div>
    );
  }

  if (isError || !data) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tictactoe"
        element={
          <ProtectedRoute>
            <TicTacToePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
