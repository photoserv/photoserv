from django.test import TestCase
from django.utils import timezone

from media.forms import PhotoChannelForm
from media.models import Channel, ChannelPhoto, Photo


class PhotoChannelFormTests(TestCase):
    def setUp(self):
        self.included = Channel.objects.create(name='Included', include_new_photos=True)
        self.excluded = Channel.objects.create(name='Excluded', include_new_photos=False)
        self.photo = Photo.objects.create(title='Photo', raw_image='photo.jpg')
        self.publish_date = timezone.now().replace(second=0, microsecond=0)

    def data(self, **overrides):
        values = {
            PhotoChannelForm.publish_field_name(self.included): 'on',
            PhotoChannelForm.date_field_name(self.included): self.publish_date.strftime('%Y-%m-%dT%H:%M'),
            PhotoChannelForm.date_field_name(self.excluded): self.publish_date.strftime('%Y-%m-%dT%H:%M'),
        }
        values.update(overrides)
        return values

    def test_defaults_to_channel_include_new_photos_and_photo_publish_date(self):
        form = PhotoChannelForm(photo_instance=self.photo)

        self.assertTrue(form[PhotoChannelForm.publish_field_name(self.included)].value())
        self.assertFalse(form[PhotoChannelForm.publish_field_name(self.excluded)].value())
        self.assertEqual(
            form[PhotoChannelForm.date_field_name(self.included)].value(),
            self.photo.canonical_publish_date.strftime('%Y-%m-%dT%H:%M'),
        )

    def test_existing_photo_defaults_to_existing_channel_photos(self):
        ChannelPhoto.objects.create(
            channel=self.excluded,
            photo=self.photo,
            publish_date=self.publish_date,
        )

        form = PhotoChannelForm(photo_instance=self.photo)

        self.assertFalse(form[PhotoChannelForm.publish_field_name(self.included)].value())
        self.assertTrue(form[PhotoChannelForm.publish_field_name(self.excluded)].value())

    def test_save_creates_and_updates_selected_channel_photo(self):
        form = PhotoChannelForm(self.data(), photo_instance=self.photo)
        self.assertTrue(form.is_valid(), form.errors)
        form.save(self.photo)
        channel_photo = ChannelPhoto.objects.get(channel=self.included, photo=self.photo)
        self.assertEqual(channel_photo.publish_date.strftime('%Y-%m-%dT%H:%M'), self.publish_date.strftime('%Y-%m-%dT%H:%M'))

        changed_date = self.publish_date + timezone.timedelta(days=1)
        form = PhotoChannelForm(self.data(**{
            PhotoChannelForm.date_field_name(self.included): changed_date.strftime('%Y-%m-%dT%H:%M'),
        }), photo_instance=self.photo)
        self.assertTrue(form.is_valid(), form.errors)
        form.save(self.photo)
        self.assertEqual(ChannelPhoto.objects.filter(channel=self.included, photo=self.photo).count(), 1)
        self.assertEqual(
            ChannelPhoto.objects.get(channel=self.included, photo=self.photo).publish_date.strftime('%Y-%m-%dT%H:%M'),
            changed_date.strftime('%Y-%m-%dT%H:%M'),
        )

    def test_save_deletes_unchecked_channel_photo(self):
        ChannelPhoto.objects.create(channel=self.included, photo=self.photo, publish_date=self.publish_date)
        form = PhotoChannelForm(self.data(**{
            PhotoChannelForm.publish_field_name(self.included): '',
        }), photo_instance=self.photo)
        self.assertTrue(form.is_valid(), form.errors)
        form.save(self.photo)
        self.assertFalse(ChannelPhoto.objects.filter(channel=self.included, photo=self.photo).exists())
