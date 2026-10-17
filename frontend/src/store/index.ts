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
  run_count?: number
  star_count?: number
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
  messagesByAgent: Record<string, Message[]>
  isLoading: boolean
  error: string | null
  setAgents: (agents: Agent[]) => void
  selectAgent: (agent: Agent | null) => void
  addMessage: (message: Message) => void
  updateLastMessage: (content: string) => void
  removeLastMessage: () => void
  clearMessages: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

function withActive(map: Record<string, Message[]>, agentId: string | undefined, messages: Message[]) {
  const next = { ...map }
  if (agentId) next[agentId] = messages
  return next
}

export const useStore = create<AppState>((set) => ({
  agents: [],
  selectedAgent: null,
  messages: [],
  messagesByAgent: {},
  isLoading: false,
  error: null,

  setAgents: (agents) => set({ agents }),
  selectAgent: (agent) =>
    set((s) => {
      const map = withActive(s.messagesByAgent, s.selectedAgent?.id, s.messages)
      return {
        selectedAgent: agent,
        messages: agent ? (map[agent.id] ?? []) : [],
        messagesByAgent: map,
      }
    }),
  addMessage: (message) =>
    set((s) => {
      const messages = [...s.messages, message]
      return { messages, messagesByAgent: withActive(s.messagesByAgent, s.selectedAgent?.id, messages) }
    }),
  updateLastMessage: (content) =>
    set((s) => {
      const messages = [...s.messages]
      const last = messages.length - 1
      if (last >= 0 && messages[last].role === 'assistant') {
        messages[last] = { ...messages[last], content }
      }
      return { messages, messagesByAgent: withActive(s.messagesByAgent, s.selectedAgent?.id, messages) }
    }),
  removeLastMessage: () =>
    set((s) => {
      const messages = s.messages.slice(0, -1)
      return { messages, messagesByAgent: withActive(s.messagesByAgent, s.selectedAgent?.id, messages) }
    }),
  clearMessages: () =>
    set((s) => ({
      messages: [],
      messagesByAgent: withActive(s.messagesByAgent, s.selectedAgent?.id, []),
    })),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}))
