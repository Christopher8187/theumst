import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createServer } from "vite";
import { createRenderer, effectScope, nextTick, ref } from "vue";

let server;
let useMediaPosts;
let useDashboardTools;
const copy = ref({
  postSaved: "saved", announcementSaved: "queued", emailPreviewRequired: "copy required",
  mediaRequestError: "request failed", mediaSaveUncertain: "check before retrying",
  mediaCreateUncertain: "retry the saved copy",
  dashboardLoadError: "load failed"
});

before(async () => {
  globalThis.location = { port: "", pathname: "/dashboard/" };
  server = await createServer({
    configFile: false,
    server: { middlewareMode: true },
    appType: "custom",
    optimizeDeps: { noDiscovery: true, include: [] }
  });
  ({ useMediaPosts } = await server.ssrLoadModule("/src/composables/useMediaPosts.js"));
  ({ useDashboardTools } = await server.ssrLoadModule("/src/composables/useDashboardTools.js"));
});
after(async () => { await server?.close(); });

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

function mediaState() {
  const scope = effectScope();
  const state = scope.run(() => useMediaPosts({ t: copy, requireLogin: res => res, scrollToEditor() {} }));
  return { state, stop: () => scope.stop() };
}

test("ordinary edits and draft saves never announce; queued posts cannot announce twice", async () => {
  const { state, stop } = mediaState();
  const sent = [];
  globalThis.fetch = async (path, options) => {
    if (options.method) {
      sent.push({ path, payload: JSON.parse(options.body) });
      return json({ announcement_queued: false });
    }
    return json({ posts: [] });
  };
  try {
    assert.equal(state.postDraft.value.announce, false);
    state.editPost({ media_post_id: 7, title: "News", body: "Full story", status: "published" });
    await state.savePost();
    assert.equal(sent[0].path, "/api/content/media/7");
    assert.equal(sent[0].payload.announce, false);

    state.postDraft.value = { title: "Draft", status: "draft", email_introduction: "Hello", announce: true };
    await state.savePost();
    assert.equal(sent[1].payload.announce, false);

    const queued = { media_post_id: 8, title: "News", status: "published", email_introduction: "Hello", announcement_queued_at: "2026-09-11T10:00:00Z" };
    state.posts.value = [queued];
    state.editPost(queued);
    state.postDraft.value.announce = true;
    await state.savePost();
    assert.equal(sent[2].payload.announce, false);
  } finally { stop(); }
});

test("announcement save submits explicit consent once and reports queuing without claiming delivery", async () => {
  const { state, stop } = mediaState();
  let resolveSave;
  const writes = [];
  globalThis.fetch = (path, options) => {
    if (options.method) {
      writes.push(JSON.parse(options.body));
      return new Promise(resolve => { resolveSave = resolve; });
    }
    return Promise.resolve(json({ posts: [] }));
  };
  try {
    state.postDraft.value = { title: "News", body: "Full story", status: "published", email_introduction: "A note", announce: true };
    const save = state.savePost();
    await state.savePost();
    assert.equal(writes.length, 1);
    assert.equal(writes[0].email_introduction, "A note");
    assert.equal(writes[0].announce, true);
    resolveSave(json({ announcement_queued: true, announcement_id: 31 }));
    await save;
    assert.equal(state.mediaMessage.value, "queued");
    assert.equal(state.postDraft.value.announce, false);
    assert.equal(state.mediaSaving.value, false);
  } finally { stop(); }
});

test("preview uses the template endpoint only and discards a response for edited copy", async () => {
  const { state, stop } = mediaState();
  let resolvePreview;
  const requests = [];
  globalThis.fetch = (path, options) => {
    requests.push({ path, payload: JSON.parse(options.body) });
    return new Promise(resolve => { resolvePreview = resolve; });
  };
  try {
    state.postDraft.value.title = "News";
    state.postDraft.value.email_introduction = "First introduction";
    await nextTick();
    const pending = state.previewEmail();
    assert.equal(requests[0].path, "/api/content/media/email-preview");
    assert.deepEqual(requests[0].payload, { title: "News", email_introduction: "First introduction" });
    state.postDraft.value.email_introduction = "Changed introduction";
    await nextTick();
    resolvePreview(json({ subject: "Old subject", html: "<p>Old copy</p>", text: "Old copy" }));
    await pending;
    assert.equal(state.emailPreview.value, null);
    assert.equal(state.previewLoading.value, false);

    const current = state.previewEmail();
    resolvePreview(json({ subject: "New subject", html: "<p>Changed</p>", text: "Changed" }));
    await current;
    assert.equal(state.emailPreview.value.subject, "New subject");
    assert.equal(requests.length, 2);
  } finally { stop(); }
});

