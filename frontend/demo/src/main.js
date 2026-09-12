import { createApp } from "vue";
import "katex/dist/katex.min.css";
// The scene study stays on the local Demo route and is removed from release builds.
async function mount() {
  if (import.meta.env.DEV && new URLSearchParams(location.search).get("prototype") === "wisdom") {
    const { default: TreePrototype } = await import("../prototypes/tree-of-wisdom/TreePrototype.vue");
    createApp(TreePrototype).mount("#app");
  } else {
    const [{ default: App }] = await Promise.all([
      import("./App.vue"), import("./style.css"), import("./release.css"),
    ]);
    createApp(App).mount("#app");
  }
}
mount();
