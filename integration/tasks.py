import functools
from django.core.cache import cache
from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from .models import WebRequest, IntegrationCaller, PythonPlugin, RunResult
from datetime import timedelta
from django.utils import timezone
from .models import PluginEntityParameters


def get_entity_parameters(plugin, data):
    """
    Look up entity parameters for a plugin and entity.
    
    Args:
        plugin: PythonPlugin instance
        data: Dict containing entity data with 'uuid' key
        
    Returns:
        Dict of entity parameters, or empty dict if none found
    """
    params = {}
    if data and 'uuid' in data:
        try:
            entity_params = PluginEntityParameters.objects.get(
                plugin=plugin,
                entity_uuid=data['uuid']
            )
            params = entity_params.get_parameters_dict()
        except PluginEntityParameters.DoesNotExist:
            pass
    return params


@shared_task
def call_web_request(web_request_id):
    web_request = WebRequest.objects.get(id=web_request_id)
    result = web_request.run(IntegrationCaller.EVENT_SCHEDULER)
    if not result.successful:
        raise Exception(str(web_request) + " - failed")

    return str(web_request) + " - success"


@shared_task
def call_single_plugin_signal(plugin_id, signal_name, data=None):
    """
    Call a specific plugin method, typically for manual triggering.
    
    This bypasses the active check but requires the plugin to be valid.
    Used for manually triggering plugin actions from the integration UI.
    
    Args:
        plugin_id: ID of the plugin to call
        signal_name: Name of the plugin method to call (e.g., 'on_photo_publish', 'on_photo_unpublish')
        data: Optional dict of serialized data to pass to the plugin method
        
    Returns:
        Success message string
        
    Raises:
        Exception: If the plugin doesn't exist, is invalid, or the execution fails
    """
    
    try:
        plugin = PythonPlugin.objects.get(id=plugin_id)
    except PythonPlugin.DoesNotExist:
        raise Exception(f"Plugin with ID {plugin_id} does not exist")
    
    if not plugin.valid:
        raise Exception(f"Plugin {plugin} is not valid")
    
    # Look up entity parameters if data contains a UUID
    params = get_entity_parameters(plugin, data)
    
    # Build method args based on signal name
    if signal_name in ['on_photo_publish', 'on_photo_unpublish']:
        method_args = (data, params) if data else (None, params)
    else:
        method_args = (data,) if data else ()
    
    plugin.run(
        IntegrationCaller.MANUAL,
        method_name=signal_name,
        method_args=method_args
    )
    
    return f"Called {signal_name} on {plugin}"


@shared_task
def call_plugin_signal(signal_name, data=None, plugin_ids=None):
    """
    Call plugin methods based on signal name.
    
    Passes serialized data to plugins instead of model instances to:
    - Prevent direct database access
    - Maintain API compatibility
    - Avoid exposing internal implementation details

    Args:
        signal_name: Name of the plugin method to call (e.g., 'on_photo_publish', 'on_global_change')
        data: Optional dict of serialized data to pass to the plugin method
        plugin_ids: Optional list of plugin IDs to include. If None, calls all active plugins.
    """
    
    if plugin_ids is not None:
        # Call only specified plugins
        plugins = PythonPlugin.objects.filter(id__in=plugin_ids, active=True)
    else:
        # Call all active plugins
        plugins = PythonPlugin.objects.filter(active=True)
    
    called_count = 0
    for plugin in plugins:
        if not plugin.valid:
            continue

        try:
            # Look up entity parameters if data contains a UUID
            params = get_entity_parameters(plugin, data)
            
            # Build method args based on signal name
            if signal_name != "on_global_change":
                method_args = (data, params) if data else (None, params)
            else:
                method_args = (data,) if data else ()
            
            plugin.run(
                IntegrationCaller.EVENT_SCHEDULER,
                method_name=signal_name,
                method_args=method_args
            )
            called_count += 1
        except Exception:
            # Continue even if one plugin fails
            pass

    return f"Called {signal_name} on {called_count} plugins"


