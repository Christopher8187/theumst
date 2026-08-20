# Theumst context

Shared Product Workspace relationships and terms live in
`C:\Business\product\CONTEXT-MAP.md`.

## Theumst terms

### Theumst

The application containing the public website, signed-in dashboard, Web Demo,
FastAPI backend, PostgreSQL data, Qdrant semantic vectors, object-storage
integrations, and deployment code.

### Web Demo

The isolated frontend application served from its own container after the
internal proxy checks the signed-in user's access.

### COM deployment

The `theumst.com` deployment using the COM server and DigitalOcean Spaces.

### CN deployment

The `theumst.cn` deployment using the CN server and Aliyun Object Storage
Service.

### Local deployment

The Windows development deployment that runs the Theumst services with Docker
Compose and local storage settings.
