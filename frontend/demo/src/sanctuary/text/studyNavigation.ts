// Reader order stays intact. Each realm visits its own types within that order.
type StudyMode = 'text' | 'questions';
type StudyPosition = { knowledge_id: number; type: string };

export function realmForNode(node: StudyPosition): StudyMode {
  return node.type === 'exercise' ? 'questions' : 'text';
}

export function adjacentStudyNode<T extends StudyPosition>(nodes: T[], id: number, mode: StudyMode, direction: 1 | -1): T | undefined {
  const start = nodes.findIndex(node => node.knowledge_id === id);
  if (start < 0) return;
  for (let at = start + direction; at >= 0 && at < nodes.length; at += direction) {
    if (realmForNode(nodes[at]) === mode) return nodes[at];
  }
}
