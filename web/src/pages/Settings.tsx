import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';

type LLMProvider = 'claude' | 'ollama' | 'vllm' | 'lmstudio';
type SearchProvider = 'patentsview' | 'uspto_odp' | 'serpapi';

interface ProviderConfig {
  llm_provider: LLMProvider;
  llm_endpoint?: string;
  llm_model?: string;
  search_providers: SearchProvider[];
  api_keys: Record<string, string>;
}

interface ApiKeyState {
  value: string;
  masked: boolean;
  saved: boolean;
}

const LLM_PROVIDERS: Array<{ value: LLMProvider; label: string; requiresEndpoint: boolean }> = [
  { value: 'claude', label: 'Anthropic Claude (Cloud)', requiresEndpoint: false },
  { value: 'ollama', label: 'Ollama (Local)', requiresEndpoint: true },
  { value: 'vllm', label: 'vLLM (Self-hosted)', requiresEndpoint: true },
  { value: 'lmstudio', label: 'LM Studio (Local)', requiresEndpoint: true },
];

const SEARCH_PROVIDERS: Array<{ value: SearchProvider; label: string; description: string }> = [
  { value: 'patentsview', label: 'PatentsView', description: 'USPTO PatentsView API — free, comprehensive US patent data' },
  { value: 'uspto_odp', label: 'USPTO ODP', description: 'USPTO Open Data Portal — official patent full-text search' },
  { value: 'serpapi', label: 'SerpAPI', description: 'Google Patents via SerpAPI — requires API key' },
];

const API_KEY_FIELDS: Array<{ provider: string; key: string; label: string }> = [
  { provider: 'claude', key: 'anthropic_api_key', label: 'Anthropic API Key' },
  { provider: 'serpapi', key: 'serpapi_key', label: 'SerpAPI Key' },
];

function maskKey(key: string): string {
  if (key.length <= 4) return '****';
  return '••••••••••••' + key.slice(-4);
}

