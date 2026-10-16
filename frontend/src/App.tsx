import { useState, useEffect, useRef } from 'react'
import { useStore, Agent } from './store'

const CATEGORIES = [
  { id: 'all', name: 'All', icon: '🌐' },
  { id: 'writing', name: 'Writing', icon: '✍️' },
  { id: 'coding', name: 'Coding', icon: '💻' },
  { id: 'research', name: 'Research', icon: '🔍' },
  { id: 'marketing', name: 'Marketing', icon: '📈' },
]

function App() {
  const [input, setInput] = useState('')
  const [category, setCategory] = useState('all')
  const [view, setView] = useState<'marketplace' | 'chat'>('marketplace')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const {
    agents,
    selectedAgent,
    messages,
    isLoading,
    error,
    setAgents,
    selectAgent,
    addMessage,
    setLoading,
    setError,
  } = useStore()

  // Fetch agents
  useEffect(() => {
    fetch('/api/agents/')
      .then(r => r.json())
      .then(data => setAgents(data.agents))
      .catch(err => console.error('Failed to fetch agents:', err))
  }, [setAgents])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const filteredAgents = category === 'all'
    ? agents
    : agents.filter(a => a.category === category)

  const handleRun = async () => {
    if (!input.trim() || !selectedAgent || isLoading) return
    
    const userMsg = input
    addMessage({ role: 'user', content: userMsg, agentId: selectedAgent.id })
    setLoading(true)
    setInput('')
    
    try {
      const res = await fetch('/api/agents/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgent.id,
          message: userMsg,
        }),
      })
      
      if (!res.ok) throw new Error('Failed')
      const data = await res.json()
      
      addMessage({ role: 'assistant', content: data.output, agentId: selectedAgent.id })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex flex-col bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🚀</span>
            <h1 className="text-xl font-bold">AgentVerse Hub</h1>
            <span className="text-gray-500 text-sm">AI Agent Marketplace</span>
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
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-hidden">
        {view === 'marketplace' ? (
          /* Marketplace View */
          <div className="h-full overflow-y-auto p-6">
            <div className="max-w-7xl mx-auto">
              {/* Categories */}
              <div className="flex gap-2 mb-6">
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
              </div>

              {/* Agent Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredAgents.map(agent => (
                  <div
                    key={agent.id}
                    className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-cyan-500 transition cursor-pointer"
                    onClick={() => {
                      selectAgent(agent)
                      setView('chat')
                    }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold">{agent.name}</h3>
                      {agent.is_template && (
                        <span className="text-xs bg-gray-800 px-2 py-1 rounded">Template</span>
                      )}
                    </div>
                    <p className="text-gray-400 text-sm mb-3">{agent.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {agent.tools.map(tool => (
                        <span key={tool} className="text-xs bg-gray-800 px-2 py-1 rounded">
                          🔧 {tool}
                        </span>
                      ))}
                      {agent.tags.slice(0, 3).map(tag => (
                        <span key={tag} className="text-xs bg-gray-800 px-2 py-1 rounded">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {filteredAgents.length === 0 && (
                <div className="text-center py-20 text-gray-500">
                  No agents in this category
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Chat View */
          selectedAgent && (
            <div className="h-full flex flex-col">
              {/* Agent Header */}
              <div className="border-b border-gray-800 p-4 bg-gray-900">
                <div className="max-w-4xl mx-auto flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold">{selectedAgent.name}</h2>
                    <p className="text-gray-400 text-sm">{selectedAgent.description}</p>
                  </div>
                  <button
                    onClick={() => setView('marketplace')}
                    className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg"
                  >
                    ← Back
                  </button>
                </div>
              </div>

              {/* Messages */}
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
                      <div className={`max-w-[80%] rounded-2xl p-4 ${
                        msg.role === 'user' ? 'bg-cyan-600' : 'bg-gray-900'
                      }`}>
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

              {/* Input */}
              <div className="border-t border-gray-800 p-4 bg-gray-900">
                <div className="max-w-4xl mx-auto flex gap-3">
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleRun()}
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
          )
        )}
      </div>

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
