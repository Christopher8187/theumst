# Real Analysis demo sample

This packages the 36 invented objects from the [Section Atlas prototype](../../../frontend/demo/prototypes/section-atlas.html), selected in [issue 28](https://github.com/Christopher8187/product/issues/28), as one grimoire named **Real Analysis (Demo Sample)**. It preserves the section hierarchy, object order, statements, formulas, two supplied explanations, and 42 explicit example dependencies. Generic prototype navigation advice is not imported as mathematical workings. No ISBN, images, or semantic vectors are fabricated.

From the repository root, with Python and Node installed:

```sh
python backend/examples/real-analysis-demo/build_archive.py .local/real-analysis-demo.zip
```

Submit the resulting ZIP through the existing master-key `/api/v1/books/ingest-archive` endpoint, following [Whole-book upload](../../../docs/ingestion.md) and the selected environment's authorization and backup requirements. Building the archive performs no server operations. Its stable book and object source keys permit later imports to update the same content. The manifest marks the book as visible in the Web Demo; readers can summon it into My grimoires.

The current demo reads the complete book order. The archive preserves the prototype's dependencies in graph-sidecar storage, but the current reader endpoint still returns generated book-order relationships. Connecting stored dependencies to that endpoint remains part of the existing integration work. Semantic Find neighbors requires real embeddings, which the original prototype does not provide.
