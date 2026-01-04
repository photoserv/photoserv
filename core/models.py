from django.db import models
import os
import uuid
from django.urls import reverse
from django.utils.text import slugify
from . import CONTENT_RAW_PHOTOS_PATH, CONTENT_RESIZED_PHOTOS_PATH
from . import tasks
from django.core.exceptions import ValidationError
from django.utils import timezone
from .signals import photo_published, photo_unpublished


class PublicEntity(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # auto_now=True already handles updated_at automatically on each save
        # No need to manually update and save again
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class Photo(PublicEntity):
    def get_image_file_path(instance, filename):
        ext = os.path.splitext(filename)[1]
        random_str = uuid.uuid4().hex[:8]
        kebab_title = slugify(instance.title)
        new_filename = f"{random_str}-{kebab_title}{ext}"
        return os.path.join(CONTENT_RAW_PHOTOS_PATH, new_filename)

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(max_length=4096, default="", blank=True)
    raw_image = models.ImageField(upload_to=get_image_file_path)
    publish_date = models.DateTimeField(default=timezone.now, blank=True, null=False)
    hidden = models.BooleanField(default=False, help_text="Hide from public API")
    _published = models.BooleanField(default=False, db_column="published")

    tags = models.ManyToManyField(
        "Tag",
        through="PhotoTag",
        related_name="photos"
    )

    @property
    def published(self):
        return self._published

    @property
    def health(self) -> "PhotoHealth":
        all_sizes = all(self.sizes.filter(size=size).exists() for size in Size.objects.all())
        metadata = PhotoMetadata.objects.filter(photo=self).exists()
        return PhotoHealth(all_sizes=all_sizes, metadata=metadata)

    def calculate_slug(self) -> str:
        slug = f"{timezone.now().strftime('%Y-%m-%d')}-{slugify(self.title)}"
        return slug[:self._meta.get_field('slug').max_length]
    
    def calculate_published(self) -> bool:
        return not self.hidden and bool(self.publish_date and self.publish_date <= timezone.now())
    
    def update_published(self, update_model: bool = False, dispatch_signals: bool = False) -> bool:
        old = self._published
        new = self.calculate_published()
        changed = new != old
        self._published = new

        if changed and dispatch_signals:
            if new:
                photo_published.send(Photo, instance=self, uuid=self.uuid)
            else:
                photo_unpublished.send(Photo, instance=self, uuid=self.uuid)
        
        if changed and update_model:
            self.save()

        return changed

    def get_absolute_url(self):
        return reverse("photo-detail", kwargs={"pk": self.pk})

    def get_size(self, size: str):
        return self.sizes.filter(size__slug=size).first()
    
    def clean(self):
        # Calculate the slug if not already set
        slug_to_check = self.slug or self.calculate_slug()

        # Check if the slug exists for a different object
        if Photo.objects.filter(slug=slug_to_check).exclude(pk=self.pk).exists():
            raise ValidationError(f"A photo with the slug '{slug_to_check}' already exists.")
    
    # After saving a new photo, trigger the task to generate sizes
    def save(self, schedule_followup_tasks: bool = False, *args, **kwargs):
        if not self.slug:
            self.slug = self.calculate_slug()
        is_new = self.pk is None

        if not is_new:
            # Recalculate published status on updates
            self.update_published(dispatch_signals=True)
        super().save(*args, **kwargs)

        if schedule_followup_tasks and is_new:
            # Generate other sizes via Celery task
            tasks.post_photo_create.delay_on_commit(self.id)
    
    def assign_albums(self, albums):
        # Remove unselected
        PhotoInAlbum.objects.filter(photo=self).exclude(album__in=albums).delete()

        for album in albums:
            if not PhotoInAlbum.objects.filter(photo=self, album=album).exists():
                last_order = (
                    PhotoInAlbum.objects.filter(album=album)
                    .aggregate(max_order=models.Max('order'))['max_order']
                )
                next_order = (last_order or 0) + 1
                PhotoInAlbum.objects.create(photo=self, album=album, order=next_order)
    
    def delete(self, *args, **kwargs):
        # Delete all sizes associated with this photo
        size_files = [s.image.path for s in self.sizes.all() if s.image]
        if self.raw_image:
            size_files.append(self.raw_image.path)

        if size_files:
            tasks.delete_files.delay_on_commit(size_files)

        if self._published:
            photo_unpublished.send(Photo, instance=self, uuid=self.uuid)

        super().delete(*args, **kwargs)

    def __str__(self):
        return self.title


class PhotoHealth:
    def __init__(self, all_sizes: bool, metadata: bool):
        self.all_sizes = all_sizes
        self.metadata = metadata


class PhotoMetadata(PublicEntity):
    photo = models.OneToOneField(Photo, on_delete=models.CASCADE, related_name="metadata", unique=True)

    capture_date = models.DateTimeField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)


    camera_make = models.CharField(max_length=255, null=True, blank=True)
    camera_model = models.CharField(max_length=255, null=True, blank=True)
    lens_model = models.CharField(max_length=255, null=True, blank=True)

    focal_length = models.FloatField(null=True, blank=True)
    focal_length_35mm = models.FloatField(null=True, blank=True)
    aperture = models.FloatField(null=True, blank=True)
    shutter_speed = models.FloatField(null=True, blank=True)
    iso = models.PositiveIntegerField(null=True, blank=True)

    exposure_program = models.CharField(max_length=255, null=True, blank=True)
    exposure_compensation = models.FloatField(null=True, blank=True)
    flash = models.CharField(max_length=255, null=True, blank=True)

    copyright = models.CharField(max_length=512, null=True, blank=True)

    def __str__(self):
        return f"Metadata for {str(self.photo)}"