def debounced_task(key_generator, delay=settings.INTEGRATION_QUEUE_DELAY):
    """
    Debounced task decorator using a counter-based approach.
    Increments a counter on each call, decrements after delay.
    Only executes if counter reaches 0 after decrement.
    """
    def decorator(func):
        @shared_task(bind=True, track_started=False, name=f"{func.__module__}.{func.__name__}")
        @functools.wraps(func)
        def celery_task(self, *args, **kwargs):
            # Generate the debounce key
            key = key_generator(*args, **kwargs)
            counter_key = f"debounce:{key}:counter"
            
            # Decrement the counter
            try:
                count = cache.decr(counter_key)
            except ValueError:
                # Key doesn't exist or isn't an integer, ignore this task
                raise Ignore()
            
            # If counter is 0, execute the task (we're the last one)
            if count == 0:
                cache.delete(counter_key)
                return func(*args, **kwargs)
            else:
                # Someone else called after us, ignore
                raise Ignore()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate the debounce key
            key = key_generator(*args, **kwargs)
            counter_key = f"debounce:{key}:counter"
            
            # Set a reasonable timeout that gets refreshed on every call
            # This prevents memory leaks while ensuring the key lives long enough
            timeout = delay + 3600  # delay + 1 hour buffer
            
            try:
                cache.incr(counter_key)
                # Refresh timeout on every increment - key lives as long as calls keep coming
                cache.touch(counter_key, timeout=timeout)
            except ValueError:
                # Key doesn't exist, create it
                cache.set(counter_key, 1, timeout=timeout)
            
            # Schedule task to run after delay
            celery_task.apply_async(args=args, kwargs=kwargs, countdown=delay)
            return True

        wrapper.celery_task = celery_task
        return wrapper
    return decorator


def queue_global_integrations(**kwargs):
    """Queue all global integrations (web requests and global plugins)."""
    # Queue web requests
    web_requests = WebRequest.objects.filter(active=True)
    for web_request in web_requests:
        call_web_request.delay(web_request.id)
    
    # Call global plugins
    plugins = PythonPlugin.objects.filter(active=True)
    for plugin in plugins:
        if not plugin.valid:
            continue
        call_plugin_signal.delay('on_global_change')

    return f"Queued {web_requests.count()} web requests and called {plugins.count()} global plugins"


call_queue_global_integrations = debounced_task(
    lambda *a, **k: "queue_global_integrations",
    delay=30 if settings.DEBUG else settings.INTEGRATION_QUEUE_DELAY
)(queue_global_integrations)


@shared_task
def scan_plugins():
    """
    Scan the plugins directory for new plugin modules.
    Creates PythonPlugin entries for any modules that don't already have one.
    """
    plugins_path = settings.PLUGINS_PATH
    
    # Ensure the plugins directory exists
    plugins_path.mkdir(parents=True, exist_ok=True)
    
    # Get all .py files in the plugins directory
    plugin_files = list(plugins_path.glob("*.py"))
    
    created_count = 0
    for plugin_file in plugin_files:
        module = plugin_file.stem
        
        # Skip __init__ and other special files
        if module.startswith("_"):
            continue
        
        # Check if a plugin entry already exists for this module
        if not PythonPlugin.objects.filter(module=module).exists():
            try:
                # Create a new plugin entry
                plugin = PythonPlugin.objects.create(
                    module=module,
                    active=False  # Start as inactive for safety
                )
                created_count += 1
            except Exception:
                # Skip if there's an error creating the plugin
                continue
    
    return f"Scanned plugins directory. Created {created_count} new plugin entries."


@shared_task
def consistency():
    # Delete all integration run results older than 1 year
    one_year_ago = timezone.now() - timedelta(days=365)
    deleted_count, _ = RunResult.objects.filter(
        start_timestamp__lt=one_year_ago
    ).delete()

    return f"Deleted {deleted_count} integration run results older than 1 year."
