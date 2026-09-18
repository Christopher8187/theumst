<script setup lang="ts">
// Selected daily notebook, with the existing Text realm's translucent blue palette.
import { computed, nextTick, onMounted, toRef, useTemplateRef } from 'vue';
import StudyView from '../../../src/components/StudyView.vue';
import NotesDesk from '../../../src/components/NotesDesk.vue';
import NoteDecision from '../../../src/components/NoteDecision.vue';
import LanguageControl from '../LanguageControl.vue';
import GrimoireCompletion from '../GrimoireCompletion.vue';
import { useWisdomI18n } from '../i18n';
import type { SampleBook } from '../books';
import { useTextStudy } from './useTextStudy';
import NotebookTools from './NotebookTools.vue';
import './notebook-variants.css';
import './notebook-selected.css';
import './atlas-instrument.css';

const props = defineProps<{ book: SampleBook; initialMode?: 'text' | 'questions' }>();
const emit = defineEmits<{ back: []; completion: [bookId: string, count: number] }>();
const { t, lang } = useWisdomI18n();
function updateNotebookUrl() {
  const query = new URLSearchParams(location.search);
  query.set('notebook', 'B');
  history.replaceState(null, '', location.pathname + '?' + query);
}
const bookId = computed(() => props.book.id);
const copy = computed(() => ({ ...t.value,
  atlasSettings: lang.value === 'zh' ? '设置' : lang.value === 'ja' ? '設定' : 'Settings',
  atlasOverview: lang.value === 'zh' ? '全图' : lang.value === 'ja' ? '全体図' : 'Map overview',
  fitMap: lang.value === 'zh' ? '适应视图' : lang.value === 'ja' ? '全体を表示' : 'Fit map',
  download: lang.value === 'zh' ? '下载' : lang.value === 'ja' ? 'ダウンロード' : 'Download',
  dependencies: lang.value === 'zh' ? '依赖' : lang.value === 'ja' ? '依存関係' : 'Dependencies',
  dependenciesMethod: lang.value === 'zh' ? '当前知识对象直接依赖的知识对象。' : lang.value === 'ja' ? 'この知識オブジェクトが直接依存する知識オブジェクト。' : 'Knowledge objects this object directly depends on.',
  noDependencies: lang.value === 'zh' ? '此知识对象尚未记录依赖关系。' : lang.value === 'ja' ? 'この知識オブジェクトの依存関係は記録されていません。' : 'No dependencies are recorded for this knowledge object.',
  similarityMethod: lang.value === 'zh' ? '此原型使用关联知识示例，分数为示例值。' : lang.value === 'ja' ? 'この試作の関連知識とスコアは例示用です。' : 'Illustrative matches for this prototype. Scores are sample values.',
}));
const state = useTextStudy(bookId, copy, (id: string, count: number) => emit('completion', id, count), toRef(props, 'initialMode'));
const { book, sampleBook, nodes, sections, selectedId, selectedNode, mode, sideMode,
  notes, allNotes, showingAllNotes, graph, similarResults, similarStatus, similarError,
  discoveryKind, originBookId, activeImage, canBack, guard, actionBusy, toast } = state;
const title = useTemplateRef<HTMLElement>('title');
function back() { state.run(() => {
  if (!showingAllNotes.value && originBookId.value && book.value.grimoire_id !== originBookId.value) state.returnOrigin();
  else emit('back');
}); }
function escape(event: KeyboardEvent) {
  if (event.target instanceof Element && event.target.closest('.notebook-tools, .atlas-settings')) return;
  if (guard.pending.value) return;
  if (showingAllNotes.value || sideMode.value === 'graph') { event.stopPropagation(); event.preventDefault(); back(); }
}
onMounted(async () => { updateNotebookUrl(); await nextTick(); title.value?.focus({ preventScroll: true }); });
</script>