class Tag(PublicEntity):
    name = models.CharField(max_length=128)

    class Meta:
        ordering = ["name"]
    
    def clean(self):
        # Disallow semicolons or newlines in tag names
        if ";" in self.name or "\n" in self.name:
            raise ValidationError("Tag names cannot contain semicolons or newlines.")
        
        return super().clean()
    
    def save(self, *args, **kwargs):
        self.name = self.name.strip().lower()  # Normalize tag name
        # Are we renaming (object already exists)?
        if self.pk:
            old = Tag.objects.get(pk=self.pk)
            if old.name != self.name:
                # Case: renaming to an existing tag -> merge
                try:
                    existing = Tag.objects.get(name=self.name)
                except Tag.DoesNotExist:
                    # unique -> just rename
                    return super().save(*args, **kwargs)

                # merge: move photos over
                for pt in PhotoTag.objects.filter(tag=old):
                    # avoid duplicates
                    if not PhotoTag.objects.filter(photo=pt.photo, tag=existing).exists():
                        pt.tag = existing
                        pt.save()
                    else:
                        pt.delete()

                # finally, delete the old tag
                old.delete()
                return existing.save(*args, **kwargs)
        # Normal creation or no name change
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("tag-detail", kwargs={"pk": self.pk})


class PhotoTag(models.Model):
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("photo", "tag")
        ordering = ["tag__name"]

    def __str__(self):
        return str(self.tag)


