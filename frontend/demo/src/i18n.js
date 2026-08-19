import { computed, ref } from "vue";

const en = {
  version: "Web Demo Version 0.0.1", exit: "Exit", mainMenu: "Main menu", back: "Back",
  library: "Arcane library", searchBooks: "Search by book name", recommended: "Recommended",
  review: "Review", advice: "Advice", expand: "Expand", generate: "Generate", comingSoon: "This realm is coming soon.",
  title: "Title", aiSummary: "AI summary", contents: "Contents", isbn: "ISBN", summon: "Summon grimoire",
  summoned: "Grimoire summoned", grimoires: "My grimoires", recent: "Recently summoned", noGrimoires: "No grimoires yet.",
  text: "Text", notes: "Notes", questions: "Questions", train: "Train", preview: "Preview", progress: "Progress",
  project: "Project", crystallize: "Crystallize", book: "Book", graph: "Graph", close: "Close",
  statement: "Statement", workings: "Workings", prompt: "Prompt", listen: "Listen", markDone: "Mark done", completed: "Completed",
  previous: "Previous", next: "Next", knowledge: "Knowledge", tag: "Tag", saveNote: "Save note", newScribble: "New scribble",
  scribbles: "Scribble notes", attachedNotes: "Attached notes", notePlaceholder: "Capture an idea, connection, or question…",
  noteConstellation: "Note constellation", allNotes: "All notes", delete: "Delete", similarity: "Resonant knowledge",
  similarityMethod: "Equal blend of statement and statement + working-summary embeddings", noResults: "No resonant objects yet.",
  returnOrigin: "Return to original book", questionMode: "Exercise path", textMode: "Knowledge path", notesMode: "Scholar's desk",
  bookwork: "Bookwork", sectionPath: "Section path", searchGrimoires: "Search your grimoires", open: "Open",
  language: "Language", emptySearch: "No books match that search.", saved: "Saved", soundSoon: "Audio playback is coming soon.",
  promptSoon: "AI prompting is coming soon.", projectSoon: "Projection search is coming soon.", selectNode: "Select a node to study it.",
  questionSymbol: "Question to solve", bookSymbol: "Source bookwork", notesHelp: "Notes stay attached to knowledge. Scribbles belong to you across books.",
  startWriting: "Select a note or create a scribble.", realmText: "Read structured knowledge in book order.", realmNotes: "Organise attached notes and free-form scribbles.",
  realmQuestions: "Work through exercises with context nearby.", realmExpand: "Explore wider connections.", realmReview: "Return to what needs reinforcement.",
  realmPreview: "Look ahead without losing your place.", realmAdvice: "Receive study guidance.", realmProgress: "See mastery grow over time."
};

