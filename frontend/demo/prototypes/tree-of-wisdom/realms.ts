// Current vocabulary, shared by the diagram chooser and its local arrival views.
export const realms = [
  { id: 'text', mark: '書', accent: '#ade7ec' },
  { id: 'questions', mark: '問', accent: '#e0c4f3' },
  { id: 'notes', mark: '寫', accent: '#e8c2d1' },
  { id: 'review', mark: '覺', accent: '#c6c7ef' },
  { id: 'preview', mark: '天', accent: '#cbddec' },
  { id: 'advice', mark: '意', accent: '#e4b9d9' },
  { id: 'expand', mark: '道', accent: '#a9d2f2' },
  { id: 'progress', mark: '境', accent: '#acdfe9' },
] as const;
export type RealmId = typeof realms[number]['id'];

const en = {
  removeGrimoire:'Remove',removedGrimoire:'Removed from My grimoires.',removalKeepsPalace:'Your Mind Palace is unchanged.',
  realmChoose: 'Choose a realm', realmEnter: 'Enter', realmReturn: 'Realms', realmSkip: 'Skip movement',
  realmBook: 'Realm book', realmLocal: 'Local study sample', realmNext: 'This study view is a later design round.',
  realmNotesHint: 'Write a thought…', realmNotesLocal: 'Notes stay here for this visit.',
  realmTextPurpose: 'Follow the knowledge in this grimoire.',
  realmQuestionsPurpose: 'Work through exercises and problems.',
  realmNotesPurpose: 'Collect your notes and scribbles.',
  realmReviewPurpose: 'Revisit knowledge through spaced repetition.',
  realmPreviewPurpose: 'Glimpse the results your study can lead to.',
  realmAdvicePurpose: 'Reflect on advice from your reading.',
  realmExpandPurpose: 'Discover knowledge beyond this grimoire.',
  realmProgressPurpose: 'See your progress and plan further study.',
};
const zh: typeof en = {
  removeGrimoire:'移除',removedGrimoire:'已从我的魔典中移除。',removalKeepsPalace:'你的思维宫殿保持不变。',
  realmChoose:'选择领域',realmEnter:'进入',realmReturn:'各领域',realmSkip:'跳过移动',realmBook:'领域之书',realmLocal:'本地学习示例',realmNext:'此学习界面将在后续设计中探索。',realmNotesHint:'写下一个想法…',realmNotesLocal:'笔记仅在本次访问中保留。',
  realmTextPurpose:'顺着魔典中的知识学习。',realmQuestionsPurpose:'练习题目，探索解法。',realmNotesPurpose:'收集笔记与随笔。',realmReviewPurpose:'通过间隔重复温习知识。',realmPreviewPurpose:'一瞥学习将带你抵达的成果。',realmAdvicePurpose:'思考阅读中收集的建议。',realmExpandPurpose:'发现这本魔典之外的知识。',realmProgressPurpose:'回顾进度，规划进一步学习。',
};
const ja: typeof en = {
  removeGrimoire:'取り除く',removedGrimoire:'自分の魔導書から取り除きました。',removalKeepsPalace:'記憶の宮殿はそのままです。',
  realmChoose:'領域を選ぶ',realmEnter:'入る',realmReturn:'領域',realmSkip:'移動をスキップ',realmBook:'領域の書',realmLocal:'ローカル学習サンプル',realmNext:'この学習画面は後のデザインで検討します。',realmNotesHint:'考えを書き留める…',realmNotesLocal:'メモは今回の訪問中のみ保持されます。',
  realmTextPurpose:'魔導書の知識を順に学ぶ。',realmQuestionsPurpose:'問題と演習に取り組む。',realmNotesPurpose:'ノートや覚え書きを集める。',realmReviewPurpose:'間隔反復で知識を振り返る。',realmPreviewPurpose:'学びの先にある成果を垣間見る。',realmAdvicePurpose:'読書で得た助言を振り返る。',realmExpandPurpose:'この魔導書の先にある知識を探す。',realmProgressPurpose:'進捗を確認し、次の学びを計画する。',
};
export const realmCopy: Record<string, typeof en> = { en, zh, ja };
export const purposeKey = (id: RealmId) => `realm${id[0].toUpperCase()}${id.slice(1)}Purpose` as keyof typeof en;
