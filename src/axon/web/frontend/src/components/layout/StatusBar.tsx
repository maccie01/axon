import { useGraphStore } from '@/stores/graphStore';
import { useDataStore } from '@/stores/dataStore';

export function StatusBar() {
  const overview = useGraphStore((s) => s.overview);
  const communities = useGraphStore((s) => s.communities);
  const deadCode = useDataStore((s) => s.deadCode);
  const healthScore = useDataStore((s) => s.healthScore);

  const nodeCount = overview?.totals.nodes ?? 0;
  const communityCount = communities.length;
  const deadCount =
    typeof deadCode === 'object' && deadCode !== null && 'count' in deadCode
      ? (deadCode as { count: number }).count
      : 0;
  const health =
    typeof healthScore === 'object' && healthScore !== null && 'score' in healthScore
      ? (healthScore as { score: number }).score
      : null;

  // Detect primary language from overview
  const language = overview?.nodesByLabel
    ? Object.keys(overview.nodesByLabel).find(
        (k) => !['File', 'Folder', 'Community', 'Process'].includes(k),
      ) ?? '--'
    : '--';

  const pipe = (
    <span
      className="mx-1.5"
      style={{ color: 'var(--text-dimmed)' }}
    >
      &#9474;
    </span>
  );

  return (
    <footer
      className="flex items-center px-3 shrink-0 select-none"
      style={{
        height: 24,
        background: 'var(--bg-surface)',
        borderTop: '1px solid var(--border)',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
        color: 'var(--text-secondary)',
      }}
    >
      {/* Indexed indicator */}
      <span className="flex items-center gap-1">
        <span style={{ color: nodeCount > 0 ? 'var(--accent)' : 'var(--text-dimmed)' }}>
          &#9679;
        </span>
        <span>{nodeCount > 0 ? 'indexed' : 'no data'}</span>
      </span>

      {pipe}

      {/* Language */}
      <span>{language.toLowerCase()}</span>

      {pipe}

      {/* Communities */}
      <span>{communityCount} communities</span>

      {pipe}

      {/* Dead code */}
      <span>{deadCount} dead</span>

      {pipe}

      {/* Health score */}
      <span>health: {health !== null ? health : '--'}</span>
    </footer>
  );
}
