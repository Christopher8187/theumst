# Theumst

This context defines Theumst application and deployment language. Shared
Product Workspace relationships and terms live in
`C:\Business\product\CONTEXT-MAP.md`.

## Vocabulary rule

Use a filesystem term, Git term, or other widely standardized technical term
whenever it describes a concept accurately. Do not replace a standard term
with a Product Workspace-specific term or keyword.

If no standard term accurately describes a genuinely unique concept, explain
the missing distinction to Christopher and ask him to settle the name and
definition before returning the task result. After Christopher settles it,
record a shared definition in `C:\Business\product\CONTEXT-MAP.md`; record a
definition used by only one repository in that repository's `CONTEXT.md`.

## Language

**Theumst**:
The application containing the public website, signed-in dashboard, Web Demo,
backend, databases, storage integrations, and deployment code.
_Avoid_: Website repository, website project

**Web Demo**:
The isolated frontend application served after the internal proxy checks the
signed-in user's access.
_Avoid_: Demo website, public website

**COM deployment**:
The `theumst.com` deployment using the COM server and DigitalOcean Spaces.
_Avoid_: Production promotion, COM child

**CN deployment**:
The `theumst.cn` deployment using the CN server and Aliyun Object Storage
Service.
_Avoid_: Production promotion, CN child

**Local deployment**:
The Windows development deployment using Docker Compose and local storage
settings.
_Avoid_: Test website, lab deployment
