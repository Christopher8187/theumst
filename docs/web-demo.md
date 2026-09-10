# Web Demo behavior

This page owns the functional decisions accepted in [Reconcile the Web Demo requirements and acceptance evidence](https://github.com/Christopher8187/product/issues/28). The combined [Theumst 0.1.0 task](https://github.com/Christopher8187/product/issues/33) implements and verifies them. The [accepted AFSR and delivery design](https://github.com/Christopher8187/product/issues/29#issuecomment-5603562451) fixes the publication scope.

## Reading and completion

Text follows the complete available grimoire order. Continue visits one next object, including completed objects, exercises and section transitions. Visiting changes position only. Train selects the next unfinished exercise ahead and stops with an explanation when none remains; it never wraps backward. Keep the familiar reader replacement with the Atlas alongside it.

Mark done saves the object's completion, refreshes visible completion feedback and keeps the object selected. Completion is shared between Text and Questions. Their saved positions are independent. A cross-book excursion preserves the first original book, object and realm through further jumps; Return to original book restores all three.

## Notes and availability

Notes opens on the right with an attached-note selector and New note. Multiple notes may attach to one object. All notes opens the broader Notes realm. Switching or leaving edited writing offers Save and continue, Discard and continue and Keep editing, preserving the intended destination. Save failure keeps the draft.

Hidden books and their objects are excluded from reader lists, details, images, semantic discovery and Crystallization. Personal writing remains readable with its source unavailable. Retain saved object IDs and completion so restored access restores progress. Authorized management and publishing still permit inspection and unhiding.

If the base grimoire becomes unavailable, withhold its source content when detected and ask the reader to confirm exit to My grimoires. If only the original grimoire becomes unavailable during an excursion, offer that exit plus staying in the available base grimoire. Availability is checked on window focus and periodically; this is detection on revalidation, not server-pushed notification.

## Discovery and presentation

Find neighbors searches across available books using stored semantic projections. Retrieve top k for each applicable projection, combine distinct candidates, obtain both scores for every complete pair and show the final top k. Absence from one result set is not a zero score. Compatible complete pairs use equal weighting. If exactly one object lacks workings, apply 0.8 to the available statement score; if both lack workings, retain it. Normalize signed cosine scores to [0,1] before the penalty so it cannot improve a negative score. Missing embeddings despite available workings are processing faults.

Crystallization retrieves actual same-crystal instances, excluding hidden sources even when they are preferred. It is separate from approximate Find neighbors. No general-search fallback choice is introduced.

Show supplied summary and ISBN, falling back to the title and an unavailable marker when absent. Contents starts at top-level chapters, expands descendants and renders a bounded list. Support English, Chinese and Japanese throughout the interface; source text remains unchanged. [Atlas](atlas.md) owns display details and [testing objectives](testing/web-demo.md) own acceptance checks. The implementation remains a release candidate until recorded verification completes.
