import kopf
import json
from hashlib import md5
from logging import Logger
from pathlib import Path

# Custom FileSystemStorage implementation
class FileSystemStorage(kopf.DiffBaseStorage):
    def __init__(self, storage_dir: str, logger: Logger):
        self.logger = logger
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, body, handler_id):
        # Generate a unique file name based on resource and handler
        resource_key = f"{body['apiVersion']}/{body['kind']}/{body['metadata']['namespace']}/{body['metadata']['name']}"
        return self.storage_dir / f"{md5(resource_key.encode()).hexdigest()}_{handler_id}.json"

    def store(self, body, handler_id, diff):
        """Store the diff for a handler."""
        file_path = self._key(body, handler_id)
        try:
            with file_path.open('w') as f:
                json.dump(diff, f)
            self.logger.debug(f"Stored diff in {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to store diff in {file_path}: {e}")
            raise

    def fetch(self, body, handler_id):
        """Retrieve the stored diff for a handler."""
        file_path = self._key(body, handler_id)
        if file_path.exists():
            try:
                with file_path.open('r') as f:
                    return json.load(f)
                logger.debug(f"Fetched diff from {file_path}")
            except Exception as e:
                self.logger.error(f"Failed to fetch diff from {file_path}: {e}")
        return None

    def purge(self, body, handler_id):
        """Remove the stored diff for a handler."""
        file_path = self._key(body, handler_id)
        if file_path.exists():
            try:
                file_path.unlink()
                self.logger.debug(f"Purged diff from {file_path}")
            except Exception as e:
                self.logger.error(f"Failed to purge diff from {file_path}: {e}")