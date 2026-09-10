# Web Demo

A reader opens a book in the library, checks its summary and nested contents, summons it, and enters a realm. Text reads all available objects in book order. Questions keeps its own exercise position. Notes holds attached notes and scribbles. The remaining realm entries are currently placeholders for their settled future purposes.

Read [Web Demo behavior](../../docs/web-demo.md) for current requirements and [Atlas](../../docs/atlas.md) for the accepted graph presentation. `src/App.vue` composes views and API actions. `StudyView.vue` combines the reader with a side panel. `SectionAtlas.vue` renders the two graph layouts from `domain/atlas.js`; `NotePanel.vue` and `NotesDesk.vue` share draft handling under `composables/`. `services/studyApi.js` owns graph/discovery request normalization. `math.js` safely renders formulas.

Source material stays in its supplied language; `i18n.js` owns English, Chinese and Japanese interface copy. `api.js` handles credentialed requests and API errors. A simulated service can exercise the frontend, but cannot establish authorization or persistence.

Run `npm ci`, `npm run build`, then the relevant [deterministic checks](tests/README.md). Local Vite uses port 5175. The deployment proxy protects `/demo/`; Vite itself is a local development tool. Browser acceptance objectives and fixture requirements live in [the verification guide](../../docs/testing/web-demo.md).
