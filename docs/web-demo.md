# Web Demo behavior

This page owns the functional decisions accepted in [Reconcile the Web Demo requirements and acceptance evidence](https://github.com/Christopher8187/product/issues/28). The combined [Theumst 0.1.0 task](https://github.com/Christopher8187/product/issues/33) implements and verifies them. The [accepted AFSR and delivery design](https://github.com/Christopher8187/product/issues/29#issuecomment-5603562451) fixes the publication scope.

## Reading and completion

Text follows available non-exercise objects in grimoire order. Back and Continue visit adjacent non-exercises, including completed objects and section transitions, without wrapping. Graph selection does not turn Back into browsing history. Text's Atlas omits exercise cards while preserving source numbering and omitted-position counts. Questions uses Back and Continue for adjacent exercises; its Atlas includes every type and selecting a non-exercise opens Text. Visiting changes position only. Train selects the next unfinished exercise ahead and explains when none remains; it never wraps backward.

Mark done saves the object's completion, refreshes visible completion feedback and keeps the object selected. Completion is shared between Text and Questions. Their saved positions are independent. A cross-book excursion preserves the first original book, object and realm through further jumps; Return to original book restores all three.

The accepted [issue 70 prototype](https://github.com/Christopher8187/product/issues/70), revision 25, is the visual basis for 0.0.7. The production entry uses the same Sanctuary, Orbit, Brief, altar transition, realms book and notebook B components with real API data. The header shows the smallest containing subsection; shared language and completion controls match the realms book. Review, Preview, Advice, Expand and Progress remain unfinished activities.

## Notes and availability

Notes opens on the right with an attached-note selector and New note. Multiple notes may attach to one object. All notes opens the broader Notes realm. Switching or leaving edited writing offers Save and continue, Discard and continue and Keep editing, preserving the intended destination. Save failure keeps the draft.

Hidden books and their objects are excluded from reader lists, details, images, semantic discovery and Crystallization. Personal writing remains readable with its source unavailable. Retain saved object IDs and completion so restored access restores progress. Authorized management and publishing still permit inspection and unhiding.

If the base grimoire becomes unavailable, withhold its source content when detected and ask the reader to confirm exit to My grimoires. If only the original grimoire becomes unavailable during an excursion, offer that exit plus staying in the available base grimoire. Availability is checked on window focus and periodically; this is detection on revalidation, not server-pushed notification.

Collection removal deletes only `user_grimoire` membership. It leaves completion, saved positions and notes intact. Adding the book again restores access to that personal study state.

Since 0.0.16 the game UMST reads and writes the same notes through an account's key, as [game accounts](game-accounts.md#books-and-notes) explains, so a note made in either shows in both. The game's create needs no book in My grimoires and adds none. Its edits and deletions name the `updated_at` they read and are refused when the note changed since, so they never overwrite an edit made here. The Web Demo's own edits are unchanged: the last save wins.

## Discovery and presentation

Find neighbors searches across available books using stored semantic projections. Retrieve top k for each applicable projection, combine distinct candidates, obtain both scores for every complete pair and show the final top k. Absence from one result set is not a zero score. Compatible complete pairs use equal weighting. If exactly one object lacks workings, apply 0.8 to the available statement score; if both lack workings, retain it. Normalize signed cosine scores to [0,1] before the penalty so it cannot improve a negative score. Missing embeddings despite available workings are processing faults.

Dependencies retrieves active objects connected to the selected object by incoming authored `dependency` edges in its available grimoire. Source order, outgoing edges and similarity do not qualify.

Crystallization retrieves actual same-crystal instances, excluding hidden sources even when they are preferred. It is separate from approximate Find neighbors. No general-search fallback choice is introduced.

Show supplied summary and ISBN, falling back to the title and an unavailable marker when absent. Contents starts at top-level chapters, expands descendants and renders a bounded list. Support English, Chinese and Japanese throughout the interface; source text remains unchanged. [Atlas](atlas.md) owns display details and [testing objectives](testing/web-demo.md) own acceptance checks. The implementation remains a release candidate until recorded verification completes.

## Whole-book read

Since 0.0.15 `GET /api/demo/grimoires/{grimoire_id}/book-read` returns a whole book in one answer: its sections, active objects in reader order, authored relations and shared crystals. Ingestion stores it, as [data architecture](architecture/data.md) explains. The route needs a session with Web Demo access and writes nothing. It does not mark the book opened, so a client that opens books this way sends `POST /api/demo/grimoires/{grimoire_id}/summon` itself.

It checks the session first and answers 401 or 403 as every Demo route does. Then it checks the book, with 404 `{"detail": "Demo grimoire not found", "code": "book_not_found"}` for an unknown or hidden one. A book with no stored answer in format 1 gets 409 `{"detail": "This book's whole read has not been computed yet", "code": "book_read_not_computed"}`. Refusals carry `Cache-Control: no-store`.

A 200 or 304 carries `ETag: "<version>"`, the two weeks of `Cache-Control: private, max-age=1209600`, and `Vary: Authorization, Cookie, Accept-Encoding`. `If-None-Match` matches when any listed tag equals the ETag, with or without `W/`, or is `*`, and the answer is then 304 with no body. A client whose `Accept-Encoding` allows gzip gets the stored gzip bytes with `Content-Encoding: gzip`; any other gets the JSON uncompressed. The application's gzip middleware sits after the route and acts on every route: it compresses an uncompressed answer of 1,000 bytes or more whenever `Accept-Encoding` contains the text `gzip`, so `gzip;q=0` still gets gzip, compressed afresh and more slowly. On those answers, and on an uncompressed 200 of 1,000 bytes or more, it adds `Accept-Encoding` to `Vary` again, so `Vary` names it twice; a client should compare its tokens. The stored gzip passes through it untouched, as one layer. The Web Demo's own 0.0.7 build does not read this route. Since 0.0.16 the game reads a larger answer of its own, with texts, figures and page scans, through its key, as [game accounts](game-accounts.md#books-and-notes) explains; this route's answer is unchanged.

## Access

An account enters the Web Demo when its authority has the `demo` access point, as betatester, manager, admin and superadmin do. A user asks for access on the dashboard, and an admin's or superadmin's approval makes that account a betatester. The internal proxy checks this access for the session before serving the Demo, and the Demo's pages load book images with the same session. Since 0.0.13 reading books through an API key needs the same access, for the knowledge list, one object and its book images under `/api/v1`. Christopher decided this in round 4, Q39, of the UMST online accounts grilling in the Parent Repo's `docs/plans/`, so that Artin's Algebra, which is under copyright, stays with approved accounts. Another account's key gets 403 `demo_access_required`. Master keys keep their reads. The game's account and character calls need no Demo access; since 0.0.16 its books and notes do. [Security](security.md) owns the boundary.
