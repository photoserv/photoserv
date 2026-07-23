from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.timezone import now, datetime
from django.conf import settings
import requests
import os
import uuid
import importlib
import sys
import logging
import json
from io import StringIO
from pathlib import Path
from typing import Optional

    
class IntegrationCaller(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    EVENT_SCHEDULER = "EVENT_SCHEDULER", "Event Scheduler"


class PluginStorage(models.Model):
    """
    Key-value storage for integration plugins to persist data.
    Keys are automatically prefixed with plugin UUID.
    """
    key = models.CharField(max_length=512, unique=True, db_index=True)
    value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integration Persistent Storage"
        verbose_name_plural = "Integration Persistent Storage"

    def __str__(self):
        return f"{self.key}: {str(self.value)[:50]}"


class PhotoPluginExclusion(models.Model):
    """
    Persistent exclusion of a photo from plugin dispatch.
    Used to permanently exclude specific plugins from being notified about
    a photo's publish/unpublish events. These must be manually managed.
    """
    photo = models.ForeignKey('media.Photo', on_delete=models.CASCADE, related_name='plugin_exclusions')
    plugin = models.ForeignKey('PythonPlugin', on_delete=models.CASCADE, related_name='photo_exclusions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('photo', 'plugin')
        verbose_name = "Photo Plugin Exclusion"
        verbose_name_plural = "Photo Plugin Exclusions"

    def __str__(self):
        return f"Exclude {self.plugin} from {self.photo}"


class PluginEntityParameters(models.Model):
    """
    Per-entity parameters for integration plugins.
    Stores custom parameters for specific entities (identified by UUID) that
    are passed to plugin methods during entity-specific events.
    """
    plugin = models.ForeignKey('PythonPlugin', on_delete=models.CASCADE, related_name='entity_parameters')
    entity_uuid = models.UUIDField(db_index=True, help_text="UUID of the entity")
    parameters = models.JSONField(blank=True, null=True, default=dict, help_text="JSON object containing entity-specific parameters")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('plugin', 'entity_uuid')
        verbose_name = "Plugin Entity Parameters"
        verbose_name_plural = "Plugin Entity Parameters"

    def __str__(self):
        return f"{self.plugin} parameters for {self.entity_uuid}"
    
    def clean(self):
        """Validate parameters format."""
        if self.parameters:
            if not isinstance(self.parameters, dict):
                raise ValidationError("Parameters must be a valid JSON object.")
    
    def get_parameters_dict(self) -> dict:
        """Get parameters dictionary with environment variables expanded."""
        if not self.parameters:
            return {}
        
        def expand_env_vars(obj):
            """Recursively expand environment variables in strings."""
            if isinstance(obj, str):
                return os.path.expandvars(obj)
            elif isinstance(obj, dict):
                return {k: expand_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [expand_env_vars(item) for item in obj]
            else:
                return obj
        
        return expand_env_vars(self.parameters)


class RunResult(models.Model):
    """
    Stores a historical record of an integration run.

    - integration_uuid: UUID of the IntegrationObject
    """
    integration_uuid = models.UUIDField(db_index=True, null=True)
    start_timestamp = models.DateTimeField(blank=True, null=True)
    end_timestamp = models.DateTimeField(blank=True, null=True)
    caller = models.CharField(max_length=32, choices=IntegrationCaller.choices)
    successful = models.BooleanField(default=False)
    run_log = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-start_timestamp']

    def __str__(self):
        status = "PASS" if self.successful else "FAIL"
        return f"[{status}] {self.start_timestamp} to {self.end_timestamp} ({self.integration_uuid})"
    
    def get_absolute_url(self):
        return reverse("integration-run-result-detail", kwargs={"pk": self.pk})


class IntegrationObject(models.Model):
    """Base abstract model for all integrations."""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nickname = models.CharField(max_length=255, blank=True, null=True, help_text="Optional")
    active = models.BooleanField(default=True)

    @property
    def integration_type(self) -> str:
        """String name of the class for display/logging."""
        return self.__class__.__name__

    def _run(self, **kwargs) -> str:
        """Subclasses must implement this to perform actual work and return a log string.
        Raise exception on error"""
        raise NotImplementedError()

    def run(self, caller: IntegrationCaller, **kwargs):
        """Execute the integration and automatically record the result."""
        result = RunResult.objects.create(
            integration_uuid=self.uuid,
            start_timestamp=now(),
            caller=caller,
        )

        try:
            log_output = self._run(**kwargs)
            result.successful = True
            result.run_log = log_output
        except Exception as e:
            result.successful = False
            result.run_log = f"ERROR: {e}"
        finally:
            result.run_log = result.run_log.strip()
            result.end_timestamp = now()
            result.save()

        return result

    @property
    def run_history(self):
        """Query run history for this integration instance by UUID."""
        return RunResult.objects.filter(
            integration_uuid=self.uuid
        ).order_by('-start_timestamp')
    
    @property
    def last_run_timestamp(self) -> Optional[datetime]:
        """Get the most recent run result for this integration instance."""
        last_run = RunResult.objects.filter(
            integration_uuid=self.uuid
        ).order_by('-start_timestamp').first()
        return last_run.start_timestamp if last_run else None

    class Meta:
        abstract = True


# Create your models here.
class WebRequest(IntegrationObject):
    class HttpMethod(models.TextChoices):
        GET = "GET", "GET"
        POST = "POST", "POST"
        PUT = "PUT", "PUT"
        DELETE = "DELETE", "DELETE"
        PATCH = "PATCH", "PATCH"
        HEAD = "HEAD", "HEAD"
        OPTIONS = "OPTIONS", "OPTIONS"

    method = models.CharField(max_length=32, choices=HttpMethod.choices)
    url = models.URLField()
    headers = models.TextField(blank=True, null=True, default="", help_text="One per line in the format Header: Value")
    body = models.TextField(blank=True, null=True)

    def clean(self):
        # Ensure headers are in the correct format
        if self.headers:
            seen_headers = set()
            for line in self.headers.splitlines():
                line = line.strip()
                if not line:
                    continue
                if ':' not in line:
                    raise ValidationError(f"Invalid header format: '{line}'. Each header must contain a colon.")
                header_name = line.split(':', 1)[0].strip()
                if header_name in seen_headers:
                    raise ValidationError(f"Duplicate header found: '{header_name}'.")
                seen_headers.add(header_name)

    def _send(self):
        # Substitute environment variables in the URL and body
        url = self._substitute_env_variables(self.url)
        body = self._substitute_env_variables(self.body) if self.body else None

        # Substitute environment variables in headers
        headers = {}
        if self.headers:
            for line in self.headers.splitlines():
                line = line.strip()
                if line:
                    key, value = map(str.strip, line.split(':', 1))
                    headers[key] = self._substitute_env_variables(value)

        # Send the HTTP request
        response = requests.request(self.method, url, headers=headers, data=body)
        return response
    
    def _run(self):
        log = f"{self.method} {self.url}\n\n{self.headers.rstrip() if self.headers else "(no headers)"}\n\n{self.body.rstrip() if self.body else "(no request body)"}\n\n"

        try:
            response = self._send()

            log += f"Response: {str(response.status_code)}\n\n{response.text}"

            if not str(response.status_code).startswith("2"):
                raise Exception(log)
        except Exception as e:
            raise Exception(e)

        return log

    def _substitute_env_variables(self, value):
        # Replace ${ENV_VAR_NAME} with the corresponding environment variable value
        if not value:
            return value
        return os.path.expandvars(value)

    def __str__(self):
        return self.nickname if self.nickname else self.method + " " + self.url[:128]

    def get_absolute_url(self):
        return reverse("web-request-detail", kwargs={"pk": self.pk})
    
    class Meta:
        verbose_name = "Web Request"


class PythonPlugin(IntegrationObject):
    """Python plugin integration that can respond to system events."""
    
    module = models.CharField(max_length=255, help_text="Python module name (without .py extension)")
    config = models.JSONField(blank=True, null=True, default=dict, help_text="JSON object containing plugin configuration with environment variable support")
    
    def clean(self):
        """Validate config format."""
        if self.config:
            if not isinstance(self.config, dict):
                raise ValidationError("Config must be a valid JSON object.")
    
    @property
    def valid(self) -> bool:
        """Check if the plugin module exists and is valid."""
        try:
            plugin_module = self._load_module()
            if plugin_module is None:
                return False
            
            # Check for required module-level variables
            required_attrs = ['__plugin_name__', '__plugin_uuid__', '__plugin_version__', '__plugin_config__']
            for attr in required_attrs:
                if not hasattr(plugin_module, attr):
                    return False
            
            # Check if module has a PhotoservPlugin subclass
            from photoserv_plugin import PhotoservPlugin
            plugin_class = self._get_plugin_class(plugin_module)
            return plugin_class is not None
        except Exception:
            return False
    
    def _load_module(self):
        """Load the plugin module from the plugins directory."""
        try:
            # Add plugins directory to sys.path if not already there
            plugins_path = str(settings.PLUGINS_PATH)
            if plugins_path not in sys.path:
                sys.path.insert(0, plugins_path)
            
            # Try to import or reload the module
            if self.module in sys.modules:
                module = importlib.reload(sys.modules[self.module])
            else:
                module = importlib.import_module(self.module)
            
            return module
        except Exception:
            return None
    
    def _get_plugin_class(self, module):
        """Find the PhotoservPlugin subclass in the module."""
        from photoserv_plugin import PhotoservPlugin
        
        for item_name in dir(module):
            item = getattr(module, item_name)
            if isinstance(item, type) and issubclass(item, PhotoservPlugin) and item is not PhotoservPlugin:
                return item
        return None
    
    def _get_config_dict(self) -> dict:
        """Get config dictionary with environment variables expanded."""
        if not self.config:
            return {}
        
        def expand_env_vars(obj):
            """Recursively expand environment variables in strings."""
            if isinstance(obj, str):
                return os.path.expandvars(obj)
            elif isinstance(obj, dict):
                return {k: expand_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [expand_env_vars(item) for item in obj]
            else:
                return obj
        
        return expand_env_vars(self.config)
    
    def _run(self, **kwargs) -> str:
        """
        Run a specific plugin method.
        
        Kwargs:
            method_name: Name of the method to call (defaults to 'register')
            method_args: Tuple of arguments to pass to the method
            
        Returns:
            Log output from the plugin execution
        """
        method_name = kwargs.get('method_name', 'register')
        method_args = kwargs.get('method_args', ())
        
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        
        plugin_logger = logging.getLogger(f'plugin.{self.module}')
        plugin_logger.setLevel(logging.DEBUG)
        plugin_logger.handlers.clear()
        plugin_logger.addHandler(handler)
        
        try:
            # Load the module
            plugin_module = self._load_module()
            if plugin_module is None:
                raise Exception(f"Plugin module '{self.module}' not found")
            
            # Get the plugin class
            plugin_class = self._get_plugin_class(plugin_module)
            if plugin_class is None:
                raise Exception(f"No PhotoservPlugin subclass found in '{self.module}'")
            
            # Prepare config and photoserv instance
            config_dict = self._get_config_dict()
            from photoserv_plugin import PhotoservInstance
            photoserv_instance = PhotoservInstance(
                plugin_uuid=str(self.uuid),
                logger=plugin_logger
            )
            
            # Instantiate the plugin (calls __init__ with config and photoserv)
            plugin_instance = plugin_class(config_dict, photoserv_instance)
            
            # Log plugin info
            plugin_logger.info(f"Plugin: {plugin_module.__plugin_name__}")
            plugin_logger.info(f"Version: {plugin_module.__plugin_version__}")
            plugin_logger.info(f"UUID: {plugin_module.__plugin_uuid__}")
            plugin_logger.info(f"Config: {list(config_dict.keys())}")
            
            # Call the requested method
            if method_name == 'register':
                # Already registered in __init__, just log success
                plugin_logger.info("Plugin initialized successfully")
            else:
                method = getattr(plugin_instance, method_name, None)
                if method is None:
                    raise Exception(f"Method '{method_name}' not found in plugin")
                
                plugin_logger.info(f"Calling {method_name}")
                method(*method_args)
            
            plugin_logger.info(f"{method_name} completed successfully")
            
        except Exception as e:
            plugin_logger.error(f"Error in {method_name}: {str(e)}")
            raise
        finally:
            handler.flush()
            plugin_logger.removeHandler(handler)
        
        return log_stream.getvalue()
    
    def __str__(self):
        return self.nickname if self.nickname else f"{self.module} ({str(self.uuid)[:8]})"
    
    def get_absolute_url(self):
        return reverse("python-plugin-detail", kwargs={"pk": self.pk})
    
    class Meta:
        verbose_name = "Python Plugin"