class Album(PublicEntity):
    class DefaultSortMethod(models.TextChoices):
        CREATED = "CREATED", "Photo Created Date (Exif)"
        PUBLISHED = "PUBLISHED", "Publish Date"
        MANUAL = "MANUAL", "Manual"
        RANDOM = "RANDOM", "Random"

    title = models.CharField(max_length=255, unique=True)
    short_description = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(max_length=4096, blank=True, default="")
    slug = models.SlugField(max_length=255, unique=True)
    sort_method = models.CharField(
        max_length=10,
        choices=DefaultSortMethod.choices,
        default=DefaultSortMethod.PUBLISHED
    )
    sort_descending = models.BooleanField(default=False)
    _photos = models.ManyToManyField(
        "Photo",
        through="PhotoInAlbum",
        related_name="albums",
        verbose_name="Photos"
    )
    parent = models.ForeignKey("Album", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")

    def get_ordered_photos(self, public_only: bool = False):
        qs = self._photos.all()

        if public_only:
            qs = qs.filter(_published=True)

        if self.sort_method == self.DefaultSortMethod.MANUAL:
            # Do not apply ascending/descending for manual sort
            return qs.order_by("photoinalbum__order")
        elif self.sort_method == self.DefaultSortMethod.CREATED:
            order_by = "metadata__capture_date"
        elif self.sort_method == self.DefaultSortMethod.PUBLISHED:
            order_by = "publish_date"
        elif self.sort_method == self.DefaultSortMethod.RANDOM:
            return qs.order_by("?")  # random order, no need for sort_descending
        else:
            order_by = "photoinalbum__order"

        if self.sort_descending:
            order_by = f'-{order_by}'

        return qs.order_by(order_by)
    
    def calculate_slug(self) -> str:
        return slugify(f"{self.title}")[:255]
    
    def clean(self):
        # Calculate the slug if not already set
        slug_to_check = self.slug or self.calculate_slug()

        # Check if the slug exists for a different object
        if Album.objects.filter(slug=slug_to_check).exclude(pk=self.pk).exists():
            raise ValidationError(f"An album with the slug '{slug_to_check}' already exists.")
        
        # Ensure parent does not create a cyclic relationship
        if self.parent:
            ancestor = self.parent
            while ancestor:
                if ancestor == self:
                    raise ValidationError("An album cannot be its own ancestor.")
                ancestor = ancestor.parent
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.calculate_slug()
        if not self.short_description and self.description:
            if len(self.description) > 100:
                self.short_description = self.description[:97] + "..."
            else:
                self.short_description = self.description
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse("album-detail", kwargs={"pk": self.pk})


class PhotoInAlbum(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        unique_together = ("album", "photo")
        ordering = ["order"]
    
    def __str__(self):
        return f"{self.album.title} -> {self.photo.title}"


class Size(PublicEntity):
    slug = models.CharField(max_length=32, unique=True)
    comment = models.CharField(max_length=255, blank=True, null=True)
    max_dimension = models.PositiveIntegerField()
    square_crop = models.BooleanField(default=False)
    builtin = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)
    public = models.BooleanField(default=True, help_text="Allow in the public API?")

    def clean(self):
        # Prevent modifications to builtin sizes
        if not self.can_edit:
            raise ValidationError("Cannot modify this size.")
        # Don't allow changes to slug or comment if it's a builtin size
        if self.pk is not None:
            orig = Size.objects.get(pk=self.pk)
            if self.builtin and (self.slug != orig.slug or self.comment != orig.comment):
                raise ValidationError("Cannot change the slug or comment of a builtin size.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        file_paths = list(self.photos.values_list("image", flat=True))
        self.photos.all().delete()

        if file_paths:
            tasks.delete_files.delay_on_commit(file_paths)

        # Trigger task to regenerate photos for this size after DB commit
        tasks.generate_photo_sizes_for_size.delay_on_commit(self.id)

    # Disallow deleting a builtin size
    def delete(self, *args, **kwargs):
        if self.builtin or not self.can_edit:
            raise ValidationError("Cannot delete a builtin size.")
        
        file_paths = list(self.photos.values_list("image", flat=True))
        self.photos.all().delete()

        if file_paths:
            tasks.delete_files.delay_on_commit(file_paths)

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.slug} ({self.max_dimension}px)"
    
    class Meta:
        ordering = ["max_dimension"]


class PhotoSize(models.Model):
    def get_image_file_path(instance, filename):
        ext = os.path.splitext(filename)[1]
        random_str = uuid.uuid4().hex[:16]
        kebab_title = slugify(instance.photo.title)
        new_filename = f"{random_str}-{kebab_title}_{instance.size.slug}{ext}"
        return os.path.join(CONTENT_RESIZED_PHOTOS_PATH, new_filename)

    photo = models.ForeignKey("core.Photo", on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=get_image_file_path)
    height = models.PositiveIntegerField(null=True)
    width = models.PositiveIntegerField(null=True)
    md5 = models.CharField(max_length=32, null=True)

    class Meta:
        unique_together = ("photo", "size")
        ordering = ["size__max_dimension"]

    def __str__(self):
        return f"{self.photo.title} - {self.size.slug}"
