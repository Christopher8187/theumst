# Frontend architecture

Each of the three applications has its own package manifest, Vite configuration, source directory and Dockerfile. The public site and dashboard builds are copied into the backend image. The demo has a separate Nginx image. Shared URL definitions live in `frontend/urls.js`.

The public site and dashboard entry components both mount `frontend/shared/DesktopApp.vue`. It composes public pages, account state and window navigation. Dashboard route metadata selects the permitted tools, which load asynchronously and request access-controlled book, media and administrative APIs. Profile and subscriptions live in their own window. The demo's root composes library, detail, realm, reader and notes views. All use the same backend session model.

## Desktop navigation and entry URLs

The public site and signed-in dashboard form one desktop at `https://theumst.com/`. Opening public pages, a News article, account forms, Profile, Settings or a dashboard tool changes window state while the address remains `/`. Window choices do not create browser-history entries. Refreshing starts Home; saved appearance preferences remain. The Demo access/request panel is also a desktop window. Its actual Enter Demo link leaves for the protected `/demo/` application.

Older public bookmarks, News email links and account confirmation/reset links remain entry addresses. Signed-in `/dashboard/...` bookmarks also select the requested tool. A signed-out dashboard entry first redirects to Login and does not retain the requested tool destination. For entries that reach the desktop, `desktopEntry.js` captures the initial path and query, then replaces the visible address with `/`. `DesktopApp.vue` opens the requested window and passes account-link data to its form. Tokens stay in memory, outside the address bar and browser storage. Refreshing after consuming a link starts Home; reopening the original email link lets the backend decide whether its token is still valid. Backend authentication, tool permissions and Demo checks remain authoritative.

Build directories and API paths are implementation boundaries. Read this section before changing their relationship to visible navigation. Preserve News links for recipients and account-token handling. The [backend HTML cache policy](backend.md) makes document requests revalidate their build; it cannot replace an already-running old tab. [Operations](../operations.md) distinguishes server output from retained browser content.

## Window and scene state

Windows remain mounted when closed, preserving their scroll position and tool drafts for the visit. Opening Profile resets its selected tab to Details. The shared scene renderer mounts once and disposes listeners, drawing resources and its animation frame on unmount. Opening or dragging a window does not pause rotation. The existing scene pause button controls rotation, and reduced-motion preferences determine its initial default. Camera direction starts at the library desk on each visit. Color and scene settings persist in browser storage; the margin note keeps its fixed warm paper colors.

The approved illustration uses a mild shader projection and drifting light. It is not a modeled 3D room. The artwork is drawn before the canvas becomes visible, avoiding an initial change of framing. Browsers without WebGL receive the still illustration. Shared Three.js source retains its MIT license. The [shared component guide](../../frontend/shared/README.md) describes responsibilities and events.

The demo caches compact book order while fetching the selected object's detail separately. Persisted completion belongs to knowledge-object IDs. Text and Questions have independent PostgreSQL positions. The current side panel, Atlas distance controls and Back history are temporary UI state. An excursion records the original book, object and realm so returning restores the original study context.

The note editor owns the current draft. A shared navigation guard defers leaving or switching an edited note until Save and continue, Discard and continue, or Keep editing is chosen. A failed save retains the draft and pending destination.

The Atlas uses compact reader objects and sections. Its pure layout module selects nearby objects and places section groups; the component renders controls and an accessible SVG. Authored dependencies and reading order have separate meanings and arrows. Source-order projection edges cannot be relabelled as dependencies.

The interface supports English, Chinese and Japanese. Changing interface language does not translate source material. Math rendering escapes ordinary text and passes formulas to KaTeX with trusted commands disabled. [Web Demo](../web-demo.md) owns the user-visible requirements; [Atlas](../atlas.md) owns its display rules.