test("a failed save retains the draft and does not retry automatically", async () => {
  const { state, stop } = mediaState();
  let calls = 0;
  globalThis.fetch = async () => { calls += 1; throw new Error("lost response"); };
  try {
    state.postDraft.value.title = "Keep my draft";
    await state.savePost();
    assert.equal(state.postDraft.value.title, "Keep my draft");
    assert.equal(state.mediaMessage.value, "retry the saved copy");
    assert.equal(state.mediaError.value, true);
    assert.equal(state.mediaSaving.value, false);
    assert.equal(calls, 1);
  } finally { stop(); }
});

test("a lost create response retries the same UUID and original payload, then starts a fresh draft", async () => {
  const { state, stop } = mediaState();
  const writes = [];
  globalThis.fetch = async (_path, options) => {
    if (!options.method) return json({ posts: [] });
    writes.push(JSON.parse(options.body));
    if (writes.length === 1) throw new Error("response lost after commit");
    return json({ media_post_id: 41, announcement_id: 9, announcement_queued: true });
  };
  try {
    Object.assign(state.postDraft.value, { title: "Original", body: "Original story", email_introduction: "A note", announce: true });
    await state.savePost();
    assert.match(writes[0].request_id, /^[0-9a-f]{8}-[0-9a-f-]{27}$/i);
    assert.equal(state.createRetryPending.value, true);
    state.postDraft.value.title = "Changed after uncertainty";
    await state.savePost();
    assert.equal(writes.length, 1, "changed content cannot silently create a fresh request");
    await state.retryCreate();
    assert.deepEqual(writes[1], writes[0]);
    assert.equal(state.createRetryPending.value, false);
    assert.equal(state.postDraft.value.title, "");
    state.postDraft.value.title = "A separate new post";
    await state.savePost();
    assert.notEqual(writes[2].request_id, writes[0].request_id);
  } finally { stop(); }
});

test("a conflicting create keeps its identity until the author selects an existing post to edit", async () => {
  const { state, stop } = mediaState();
  const requests = [];
  globalThis.fetch = async (path, options) => {
    if (!options.method) return json({ posts: [] });
    requests.push({ path, method: options.method, payload: JSON.parse(options.body) });
    return options.method === "POST" ? json({ detail: "Refresh Media and edit the saved post." }, 409) : json({ ok: true });
  };
  try {
    state.postDraft.value.title = "Original";
    await state.savePost();
    assert.equal(state.createRetryPending.value, true);
    await state.retryCreate();
    assert.equal(requests[1].payload.request_id, requests[0].payload.request_id);
    state.editPost({ media_post_id: 41, title: "Original", body: "Saved copy", status: "published" });
    await state.savePost();
    assert.equal(requests[2].method, "PUT");
    assert.equal(requests[2].path, "/api/content/media/41");
    assert.equal(requests[2].payload.request_id, undefined);
  } finally { stop(); }
});

const renderer = createRenderer({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null,
  insert() {}, remove() {}, patchProp() {}
});
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

test("an ordinary account cannot open a privileged tool through an initial or changed route", async () => {
  const initialRoute = ref("superadmin");
  const changes = [];
  const requests = [];
  let state;
  globalThis.fetch = async path => {
    requests.push(path);
    if (path === "/api/me") return json({ user: { access_points: ["profile", "api-keys"] } });
    if (path === "/api/demo/access") return json({ can_review: false });
    if (path === "/api/api-keys") return json({ keys: [] });
    throw new Error(`Unexpected privileged request: ${path}`);
  };
  const app = renderer.createApp({
    setup() {
      state = useDashboardTools({ initialRoute: () => initialRoute.value, onRouteChange: value => changes.push(value), scrollToEditor() {}, t: copy });
      return () => null;
    }
  });
  app.mount({});
  try {
    await settle();
    assert.equal(state.route.value, "demo");
    assert.deepEqual(changes, ["demo"]);
    assert.deepEqual(requests, ["/api/me", "/api/demo/access"]);
    await state.go("admin");
    assert.equal(state.route.value, "demo");
    initialRoute.value = "api-keys";
    await settle();
    assert.equal(state.route.value, "api-keys");
    assert.equal(requests.at(-1), "/api/api-keys");
    initialRoute.value = "media";
    await settle();
    assert.equal(state.route.value, "demo");
    assert.equal(requests.some(path => path.startsWith("/api/content") || path.startsWith("/api/admin")), false);
  } finally { app.unmount(); }
});
