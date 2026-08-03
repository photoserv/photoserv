from django.test import TestCase
from media.models import *


class CommonEntityTests(TestCase):
    def test_created_at_and_updated_at(self):
        album = Album.objects.create(title="Album", description="desc")
        self.assertIsNotNone(album.created_at)
        self.assertIsNotNone(album.updated_at)

        old_updated_at = album.updated_at
        album.title = "New Title"
        album.save()
        self.assertGreater(album.updated_at, old_updated_at)
    
    def test_uuid_field_exists(self):
        photo_meta = PhotoMetadata.objects.create(photo=Photo.objects.create(title="P", raw_image="r.jpg"))
        self.assertIsNotNone(photo_meta.uuid)