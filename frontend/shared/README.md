# Shared homepage and dashboard desktop

The public site and dashboard compose the same desktop so opening an account or tool window does not restart the background. The protected Demo remains a separate build and never imports this directory.

`DesktopApp.vue` composes navigation, account state and windows. `DesktopChrome.vue` renders branding and the dock through props and emits page choices. `DesktopWindow.vue` owns dragging, bounds, expansion and focus, and emits focus/close. `SceneBackground.vue` owns the renderer lifecycle and emits its state; its methods change the camera/settings. `SettingsPanel.vue` receives appearance and scene state and emits changes. `ProfileContent.vue` owns account forms and subscription preferences, receives the authenticated user and language, and emits updated user, dashboard/card and sign-out actions. Dashboard tools retain their own access checks and are loaded when needed.

`useDesktopWindows.js` keeps open/visited/focused state for the visit. Closing a window hides it while retaining its reading position. Profile resets to Details when reopened. Scene and palette preferences use local browser storage; the camera starts at the library desk on each visit. Authentication and subscriptions remain server-owned.

Assets come from the approved revision 8 prototype. Three.js is retained with its MIT license in `vendor/`. Build both public and dashboard applications together. The entry applications are independent deployment outputs, with shared source and deduplicated Vue resolution.
