# Frontend architecture

Each of the three applications has its own package manifest, Vite configuration, source directory and Dockerfile. The public site and dashboard builds are copied into the backend image. The demo has a separate Nginx image. Shared URL definitions live in `frontend/urls.js`.

The public site has account forms and public page navigation. The dashboard uses Vue Router and requests access-controlled profile, book, media and administrative APIs. The demo's root composes library, detail, realm, reader and notes views. All use the same backend session model.

The demo caches compact book order while fetching the selected object's detail separately. Persisted completion belongs to knowledge-object IDs. Text and Questions have independent PostgreSQL positions. The current side panel, Atlas distance controls and Back history are temporary UI state. An excursion records the original book, object and realm so returning restores the original study context.

The note editor owns the current draft. A shared navigation guard defers leaving or switching an edited note until Save and continue, Discard and continue, or Keep editing is chosen. A failed save retains the draft and pending destination.

The Atlas uses compact reader objects and sections. Its pure layout module selects nearby objects and places section groups; the component renders controls and an accessible SVG. Authored dependencies and reading order have separate meanings and arrows. Source-order projection edges cannot be relabelled as dependencies.

The interface supports English, Chinese and Japanese. Changing interface language does not translate source material. Math rendering escapes ordinary text and passes formulas to KaTeX with trusted commands disabled. [Web Demo](../web-demo.md) owns the user-visible requirements; [Atlas](../atlas.md) owns its display rules.