<template>
  <section class="text-realm notebook-study notebook-B notebook-selected" :class="{'all-notes-open':showingAllNotes}" @keydown.esc.capture="escape" :aria-label="showingAllNotes?t.notes:mode==='questions'?t.questions:t.text">
    <div class="text-folio" :inert="actionBusy || !!guard.pending.value">
    <nav class="text-topnav" :inert="actionBusy || !!guard.pending.value">
      <button class="text-return" type="button" @click="back"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 5-7 7 7 7M3 12h17"/></svg>{{!showingAllNotes && originBookId && book.grimoire_id!==originBookId?t.returnOrigin:t.realmReturn}}</button>
      <span v-if="showingAllNotes" tabindex="-1" class="text-realm-mark"><span aria-hidden="true">寫</span>{{t.notes}}</span>
      <GrimoireCompletion class="text-completion" :book="sampleBook" compact/>
      <LanguageControl/>
    </nav>
      <div class="text-spine" aria-hidden="true"><i></i></div>
      <StudyView v-if="!showingAllNotes" notebook :t="copy" :book="book" :nodes="nodes" :sections="sections"
        :selected-id="selectedId" :selected-node="selectedNode" :mode="mode" :side-mode="sideMode" :can-back="canBack"
        :notes="notes" :graph="graph" graph-status="ready" graph-error=""
        :similar-results="similarResults" :similar-status="similarStatus" :similar-error="similarError"
        :discovery-kind="discoveryKind" :origin-book-id="originBookId" :active-image="activeImage"
        @continue="state.run(state.continueReading)" @back-object="state.run(state.backObject)"
        @select="state.run(state.select,$event)" @action="state.run(state.action,$event)"
        @close-side="state.run(state.closeSide)" @save-note="state.saveNote($event)"
        @notes-page="state.run(state.notesPage)" @open-result="state.run(state.openResult,$event)"
        @return-origin="state.run(state.returnOrigin)" @move="state.run(state.moveExercise,$event)"
        @done="state.run(state.markDone,$event)" @open-image="state.run(state.openImage,$event)"
        @soon="state.comingSoon($event)">
        <template #study-heading>
          <h1>{{book.title}}</h1>
          <span ref="title" tabindex="-1" class="text-realm-mark"><span aria-hidden="true">{{mode==='questions'?'問':'書'}}</span>{{mode==='questions'?t.questions:t.text}}</span>
        </template>
        <template #reading-footer>
          <div class="notebook-action-row">
            <NotebookTools :labels="copy" :side-mode="sideMode" :discovery-kind="discoveryKind" :mode="mode" @action="state.run(state.action,$event)"/>
            <button class="notebook-prompt" type="button" @click="state.comingSoon('prompt')">✦ {{t.prompt}}</button>
          </div>
        </template>
        <template #reading-actions="{current}">
          <button type="button" :disabled="!canBack" @click="state.run(state.backObject)">{{t.back}}</button>
          <button type="button" :disabled="!current" @click="state.run(state.continueReading)">{{t.continue}}</button>
          <button v-if="current" class="notebook-done" type="button" :class="{done:current.completed}" @click="state.run(state.markDone,current)">{{current.completed?'✓ '+t.completed:'○ '+t.markDone}}</button>
        </template>
      </StudyView>
      <NotesDesk v-else :t="copy" :notes="allNotes" :grimoire-id="book.grimoire_id"/>
    </div>
    <p v-if="toast" class="text-notice" role="status">{{toast}}</p>
    <NoteDecision :t="copy" :guard="guard"/>
  </section>
</template>