export function Settings() {
  const navigate = useNavigate();

  const [llmProvider, setLlmProvider] = useState<LLMProvider>('claude');
  const [llmEndpoint, setLlmEndpoint] = useState('');
  const [llmModel, setLlmModel] = useState('');
  const [searchProviders, setSearchProviders] = useState<SearchProvider[]>(['patentsview', 'uspto_odp']);
  const [apiKeys, setApiKeys] = useState<Record<string, ApiKeyState>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadConfig() {
      try {
        const config = await api.getConfig() as ProviderConfig;
        setLlmProvider(config.llm_provider ?? 'claude');
        setLlmEndpoint(config.llm_endpoint ?? '');
        setLlmModel(config.llm_model ?? '');
        setSearchProviders(config.search_providers ?? ['patentsview', 'uspto_odp']);

        const initialKeys: Record<string, ApiKeyState> = {};
        for (const field of API_KEY_FIELDS) {
          const existingKey = config.api_keys?.[field.key] ?? '';
          initialKeys[field.key] = {
            value: existingKey,
            masked: existingKey.length > 0,
            saved: existingKey.length > 0,
          };
        }
        setApiKeys(initialKeys);
      } catch {
        // Config may not exist yet — use defaults
      } finally {
        setLoading(false);
      }
    }
    loadConfig();
  }, []);

  function toggleSearchProvider(provider: SearchProvider) {
    setSearchProviders((prev) =>
      prev.includes(provider) ? prev.filter((p) => p !== provider) : [...prev, provider]
    );
  }

  function handleApiKeyChange(key: string, value: string) {
    setApiKeys((prev) => ({
      ...prev,
      [key]: { value, masked: false, saved: false },
    }));
  }

  function handleApiKeyFocus(key: string) {
    setApiKeys((prev) => ({
      ...prev,
      [key]: { ...prev[key], masked: false },
    }));
  }

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const keysToSave: Record<string, string> = {};
      for (const field of API_KEY_FIELDS) {
        const state = apiKeys[field.key];
        if (state?.value && !state.masked) {
          keysToSave[field.key] = state.value;
        }
      }

      await api.updateConfig({
        llm_provider: llmProvider,
        llm_endpoint: llmEndpoint,
        llm_model: llmModel,
        search_providers: searchProviders,
        api_keys: keysToSave,
      });

      // Mark all saved keys as masked
      setApiKeys((prev) => {
        const updated = { ...prev };
        for (const key of Object.keys(updated)) {
          if (updated[key].value) {
            updated[key] = { ...updated[key], masked: true, saved: true };
          }
        }
        return updated;
      });

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  const selectedProvider = LLM_PROVIDERS.find((p) => p.value === llmProvider);

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-14 gap-4">
            <button
              onClick={() => navigate('/')}
              className="text-sm text-gray-500 hover:text-gray-900"
            >
              &larr; Dashboard
            </button>
            <h1 className="text-base font-semibold text-gray-900">Settings</h1>
          </div>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full" />
            <span className="ml-3 text-sm text-gray-500">Loading configuration...</span>
          </div>
        ) : (
          <div className="space-y-6">
            {/* LLM Provider */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <h2 className="text-base font-semibold text-gray-900 mb-4">Language Model Provider</h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
                  <select
                    value={llmProvider}
                    onChange={(e) => setLlmProvider(e.target.value as LLMProvider)}
                    className="w-full sm:w-auto px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-gray-900"
                  >
                    {LLM_PROVIDERS.map((p) => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                </div>

                {selectedProvider?.requiresEndpoint && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Endpoint URL
                    </label>
                    <input
                      type="url"
                      value={llmEndpoint}
                      onChange={(e) => setLlmEndpoint(e.target.value)}
                      placeholder="http://localhost:11434"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-gray-900"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      Base URL for the local model server.
                    </p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Model Name</label>
                  <input
                    type="text"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder={
                      llmProvider === 'claude'
                        ? 'claude-3-5-sonnet-20241022'
                        : llmProvider === 'ollama'
                        ? 'qwen2.5:72b'
                        : 'model-name'
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                </div>
              </div>
            </div>

            {/* Search Providers */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <h2 className="text-base font-semibold text-gray-900 mb-4">Patent Search Providers</h2>
              <div className="space-y-3">
                {SEARCH_PROVIDERS.map((p) => (
                  <label key={p.value} className="flex items-start gap-3 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={searchProviders.includes(p.value)}
                      onChange={() => toggleSearchProvider(p.value)}
                      className="mt-0.5 w-4 h-4 accent-gray-900 cursor-pointer"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-800 group-hover:text-gray-900">
                        {p.label}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">{p.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* API Keys */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <h2 className="text-base font-semibold text-gray-900 mb-1">API Keys</h2>
              <p className="text-xs text-gray-400 mb-4">
                Keys are stored securely. After saving, only the last 4 characters are displayed.
              </p>

              <div className="space-y-4">
                {API_KEY_FIELDS.map((field) => {
                  const state = apiKeys[field.key] ?? { value: '', masked: false, saved: false };
                  return (
                    <div key={field.key}>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {field.label}
                        {state.saved && (
                          <span className="ml-2 text-xs text-green-600 font-normal">Saved</span>
                        )}
                      </label>
                      <input
                        type={state.masked ? 'password' : 'text'}
                        value={state.masked ? maskKey(state.value) : state.value}
                        onFocus={() => handleApiKeyFocus(field.key)}
                        onChange={(e) => handleApiKeyChange(field.key, e.target.value)}
                        placeholder="Enter API key..."
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-gray-900"
                        autoComplete="off"
                      />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Save Controls */}
            <div className="flex items-center gap-4">
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-5 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? 'Saving...' : 'Save Settings'}
              </button>

              {saveSuccess && (
                <p className="text-sm text-green-600 font-medium">Settings saved successfully.</p>
              )}
              {saveError && (
                <p className="text-sm text-red-600">{saveError}</p>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
