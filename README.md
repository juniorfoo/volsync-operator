# Volsync operator

A Kubernetes operator that creates Secrets and ReplicationSources for PVCs that are flagged for backups.

Why use this operator? For all PVCs that have the annotation `volsync.backube/restic.enabled`, it will:

- Copy the data from secret `volsync-restic-secrets` and append the `namespace` and `name` of the PVC to the bucket into a new secret
- Create the `ReplicationSources` for the PVC.

## Getting Started

First, copy the helm chart into `homelab-harvester`:

```sh
bash helmify.sh
```

Then, deploy `homelab-harvester`