<style scoped>
.text-realm{position:absolute;inset:22px 2.7% 3.5%;color:#e2ebee;font:13px/1.5 'Bahnschrift','Segoe UI',sans-serif;--text-ink:#e1eaec;--text-muted:#acc3ce;--text-cyan:#b4e4e2;--text-line:#b9d9dd33;animation:text-unfold .5s ease-out both}
.text-topnav{display:flex;align-items:center;gap:20px;min-height:44px;margin:0 4px 20px}.text-return{display:flex;gap:10px;align-items:center;min-height:44px;padding:8px 15px;color:#dcebef;background:#173347ca;border:1px solid var(--text-line);backdrop-filter:blur(15px);border-radius:3px;font:12px 'Bahnschrift','Segoe UI',sans-serif}.text-return svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.25}.text-realm-mark{display:flex;align-items:center;gap:9px;font:italic 17px Georgia,serif;color:#e8edf0;outline:none;text-shadow:0 1px 9px #122e4b}.text-realm-mark>span{font:22px 'SimSun',serif;color:#c4e7e2}.text-completion{margin-left:auto;width:165px}.text-completion :deep(.completion-label){display:none}.text-completion :deep(.completion-copy){justify-content:flex-end}.text-completion :deep(progress){height:2px}.text-completion :deep(.completion-values strong){font:11px 'Courier New',monospace}.text-topnav :deep(.wisdom-language){background:#173347c9;border-radius:3px;min-height:42px}
.text-folio{position:absolute;inset:64px 0 0;isolation:isolate;border:1px solid #c3e3e16c;border-radius:4px 13px 5px 5px;box-shadow:0 22px 45px #122b393f,0 4px 0 -1px #3a556a,0 6px 0 -1px #b4cdd636;background:linear-gradient(90deg,#153447f2 0%,#183645f2 52.5%,#1e3e4ce6 52.5%,#203b4be6 100%);backdrop-filter:blur(23px) saturate(.7)}
.text-folio::before{content:'';position:absolute;inset:66px 18px 20px;z-index:-1;pointer-events:none;background:repeating-linear-gradient(transparent 0 31px,#a6ccda0d 31px 32px)}
.text-spine{position:absolute;top:-5px;bottom:-5px;left:52.5%;width:15px;transform:translateX(-50%);pointer-events:none;background:linear-gradient(90deg,#152a3320,#071e3252 45%,#c8e2e338 50%,#213c4994 60%,transparent);z-index:2}.text-spine i{display:block;width:6px;height:40px;background:#c4b7ce8a;margin:auto;clip-path:polygon(0 0,100% 0,100% 100%,50% 85%,0 100%)}
.text-folio :deep(button),.text-folio :deep(input),.text-folio :deep(select),.text-folio :deep(textarea){font:inherit}.text-folio :deep(button){cursor:pointer;transition:background .15s,border-color .15s,color .15s}.text-realm :deep(button:disabled){opacity:.4;cursor:default}.text-realm :deep(button:focus-visible),.text-realm :deep(select:focus-visible),.text-realm :deep(input:focus-visible),.text-realm :deep(textarea:focus-visible){outline:2px solid #bee9e4;outline-offset:3px}.text-realm :deep(button:hover:not(:disabled)){color:#fff5e8;border-color:#b7dddb91;background-color:#b7e7eb14}.text-folio :deep(*){box-sizing:border-box;scrollbar-width:thin;scrollbar-color:#a7c5d16b transparent}
.text-folio :deep(.study-view){height:100%;min-height:0;display:grid;grid-template-rows:66px minmax(0,1fr)}
.text-folio :deep(.study-topbar){display:flex;justify-content:space-between;gap:22px;align-items:center;min-height:0;padding:12px 28px;background:transparent;border-bottom:1px solid var(--text-line)}
.text-folio :deep(.study-topbar>div:first-child){display:flex;align-items:baseline;gap:13px;min-width:0}.text-folio :deep(.study-topbar p){margin:0;color:#9fbec6;font:10px 'Courier New',monospace;white-space:nowrap}.text-folio :deep(.study-topbar h1){margin:0;font:italic 18px/1.25 Georgia,serif;overflow-wrap:anywhere;color:#dce7e7}.text-folio :deep(.breadcrumbs){max-width:48%;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:5px 13px;color:#b7c9d1;font:10px/1.4 'Courier New',monospace}.text-folio :deep(.breadcrumbs span){display:flex;gap:7px;align-items:baseline}.text-folio :deep(.breadcrumbs i){font-style:normal;color:#cfbbd3}
.text-folio :deep(.study-split){display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,.95fr);min-height:0;height:100%;gap:0}
.text-folio :deep(.knowledge-side){display:flex;flex-direction:column;min-height:0;min-width:0;overflow:hidden;padding:0 21px 18px 27px}
.text-folio :deep(.knowledge-viewer){display:grid;grid-template-rows:49px minmax(0,.8fr) minmax(0,1.2fr);min-height:0;flex:1;overflow:hidden}
.text-folio :deep(.knowledge-meta){display:flex;align-items:center;gap:11px;color:#9db5c3;font:10px 'Courier New',monospace;border-bottom:1px solid #b6ccda1c;min-width:0}.text-folio :deep(.knowledge-meta>span:nth-child(3)){flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:12px 'Bahnschrift','Segoe UI',sans-serif;color:#d7d6e1}.text-folio :deep(.knowledge-meta strong){font-size:17px;color:#bbd8dc;font-weight:400}.text-folio :deep(.type-chip){padding:4px 7px;color:#b7dedd;border:1px solid #9ccac13a;border-radius:2px;text-transform:capitalize}.text-folio :deep(.type-chip.theorem){color:#cfbedc;border-color:#bfadd044}.text-folio :deep(.type-chip.exercise){color:#ded0a4;border-color:#c9b87844}
.text-folio :deep(.knowledge-section){overflow:auto;min-height:0;padding:19px 5px 20px 0;overscroll-behavior:contain;scrollbar-gutter:stable;background:transparent;position:relative}.text-folio :deep(.statement-section){border-bottom:1px solid #bed8dc35}.text-folio :deep(.knowledge-section-head){display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.text-folio :deep(.knowledge-section h2){margin:0;color:#c8ddde;font:italic 17px Georgia,serif}.text-folio :deep(.knowledge-section-head button),.text-folio :deep(.sound-corner){background:none;border:0;color:#aec9d4;font-size:11px;padding:5px 7px;min-height:30px}
.text-folio :deep(.math-content){font:16px/1.85 Georgia,'Times New Roman',serif;color:#edf0ec;overflow-wrap:anywhere}.text-folio :deep(.math-content p){margin:0 0 1em}.text-folio :deep(.math-content .katex){font-size:1.04em}.text-folio :deep(.katex-display){overflow-x:auto;overflow-y:hidden;padding:5px 0;margin:14px 0;text-align:left}.text-folio :deep(.katex-display>.katex){text-align:left}.text-folio :deep(.sound-corner){display:block;margin-left:auto;margin-top:8px}.text-folio :deep(.knowledge-images){display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.text-folio :deep(.knowledge-images button){padding:6px 10px;border:1px solid #b5d4df4a;border-radius:2px;color:#c0dce3;background:#a3d2d508;font-size:11px}
.text-folio :deep(.study-actions){display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:12px;padding-top:12px;border-top:1px solid #b8d4da35}.text-folio :deep(.study-actions button){min-height:35px;min-width:0;padding:7px 5px;border:1px solid #b6d7df35;border-radius:2px;background:#b0d8de06;color:#c3d5dc;font-size:10px;line-height:1.4;overflow-wrap:anywhere}.text-folio :deep(.study-actions button:nth-child(2)){background:#b0e1dd18;border-color:#b6e4df8c;color:#def4e9}.text-folio :deep(.study-actions button.active){color:#e1f3ee;border-color:#b6dbe1aa;background:#a3dcd51c}
.text-folio :deep(.study-side-panel){display:flex;flex-direction:column;min-width:0;min-height:0;padding:15px 22px 18px 24px;overflow:hidden;gap:12px}.text-folio :deep(.study-side-panel>:first-child){flex:1;min-height:0}.text-folio :deep(.study-side-controls){display:flex;gap:10px;align-items:center;justify-content:space-between;flex-shrink:0;border-top:1px solid #bed8dc35;padding-top:13px}.text-folio :deep(.study-side-controls button){min-height:35px;padding:7px 12px;border:1px solid #b8dada5c;border-radius:2px;background:#a5d0d80a;color:#d5e3e4;font-size:11px}.text-folio :deep(.study-side-controls button.done){background:#a4d9ba23;color:#c2e5b9;border-color:#b8e5be99}
.text-folio :deep(.section-atlas){display:flex;flex-direction:column;border:0;border-radius:0;background:transparent;color:#c8dade;overflow:hidden}.text-folio :deep(.section-atlas header){padding:0 0 13px;display:flex;justify-content:space-between;align-items:center;gap:8px}.text-folio :deep(.section-atlas h2){font:italic 18px Georgia,serif;color:#d2e2e4}.text-folio :deep(.section-atlas button),.text-folio :deep(.section-atlas select){background:#15374466;border:1px solid #aecfd144;border-radius:2px;color:#c7dce1;font-size:10px;padding:6px 9px;min-height:30px}.text-folio :deep(.section-atlas header button){background:transparent;border-color:transparent;color:#b9dcd8;font-size:10px}.text-folio :deep(.atlas-controls){padding:0;gap:9px 20px;grid-template-columns:1fr 1fr}.text-folio :deep(.atlas-controls label){font:10px 'Courier New',monospace;color:#bfd0d7;gap:7px}.text-folio :deep(input[type=range]){width:100%;accent-color:#bdd6dd;height:13px;margin:0;cursor:pointer}.text-folio :deep(.atlas-controls>p){font:10px/1.5 'Bahnschrift','Segoe UI',sans-serif;color:#a9bdc8;align-self:center}.text-folio :deep(.atlas-views){gap:0}.text-folio :deep(.atlas-views button){padding:6px 8px;white-space:nowrap;background:#15374444}.text-folio :deep(.atlas-views button+button){border-left:0}.text-folio :deep(.atlas-views button[aria-pressed=true]){color:#e5f4ed;border-color:#addad980;background:#b7ded422;box-shadow:inset 0 -2px #aedbd4}.text-folio :deep(.atlas-legend){padding:11px 0 8px;font:9px 'Courier New',monospace;gap:18px;color:#b8cdda}.text-folio :deep(.atlas-legend .gold){color:#d8c996}
.text-folio :deep(.atlas-viewport){flex:1;min-height:110px;height:auto;border-top:1px solid #b3d1d528;border-bottom:1px solid #b3d1d528;background:radial-gradient(ellipse at 50% 40%,#9cccd108,transparent 70%);overflow:auto}.text-folio :deep(.atlas-parent rect){fill:#a4d0d406;stroke:#adcbd54d;stroke-width:1.3}.text-folio :deep(.atlas-parent text){fill:#c3d7de;font:17px Georgia,serif}.text-folio :deep(.atlas-section rect){fill:#a7cfda08;stroke:#b3d3da18;stroke-width:1}.text-folio :deep(.atlas-section text){fill:#bcd1d8}.text-folio :deep(.atlas-section text+text){fill:#91adbd}.text-folio :deep(.section-atlas .atlas-node){display:flex;flex-direction:column;align-items:flex-start;justify-content:center;width:160px;height:64px;min-height:64px;padding:8px 12px;border:1px solid #a4c8d070;border-radius:4px 12px 4px 4px;background:#254650eb;color:#dce9e9;text-align:left;font-size:12px}.text-folio :deep(.atlas-node-title){max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.5}.text-folio :deep(.atlas-node small){font:9px 'Courier New',monospace;color:#a8c1cc;margin-top:3px}.text-folio :deep(.section-atlas .atlas-node.selected){background:#3d5d66f0;border-color:#c5ede6;box-shadow:inset 3px 0 #b5e0db,0 0 10px #b2ddd52b;color:#f6f2e4}.text-folio :deep(.section-atlas .atlas-node.done){border-color:#bedab373}.text-folio :deep(.atlas-edge){opacity:.78}.text-folio :deep(.atlas-gap rect){fill:#27424bf2;stroke:#cebd8d66}.text-folio :deep(.atlas-gap text){fill:#e0d19d}.text-folio :deep(.section-atlas footer){padding:10px 0 0;font:9px 'Courier New',monospace;color:#a9beca}.text-folio :deep(.section-atlas footer label){display:flex;align-items:center;gap:8px}.text-folio :deep(.section-atlas footer select){font-size:10px;padding:3px 5px;min-height:25px}.text-folio :deep(.atlas-message),.text-folio :deep(.section-atlas>p){font:10px/1.5 'Bahnschrift','Segoe UI',sans-serif;margin:5px 0;color:#c4cbd9}
.text-folio :deep(.note-panel),.text-folio :deep(.search-panel),.text-folio :deep(.image-panel){display:flex;flex-direction:column;min-width:0;min-height:0;background:transparent;border:0;border-radius:0;overflow:hidden}.text-folio :deep(.note-panel header),.text-folio :deep(.search-panel header),.text-folio :deep(.image-panel header){display:flex;align-items:center;justify-content:space-between;gap:15px;padding:0 0 14px;border-bottom:1px solid var(--text-line);margin-bottom:14px}.text-folio :deep(.note-panel h2),.text-folio :deep(.search-panel h2),.text-folio :deep(.image-panel h2){font:italic 19px Georgia,serif;margin:0;color:#d5e7e6}.text-folio :deep(.note-panel header button),.text-folio :deep(.search-panel header button),.text-folio :deep(.image-panel header button){background:none;border:0;color:#d9e6e8;font-size:23px;min-width:32px;min-height:32px}.text-folio :deep(.note-panel label),.text-folio :deep(.note-editor-pane label){display:flex;flex-direction:column;gap:6px;margin:10px 0;color:#b7c9d3;font-size:11px}.text-folio :deep(.note-panel select),.text-folio :deep(.note-panel input),.text-folio :deep(.notes-desk input){color:#e2e8e9;background:#132e4080;border:1px solid #aecfd23a;border-radius:2px;padding:9px;min-height:36px}.text-folio :deep(.note-panel>button){background:none;border:0;color:#cce3de;align-self:flex-end;font-size:11px;padding:5px}.text-folio :deep(textarea){min-height:100px;flex:1;resize:none;padding:14px 15px;color:#e6eae5;border:1px solid #a8cad23f;border-radius:2px;background:repeating-linear-gradient(transparent 0 29px,#bed7de0f 29px 30px),#142e3d54;font:15px/30px Georgia,serif}.text-folio :deep(.note-footer){display:flex;justify-content:space-between;gap:10px;margin-top:13px}.text-folio :deep(.note-footer button),.text-folio :deep(.notes-desk button){border:1px solid #a4cbd84d;background:#15364465;color:#d7e9e7;padding:8px 12px;border-radius:2px;font-size:11px;min-height:35px}.text-folio :deep(.note-footer .primary-button){border-color:#b4dfd999;background:#abd9d51a}.text-folio :deep(.search-method),.text-folio :deep(.empty-state){font-size:12px;color:#afc3cf;line-height:1.65}.text-folio :deep(.demo-kicker){margin:0 0 4px;font:9px 'Courier New',monospace;color:#a7baca}.text-folio :deep(.resonance-list){overflow:auto;display:flex;flex-direction:column;gap:0;min-height:0}.text-folio :deep(.resonance-list button){text-align:left;background:none;border:0;border-bottom:1px solid var(--text-line);color:#cfdee3;padding:15px 8px;min-width:0}.text-folio :deep(.resonance-list button>div){display:flex;flex-direction:column;gap:5px}.text-folio :deep(.resonance-list span){font:10px 'Courier New',monospace;color:#b8afc8}.text-folio :deep(.resonance-list strong){font:16px Georgia,serif;color:#dce8e7}.text-folio :deep(.resonance-list p){font:13px/1.6 Georgia,serif;margin:10px 0;overflow-wrap:anywhere}.text-folio :deep(.resonance-list i){font:10px 'Courier New',monospace;color:#b2cacd}.text-folio :deep(.search-loader){padding:20px;color:#b7d9db}.text-folio :deep(.image-stage){flex:1;min-height:0;overflow:auto;display:grid;place-items:center;background:#edf0e508;border:1px solid var(--text-line)}.text-folio :deep(.image-stage img){max-width:100%;max-height:100%;object-fit:contain}.text-folio :deep(.image-panel footer){display:flex;flex-wrap:wrap;gap:10px;font-size:11px;padding:12px 0}.text-folio :deep(.image-panel footer a){color:#b7dadc;margin-left:auto}.text-folio :deep(.image-panel header p){font:10px 'Courier New',monospace;color:#a9c0c8}
.text-folio :deep(.exercise-nav){display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:10px}.text-folio :deep(.exercise-nav button){border:0;background:none;color:#cde2e3;padding:8px;font-size:11px}.text-folio :deep(.exercise-nav>span){font:11px 'Courier New',monospace;color:#b9c5d0}.text-folio :deep(.knowledge-empty){padding:40px 20px;color:#bfd0d8;flex:1}
.text-folio :deep(.notes-desk){display:grid;grid-template-columns:1.05fr .95fr;height:100%;min-height:0}.text-folio :deep(.note-editor-pane),.text-folio :deep(.note-constellation-pane){display:flex;flex-direction:column;min-height:0;min-width:0;padding:25px 28px}.text-folio :deep(.notes-desk header){display:flex;justify-content:space-between;gap:16px;align-items:flex-start;min-width:0}.text-folio :deep(.notes-desk h1),.text-folio :deep(.notes-desk h2){font:italic 20px Georgia,serif;color:#d7e5e6;margin:5px 0}.text-folio :deep(.notes-help){font-size:12px;color:#b6c8d1}.text-folio :deep(.note-groups){overflow:auto;min-height:0}.text-folio :deep(.note-groups h3){font:11px 'Courier New',monospace;color:#c8d8dc}.text-folio :deep(.note-groups section>button){display:flex;flex-direction:column;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--text-line);padding:12px 6px}.text-folio :deep(.note-groups section>button.active){background:#a3d4d916}.text-folio :deep(.note-groups strong){font:14px Georgia,serif;color:#e0e6e4}.text-folio :deep(.note-groups p){font-size:12px;color:#b8cbd3;white-space:pre-wrap;overflow-wrap:anywhere}.text-folio :deep(.note-groups small){font:10px 'Courier New',monospace;color:#bdb2c8}.text-folio :deep(.note-editor-actions){display:flex;gap:12px;justify-content:space-between;padding-top:15px}
.text-notice{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);max-width:min(540px,90vw);padding:13px 22px;background:#173448f5;border:1px solid #bededb70;box-shadow:0 8px 24px #10263755;border-radius:3px;color:#e1ecec;z-index:1100;font:12px/1.6 'Bahnschrift','Segoe UI',sans-serif}.text-realm :deep(.note-decision){background:#183849f5;border-color:#bedade70;border-radius:3px 13px 3px 3px;backdrop-filter:blur(20px)}.text-realm :deep(.note-decision h2){font:italic 22px Georgia,serif}.text-realm :deep(.note-decision p){color:#c4d4de}.text-realm :deep(.note-decision button){border-color:#a9cbd359;background:#aacdd610;color:#dbe9e6}
@keyframes text-unfold{from{opacity:0;transform:translate3d(0,14px,0) scale(.985)}to{opacity:1;transform:none}}
@media(min-width:1450px){.text-realm{inset-inline:max(2.7%,calc((100vw - 1620px)/2))}.text-folio :deep(.knowledge-side){padding-left:36px;padding-right:31px}.text-folio :deep(.math-content){font-size:18px}.text-folio :deep(.study-side-panel){padding-left:31px;padding-right:31px}.text-folio :deep(.study-actions button){font-size:12px;min-height:39px}}
@media(max-width:1050px) and (min-width:901px){.text-folio :deep(.study-topbar){padding-inline:19px}.text-folio :deep(.study-topbar>div:first-child){display:block}.text-folio :deep(.study-topbar p){margin-bottom:4px}.text-folio :deep(.knowledge-side){padding-inline:17px}.text-folio :deep(.study-side-panel){padding-inline:17px}.text-folio :deep(.atlas-controls){gap:8px}.text-folio :deep(.study-actions){grid-template-columns:repeat(3,minmax(0,1fr))}.text-folio :deep(.math-content){font-size:15px}}
@media(max-width:900px){.text-realm{position:absolute;inset:18px 16px 0;overflow:visible;padding-bottom:24px}.text-topnav{gap:13px;margin-bottom:18px}.text-realm-mark{font-size:14px;gap:5px}.text-realm-mark>span{font-size:19px}.text-completion{width:110px}.text-folio{position:relative;inset:auto;height:auto;min-height:0;background:#173749f2}.text-spine{display:none}.text-folio :deep(.study-view){display:block;height:auto}.text-folio :deep(.study-topbar){min-height:72px;height:auto;gap:10px;padding:13px 21px}.text-folio :deep(.study-topbar>div:first-child){display:block}.text-folio :deep(.study-topbar p){margin-bottom:5px}.text-folio :deep(.study-split){display:flex;flex-direction:column;height:auto}.text-folio :deep(.knowledge-side){height:660px;padding:0 23px 19px}.text-folio :deep(.study-side-panel){height:640px;border-top:1px solid #b5d8df70;padding:23px;background:#bddbdf05}.text-folio :deep(.math-content){font-size:16px}.text-folio :deep(.study-actions button){min-height:41px;font-size:11px}.text-folio :deep(.section-atlas header button){min-height:40px}.text-folio :deep(.notes-desk){grid-template-columns:1fr}.text-folio :deep(.note-editor-pane){min-height:550px}.text-folio :deep(.note-constellation-pane){min-height:360px;max-height:650px;border-top:1px solid var(--text-line)}}
@media(max-width:540px){.text-realm{inset:14px 12px 0}.text-topnav{gap:8px;flex-wrap:wrap;margin:0 2px 14px}.text-return{padding:7px 10px;gap:6px;font-size:11px;min-height:39px}.text-realm-mark{margin-right:auto}.text-topnav :deep(.wisdom-language){min-height:38px}.text-completion{order:5;flex-basis:100%;width:100%;margin:0}.text-completion :deep(.completion-copy){justify-content:flex-end}.text-completion :deep(.completion-values){gap:6px}.text-completion :deep(.completion-values strong){font-size:9px}.text-completion :deep(.completion-values small){font-size:9px}.text-completion :deep(progress){height:2px}.text-folio :deep(.study-topbar){min-height:62px;padding:12px 18px}.text-folio :deep(.study-topbar h1){font-size:17px}.text-folio :deep(.breadcrumbs){display:none}.text-folio :deep(.knowledge-side){height:690px;padding:0 18px 17px}.text-folio :deep(.knowledge-meta){gap:8px}.text-folio :deep(.knowledge-meta>span:nth-child(3)){font-size:10px}.text-folio :deep(.knowledge-meta strong){display:none}.text-folio :deep(.study-actions){grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.text-folio :deep(.study-actions button){font-size:11px;min-height:39px}.text-folio :deep(.knowledge-section){padding-top:16px}.text-folio :deep(.math-content){font-size:15px;line-height:1.8}.text-folio :deep(.study-side-panel){height:650px;padding:20px 17px}.text-folio :deep(.atlas-controls){gap:9px 12px}.text-folio :deep(.atlas-controls>p){font-size:9px}.text-folio :deep(.atlas-views button){padding:6px;font-size:9px}.text-folio :deep(.section-atlas h2){font-size:18px}.text-folio :deep(.note-editor-pane),.text-folio :deep(.note-constellation-pane){padding:20px 18px}.text-folio :deep(.study-side-controls){flex-wrap:wrap}.text-folio :deep(.study-side-controls button){min-height:40px}}
@media(prefers-reduced-motion:reduce){.text-realm{animation:none}.text-realm :deep(*){transition:none!important}}
</style>

<style scoped>
/* Instrument labels stay readable even though their frames are compact. */
.text-folio :deep(.study-actions button){font-size:12px;min-height:38px}
.text-folio :deep(.study-side-controls button){font-size:12px;min-height:38px}
.text-folio :deep(.atlas-controls label){font-size:11px}
.text-folio :deep(.section-atlas header button){font-size:11px}
.text-folio :deep(.atlas-views button){font-size:11px}
.text-folio :deep(.atlas-legend),.text-folio :deep(.section-atlas footer){font-size:10px}
.text-folio :deep(.section-atlas .atlas-node){font-size:14px;padding:6px 10px}
.text-folio :deep(.atlas-node-title){display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;white-space:normal;line-height:1.15;max-height:33px}
@media(max-width:1050px){.text-folio :deep(.study-actions button){font-size:11px}.text-folio :deep(.atlas-views button){font-size:10px}}
</style>

<style>
@media(max-width:900px){
  .wisdom-prototype:has(.text-realm){height:auto!important;min-height:100dvh!important;overflow:visible!important}
  .wisdom-prototype .altar-interface:has(.text-realm){position:absolute;min-height:100dvh;overflow:visible}
  .altar-interface>.text-realm{position:relative;inset:auto;margin:18px 16px 24px;padding-bottom:0}
}
@media(max-width:540px){.altar-interface>.text-realm{margin:14px 12px 22px}}
</style>
