import { ref } from 'vue';
import { demoFetch } from '../api';
import type { SampleBook, BookSection } from './books';

export interface BookRecord {
  grimoire_id: number; title: string; knowledge_count: number; completed_count: number;
  summary?: string; publisher?: string; isbn?: string; version?: string; summoned?: boolean;
  presentation?: { subject?: string; color?: string; symbol?: string; short?: string };
}

/** The visual book reads the same metadata and identities as the persisted grimoire. */
export function displayBook(book: BookRecord, contents: BookSection[] = []): SampleBook {
  const colors = ['#526c89', '#7c678d', '#648788'];
  const art = book.presentation || {};
  return { id: String(book.grimoire_id), title: book.title || '', short: art.short || book.title || '',
    subject: art.subject || '', color: /^#[0-9a-f]{6}$/i.test(art.color || '') ? art.color! : colors[Math.abs(book.grimoire_id) % colors.length], symbol: art.symbol || '✧',
    count: Number(book.knowledge_count) || 0, completed: Number(book.completed_count) || 0,
    edition: book.version || '', summary: book.summary || '', passages: [], contents,
    publisher: book.publisher, isbn: book.isbn, version: book.version };
}

export function useGrimoireLibrary() {
  const books = ref<SampleBook[]>([]), added = ref<string[]>([]);
  const loading = ref(true), error = ref(''), busy = ref(false);
  const details = new Map<string, BookSection[]>();
  async function load() {
    loading.value = true; error.value = '';
    try {
      const data = await demoFetch('/api/demo/books');
      books.value = data.books.map((book: BookRecord) => displayBook(book, details.get(String(book.grimoire_id))));
      added.value = data.books.filter((book: BookRecord) => book.summoned).map((book: BookRecord) => String(book.grimoire_id));
    } catch (reason) { error.value = reason instanceof Error ? reason.message : 'Unable to load grimoires'; }
    finally { loading.value = false; }
  }
  async function detail(id: string) {
    const data = await demoFetch(`/api/demo/books/${id}`);
    details.set(id, data.contents || []);
    const book = displayBook(data.book, data.contents || []);
    books.value = books.value.map(current => current.id === id ? book : current);
    return book;
  }
  async function add(id: string) {
    await demoFetch(`/api/demo/grimoires/${id}/summon`, { method: 'POST' });
    added.value = [id, ...added.value.filter(value => value !== id)];
  }
  async function remove(id: string) {
    await demoFetch(`/api/demo/grimoires/${id}`, { method: 'DELETE' });
    added.value = added.value.filter(value => value !== id);
  }
  async function run(operation: () => unknown) {
    if (busy.value) return;
    busy.value = true; error.value = '';
    try { await operation(); }
    catch (reason) { error.value = reason instanceof Error ? reason.message : 'Unable to save this change'; }
    finally { busy.value = false; }
  }
  return { books, added, loading, error, busy, load, detail, add, remove, run };
}
