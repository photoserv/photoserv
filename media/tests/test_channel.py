from unittest import mock
from django.test import TestCase
from media.models import *
from datetime import timedelta


class ChannelTests(TestCase):
    def setUp(self):
        self.channel: Channel = Channel.objects.create(
            name = "B"
        )
        self.default_channel: Channel = Channel.objects.get(builtin=True)
        self.photo: Photo = Photo.objects.create(
            title="Test Photo",
            description="A test photo",
            raw_image="test.jpg",
            canonical_publish_date = timezone.now()
        )
        self.default_channel.add_photo(self.photo)

    def test_add_photo_unpublished_by_default(self):
        self.channel.add_photo(self.photo)
        self.assertFalse(self.photo.is_published(self.channel))
        self.assertEqual(self.channel.photos.all()[0].photo.canonical_publish_date, self.photo.channels.all()[0].publish_date)

    def test_no_publish_when_unhealthy(self):
        self.channel.add_photo(self.photo)

        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_published.send") as mock_publish:
            channel_photo.update_published()

            self.assertFalse(channel_photo.published)
            mock_publish.assert_not_called()

    def test_publish_when_healthy(self):
        self.channel.add_photo(self.photo)

        # Add metadata
        PhotoMetadata.objects.create(photo=self.photo, camera_make="Canon")

        # Add all sizes
        for size in Size.objects.all():
            PhotoSize.objects.create(
                photo=self.photo,
                size=size,
                image=f"{size.slug}.jpg",
            )

        self.photo.refresh_from_db()

        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_published.send") as mock_publish:
            channel_photo.update_published()
            channel_photo.save()

            self.assertTrue(channel_photo.published)
            mock_publish.assert_called_once()
    
    def broken_published_photo_not_revoked(self):
        PhotoMetadata.objects.all().delete()

        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            channel_photo.update_published()
            channel_photo.save()

            self.assertTrue(channel_photo.published)
            mock_publish.assert_not_called()
    
    def move_publish_date_unpublished(self):
        channel_photo = self.channel.photos.first()
        channel_photo.publish_date = timezone.now() + timedelta(days=365)
        channel_photo.save()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            channel_photo.update_published()

            self.assertFalse(channel_photo.published)
            mock_publish.assert_called_once()

        channel_photo.publish_date = timezone.now() - timedelta(days=365)
        channel_photo.update_published()
        channel_photo.save()
    
    def delete_channel_unpublish(self):
        channel_photo = self.channel.photos.first()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            self.channel.delete()
            mock_publish.assert_called_once()
        
        self.assertFalse(ChannelPhoto.objects.filter(pk=self.channel.pk).exists())
    
    def delete_photo_unpublish(self):
        channel_photo = self.default_channel.photos.first()

        with mock.patch("media.signals.channel_photo_unpublished.send") as mock_publish:
            self.photo.delete()
            mock_publish.assert_called_once()
        
        self.assertFalse(ChannelPhoto.objects.filter(pk=self.channel.pk).exists())
