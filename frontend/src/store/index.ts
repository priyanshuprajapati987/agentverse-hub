import { create } from 'zustand'

export interface Agent {
  id: string
  name: string
  description: string
  category: string
  tools: string[]
  tags: string[]
  author: string
  is_template: boolean
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  agentId?: string
}

interface AppState {
  agents: Agent[]
  selectedAgent: Agent | null
  messages: Message[]
  isLoading: boolean
  error: string | null
  setAgents: (agents: Agent[]) => void
  selectAgent: (agent: Agent | null) => void
  addMessage: (message: Message) => void
  updateLastMessage: (content: string) => void
  clearMessages: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useStore = create<AppState>((set) => ({
  agents: [],
  selectedAgent: null,
  messages: [],
  isLoading: false,
  error: null,
  
  setAgents: (agents) => set({ agents }),
  selectAgent: (agent) => set({ selectedAgent: agent, messages: [] }),
  addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
  updateLastMessage: (content) =>
    set((s) => {
      const messages = [...s.messages]
      const last = messages.length - 1
      if (last >= 0 && messages[last].role === 'assistant') {
        messages[last] = { ...messages[last], content }
      }
      return { messages }
    }),
  clearMessages: () => set({ messages: [] }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}))
