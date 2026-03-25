import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';
import { PatentCard, type PatentCardData } from '../components/PatentCard';

interface PatentProject extends PatentCardData {
  id: string;
}

export function Dashboard() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<PatentProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.search({ list: true }) as { results: PatentProject[] };
        setProjects(data.results ?? []);
      } catch (err) {
        // Gracefully handle — projects endpoint may differ; show empty state
        setError(err instanceof Error ? err.message : 'Failed to load projects');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const upcomingDeadlines = projects.filter(
    (p) =>
      p.nonprovisional_deadline &&
      new Date(p.nonprovisional_deadline) > new Date() &&
      new Date(p.nonprovisional_deadline) <= new Date(Date.now() + 90 * 24 * 60 * 60 * 1000)
  );

  async function handleSignOut() {
    await signOut();
    navigate('/login');
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <h1 className="text-lg font-bold text-gray-900 tracking-tight">
              Memoriant Patent Platform
            </h1>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-500 hidden sm:block">{user?.email}</span>
              <Link
                to="/settings"
                className="text-sm text-gray-600 hover:text-gray-900 font-medium"
              >
                Settings
              </Link>
              <button
                onClick={handleSignOut}
                className="text-sm text-gray-500 hover:text-gray-800"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Patent Projects</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              Manage and track your patent applications
            </p>
          </div>
          <Link
            to="/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Patent
          </Link>
        </div>

        {upcomingDeadlines.length > 0 && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <h3 className="text-sm font-semibold text-amber-800 mb-2">Upcoming Deadlines</h3>
            <ul className="space-y-1">
              {upcomingDeadlines.map((p) => (
                <li key={p.id} className="text-sm text-amber-700">
                  <span className="font-medium">{p.title}</span> — nonprovisional deadline:{' '}
                  {new Date(p.nonprovisional_deadline!).toLocaleDateString('en-US', {
                    month: 'long',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                </li>
              ))}
            </ul>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full" />
            <span className="ml-3 text-sm text-gray-500">Loading projects...</span>
          </div>
        )}

        {!loading && error && (
          <div className="text-center py-16">
            <p className="text-sm text-gray-500 mb-4">{error}</p>
            <p className="text-sm text-gray-400">
              Start by creating your first patent project.
            </p>
            <Link
              to="/new"
              className="mt-4 inline-block px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800"
            >
              Create First Project
            </Link>
          </div>
        )}

        {!loading && !error && projects.length === 0 && (
          <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
            <div className="max-w-sm mx-auto">
              <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-gray-800 mb-1">No patent projects yet</h3>
              <p className="text-sm text-gray-500 mb-4">
                Begin by describing your invention to initiate the patent research process.
              </p>
              <Link
                to="/new"
                className="inline-block px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800"
              >
                Start New Patent
              </Link>
            </div>
          </div>
        )}

        {!loading && projects.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <PatentCard
                key={project.id}
                patent={project}
                onClick={() => navigate(`/draft/${project.id}`)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
