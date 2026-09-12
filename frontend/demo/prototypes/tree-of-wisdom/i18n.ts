import { computed, inject, provide, type InjectionKey } from 'vue';
import { useDemoI18n, languageOptions } from '../../src/i18n';
export { languageOptions };
const en = {
  brief:'Brief', overview:'Overview', extract:'Extract', sanctuary:'The Sanctuary', tree:'Tree of Wisdom',
  search:'Search grimoires', allGrimoires:'All grimoires', add:'Add grimoire', enter:'Enter grimoire',
  inCollection:'In your grimoires', available:'Available to add', objects:'objects', passages:'passages',
  publisher:'Publisher', edition:'Edition', unavailable:'Unavailable', backToTree:'Back to Tree of Wisdom',
  closeBrief:'Close Brief and return to grimoires', reading:'Sample reading', samplePages:'Sample passages',
  previousPassage:'Previous passage', nextPassage:'Next passage', revealAnswer:'Reveal answer', hideAnswer:'Hide answer',
  sourceNote:'Source text stays in its supplied language.', collection:'My grimoires', collectionCount:'grimoires',
  noMatches:'No matching grimoires', trySearch:'Try another title or subject.', clearSearch:'Clear search',
  discover:'Explore grimoires', emptyCollection:'No grimoires yet', emptyCollectionHelp:'Add a grimoire from the tree to find it here.',
  recentlyOpened:'Recent activity', selected:'Selected grimoire', selectedSection:'Selected section',
  descend:'Descend', home:'Home', ascend:'Ascend to the tree', ascending:'Ascending', descending:'Descending',
  skipAscent:'Skip ascent', skipDescent:'Skip descent', openHomepage:'Open homepage', awaiting:'The Sanctuary awaits',
  projection:'Projection', orbit:'Orbit', signals:'Signals', prototype:'Prototype', added:'added',
  variant:'Variant', previousVariant:'Previous prototype', nextVariant:'Next prototype', tools:'More',
  realmsNext:'Realms will be designed in the next scene.', ready:'Your grimoire is ready.',
  readingHint:'Choose a passage to read.', noExtract:'No extract is available.', notStarted:'Not started',
  version:'Web Demo Version 0.0.4', progressLabel:'Completed', chapters:'chapters', fixtures:'Sample state',
};
const zh:typeof en = {
  brief:'简介', overview:'概览', extract:'节选', sanctuary:'圣所', tree:'智慧之树',
  search:'搜索魔典', allGrimoires:'所有魔典', add:'添加魔典', enter:'进入魔典',
  inCollection:'已加入我的魔典', available:'可以添加', objects:'个知识对象', passages:'段内容',
  publisher:'出版方', edition:'版本', unavailable:'暂无信息', backToTree:'返回智慧之树',
  closeBrief:'关闭简介并返回魔典', reading:'节选阅读', samplePages:'节选段落',
  previousPassage:'上一段', nextPassage:'下一段', revealAnswer:'显示答案', hideAnswer:'隐藏答案',
  sourceNote:'原文保持其提供的语言。', collection:'我的魔典', collectionCount:'本魔典',
  noMatches:'没有匹配的魔典', trySearch:'试试其他书名或学科。', clearSearch:'清除搜索',
  discover:'探索魔典', emptyCollection:'还没有魔典', emptyCollectionHelp:'从智慧之树添加魔典后，可以在这里找到它。',
  recentlyOpened:'最近活动', selected:'已选择魔典', selectedSection:'已选择章节',
  descend:'下降', home:'主页', ascend:'升向智慧之树', ascending:'正在上升', descending:'正在下降',
  skipAscent:'跳过上升', skipDescent:'跳过下降', openHomepage:'打开主页', awaiting:'圣所正在等候',
  projection:'投影', orbit:'轨道', signals:'信号', prototype:'原型', added:'本已添加',
  variant:'方案', previousVariant:'上一个方案', nextVariant:'下一个方案', tools:'更多',
  realmsNext:'下一个场景将设计各个领域。', ready:'你的魔典已准备好。',
  readingHint:'选择一段内容阅读。', noExtract:'暂无节选。', notStarted:'尚未开始',
  version:'Web Demo 版本 0.0.4', progressLabel:'已完成', chapters:'章', fixtures:'示例状态',
};
const ja:typeof en = {
  brief:'概要', overview:'全体像', extract:'抜粋', sanctuary:'聖域', tree:'知恵の樹',
  search:'魔導書を検索', allGrimoires:'すべての魔導書', add:'魔導書を追加', enter:'魔導書を開く',
  inCollection:'自分の魔導書に追加済み', available:'追加できます', objects:'個の知識', passages:'つの文章',
  publisher:'出版元', edition:'版', unavailable:'情報なし', backToTree:'知恵の樹へ戻る',
  closeBrief:'概要を閉じて魔導書に戻る', reading:'抜粋を読む', samplePages:'抜粋の文章',
  previousPassage:'前の文章', nextPassage:'次の文章', revealAnswer:'解答を表示', hideAnswer:'解答を隠す',
  sourceNote:'原文は提供された言語のまま表示されます。', collection:'自分の魔導書', collectionCount:'冊の魔導書',
  noMatches:'一致する魔導書がありません', trySearch:'別の書名や分野で検索してください。', clearSearch:'検索をクリア',
  discover:'魔導書を探す', emptyCollection:'魔導書はまだありません', emptyCollectionHelp:'知恵の樹から追加した魔導書がここに表示されます。',
  recentlyOpened:'最近の活動', selected:'選択した魔導書', selectedSection:'選択した章',
  descend:'下降', home:'ホーム', ascend:'知恵の樹へ昇る', ascending:'上昇中', descending:'下降中',
  skipAscent:'上昇をスキップ', skipDescent:'下降をスキップ', openHomepage:'ホームページを開く', awaiting:'聖域が待っています',
  projection:'投影', orbit:'軌道', signals:'シグナル', prototype:'プロトタイプ', added:'冊を追加済み',
  variant:'案', previousVariant:'前の案', nextVariant:'次の案', tools:'その他',
  realmsNext:'次の場面で各領域をデザインします。', ready:'魔導書の準備ができました。',
  readingHint:'読む文章を選んでください。', noExtract:'抜粋はありません。', notStarted:'未開始',
  version:'Web Demo バージョン 0.0.4', progressLabel:'完了', chapters:'章', fixtures:'サンプル状態',
};
const extra:Record<string,typeof en>={en,zh,ja};
const roundCopy:Record<string,Record<string,string>>={
  en:{folio:'Folio',contentsBeside:'Contents beside',sidePanel:'Side panel',topMenu:'Top menu',sideRail:'Side rail',bottomDock:'Bottom dock',actions:'Actions',acrossGrimoires:'Across grimoires',acrossReview:'Spaced repetition across your grimoires',acrossAdvice:'Revisit collected advice',acrossExpand:'Discover knowledge beyond your grimoires',acrossProgress:'Study statistics and longer-term planning',bookDetails:'Book details',read:'Read',backToTree:'Back to grimoires'},
  zh:{folio:'双页',contentsBeside:'侧边目录',sidePanel:'侧面板',topMenu:'顶部菜单',sideRail:'侧栏',bottomDock:'底部栏',actions:'功能',acrossGrimoires:'跨魔典',acrossReview:'跨魔典进行间隔复习',acrossAdvice:'回顾收集的建议',acrossExpand:'探索魔典之外的知识',acrossProgress:'学习统计与长期规划',bookDetails:'书籍信息',read:'阅读',backToTree:'返回魔典'},
  ja:{folio:'見開き',contentsBeside:'目次を併置',sidePanel:'サイドパネル',topMenu:'上部メニュー',sideRail:'サイドバー',bottomDock:'下部ドック',actions:'機能',acrossGrimoires:'魔導書を横断',acrossReview:'魔導書を横断した間隔反復',acrossAdvice:'集めた助言を振り返る',acrossExpand:'魔導書の外の知識を探す',acrossProgress:'学習統計と長期計画',bookDetails:'書籍情報',read:'読む',backToTree:'魔導書に戻る'},
};
function createI18n(){
  const base=useDemoI18n();
  return {...base,t:computed<Record<string,string>>(()=>({...base.t.value,...(extra[base.lang.value]||en),...(roundCopy[base.lang.value]||roundCopy.en)}))};
}
const key:InjectionKey<ReturnType<typeof createI18n>>=Symbol('wisdom-language');
export function provideWisdomI18n(){const value=createI18n();provide(key,value);return value}
export function useWisdomI18n(){return inject(key)!}
