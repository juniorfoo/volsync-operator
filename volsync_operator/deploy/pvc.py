"""
Controls creation of Secrets and ReplicationSources for PVCs that that are
annotated with `volsync.backube/restic.enabled`
"""

import base64
from logging import Logger

from kubernetes import config, client
from kubernetes.client.models.v1_persistent_volume_claim import V1PersistentVolumeClaim
from kubernetes.client.models.v1_secret import V1Secret
import kopf

# from .util import FileSystemStorage
from volsync_operator.deployer import Deployer

# # Initialize Kubernetes client
# config.load_incluster_config()  # For running inside a cluster
# # kubernetes.config.load_kube_config()  # Uncomment for local development

# # Configure custom FileSystemStorage
# storage_dir = "/kopf-state"
# kopf.configure(diffbase_storage=FileSystemStorage(storage_dir=storage_dir))

@kopf.on.create('', 'v1', 'persistentvolumeclaims',
                annotations={'volsync.backube/restic.enabled': 'true'})
async def on_create_pvc(
    spec: V1PersistentVolumeClaim,
    name: str,
    namespace: str,
    logger: Logger,
    **kwargs,
):
    """
    Handler for PersistentVolumeClaim creation events.
    Creates/updates the required Secret and ReplicationSources for volsync to work properly
    """
    await on_pvc(spec, name, namespace, logger, kwargs)
    return None
    
@kopf.on.update('', 'v1', 'persistentvolumeclaims',
                annotations={'volsync.backube/restic.enabled': 'true'})
async def on_update_pvc(
    spec: V1PersistentVolumeClaim,
    name: str,
    namespace: str,
    logger: Logger,
    **kwargs,
):
    """
    Handler for PersistentVolumeClaim update events.
    Creates/updates the required Secret and ReplicationSources for volsync to work properly
    """
    await on_pvc(spec, name, namespace, logger, kwargs)
    return None

async def on_pvc(
    spec: V1PersistentVolumeClaim,
    name: str,
    namespace: str,
    logger: Logger,
    kwargs: dict,
):
    """
    Handler for PersistentVolumeClaim events.
    Creates/updates the required Secret and ReplicationSources for volsync to work properly
    """

    source_secret_name='volsync-restic-secrets'
    logger.info(f"PVC {name} created in namespace {namespace}")
    deployer = Deployer(namespace, "N/A", logger)

    core = client.CoreV1Api()
    source_secret_namespace=get_current_namespace()

    # Fetch the source secret from the namespace we are running in (not the namespace of the PVC)
    try:
        source_secret: V1Secret = core.read_namespaced_secret(name=source_secret_name, namespace=source_secret_namespace)
        logger.error(f"Source secret {source_secret_name} found in namespace {source_secret_namespace}")
    except client.ApiException as e:
        if e.status == 404:
            # Source Secret should have been created before hand, no need to keep trying
            logger.error(f"Source secret {source_secret_name} not found in namespace {source_secret_namespace}")
            raise kopf.PermanentError(f"Source secret {source_secret_name} does not exist")
        raise kopf.TemporaryError(f"Failed to fetch source secret: {e}", delay=30)
    
    # Prepare the new secret with modified contents
    try:
        new_secret_data = {}
        for key, value in source_secret.data.items():
            if key == "RESTIC_REPOSITORY":
                # Decode, modify, and re-encode the username
                decoded_value = base64.b64decode(value).decode('utf-8')
                modified_value = f"{decoded_value}/{namespace}/{name}"  # Append the namespace and name of the PVC
                new_secret_data[key] = modified_value
            else:
                # Copy other fields unchanged
                new_secret_data[key] = base64.b64decode(value).decode('utf-8')

        result = deployer.deploy(
            template_name="secret.yaml",
            name=name,
            namespace=namespace,
            restic_password=new_secret_data["RESTIC_PASSWORD"],
            restic_repository=new_secret_data["RESTIC_REPOSITORY"],
            aws_access_key_id=new_secret_data["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=new_secret_data["AWS_SECRET_ACCESS_KEY"],
        )
        logger.debug(result)
    except client.ApiException as e:
        raise kopf.TemporaryError(f"Failed to create Secret for PVC {name}: {e}", delay=30)

    try:
        result = deployer.deploy(
            template_name="replicationsource.yaml",
            name=name,
            namespace=namespace,
        )
        logger.debug(result)
    except client.ApiException as e:
        raise kopf.TemporaryError(f"Failed to create ReplicationSource for PVC {name}: {e}", delay=30)

    logger.info(f"All volsync resources for PVC {name} have been deployed")
    return None

def get_current_namespace():
    try:
        # Attempt to load in-cluster configuration first
        config.load_incluster_config()
        # Read the namespace from the service account file
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            current_namespace = f.read().strip()
        return current_namespace
    except Exception:
        # If in-cluster config fails, try loading kube config
        config.load_kube_config()
        # Get the current context
        contexts = config.list_kube_config_contexts()
        if not contexts:
            raise Exception("No Kubernetes context found")
        current_context = contexts[1]
        return current_context['context']['namespace']