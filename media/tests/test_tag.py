from django.test import TestCase
from django.core.exceptions import ValidationError
from media.models import *
from media.views import TagUpdateView
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse


class TagTests(TestCase):
    def setUp(self):
        self.tag = Tag.objects.create(name="nature")

    def test_str_returns_name(self):
        self.assertEqual(str(self.tag), "nature")

    def test_get_absolute_url(self):
        url = self.tag.get_absolute_url()
        self.assertIn(str(self.tag.pk), url)

    def test_clean_rejects_invalid_characters(self):
        t = Tag(name="bad;tag")
        with self.assertRaises(ValidationError):
            t.clean()

    def test_name_is_normalized_on_save(self):
        t = Tag.objects.create(name="  Nature  ")
        self.assertEqual(t.name, "nature")

    def test_merging_tags_moves_photo_tags(self):
        photo = Photo.objects.create(title="P", raw_image="r.jpg")
        t1 = Tag.objects.create(name="tree")
        t2 = Tag.objects.create(name="forest")
        PhotoTag.objects.create(photo=photo, tag=t1)

        # Rename t1 -> "forest", should merge into t2
        t1.name = "forest"
        merged = t1.save()
        self.assertEqual(PhotoTag.objects.filter(photo=photo, tag=t2).count(), 1)
        self.assertFalse(Tag.objects.filter(pk=t1.pk).exists())


class PhotoTagTests(TestCase):
    def test_str_returns_tag_name(self):
        photo = Photo.objects.create(title="T", raw_image="r.jpg")
        tag = Tag.objects.create(name="taggy")
        pt = PhotoTag.objects.create(photo=photo, tag=tag)
        self.assertEqual(str(pt), "taggy")

    def test_unique_constraint(self):
        photo = Photo.objects.create(title="T", raw_image="r.jpg")
        tag = Tag.objects.create(name="uniq")
        PhotoTag.objects.create(photo=photo, tag=tag)
        with self.assertRaises(Exception):
            PhotoTag.objects.create(photo=photo, tag=tag)
    
    def test_renaming_tag2_to_tag1_then_get_url_points_to_tag_list(self):
        photo = Photo.objects.create(title="P", raw_image="r.jpg")
        tag1 = Tag.objects.create(name="tag1")
        tag2 = Tag.objects.create(name="tag2")

        PhotoTag.objects.create(photo=photo, tag=tag1)
        PhotoTag.objects.create(photo=photo, tag=tag2)

        # Rename tag2 to tag1 — triggers merge (tag2 will be deleted)
        tag2.name = "tag1"
        tag2.save()

        # After merge, tag2 should be gone
        with self.assertRaises(ObjectDoesNotExist):
            Tag.objects.get(pk=tag2.pk)

        # Simulate the view's get_success_url() behavior
        # If the tag was merged and deleted, we should be redirected to tag-list
        view = TagUpdateView()
        view.object = tag2  # mimic what the view would have before deletion
        url = view.get_success_url()

        expected = reverse("tag-list")
        self.assertEqual(url, expected)