"""
Base plugin class for photoserv plugins.

All plugins must inherit from PhotoservPlugin and implement its methods.
Plugins must also define the following module-level variables:
- __plugin_name__: str - Human-readable name of the plugin
- __plugin_uuid__: str - UUID for the plugin
- __plugin_version__: str - Version string
- __plugin_config__: dict[str, str] - Example configuration schema as a dictionary.
  Each key represents a config parameter name, and the value is a description.
  Users will provide actual config as JSON in the admin interface.
- __plugin_entity_parameters__: dict[str, str] - (Optional) Example entity parameter 
  schema as a dictionary. Each key represents a parameter name, and the value is a 
  description. Users will provide actual parameters as JSON per entity.
"""

import logging
from typing import Any, Dict, Optional, Union, BinaryIO
from integration.models import PluginStorage


class PluginConfigManager:
    """
    Configuration manager for plugin persistent storage.
    Automatically prefixes keys with plugin UUID.
    """
    
    def __init__(self, plugin_uuid: str):
        """
        Initialize the config manager.
        
        Args:
            plugin_uuid: UUID of the plugin (used to prefix keys)
        """
        self.plugin_uuid = plugin_uuid
    
    def _make_key(self, key: str) -> str:
        """Create a prefixed key with plugin UUID."""
        return f"{self.plugin_uuid}_{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from persistent storage.
        
        Args:
            key: The key to retrieve (will be automatically prefixed)
            default: Default value if key doesn't exist
            
        Returns:
            The stored value or default if not found
        """
        
        prefixed_key = self._make_key(key)
        try:
            storage = PluginStorage.objects.get(key=prefixed_key)
            return storage.value
        except PluginStorage.DoesNotExist:
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a value in persistent storage.
        
        Args:
            key: The key to store (will be automatically prefixed)
            value: The value to store (must be JSON-serializable)
        """
        
        prefixed_key = self._make_key(key)
        storage, created = PluginStorage.objects.update_or_create(
            key=prefixed_key,
            defaults={'value': value}
        )
    
    def delete(self, key: str) -> None:
        """
        Delete a value from persistent storage.
        
        Args:
            key: The key to delete (will be automatically prefixed)
        """
        
        prefixed_key = self._make_key(key)
        PluginStorage.objects.filter(key=prefixed_key).delete()


class PhotoservInstance:
    """
    Wrapper object providing access to photoserv functionality for plugins.
    Passed to plugins during registration.
    """
    
    def __init__(self, plugin_uuid: str, logger: logging.Logger):
        """
        Initialize the photoserv instance.
        
        Args:
            plugin_uuid: UUID of the plugin
            logger: Logger instance for the plugin
        """
        self.logger = logger
        self.config = PluginConfigManager(plugin_uuid)
    
    def get_photo_image(self, photo: Union[str, Dict[str, Any]], size: str) -> Optional[BinaryIO]:
        """
        Get the binary stream of a photo at a specific size.
        
        Args:
            photo: Either a photo UUID string, or a dict with 'id' or 'uuid' key
            size: The size slug (e.g., 'thumbnail', 'large', 'original')
            
        Returns:
            Binary file stream of the photo, or None if not found
        """
        # Import here to avoid circular imports
        from media.models import Photo, PhotoSize
        
        # Extract photo identifier
        photo_id = None
        photo_uuid = None
        
        if isinstance(photo, str):
            # Assume it's a UUID
            photo_uuid = photo
        elif isinstance(photo, dict):
            photo_id = photo.get('id')
            photo_uuid = photo.get('uuid')
        
        # Find the photo
        photo_obj = None
        try:
            if photo_uuid:
                photo_obj = Photo.objects.get(uuid=photo_uuid)
            elif photo_id:
                photo_obj = Photo.objects.get(id=photo_id)
            else:
                return None
        except Photo.DoesNotExist:
            return None
        
        # Find the photo size
        try:
            photo_size = PhotoSize.objects.get(photo=photo_obj, size__slug=size)
            # Open and return the file
            return photo_size.image.open('rb')
        except PhotoSize.DoesNotExist:
            return None


class PhotoservPlugin:
    """Base class for all photoserv plugins."""
    config: Dict[str, Any]
    photoserv: PhotoservInstance
    logger: logging.Logger

    def __init__(self, config: Dict[str, Any], photoserv: PhotoservInstance):
        """
        Initialize the plugin with configuration data.
        
        Args:
            config: Configuration dictionary with environment variables already expanded.
                    This is a JSON object (dict) provided by the user in the admin interface.
                    Values can be strings, numbers, booleans, lists, or nested objects.
            photoserv: PhotoservInstance providing access to logger, config storage, and photoserv functionality
        
        Raises:
            Exception: If initialization fails
        """
        self.config = config
        self.photoserv = photoserv
        self.logger = photoserv.logger

    def on_global_change(self, **kwargs) -> None:
        """
        Called when any global change occurs in the system.
        Only called if the plugin is registered with global=True.
        
        Args:
            **kwargs: Additional parameters for future compatibility
        
        Raises:
            Exception: If the handler fails
        """
        pass

    def on_photo_publish(self, data: Dict[str, Any], params: Dict[str, Any], **kwargs) -> None:
        """
        Called when a photo is published.
        
        Args:
            data: Serialized photo data (dict) matching the public API format.
                  This is a read-only snapshot and cannot modify the database.
            params: Per-entity parameters configured for this specific photo.
                    Dictionary of custom parameters from PluginEntityParameters.
                    This is a JSON object (dict) provided by the user per entity.
                    Values can be strings, numbers, booleans, lists, or nested objects.
            **kwargs: Additional parameters for future compatibility
        
        Raises:
            Exception: If the handler fails
        """
        pass

    def on_photo_unpublish(self, data: Dict[str, Any], params: Dict[str, Any], **kwargs) -> None:
        """
        Called when a photo is unpublished.
        
        Args:
            data: Serialized photo data (dict) matching the public API format.
                  This is a read-only snapshot and cannot modify the database.
            params: Per-entity parameters configured for this specific photo.
                    Dictionary of custom parameters from PluginEntityParameters.
                    This is a JSON object (dict) provided by the user per entity.
                    Values can be strings, numbers, booleans, lists, or nested objects.
            **kwargs: Additional parameters for future compatibility
        
        Raises:
            Exception: If the handler fails
        """
        pass
