import { useState, useEffect, useRef } from 'react'
import { useStore, Agent } from './store'

const CATEGORIES = [
  { id: 'all', name: 'All', icon: '🌐' },
  { id: 'writing', name: 'Writing', icon: '✍️' },
  { id: 'coding', name: 'Coding', icon: '💻' },
  { id: 'research', name: 'Research', icon: '🔍' },
  { id: 'marketing', name: 'Marketing', icon: '📈' },
  { id: 'design', name: 'Design', icon: '🎨' },
  { id: 'business', name: 'Business', icon: '💼' },
  { id: 'education', name: 'Education', icon: '📚' },
  { id: 'productivity', name: 'Productivity', icon: '⚡' },
]

const ALL_TOOLS = ['web_search', 'code_execution', 'file_ops']

type View = 'marketplace' | 'chat' | 'builder'

function App() {
  const [input, setInput] = useState('')
  const [category, setCategory] = useState('all')
  const [view, setView] = useState<View>('marketplace')
  const [searchQuery, setSearchQuery] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Builder state
  const [builderForm, setBuilderForm] = useState({
    name: '',
    description: '',
    category: 'writing',
    system_prompt: '',
    model: 'llama3.2',
    tools: [] as string[],
    temperature: 0.7,
  })
  const [builderStatus, setBuilderStatus] = useState<'idle' | 'saving' | 'done' | 'error'>('idle')
  const [builderMsg, setBuilderMsg] = useState('')

  // Export state
  const [exportData, setExportData] = useState<{ code: string; format: string; agent: string } | null>(null)

  // Starred agents (localStorage)
  const [starred, setStarred] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem('agentverse-starred')
      return new Set(raw ? JSON.parse(raw) : [])
    } catch { return new Set() }
  })

  // Run counts (localStorage)
  const [runCounts, setRunCounts] = useState<Record<string, number>>(() => {
    try {
      const raw = localStorage.getItem('agentverse-runs')
      return raw ? JSON.parse(raw) : {}
    } catch { return {} }
  })

  const incrementRuns = (agentId: string) => {
    setRunCounts(prev => {
      const next = { ...prev, [agentId]: (prev[agentId] || 0) + 1 }
      localStorage.setItem('agentverse-runs', JSON.stringify(next))
      return next
    })
  }

  const toggleStar = (agentId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setStarred(prev => {
      const next = new Set(prev)
      if (next.has(agentId)) next.delete(agentId)
      else next.add(agentId)
      localStorage.setItem('agentverse-starred', JSON.stringify([...next]))
      return next
    })
  }

  const {
    agents, selectedAgent, messages, isLoading, error,
    setAgents, selectAgent, addMessage, updateLastMessage, setLoading, setError,
  } = useStore()

  useEffect(() => {
    fetch('/api/agents/')
      .then(r => r.json())
      .then(data => setAgents(data.agents))
      .catch(err => console.error('Failed to fetch agents:', err))
  }, [setAgents])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const [sortBy, setSortBy] = useState<'default' | 'popular' | 'az'>('default')

  const filteredAgents = agents.filter(a => {
    const catMatch = category === 'all' || (category === 'starred' ? starred.has(a.id) : a.category === category)
    const searchMatch = !searchQuery ||
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.description.toLowerCase().includes(searchQuery.toLowerCase())
    return catMatch && searchMatch
  }).sort((a, b) => {
    if (sortBy === 'popular') {
      return (runCounts[b.id] || 0) - (runCounts[a.id] || 0)
    }
    if (sortBy === 'az') {
      return a.name.localeCompare(b.name)
    }
    return 0
  })

  const handleRun = async () => {
    if (!input.trim() || !selectedAgent || isLoading) return
    const userMsg = input
    addMessage({ role: 'user', content: userMsg, agentId: selectedAgent.id })
    addMessage({ role: 'assistant', content: '', agentId: selectedAgent.id })
    setLoading(true)
    setInput('')
    try {
      const res = await fetch('/api/agents/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: selectedAgent.id, message: userMsg }),
      })
      if (!res.ok || !res.body) throw new Error('Failed')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'token') {
              const msgs = useStore.getState().messages
              const last = msgs[msgs.length - 1]
              if (last && last.role === 'assistant') {
                updateLastMessage(last.content + data.content)
              }
            } else if (data.type === 'error') {
              throw new Error(data.content)
            }
          } catch { /* skip unparseable */ }
        }
      }
      incrementRuns(selectedAgent.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error')
    } finally {
      setLoading(false)
    }
  }

  const handleExport = async (agentId: string, format: string) => {
    try {
      const res = await fetch(`/api/agents/${agentId}/export?format=${format}`)
      if (!res.ok) throw new Error('Export failed')
      const data = await res.json()
      setExportData(data)
    } catch (err) {
      setError('Export failed')
    }
  }

  const handleCreateAgent = async () => {
    if (!builderForm.name || !builderForm.system_prompt) {
      setBuilderStatus('error')
      setBuilderMsg('Name and system prompt are required')
      return
    }
    setBuilderStatus('saving')
    try {
      const res = await fetch('/api/agents/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(builderForm),
      })
      if (!res.ok) throw new Error('Failed')
      const data = await res.json()
      setBuilderStatus('done')
      setBuilderMsg(`Agent "${builderForm.name}" created! ID: ${data.id}`)
      // Refresh agents
      const listRes = await fetch('/api/agents/')
      const listData = await listRes.json()
      setAgents(listData.agents)
      // Reset form
      setBuilderForm({ name: '', description: '', category: 'writing', system_prompt: '', model: 'llama3.2', tools: [], temperature: 0.7 })
    } catch (err) {
      setBuilderStatus('error')
      setBuilderMsg('Failed to create agent')
    }
  }

  const toggleTool = (tool: string) => {
    setBuilderForm(f => ({
      ...f,
      tools: f.tools.includes(tool) ? f.tools.filter(t => t !== tool) : [...f.tools, tool],
    }))
  }

  return (
    <div className="h-screen flex flex-col bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🚀</span>
            <h1 className="text-xl font-bold">AgentVerse Hub</h1>
            <span className="text-gray-500 text-sm">101 AI Agents</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setView('marketplace')}
              className={`px-4 py-2 rounded-lg ${view === 'marketplace' ? 'bg-cyan-600' : 'bg-gray-800 hover:bg-gray-700'}`}
            >
              Marketplace
            </button>
            <button
              onClick={() => selectedAgent && setView('chat')}
              className={`px-4 py-2 rounded-lg ${view === 'chat' ? 'bg-cyan-600' : 'bg-gray-800 hover:bg-gray-700'}`}
              disabled={!selectedAgent}
            >
              Chat
            </button>
            <button
              onClick={() => setView('builder')}
              className={`px-4 py-2 rounded-lg ${view === 'builder' ? 'bg-cyan-600' : 'bg-gray-800 hover:bg-gray-700'}`}
            >
              + Build Agent
                </button>
              </div>

              {/* Sort */}
              <div className="flex items-center gap-2 mb-6">
                <span className="text-xs text-gray-400">Sort:</span>
                {([['default', 'Default'], ['popular', '🔥 Popular'], ['az', 'A-Z']] as const).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setSortBy(key)}
                    className={`px-3 py-1.5 rounded-lg text-sm ${
                      sortBy === key ? 'bg-cyan-600' : 'bg-gray-800 hover:bg-gray-700'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
        </div>
      </header>

      <div className="flex-1 overflow-hidden">
        {view === 'marketplace' && (
          <div className="h-full overflow-y-auto p-6">
            <div className="max-w-7xl mx-auto">
              {/* Search */}
              <div className="mb-4">
                <input
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="🔍 Search agents..."
                  className="w-full bg-gray-900 border border-gray-800 px-4 py-3 rounded-xl focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Categories */}
              <div className="flex flex-wrap gap-2 mb-6">
                {CATEGORIES.map(cat => (
                  <button
                    key={cat.id}
                    onClick={() => setCategory(cat.id)}
                    className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
                      category === cat.id ? 'bg-cyan-600' : 'bg-gray-800 hover:bg-gray-700'
                    }`}
                  >
                    <span>{cat.icon}</span>
                    <span>{cat.name}</span>
                  </button>
                ))}
                <button
                  onClick={() => setCategory('starred')}
                  className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
                    category === 'starred' ? 'bg-yellow-600' : 'bg-gray-800 hover:bg-gray-700'
                  }`}
                >
                  <span>⭐</span>
                  <span>Starred ({starred.size})</span>
                </button>
              </div>

              {/* Agent Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredAgents.map(agent => (
                  <div
                    key={agent.id}
                    className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-cyan-500 transition cursor-pointer"
                    onClick={() => { selectAgent(agent); setView('chat') }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold">{agent.name}</h3>
                      <div className="flex gap-1 items-center">
                        {(runCounts[agent.id] || 0) > 0 && (
                          <span className="text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded" title="Times run">
                            ▶ {runCounts[agent.id]}
                          </span>
                        )}
                        <button
                          onClick={e => toggleStar(agent.id, e)}
                          className={`text-lg transition ${starred.has(agent.id) ? 'text-yellow-400' : 'text-gray-600 hover:text-yellow-400'}`}
                          title={starred.has(agent.id) ? 'Unstar' : 'Star'}
                        >
                          {starred.has(agent.id) ? '★' : '☆'}
                        </button>
                        {agent.is_template ? (
                          <span className="text-xs bg-gray-800 px-2 py-1 rounded">Template</span>
                        ) : (
                          <span className="text-xs bg-cyan-900 text-cyan-300 px-2 py-1 rounded">Custom</span>
                        )}
                      </div>
                    </div>
                    <p className="text-gray-400 text-sm mb-3">{agent.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {agent.tools.map(tool => (
                        <span key={tool} className="text-xs bg-gray-800 px-2 py-1 rounded">🔧 {tool}</span>
                      ))}
                      {agent.tags.slice(0, 2).map(tag => (
                        <span key={tag} className="text-xs bg-gray-800 px-2 py-1 rounded">#{tag}</span>
                      ))}
                    </div>
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={e => { e.stopPropagation(); handleExport(agent.id, 'python') }}
                        className="text-xs bg-gray-800 hover:bg-gray-700 px-2 py-1 rounded"
                      >
                        📋 Export Py
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); handleExport(agent.id, 'typescript') }}
                        className="text-xs bg-gray-800 hover:bg-gray-700 px-2 py-1 rounded"
                      >
                        📋 Export TS
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {filteredAgents.length === 0 && (
                <div className="text-center py-20 text-gray-500">No agents found</div>
              )}
            </div>
          </div>
        )}

        {view === 'builder' && (
          <div className="h-full overflow-y-auto p-6">
            <div className="max-w-2xl mx-auto">
              <h2 className="text-2xl font-bold mb-6">🛠️ Build Custom Agent</h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Agent Name *</label>
                  <input
                    value={builderForm.name}
                    onChange={e => setBuilderForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="e.g., My Custom Writer"
                    className="w-full bg-gray-900 border border-gray-800 px-4 py-3 rounded-xl focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <input
                    value={builderForm.description}
                    onChange={e => setBuilderForm(f => ({ ...f, description: e.target.value }))}
                    placeholder="What does this agent do?"
                    className="w-full bg-gray-900 border border-gray-800 px-4 py-3 rounded-xl focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Category</label>
                    <select
                      value={builderForm.category}
                      onChange={e => setBuilderForm(f => ({ ...f, category: e.target.value }))}
                      className="w-full bg-gray-900 border border-gray-800 px-4 py-3 rounded-xl focus:outline-none focus:border-cyan-500"
                    >
                      {CATEGORIES.filter(c => c.id !== 'all').map(c => (
                        <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Model</label>
                    <select
                      value={builderForm.model}
                      onChange={e => setBuilderForm(f => ({ ...f, model: e.target.value }))}
                      className="w-full bg-gray-900 border border-gray-800 px-4 py-3 rounded-xl focus:outline-none focus:border-cyan-500"
                    >
                      <option value="llama3.2">llama3.2 (fast)</option>
                      <option value="qwen3:8b">qwen3:8b (smart)</option>
                      <option value="qwen3:1.7b">qwen3:1.7b (light)</option>
                      <option value="deepseek-r1:14b">deepseek-r1:14b (reasoning)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">System Prompt * (How the agent behaves)</label>
                  <textarea
                    value={builderForm.system_prompt}
                    onChange={e => setBuilderForm(f => ({ ...f, system_prompt: e.target.value }))}
                    placeholder="You are an expert..."
                    rows={6}
                    className="w-full bg-gray-900 border border-gray-800 px-4 py-3 rounded-xl focus:outline-none focus:border-cyan-500 font-mono text-sm"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-2">Tools</label>
                  <div className="flex gap-2">
                    {ALL_TOOLS.map(tool => (
                      <button
                        key={tool}
                        onClick={() => toggleTool(tool)}
                        className={`px-4 py-2 rounded-lg text-sm ${
                          builderForm.tools.includes(tool)
                            ? 'bg-cyan-600 text-white'
                            : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                        }`}
                      >
                        🔧 {tool}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">
                    Temperature: {builderForm.temperature.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={builderForm.temperature}
                    onChange={e => setBuilderForm(f => ({ ...f, temperature: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Precise (0.0)</span>
                    <span>Creative (1.0)</span>
                  </div>
                </div>

                <button
                  onClick={handleCreateAgent}
                  disabled={builderStatus === 'saving'}
                  className="w-full bg-cyan-600 hover:bg-cyan-700 disabled:bg-gray-700 py-3 rounded-xl font-semibold"
                >
                  {builderStatus === 'saving' ? 'Creating...' : '🚀 Create Agent'}
                </button>

                {builderStatus === 'done' && (
                  <div className="bg-green-900 border border-green-700 text-green-300 p-3 rounded-xl text-sm">
                    ✅ {builderMsg}
                  </div>
                )}
                {builderStatus === 'error' && (
                  <div className="bg-red-900 border border-red-700 text-red-300 p-3 rounded-xl text-sm">
                    ❌ {builderMsg}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {view === 'chat' && selectedAgent && (
          <div className="h-full flex flex-col">
            <div className="border-b border-gray-800 p-4 bg-gray-900">
              <div className="max-w-4xl mx-auto flex items-center justify-between">
                <div>
                  <h2 className="font-semibold">{selectedAgent.name}</h2>
                  <p className="text-gray-400 text-sm">{selectedAgent.description}</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleExport(selectedAgent.id, 'python')} className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm">📋 Export</button>
                  <button onClick={() => setView('marketplace')} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg">← Back</button>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <div className="max-w-4xl mx-auto space-y-4">
                {messages.length === 0 && (
                  <div className="text-center py-20 text-gray-500">
                    <div className="text-4xl mb-4">💬</div>
                    <p>Start chatting with {selectedAgent.name}</p>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-2xl p-4 ${msg.role === 'user' ? 'bg-cyan-600' : 'bg-gray-900'}`}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-900 rounded-2xl p-4">
                      <div className="flex gap-2">
                        <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                        <div className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="border-t border-gray-800 p-4 bg-gray-900">
              <div className="max-w-4xl mx-auto flex gap-3">
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyPress={e => e.key === 'Enter' && handleRun()}
                  placeholder={`Message ${selectedAgent.name}...`}
                  className="flex-1 bg-gray-800 px-4 py-3 rounded-xl border border-gray-700 focus:outline-none focus:border-cyan-500"
                  disabled={isLoading}
                />
                <button
                  onClick={handleRun}
                  disabled={isLoading || !input.trim()}
                  className="bg-cyan-600 hover:bg-cyan-700 disabled:bg-gray-700 px-6 py-3 rounded-xl font-semibold"
                >
                  {isLoading ? '...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Export Modal */}
      {exportData && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50" onClick={() => setExportData(null)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl max-w-3xl w-full max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-gray-800">
              <h3 className="font-semibold">📋 Export: {exportData.agent} ({exportData.format})</h3>
              <div className="flex gap-2">
                <button
                  onClick={() => { navigator.clipboard.writeText(exportData.code); }}
                  className="px-3 py-1 bg-cyan-600 hover:bg-cyan-700 rounded text-sm"
                >
                  Copy
                </button>
                <button onClick={() => setExportData(null)} className="text-gray-400 hover:text-white">✕</button>
              </div>
            </div>
            <pre className="p-4 overflow-auto text-sm text-gray-300 font-mono flex-1">{exportData.code}</pre>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="bg-red-600 text-white px-4 py-2 text-sm flex justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}
    </div>
  )
}

export default App