const zh = {
  ...en, version: "网页演示版本 0.0.1", exit: "退出", mainMenu: "主菜单", back: "返回", library: "玄秘书库", searchBooks: "按书名搜索", recommended: "推荐",
  review: "复习", advice: "建议", expand: "拓展", generate: "生成", comingSoon: "此境域即将开放。", title: "书名", aiSummary: "AI 摘要", contents: "目录", isbn: "ISBN", summon: "召唤魔典", summoned: "魔典已召唤", grimoires: "我的魔典", recent: "最近召唤", noGrimoires: "尚未召唤魔典。",
  text: "正文", notes: "笔记", questions: "问题", train: "训练", preview: "预览", progress: "进度", project: "投射", crystallize: "晶化", book: "书籍", graph: "图谱", close: "关闭",
  statement: "陈述", workings: "推导", prompt: "提示", listen: "聆听", markDone: "标记完成", completed: "已完成", previous: "上一个", next: "下一个", knowledge: "知识", tag: "标签", saveNote: "保存笔记", newScribble: "新建随笔",
  scribbles: "随笔", attachedNotes: "关联笔记", notePlaceholder: "记录想法、联系或问题…", noteConstellation: "笔记星图", allNotes: "全部笔记", delete: "删除", similarity: "共鸣知识", similarityMethod: "陈述嵌入与陈述加推导摘要嵌入等权融合", noResults: "暂无共鸣对象。",
  returnOrigin: "返回原始书籍", questionMode: "习题路径", textMode: "知识路径", notesMode: "学者书案", bookwork: "书本知识", sectionPath: "章节路径", searchGrimoires: "搜索魔典", open: "打开", language: "语言", emptySearch: "没有匹配的书籍。", saved: "已保存", soundSoon: "音频播放即将推出。", promptSoon: "AI 提示即将推出。", projectSoon: "投射搜索即将推出。", selectNode: "选择节点开始学习。", questionSymbol: "待解问题", bookSymbol: "来源书本", notesHelp: "关联笔记依附知识；随笔跨书籍归属于你。", startWriting: "选择笔记或新建随笔。",
  realmText: "按原书顺序阅读结构化知识。", realmNotes: "整理关联笔记与自由随笔。", realmQuestions: "结合上下文完成练习。", realmExpand: "探索更广泛的联系。", realmReview: "回到需要巩固的内容。", realmPreview: "在不丢失进度的情况下提前查看。", realmAdvice: "获得学习建议。", realmProgress: "观察掌握程度逐步提升。"
};

const ja = {
  ...en, version: "Web デモ バージョン 0.0.1", exit: "終了", mainMenu: "メインメニュー", back: "戻る", library: "秘術図書館", searchBooks: "書名で検索", recommended: "おすすめ", review: "復習", advice: "助言", expand: "展開", generate: "生成", comingSoon: "この領域は近日公開です。", title: "題名", aiSummary: "AI 要約", contents: "目次", isbn: "ISBN", summon: "グリモアを召喚", summoned: "グリモアを召喚しました", grimoires: "マイグリモア", recent: "最近の召喚", noGrimoires: "グリモアはまだありません。",
  text: "本文", notes: "ノート", questions: "問題", train: "訓練", preview: "プレビュー", progress: "進捗", project: "投影", crystallize: "結晶化", book: "書籍", graph: "グラフ", close: "閉じる", statement: "命題", workings: "導出", prompt: "プロンプト", listen: "音声", markDone: "完了にする", completed: "完了", previous: "前へ", next: "次へ", knowledge: "知識", tag: "タグ", saveNote: "ノート保存", newScribble: "新しい走り書き", scribbles: "走り書き", attachedNotes: "関連ノート", notePlaceholder: "アイデア、つながり、疑問を記録…", noteConstellation: "ノート星座", allNotes: "すべてのノート", delete: "削除", similarity: "共鳴する知識", similarityMethod: "命題と命題＋導出要約の埋め込みを同じ重みで合成", noResults: "共鳴するオブジェクトはまだありません。", returnOrigin: "元の本に戻る", questionMode: "演習ルート", textMode: "知識ルート", notesMode: "学者の机", bookwork: "本文", sectionPath: "章の経路", searchGrimoires: "グリモアを検索", open: "開く", language: "言語", emptySearch: "一致する書籍はありません。", saved: "保存しました", soundSoon: "音声再生は近日公開です。", promptSoon: "AI プロンプトは近日公開です。", projectSoon: "投影検索は近日公開です。", selectNode: "ノードを選択してください。", questionSymbol: "解く問題", bookSymbol: "出典", notesHelp: "関連ノートは知識に付き、走り書きは書籍を越えて保存されます。", startWriting: "ノートを選ぶか走り書きを作成してください。", realmText: "書籍順に構造化知識を読みます。", realmNotes: "関連ノートと走り書きを整理します。", realmQuestions: "文脈とともに演習を進めます。", realmExpand: "より広い接続を探索します。", realmReview: "補強が必要な内容へ戻ります。", realmPreview: "位置を失わず先を見ます。", realmAdvice: "学習助言を受けます。", realmProgress: "習熟度の成長を確認します。"
};

