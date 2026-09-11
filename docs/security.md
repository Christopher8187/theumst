# Security and access

Sessions and API keys are authenticated at the backend. `dependencies.py` resolves the current user and checks access points or roles. The dashboard renders permitted destinations, while the corresponding API checks remain authoritative. The internal proxy protects the Web Demo through its auth subrequest; the separate demo container is not publicly exposed by the production Compose arrangement.

Regular reading keys have a rolling database request limit and smaller pages. Master keys permit publishing and larger reads. Full keys are shown at creation; the database stores hashes. Keep account authentication, API compatibility metadata and the application release version separate.

Reader visibility filters hidden books and inactive knowledge from content, discovery and governed images. Personal notes remain the user's writing and withhold unavailable source labels. Content management, master publishing and authorized storage inspection have separate access. Existing externally issued image URLs cannot be recalled by changing HTML; governed reads must check availability on each new request and avoid public caching. Governed image responses also sandbox SVG content and disable MIME sniffing so uploaded image scripts cannot run with application privileges.

Public branding images under `/images` are separate from book object storage. Startup checks their local paths do not overlap. Do not place book uploads under the public static-image directory.

News consent belongs to the current account email and does not grant login or additional access. Subscriptions require the user's session; announcement publication and preview require Media access. Public unsubscribe tokens permit only stopping that subscription, and GET never changes it. Provider suppression events require a verified raw-body signature before persistence. [News subscriptions](news-subscriptions.md) owns these boundaries and the separation from required account security emails.

Keep `.env`, private environment overrides, private keys and backups out of Git and published release attachments. COM and CN use target-specific settings. Preserve their existing configuration during updates. [Operations](operations.md) owns backup and deployment; [account recovery](account-recovery.md) owns reset-token behavior. Future security changes must state the concrete access boundary they alter.
