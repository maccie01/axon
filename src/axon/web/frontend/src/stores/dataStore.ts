import { create } from 'zustand';

export interface NodeContext {
  node: any;
  callers: Array<{ node: any; confidence: number }>;
  callees: Array<{ node: any; confidence: number }>;
  typeRefs: any[];
  processes: string[];
}

export interface CypherEntry {
  query: string;
  timestamp: number;
}

export interface CypherResult {
  columns: string[];
  rows: any[][];
  rowCount: number;
  durationMs: number;
}

interface DataStore {
  // Node detail
  nodeContext: NodeContext | null;
  impactResult: any | null;
  fileContent: { path: string; content: string; language: string } | null;
  nodeProcesses: any[] | null;

  // Analysis data
  healthScore: any | null;
  deadCode: any | null;
  couplingData: any[] | null;
  allProcesses: any[] | null;

  // Cypher
  cypherHistory: CypherEntry[];
  cypherResult: CypherResult | null;

  // Loading states
  loading: Record<string, boolean>;

  // Actions
  setNodeContext: (ctx: NodeContext | null) => void;
  setImpactResult: (result: any | null) => void;
  setFileContent: (content: { path: string; content: string; language: string } | null) => void;
  setNodeProcesses: (processes: any[] | null) => void;
  setHealthScore: (score: any | null) => void;
  setDeadCode: (report: any | null) => void;
  setCouplingData: (data: any[] | null) => void;
  setAllProcesses: (processes: any[] | null) => void;
  setCypherResult: (result: CypherResult | null) => void;
  addCypherHistory: (query: string) => void;
  setLoading: (key: string, value: boolean) => void;
}

export const useDataStore = create<DataStore>((set) => ({
  nodeContext: null,
  impactResult: null,
  fileContent: null,
  nodeProcesses: null,
  healthScore: null,
  deadCode: null,
  couplingData: null,
  allProcesses: null,
  cypherHistory: JSON.parse(localStorage.getItem('axon-cypher-history') || '[]'),
  cypherResult: null,
  loading: {},

  setNodeContext: (ctx) => set({ nodeContext: ctx }),
  setImpactResult: (result) => set({ impactResult: result }),
  setFileContent: (content) => set({ fileContent: content }),
  setNodeProcesses: (processes) => set({ nodeProcesses: processes }),
  setHealthScore: (score) => set({ healthScore: score }),
  setDeadCode: (report) => set({ deadCode: report }),
  setCouplingData: (data) => set({ couplingData: data }),
  setAllProcesses: (processes) => set({ allProcesses: processes }),
  setCypherResult: (result) => set({ cypherResult: result }),
  addCypherHistory: (query) => set((s) => {
    const entry: CypherEntry = { query, timestamp: Date.now() };
    const history = [entry, ...s.cypherHistory].slice(0, 20);
    localStorage.setItem('axon-cypher-history', JSON.stringify(history));
    return { cypherHistory: history };
  }),
  setLoading: (key, value) => set((s) => ({
    loading: { ...s.loading, [key]: value },
  })),
}));
