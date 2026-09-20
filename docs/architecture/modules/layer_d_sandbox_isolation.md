# Layer D — Sandbox & Isolation Boundaries

Layer D provides strict process containment without inventing custom kernel sandboxes:
- Linux Bubblewrap unprivileged namespaces.
- Docker and Podman OCI standard container isolation.
- gVisor application kernel sandboxing.
