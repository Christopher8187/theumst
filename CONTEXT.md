# Theumst

This context defines Theumst application and deployment language. Shared
Product Workspace relationships and terms live in
`C:\Business\product\CONTEXT-MAP.md`.

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
