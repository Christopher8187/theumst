# Documentation ownership

README.md explains the application, common work and architecture before linking to detail. CONTEXT.md contains definitions only, with shared meanings in the Parent Repo map. AGENTS.md owns reading order, task triggers and boundaries. Architecture pages own current structure; subject pages own behavior; component READMEs explain workflow and source organization; RUN files hold concise useful current operating knowledge.

Write for Theumst's architecture and needs. MWF supplies the selected file arrangement and reading pattern, not documentation content or length. Keep each explanation in one place and link to it from procedures. Instruction-only skills perform repeatable work and point to the documents that own the explanation.

Current README/RUN files do not accumulate chronological release histories. Put useful dated observations under `docs/history/` and explicitly proposed work under `docs/plans/`. Keep raw logs and screenshots in the Test Area. Retain short relevant test links in component READMEs, useful current test findings in RUN, and full coverage explanations in test guides.

Every implementing issue must explicitly name its selected required documents and decisions. After moving content, check inbound links and remove competing old entry files rather than leaving alternate instructions or redirect stubs. Compare all current-source claims adversarially before publication. The [accepted design](https://github.com/Christopher8187/product/issues/29#issuecomment-5603562451) and [README/RUN requirements](https://github.com/Christopher8187/product/issues/25#issuecomment-5599927768) own the selected documentation model.
