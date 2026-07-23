from django.dispatch import receiver
from django.db import transaction
from media.signals import photo_published, photo_unpublished
from django.db.models.signals import post_save, post_delete
from media.models import Photo, PhotoMetadata, PhotoSize, Size, Album, PhotoInAlbum, Tag, PhotoTag
from integration.tasks import call_queue_global_integrations, call_plugin_signal
from public_rest_api.serializers import PhotoSerializer
from .models import PluginEntityParameters


def dispatch_photo_signal(photo_instance, signal_name):
    """
    Helper function to dispatch plugin signals for photo events with exclusion handling.
    
    Args:
        photo_instance: The Photo instance
        signal_name: The plugin method to call ('on_photo_publish' or 'on_photo_unpublish')
    """
    from .models import PhotoPluginExclusion, PythonPlugin
    
    # Get list of excluded plugins for this photo
    excluded_plugin_ids = set(
        PhotoPluginExclusion.objects.filter(photo=photo_instance)
        .values_list('plugin_id', flat=True)
    )
    
    # Get list of active plugins that are NOT excluded
    included_plugin_ids = list(
        PythonPlugin.objects.filter(active=True)
        .exclude(id__in=excluded_plugin_ids)
        .values_list('id', flat=True)
    )
    
    # Serialize photo data
    photo_data = PhotoSerializer(photo_instance).data
    
    # Queue task with plugin filtering
    transaction.on_commit(
        lambda: call_plugin_signal.delay(signal_name, data=photo_data, plugin_ids=included_plugin_ids)
    )


@receiver(photo_published)
def handle_photo_published(sender, instance, **kwargs):
    """Handle photo published event."""
    dispatch_photo_signal(instance, 'on_photo_publish')


@receiver(photo_unpublished)
def handle_photo_unpublished(sender, instance, **kwargs):
    """Handle photo unpublished event."""
    dispatch_photo_signal(instance, 'on_photo_unpublish')


@receiver(post_save, sender=Photo)
@receiver(post_save, sender=PhotoMetadata)
@receiver(post_save, sender=PhotoSize)
@receiver(post_save, sender=Size)
@receiver(post_save, sender=Album)
@receiver(post_save, sender=PhotoInAlbum)
@receiver(post_save, sender=Tag)
@receiver(post_save, sender=PhotoTag)

@receiver(post_delete, sender=Photo)
@receiver(post_delete, sender=PhotoMetadata)
@receiver(post_delete, sender=PhotoSize)
@receiver(post_delete, sender=Size)
@receiver(post_delete, sender=Album)
@receiver(post_delete, sender=PhotoInAlbum)
@receiver(post_delete, sender=Tag)
@receiver(post_delete, sender=PhotoTag)
def handle_global_integrations(*args, **kwargs):
    call_queue_global_integrations()