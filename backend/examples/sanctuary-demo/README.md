# Sanctuary sample books

Run `python backend/examples/sanctuary-demo/build_archive.py <output-directory>` from the repository root with Node and the Demo dependencies installed. Keep output in the Parent Repo Test Area. The builder exports the frozen accepted prototype data into three Whole-book archives with optional object names, chapter hierarchy, authored dependencies and governed SVG source images.

Real Analysis retains source key `theumst-demo-section-atlas-real-analysis-v1`, its former section keys and `item-01` through `item-36`. Light and Symmetry have separate stable source keys and four objects each. Reimport uses these identities to update content without deleting completion, positions or notes. It does not remove other books. Only import into the environment authorized for the release.

These are illustrative mathematics and science books. No semantic embeddings are invented by this builder. Find neighbors requires available stored embeddings and Qdrant. The frontend loads all content from the authenticated API; these fixture files are not a production data adapter.
