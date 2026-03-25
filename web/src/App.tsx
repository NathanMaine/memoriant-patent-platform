import type { ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { NewPatent } from './pages/NewPatent';
import { SearchResults } from './pages/SearchResults';
import { DraftEditor } from './pages/DraftEditor';
import { Settings } from './pages/Settings';

function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center"><div className="animate-spin w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full" /></div>;
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/new" element={<RequireAuth><NewPatent /></RequireAuth>} />
        <Route path="/search/:id" element={<RequireAuth><SearchResults /></RequireAuth>} />
        <Route path="/draft/:id" element={<RequireAuth><DraftEditor /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
