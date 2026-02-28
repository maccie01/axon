/**
 * Typed HTTP client for the Axon Web UI API.
 *
 * Uses `ky` with a `/api` prefix that the Vite dev-server proxies to the
 * FastAPI backend at `http://localhost:8420`.
 */

import ky from 'ky';
import type {
  GraphNode,
  GraphEdge,
  NodeContext,
  OverviewStats,
  SearchResult,
  ImpactResult,
  DeadCodeReport,
  CouplingPair,
  Community,
  Process,
  HealthScore,
  FolderNode,
  FileContent,
  CypherResult,
  DiffResult,
} from '@/types';

// ---------------------------------------------------------------------------
// Base instance
// ---------------------------------------------------------------------------

const api = ky.create({
  prefixUrl: '/api',
  timeout: 30_000,
});

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------

export const graphApi = {
  /** Fetch the full knowledge graph (all nodes and edges). */
  getGraph: () =>
    api.get('graph').json<{ nodes: GraphNode[]; edges: GraphEdge[] }>(),

  /** Fetch a single node with its callers, callees, type refs, and process memberships. */
  getNode: (id: string) =>
    api.get(`node/${id}`).json<NodeContext>(),

  /** Fetch aggregate counts of nodes by label, edges by type, and totals. */
  getOverview: () =>
    api.get('overview').json<OverviewStats>(),
};

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export const searchApi = {
  /** Run hybrid search (FTS + optional vector) and return ranked results. */
  search: (query: string, limit = 20) =>
    api
      .post('search', { json: { query, limit } })
      .json<{ results: SearchResult[] }>(),
};

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------

export const analysisApi = {
  /** Analyse the blast radius of a node by traversing callers up to `depth` hops. */
  getImpact: (nodeId: string, depth = 3) =>
    api
      .get(`impact/${nodeId}`, { searchParams: { depth } })
      .json<ImpactResult>(),

  /** List all symbols flagged as dead code, grouped by file. */
  getDeadCode: () =>
    api.get('dead-code').json<DeadCodeReport>(),

  /** Return temporal coupling pairs between files. */
  getCoupling: () =>
    api.get('coupling').json<{ pairs: CouplingPair[] }>(),

  /** Return community clusters with their member nodes. */
  getCommunities: () =>
    api.get('communities').json<{ communities: Community[] }>(),

  /** Query all Process nodes and their ordered steps. */
  getProcesses: () =>
    api.get('processes').json<{ processes: Process[] }>(),

  /** Compute a composite codebase health score from multiple dimensions. */
  getHealth: () =>
    api.get('health').json<HealthScore>(),
};

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

export const fileApi = {
  /** Build a nested folder tree from File and Folder nodes in the graph. */
  getTree: () =>
    api.get('tree').json<{ tree: FolderNode[] }>(),

  /** Read a source file from the repository. */
  getFile: (path: string) =>
    api.get('file', { searchParams: { path } }).json<FileContent>(),
};

// ---------------------------------------------------------------------------
// Cypher
// ---------------------------------------------------------------------------

export const cypherApi = {
  /** Execute a read-only Cypher query against the graph. */
  execute: (query: string) =>
    api.post('cypher', { json: { query } }).json<CypherResult>(),
};

// ---------------------------------------------------------------------------
// Diff
// ---------------------------------------------------------------------------

export const diffApi = {
  /** Compare two git refs structurally and return added/removed/modified entities. */
  compare: (base: string, compare: string) =>
    api
      .post('diff', { json: { base, compare } })
      .json<DiffResult>(),
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export const actionApi = {
  /** Trigger a full reindex (only available in watch mode). */
  reindex: () =>
    api.post('reindex').json<{ status: string }>(),
};