const es = { ...en, exit: "Salir", mainMenu: "Menú principal", back: "Volver", library: "Biblioteca arcana", searchBooks: "Buscar por título", recommended: "Recomendados", comingSoon: "Este reino estará disponible pronto.", aiSummary: "Resumen de IA", contents: "Contenido", summon: "Invocar grimorio", grimoires: "Mis grimorios", text: "Texto", notes: "Notas", questions: "Preguntas", progress: "Progreso", statement: "Enunciado", workings: "Desarrollo", markDone: "Marcar como hecho", completed: "Completado", previous: "Anterior", next: "Siguiente", language: "Idioma", saveNote: "Guardar nota", newScribble: "Nueva nota libre", similarity: "Conocimiento resonante" };
const fr = { ...en, exit: "Quitter", mainMenu: "Menu principal", back: "Retour", library: "Bibliothèque arcanique", searchBooks: "Rechercher par titre", recommended: "Recommandés", comingSoon: "Ce royaume arrive bientôt.", aiSummary: "Résumé IA", contents: "Sommaire", summon: "Invoquer le grimoire", grimoires: "Mes grimoires", text: "Texte", notes: "Notes", questions: "Questions", progress: "Progression", statement: "Énoncé", workings: "Démonstration", markDone: "Marquer terminé", completed: "Terminé", previous: "Précédent", next: "Suivant", language: "Langue", saveNote: "Enregistrer", newScribble: "Nouvelle note libre", similarity: "Connaissances en résonance" };
const de = { ...en, exit: "Beenden", mainMenu: "Hauptmenü", back: "Zurück", library: "Arkane Bibliothek", searchBooks: "Nach Buchtitel suchen", recommended: "Empfohlen", comingSoon: "Dieser Bereich erscheint bald.", aiSummary: "KI-Zusammenfassung", contents: "Inhalt", summon: "Grimoire beschwören", grimoires: "Meine Grimoires", text: "Text", notes: "Notizen", questions: "Fragen", progress: "Fortschritt", statement: "Aussage", workings: "Herleitung", markDone: "Als erledigt markieren", completed: "Abgeschlossen", previous: "Zurück", next: "Weiter", language: "Sprache", saveNote: "Notiz speichern", newScribble: "Neue freie Notiz", similarity: "Resonierendes Wissen" };
const ko = { ...en, exit: "나가기", mainMenu: "메인 메뉴", back: "뒤로", library: "비전 도서관", searchBooks: "책 제목 검색", recommended: "추천", comingSoon: "이 영역은 곧 공개됩니다.", aiSummary: "AI 요약", contents: "목차", summon: "그리모어 소환", grimoires: "내 그리모어", text: "본문", notes: "노트", questions: "문제", progress: "진행도", statement: "명제", workings: "풀이", markDone: "완료 표시", completed: "완료", previous: "이전", next: "다음", language: "언어", saveNote: "노트 저장", newScribble: "새 자유 노트", similarity: "공명 지식" };

const dictionaries = { en, zh, ja, ko, es, fr, de };
export const languageOptions = [
  ["en", "English"], ["zh", "中文"], ["ja", "日本語"], ["ko", "한국어"],
  ["es", "Español"], ["fr", "Français"], ["de", "Deutsch"]
];

export function useDemoI18n() {
  const lang = ref(localStorage.getItem("demo-language") || localStorage.getItem("language") || "en");
  const t = computed(() => dictionaries[lang.value] || dictionaries.en);
  function setLang(value) {
    lang.value = dictionaries[value] ? value : "en";
    localStorage.setItem("demo-language", lang.value);
    document.documentElement.lang = lang.value === "zh" ? "zh-CN" : lang.value;
  }
  setLang(lang.value);
  return { lang, t, setLang };
}
