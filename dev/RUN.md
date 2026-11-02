# Current operating findings

Both normal Compose paths set schema startup to disabled. Application startup checks readiness; it does not provision an empty database. Historical SQL replay contains demo seeds and is restricted to explicit local initialization.

The remote update preserves PostgreSQL/Qdrant containers and volumes. It retains the previous source tree as `<REMOTE_ROOT>.previous` and refuses another upload while that path exists. It does not prove that a database backup is restorable merely by accepting a 64-character digest.

COM runs on theumst-lon1, Droplet 614781178, Ubuntu 24.04 at 209.97.130.228 in London. It began on 1 November 2026 as a live snapshot of the New York droplet theumst-com, 167.71.20.50, and kept its release, data, certificate and settings. DNS for theumst.com and www.theumst.com points there. SSH uses chris, the chris-theumst-com.pem key and passwordless sudo. Both 167.71.20.50 and 165.227.23.136 are destroyed.

The droplet has 1 vCPU, 2 GB RAM, a 50 GB disk and the 1 GiB swap file. After the move it had 1.4 GB of memory free and no swap in use. Updates use agent_deploy with a verified backup. The packager copies the local `.env` DO_SPACES_* settings to the server, so keep them pointed at London. The Parent Repo handoff is docs/theumst-droplet-deployment-handoff.md. Preserve dated observations there and in the Test Area.

The server runs Docker Engine 29.8.0, Compose 5.5.1, host Nginx and Certbot, and UFW allows TCP 22/80/443. Certificate `theumst-com` covers both COM hostnames and expires 9 December 2026. A renewal dry run passed in London on 1 November 2026. Storage is the London bucket `theumst-lon1`, 126 objects totaling 1,076,136 bytes, reached through the key `ultimate-mega-bucket-key`. Christopher deleted the old San Francisco bucket `ultimatemega-audiospace` on 2 November 2026.
