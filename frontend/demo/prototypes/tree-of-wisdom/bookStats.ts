import { buildContentsTree } from '../../src/domain/contents';
import type { BookSection, SampleBook } from './books';

type ContentsNode = BookSection & { children: ContentsNode[] };

export function bookChapterRoots(book: SampleBook): ContentsNode[] {
  const hierarchy = buildContentsTree(book.contents || []) as ContentsNode[];
  return hierarchy.flatMap(section => section.children.length && (
    section.is_book_root || ['', '0'].includes(String(section.section_number ?? ''))
  ) ? section.children : [section]);
}

export function bookChapterCount(book: SampleBook): number {
  return bookChapterRoots(book).length;
}

export function bookObjectCount(book: SampleBook): number {
  const count = Number(book.count);
  return Number.isFinite(count) ? Math.max(0, Math.trunc(count)) : 0;
}

export function bookCompletion(book: SampleBook) {
  const total = bookObjectCount(book);
  const supplied = Number(book.completed ?? 0);
  const completed = Math.min(total, Math.max(0, Number.isFinite(supplied) ? Math.trunc(supplied) : 0));
  const percent = total > 0 ? Math.round(completed / total * 100) : 0;
  return { completed, total, progressMax: Math.max(1, total), percent };
}
