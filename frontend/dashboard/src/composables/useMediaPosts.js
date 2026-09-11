import { computed, ref, watch } from "vue";
import { apiFetch } from "../../../urls.js";

export function useMediaPosts({ t, requireLogin, scrollToEditor }) {
  const posts = ref([]);
  const editingPostId = ref(null);
  const mediaMessage = ref("");
  const mediaError = ref(false);
  const mediaSaving = ref(false);
  const createRetryPending = ref(false);
  let createAttempt = null;
  const emailPreview = ref(null);
  const previewLoading = ref(false);
  const previewError = ref("");
  let previewRequest = 0;
  const blankPost = () => ({
    title: "", excerpt: "", body: "", image_url: "/images/graph.jpg",
    status: "published", email_introduction: "", announce: false
  });
  const postDraft = ref(blankPost());
  const announcementQueued = computed(() => Boolean(
    posts.value.find(post => post.media_post_id === editingPostId.value)?.announcement_queued_at
  ));

  function message(value, isError = false) {
    mediaMessage.value = value;
    mediaError.value = isError;
  }

  function clearPreview() {
    previewRequest += 1;
    emailPreview.value = null;
    previewError.value = "";
    previewLoading.value = false;
  }

  watch(() => [postDraft.value.title, postDraft.value.email_introduction], clearPreview);
  watch(() => postDraft.value.status, status => {
    if (status !== "published") postDraft.value.announce = false;
  });

  async function loadMedia() {
    try {
      const res = requireLogin(await apiFetch("/api/content/media"));
      const data = await res.json();
      if (!res.ok) return message(data.detail || t.value.mediaRequestError, true);
      posts.value = data.posts;
    } catch {
      message(t.value.mediaRequestError, true);
    }
  }

  function resetPost() {
    createAttempt = null;
    createRetryPending.value = false;
    editingPostId.value = null;
    postDraft.value = blankPost();
    message("");
    clearPreview();
  }

  function editPost(post) {
    if (mediaSaving.value) return;
    createAttempt = null;
    createRetryPending.value = false;
    editingPostId.value = post.media_post_id;
    postDraft.value = {
      title: post.title || "", excerpt: post.excerpt || "", body: post.body || "",
      image_url: post.image_url || "", status: post.status || "draft",
      email_introduction: post.email_introduction || "", announce: false
    };
    message("");
    clearPreview();
    scrollToEditor();
  }

  async function previewEmail() {
    if (!postDraft.value.title.trim() || !postDraft.value.email_introduction.trim()) {
      previewError.value = t.value.emailPreviewRequired;
      return;
    }
    const request = ++previewRequest;
    previewLoading.value = true;
    previewError.value = "";
    emailPreview.value = null;
    try {
      const res = requireLogin(await apiFetch("/api/content/media/email-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: postDraft.value.title,
          email_introduction: postDraft.value.email_introduction
        })
      }));
      const data = await res.json();
      if (request !== previewRequest) return;
      if (!res.ok) {
        previewError.value = data.detail || t.value.mediaRequestError;
        return;
      }
      emailPreview.value = data;
    } catch {
      if (request === previewRequest) previewError.value = t.value.mediaRequestError;
    } finally {
      if (request === previewRequest) previewLoading.value = false;
    }
  }

  async function savePost(retrySavedSubmission = false) {
    if (mediaSaving.value) return;
    if (createRetryPending.value && !retrySavedSubmission) {
      message(t.value.mediaCreateUncertain, true);
      return;
    }
    const creating = !editingPostId.value;
    const payload = retrySavedSubmission && createAttempt ? { ...createAttempt.payload } : {
      ...postDraft.value,
      announce: postDraft.value.status === "published" && !announcementQueued.value && postDraft.value.announce
    };
    if (payload.announce && !payload.email_introduction.trim()) {
      message(t.value.emailPreviewRequired, true);
      return;
    }
    if (creating) {
      // The identity belongs to this submitted copy, including when its response is lost.
      if (!createAttempt) createAttempt = { id: crypto.randomUUID(), payload: { ...payload } };
      payload.request_id = createAttempt.id;
    }
    mediaSaving.value = true;
    try {
      const path = editingPostId.value ? `/api/content/media/${editingPostId.value}` : "/api/content/media";
      const res = requireLogin(await apiFetch(path, {
        method: editingPostId.value ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }));
      const data = await res.json();
      if (!res.ok) {
        if (creating) {
          createRetryPending.value = res.status >= 500 || res.status === 409;
          if (!createRetryPending.value) createAttempt = null;
        }
        return message(data.detail || t.value.mediaRequestError, true);
      }
      resetPost();
      message(data.announcement_queued ? t.value.announcementSaved : t.value.postSaved);
      await loadMedia();
    } catch {
      createRetryPending.value = creating;
      message(creating ? t.value.mediaCreateUncertain : t.value.mediaSaveUncertain, true);
    } finally {
      mediaSaving.value = false;
    }
  }

  function retryCreate() {
    if (createRetryPending.value && createAttempt) return savePost(true);
  }

  async function deletePost(post) {
    if (mediaSaving.value || createRetryPending.value || !confirm(`${t.value.deletePostConfirm} “${post.title}”?`)) return;
    try {
      const res = requireLogin(await apiFetch(`/api/content/media/${post.media_post_id}`, { method: "DELETE" }));
      const data = await res.json();
      if (!res.ok) return message(data.detail || t.value.mediaRequestError, true);
      if (editingPostId.value === post.media_post_id) resetPost();
      message(t.value.postDeleted);
      await loadMedia();
    } catch {
      message(t.value.mediaRequestError, true);
    }
  }

  return {
    posts, editingPostId, mediaMessage, mediaError, mediaSaving, postDraft, announcementQueued, createRetryPending, retryCreate,
    emailPreview, previewLoading, previewError, loadMedia, resetPost, editPost, savePost, deletePost, previewEmail
  };
}
