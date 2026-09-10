# Current operating findings

Both normal Compose paths set schema startup to disabled. Application startup checks readiness; it does not provision an empty database. Historical SQL replay contains demo seeds and is restricted to explicit local initialization.

The remote update preserves PostgreSQL/Qdrant containers and volumes. It retains the previous source tree as `<REMOTE_ROOT>.previous` and refuses another upload while that path exists. It does not prove that a database backup is restorable merely by accepting a 64-character digest.

On 10 September 2026 Christopher confirmed that the previous COM Droplet was destroyed after its renewal lapsed. Its old address, 165.227.23.136, is retired. The replacement is theumst-com (Droplet 599318818), Ubuntu 24.04 at 167.71.20.50. DNS for theumst.com and www.theumst.com points there. Bootstrap SSH uses root and the existing chris-theumst-com.pem client key; normal deployment uses chris only after that account and sudo access are verified.

The replacement initially had 512 MB RAM, no swap and no application data/runtime. This is first provisioning, so the established-server agent_deploy update procedure alone is insufficient. Spaces was recovered, but PostgreSQL and Qdrant were not restored by that recovery. The data initialization decision and measured resource use belong in the release deployment record. The Parent Repo handoff is docs/theumst-droplet-deployment-handoff.md. Preserve dated observations there and in the Test Area.

The same day's bootstrap installed Docker Engine 29.8.0, Compose 5.5.1, Nginx and Certbot; added 1 GiB swap; enabled UFW for TCP 22/80/443; and verified key-only `chris` SSH and passwordless sudo. Certificate `theumst-com` covers both COM hostnames and expires 9 December 2026. Certificate issuance succeeded before application deployment. Host Nginx activation and renewal rehearsal follow application readiness. Christopher selected fresh PostgreSQL/Qdrant state and administrator username `christopher`. Authenticated read-only Spaces access found 123 objects totaling 1,073,844 bytes; those objects were preserved.
