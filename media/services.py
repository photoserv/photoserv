from celery import shared_task
from media.models import *
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from PIL.ExifTags import TAGS as ExifTags
from datetime import datetime
import exiftool
import hashlib


# Metadata tag constants
METADATA_EXIF_DATETIME_ORIGINAL = "EXIF:DateTimeOriginal"
METADATA_XMP_RATING = "XMP:Rating"

METADATA_EXIF_MAKE = "EXIF:Make"
METADATA_EXIF_MODEL = "EXIF:Model"
METADATA_COMPOSITE_LENS_ID = "Composite:LensID"

METADATA_EXIF_FOCAL_LENGTH = "EXIF:FocalLength"
METADATA_EXIF_FOCAL_LENGTH_35MM = "Composite:FocalLength35efl"
METADATA_EXIF_APERTURE = "EXIF:FNumber"
METADATA_EXIF_SHUTTER_SPEED = "EXIF:ExposureTime"
METADATA_EXIF_ISO = "EXIF:ISO"

METADATA_EXIF_EXPOSURE_PROGRAM = "EXIF:ExposureProgram"
METADATA_EXIF_EXPOSURE_COMPENSATION = "EXIF:ExposureCompensation"
METADATA_EXIF_FLASH = "EXIF:Flash"

METADATA_EXIF_COPYRIGHT = "EXIF:Copyright"

METADATA_COMPOSITE_LATITUDE = "Composite:GPSLatitude"
METADATA_COMPOSITE_LONGITUDE = "Composite:GPSLongitude"


def gen_size(photo, size):
    photo.raw_image.open()  # ensure file is ready
    with Image.open(photo.raw_image) as img:
        exif_data = img.info.get('exif') # Preserve EXIF data

        # Use updated resampling constant
        img.thumbnail((size.max_dimension, size.max_dimension), Image.Resampling.LANCZOS)

        # Square crop, centered
        if size.square_crop:
            width, height = img.size
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            right = left + min_dim
            bottom = top + min_dim
            img = img.crop((left, top, right, bottom))
            # Resize to exact max_dimension if necessary
            if min_dim != size.max_dimension:
                img = img.resize((size.max_dimension, size.max_dimension), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        if exif_data:
            img.save(buffer, format='JPEG', exif=exif_data)
        else:
            img.save(buffer, format='JPEG')

        photo_size = PhotoSize(photo=photo, size=size, height=img.height, width=img.width, md5=hashlib.md5(buffer.getvalue()).hexdigest())
        photo_size.image.save(
            f"{photo.id}_{size.slug}.jpg",
            ContentFile(buffer.getvalue()),
            save=True
        )

        return f"Sizes generated for photo id {photo.id}."


# Function parse_exif_date. Returns datetime object or None
def parse_exif_date(date_str) -> datetime | None:
    try:
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def parse_numeric(value, cast=float):
    """Convert a value to a numeric type, returning None if conversion fails."""
    if value is None:
        return None
    try:
        return cast(value)
    except (ValueError, TypeError):
        return None


def generate_metadata_for_photo(photo: Photo):
    photo.raw_image.open()  # ensure file is ready
    temp_file_path = photo.raw_image.path

    with exiftool.ExifToolHelper(common_args=["-G"]) as et:
        metadata_list = et.get_metadata(temp_file_path, [
            f"-{METADATA_EXIF_DATETIME_ORIGINAL}",
            f"-{METADATA_XMP_RATING}",
            f"-{METADATA_EXIF_MAKE}",
            f"-{METADATA_EXIF_MODEL}",
            f"-{METADATA_COMPOSITE_LENS_ID}",
            f"-{METADATA_EXIF_FOCAL_LENGTH}#",
            f"-{METADATA_EXIF_FOCAL_LENGTH_35MM}#",
            f"-{METADATA_EXIF_APERTURE}#",
            f"-{METADATA_EXIF_SHUTTER_SPEED}#",
            f"-{METADATA_EXIF_ISO}#",
            f"-{METADATA_EXIF_EXPOSURE_PROGRAM}",
            f"-{METADATA_EXIF_EXPOSURE_COMPENSATION}#",
            f"-{METADATA_EXIF_FLASH}",
            f"-{METADATA_EXIF_COPYRIGHT}",
            f"-{METADATA_COMPOSITE_LATITUDE}#",
            f"-{METADATA_COMPOSITE_LONGITUDE}#",
        ])
        if not metadata_list:
            return f"No metadata found for photo id {photo.id}."

        # Roll all dicts into one (later dicts overwrite earlier ones)
        metadata_dict = {}
        for d in metadata_list:
            metadata_dict.update(d)

        metadata, created = models.PhotoMetadata.objects.get_or_create(photo=photo)

        # Extract relevant metadata
        metadata.capture_date = parse_exif_date(metadata_dict.get(METADATA_EXIF_DATETIME_ORIGINAL))
        metadata.rating = parse_numeric(metadata_dict.get(METADATA_XMP_RATING), cast=int)

        metadata.camera_make = metadata_dict.get(METADATA_EXIF_MAKE)
        metadata.camera_model = metadata_dict.get(METADATA_EXIF_MODEL)
        metadata.lens_model = metadata_dict.get(METADATA_COMPOSITE_LENS_ID)

        metadata.focal_length = parse_numeric(metadata_dict.get(METADATA_EXIF_FOCAL_LENGTH))
        metadata.focal_length_35mm = parse_numeric(metadata_dict.get(METADATA_EXIF_FOCAL_LENGTH_35MM))
        metadata.aperture = parse_numeric(metadata_dict.get(METADATA_EXIF_APERTURE))
        metadata.shutter_speed = parse_numeric(metadata_dict.get(METADATA_EXIF_SHUTTER_SPEED))
        metadata.iso = parse_numeric(metadata_dict.get(METADATA_EXIF_ISO), cast=int)

        metadata.exposure_program = metadata_dict.get(METADATA_EXIF_EXPOSURE_PROGRAM)
        metadata.exposure_compensation = parse_numeric(metadata_dict.get(METADATA_EXIF_EXPOSURE_COMPENSATION))
        metadata.flash = metadata_dict.get(METADATA_EXIF_FLASH)

        metadata.copyright = metadata_dict.get(METADATA_EXIF_COPYRIGHT)

        metadata.raw_latitude = parse_numeric(metadata_dict.get(METADATA_COMPOSITE_LATITUDE))
        metadata.raw_longitude = parse_numeric(metadata_dict.get(METADATA_COMPOSITE_LONGITUDE))

        metadata.save()

        # If the photo's lat/long is null, update it from metadata
        if photo.latitude is None or photo.longitude is None:
            if metadata.raw_latitude is not None and metadata.raw_longitude is not None:
                photo.latitude = metadata.raw_latitude
                photo.longitude = metadata.raw_longitude
                photo.save(update_fields=['latitude', 'longitude'])


def publish_photos() -> int:
    chg = 0
    for channel_photo in ChannelPhoto.objects.all():
        if channel_photo.update_published():
            chg += 1
        channel_photo.save()

    return chg
