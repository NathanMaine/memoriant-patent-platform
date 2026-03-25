import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { NewPatent } from './pages/NewPatent';
import { SearchResults } from './pages/SearchResults';
import { DraftEditor } from './pages/DraftEditor';
import { Settings } from './pages/Settings';

const DISCLAIMER_KEY = 'memoriant_disclaimer_dismissed';
const DISCLAIMER_TEXT =
  'This platform is a research and drafting aid, not a substitute for professional legal counsel. ' +
  'Always have a qualified patent attorney review applications before filing.';

function DisclaimerBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem(DISCLAIMER_KEY);
    if (!dismissed) {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISCLAIMER_KEY, 'true');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="alert"
      style={{
        backgroundColor: '#fefce8',
        borderBottom: '1px solid #fde68a',
        padding: '8px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        fontSize: '0.8125rem',
        color: '#92400e',
        lineHeight: '1.4',
      }}
    >
      <span>
        <strong>Legal Notice:</strong> {DISCLAIMER_TEXT}
      </span>
      <button
        onClick={dismiss}
        aria-label="Dismiss disclaimer"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: '#92400e',
          fontSize: '1rem',
          lineHeight: 1,
          padding: '2px 4px',
          flexShrink: 0,
        }}
      >
        ×
      </button>
    </div>
  );
}

function PageFooter() {
  return (
    <footer
      style={{
        borderTop: '1px solid #e5e7eb',
        padding: '12px 16px',
        fontSize: '0.75rem',
        color: '#6b7280',
        textAlign: 'center',
        lineHeight: '1.5',
      }}
    >
      {DISCLAIMER_TEXT}
    </footer>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading)
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full" />
      </div>
    );
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppShell({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <DisclaimerBanner />
      <div style={{ flex: 1 }}>{children}</div>
      <PageFooter />
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
          <Route path="/new" element={<RequireAuth><NewPatent /></RequireAuth>} />
          <Route path="/search/:id" element={<RequireAuth><SearchResults /></RequireAuth>} />
          <Route path="/draft/:id" element={<RequireAuth><DraftEditor /></RequireAuth>} />
          <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

export default App;
