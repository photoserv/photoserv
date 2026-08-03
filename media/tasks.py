from celery import shared_task
from . import models
import os
from . import CONTENT_RESIZED_PHOTOS_PATH
from django.conf import settings
from media import services


@shared_task
def generate_sizes_for_photo(photo_id):
    try:
        photo = models.Photo.objects.get(id=photo_id)
    except models.Photo.DoesNotExist:
        return f"Photo with id {photo_id} does not exist."

    sizes = models.Size.objects.all()
    for size in sizes:
        if models.PhotoSize.objects.filter(photo=photo, size=size).exists():
            continue  # Skip if already exists

        try:
            services.gen_size(photo, size)
        except FileNotFoundError:
            return f"Raw image file for photo id {photo.id} not found."
    
    return f"Sizes generated for photo id {photo.id}."


@shared_task
def generate_photo_sizes_for_size(size_id):
    try:
        size = models.Size.objects.get(id=size_id)
    except models.Size.DoesNotExist:
        return f"Size with id {size_id} does not exist."

    photos = models.Photo.objects.all()
    for photo in photos:
        generate_sizes_for_photo.delay(photo.id)
    
    return f"Size generation tasks queued for size id {size.id}."


@shared_task
def delete_files(files):
    for path in files:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    
    return f"Deleted {len(files)} files."


@shared_task
def generate_photo_metadata(photo_id):
    photo: models.Photo

    try:
        photo = models.Photo.objects.get(id=photo_id)
    except models.Photo.DoesNotExist:
        return f"Photo with id {photo_id} does not exist."
    
    services.generate_metadata_for_photo(photo)
    return f"Metadata generated for photo id {photo.id}."


@shared_task
def photo_replace_image(photo_id, old_image_path):
    """
    Handle replacing a photo's image file.
    Deletes old file and all associated PhotoSize objects/files,
    then regenerates everything.
    """
    try:
        photo = models.Photo.objects.get(id=photo_id)
    except models.Photo.DoesNotExist:
        return f"Photo with id {photo_id} does not exist."
    
    # Delete old PhotoSize objects and their files (must loop to handle file deletion)
    photo_sizes = models.PhotoSize.objects.filter(photo=photo)
    deleted_count = 0
    for photo_size in photo_sizes:
        if photo_size.image:
            try:
                os.remove(photo_size.image.path)
            except (FileNotFoundError, ValueError):
                pass
        photo_size.delete()
        deleted_count += 1
    
    # Delete the old raw image file
    if old_image_path:
        try:
            os.remove(old_image_path)
        except (FileNotFoundError, ValueError):
            pass
    
    # Delete old metadata (if exists)
    try:
        photo.metadata.delete()
    except models.PhotoMetadata.DoesNotExist:
        pass
    
    # Regenerate everything (called directly, not as delayed task)
    post_photo_create(photo_id)
    
    return f"Replaced image for photo {photo_id}, deleted {deleted_count} old sizes and regenerated."


@shared_task
def post_photo_create(photo_id):
    # Run these synchronously after photo creation
    generate_photo_metadata(photo_id)
    generate_sizes_for_photo(photo_id)
    photo = models.Photo.objects.get(id=photo_id)
    photo.update_published(dispatch_signals=True, update_model=True)
    
    return f"Generated sizes, metadata, and calculated publish state for photo {photo_id}."


@shared_task
def consistency():
    issues = 0

    # Filesystem
    # --- Build full paths under MEDIA_ROOT ---
    resized_photos_dir = os.path.join(settings.MEDIA_ROOT, CONTENT_RESIZED_PHOTOS_PATH)

    # Ensure directories exist
    os.makedirs(resized_photos_dir, exist_ok=True)

    # Photo Sizes
    # 1. Ensure every photo size's image file exists
    photo_sizes = models.PhotoSize.objects.all()
    for photo_size in photo_sizes:
        if (not photo_size.image
            or not os.path.isfile(photo_size.image.path)
            or not photo_size.height
            or not photo_size.width
            or not photo_size.md5):
            issues += 1
            photo_size.delete()

    # Photo Objects
    photos = models.Photo.objects.all()
    for photo in photos:
        # 1. Ensure every photo has metadata
        if not hasattr(photo, 'metadata'):
            issues += 1
            generate_photo_metadata.delay(photo.id)

        # 3. Ensure every photo has sizes
        sizes = models.Size.objects.all()
        photo_sizes = models.PhotoSize.objects.filter(photo=photo)
        if photo_sizes.count() < sizes.count():
            issues += 1
            generate_sizes_for_photo.delay(photo.id)

    # Filesystem
    # 1. Delete stray resized photos
    resized_photos = models.PhotoSize.objects.values_list('image', flat=True)
    delete_files_list = []
    for disk_file in os.listdir(resized_photos_dir):
        rel_path = os.path.join(CONTENT_RESIZED_PHOTOS_PATH, disk_file)
        abs_path = os.path.join(resized_photos_dir, disk_file)
        if rel_path not in resized_photos:
            issues += 1
            delete_files_list.append(abs_path)

    if len(delete_files_list) > 0:
        delete_files.delay(delete_files_list)

    return f"Identified and queued fixes for {issues} issues." if issues > 0 else "No issues found."


@shared_task
def publish_photos():
    return f"{services.publish_photos()} photos published/unpublished."
