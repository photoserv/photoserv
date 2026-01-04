from unittest import mock, skipIf
from django.test import TestCase
from django.core.exceptions import ValidationError
from .models import *
from .views import TagUpdateView
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from django.apps import apps
from django.conf import settings


class PhotoModelTests(TestCase):
    def setUp(self):
        self.photo = Photo.objects.create(
            title="Test Photo",
            description="A test photo",
            raw_image="test.jpg",
        )

    def test_str_returns_title(self):
        self.assertEqual(str(self.photo), "Test Photo")

    def test_get_absolute_url(self):
        url = self.photo.get_absolute_url()
        self.assertIn(str(self.photo.pk), url)

    @mock.patch("core.tasks.post_photo_create.delay_on_commit")
    def test_save_triggers_tasks_on_create(self, mock_post_photo_create):
        p = Photo(title="Another", raw_image="raw.jpg")
        p.save(schedule_followup_tasks=True)

        self.assertTrue(mock_post_photo_create.called)

    @mock.patch("core.tasks.delete_files.delay_on_commit")
    def test_delete_triggers_delete_files(self, mock_delete):
        self.photo.delete()
        self.assertTrue(mock_delete.called)

    def test_assign_albums_adds_and_removes(self):
        album1 = Album.objects.create(title="Album1", description="d")
        album2 = Album.objects.create(title="Album2", description="d")

        # assign album1
        self.photo.assign_albums([album1])
        self.assertTrue(PhotoInAlbum.objects.filter(photo=self.photo, album=album1).exists())

        # replace with album2
        self.photo.assign_albums([album2])
        self.assertFalse(PhotoInAlbum.objects.filter(photo=self.photo, album=album1).exists())
        self.assertTrue(PhotoInAlbum.objects.filter(photo=self.photo, album=album2).exists())
    
    def test_photo_health(self):
        # Initially, photo.health.* is false
        self.assertFalse(self.photo.health.metadata)
        self.assertFalse(self.photo.health.all_sizes)

        # Add metadata
        PhotoMetadata.objects.create(photo=self.photo, camera_make="Canon")
        self.photo.refresh_from_db()
        self.assertTrue(self.photo.health.metadata)
        self.assertFalse(self.photo.health.all_sizes)

        # Add sizes
        for size in Size.objects.all():
            PhotoSize.objects.create(photo=self.photo, size=size, image=f"{size.slug}.jpg")
        self.photo.refresh_from_db()
        self.assertTrue(self.photo.health.metadata)
        self.assertTrue(self.photo.health.all_sizes)


class PhotoFormTests(TestCase):
    @mock.patch("core.tasks.post_photo_create.delay_on_commit")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    @mock.patch("PIL.Image.open")
    def test_new_photo_schedules_post_photo_create(self, mock_image_open, mock_storage_save, mock_post_photo_create):
        """Ensure for a new photo, post_photo_create is scheduled"""
        from .forms import PhotoForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Mock PIL Image.open to avoid actual image validation
        mock_image_open.return_value.verify.return_value = None
        mock_image_open.return_value.size = (100, 100)
        mock_image_open.return_value.format = 'JPEG'
        
        # Mock storage save to avoid actual file operations
        mock_storage_save.return_value = 'test_image.jpg'
        
        image_file = SimpleUploadedFile(
            name='test_image.jpg',
            content=b'fake image content',
            content_type='image/jpeg'
        )
        
        form_data = {
            'title': 'New Photo',
            'description': 'A new test photo',
            'slug': 'new-photo',
            'hidden': False,
        }
        
        form = PhotoForm(data=form_data, files={'raw_image': image_file})
        self.assertTrue(form.is_valid(), form.errors)
        
        photo = form.save(commit=True)
        
        # Verify post_photo_create was called with the photo's id
        mock_post_photo_create.assert_called_once_with(photo.id)
    
    @mock.patch("core.tasks.post_photo_create.delay_on_commit")
    def test_existing_photo_does_not_schedule_post_photo_create(self, mock_post_photo_create):
        """Ensure for an existing photo, post_photo_create is not called"""
        from .forms import PhotoForm
        
        # Create an existing photo
        photo = Photo.objects.create(
            title="Existing Photo",
            raw_image="existing.jpg"
        )
        
        # Update the photo through the form
        form_data = {
            'title': 'Updated Photo Title',
            'description': 'Updated description',
            'slug': photo.slug,
            'hidden': False,
        }
        
        form = PhotoForm(data=form_data, instance=photo)
        self.assertTrue(form.is_valid(), form.errors)
        
        form.save(commit=True)
        
        # Verify post_photo_create was NOT called
        mock_post_photo_create.assert_not_called()
    
    @mock.patch.object(Photo, 'update_published')
    def test_existing_photo_calls_update_published_correctly(self, mock_update_published):
        """For an existing photo, photo.update_published is called with dispatch_signals=True and update_model=False"""
        from .forms import PhotoForm
        
        # Create an existing photo
        photo = Photo.objects.create(
            title="Existing Photo",
            raw_image="existing.jpg"
        )
        
        # Reset the mock to clear any calls from photo creation
        mock_update_published.reset_mock()
        
        # Update the photo through the form
        form_data = {
            'title': 'Updated Photo Title',
            'description': 'Updated description',
            'slug': photo.slug,
            'hidden': True,  # Change hidden status to trigger update
        }
        
        form = PhotoForm(data=form_data, instance=photo)
        self.assertTrue(form.is_valid(), form.errors)
        
        form.save(commit=True)
        
        # Verify update_published was called with correct arguments
        # Note: update_published is called during Photo.save() when is_new=False
        mock_update_published.assert_called_with(dispatch_signals=True)


class PhotoSlugTests(TestCase):
    def test_photo_created_without_slug(self):
        # Create a photo without specifying a slug
        photo = Photo.objects.create(title="Photo Without Slug", raw_image="image.jpg")
        self.assertIsNotNone(photo.slug)
        self.assertTrue(photo.slug)

    def test_photo_can_be_updated(self):
        # Create and update a photo
        photo = Photo.objects.create(title="Initial Title", raw_image="image.jpg")
        photo.title = "Updated Title"
        photo.save()
        self.assertEqual(photo.title, "Updated Title")

    def test_photo_created_with_specific_slug(self):
        # Create a photo with a specific slug
        photo = Photo.objects.create(title="Photo With Slug", raw_image="image.jpg", slug="custom-slug")
        self.assertEqual(photo.slug, "custom-slug")

    def test_duplicate_slug_raises_validation_error(self):
        # Create a photo with a specific slug
        Photo.objects.create(title="First Photo", raw_image="image1.jpg", slug="duplicate-slug")
        
        # Attempt to create another photo with the same slug
        with self.assertRaises(ValidationError):
            photo = Photo(title="Second Photo", raw_image="image2.jpg", slug="duplicate-slug")
            photo.full_clean()  # Trigger validation


class PhotoMetadataTests(TestCase):
    def test_str_includes_photo(self):
        photo = Photo.objects.create(title="MetaPhoto", raw_image="raw.jpg")
        metadata = PhotoMetadata.objects.create(photo=photo, camera_make="Canon")
        self.assertIn("MetaPhoto", str(metadata))


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


class AlbumTests(TestCase):
    def setUp(self):
        self.album = Album.objects.create(title="Holiday", description="Trip")

    def test_str_returns_title(self):
        self.assertEqual(str(self.album), "Holiday")

    def test_get_absolute_url(self):
        url = self.album.get_absolute_url()
        self.assertIn(str(self.album.pk), url)

    def test_get_ordered_photos_manual_order(self):
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg")
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg")
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=1)

        self.album.sort_method = Album.DefaultSortMethod.MANUAL
        ordered = list(self.album.get_ordered_photos())
        self.assertEqual(ordered[0], photo2)
    
    def test_get_ordered_photos_published_ascending(self):
        """Test that photos are sorted by publish_date in ascending order"""
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg", publish_date=timezone.now() - timezone.timedelta(days=2))
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg", publish_date=timezone.now() - timezone.timedelta(days=1))
        photo3 = Photo.objects.create(title="P3", raw_image="3.jpg", publish_date=timezone.now())
        
        PhotoInAlbum.objects.create(album=self.album, photo=photo3, order=1)
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=3)

        self.album.sort_method = Album.DefaultSortMethod.PUBLISHED
        self.album.sort_descending = False
        ordered = list(self.album.get_ordered_photos())
        
        self.assertEqual(len(ordered), 3)
        self.assertEqual(ordered[0], photo1)  # oldest first
        self.assertEqual(ordered[1], photo2)
        self.assertEqual(ordered[2], photo3)  # newest last
    
    def test_get_ordered_photos_published_descending(self):
        """Test that photos are sorted by publish_date in descending order"""
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg", publish_date=timezone.now() - timezone.timedelta(days=2))
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg", publish_date=timezone.now() - timezone.timedelta(days=1))
        photo3 = Photo.objects.create(title="P3", raw_image="3.jpg", publish_date=timezone.now())
        
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=1)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo3, order=3)

        self.album.sort_method = Album.DefaultSortMethod.PUBLISHED
        self.album.sort_descending = True
        ordered = list(self.album.get_ordered_photos())
        
        self.assertEqual(len(ordered), 3)
        self.assertEqual(ordered[0], photo3)  # newest first
        self.assertEqual(ordered[1], photo2)
        self.assertEqual(ordered[2], photo1)  # oldest last
    
    def test_get_ordered_photos_created_ascending(self):
        """Test that photos are sorted by capture_date (metadata) in ascending order"""
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg")
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg")
        photo3 = Photo.objects.create(title="P3", raw_image="3.jpg")
        
        PhotoMetadata.objects.create(photo=photo1, capture_date=timezone.now() - timezone.timedelta(days=10))
        PhotoMetadata.objects.create(photo=photo2, capture_date=timezone.now() - timezone.timedelta(days=5))
        PhotoMetadata.objects.create(photo=photo3, capture_date=timezone.now())
        
        PhotoInAlbum.objects.create(album=self.album, photo=photo3, order=1)
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=3)

        self.album.sort_method = Album.DefaultSortMethod.CREATED
        self.album.sort_descending = False
        ordered = list(self.album.get_ordered_photos())
        
        self.assertEqual(len(ordered), 3)
        self.assertEqual(ordered[0], photo1)  # oldest capture date first
        self.assertEqual(ordered[1], photo2)
        self.assertEqual(ordered[2], photo3)  # newest capture date last
    
    def test_get_ordered_photos_created_descending(self):
        """Test that photos are sorted by capture_date (metadata) in descending order"""
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg")
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg")
        photo3 = Photo.objects.create(title="P3", raw_image="3.jpg")
        
        PhotoMetadata.objects.create(photo=photo1, capture_date=timezone.now() - timezone.timedelta(days=10))
        PhotoMetadata.objects.create(photo=photo2, capture_date=timezone.now() - timezone.timedelta(days=5))
        PhotoMetadata.objects.create(photo=photo3, capture_date=timezone.now())
        
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=1)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo3, order=3)

        self.album.sort_method = Album.DefaultSortMethod.CREATED
        self.album.sort_descending = True
        ordered = list(self.album.get_ordered_photos())
        
        self.assertEqual(len(ordered), 3)
        self.assertEqual(ordered[0], photo3)  # newest capture date first
        self.assertEqual(ordered[1], photo2)
        self.assertEqual(ordered[2], photo1)  # oldest capture date last
    
    def test_manual_order_ignores_sort_descending(self):
        """Test that manual ordering is not affected by sort_descending setting"""
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg")
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg")
        photo3 = Photo.objects.create(title="P3", raw_image="3.jpg")
        
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=1)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo3, order=3)

        self.album.sort_method = Album.DefaultSortMethod.MANUAL
        
        # Test with sort_descending = False
        self.album.sort_descending = False
        ordered = list(self.album.get_ordered_photos())
        self.assertEqual(ordered[0], photo1)
        self.assertEqual(ordered[1], photo2)
        self.assertEqual(ordered[2], photo3)
        
        # Test with sort_descending = True (should produce same order)
        self.album.sort_descending = True
        ordered = list(self.album.get_ordered_photos())
        self.assertEqual(ordered[0], photo1)
        self.assertEqual(ordered[1], photo2)
        self.assertEqual(ordered[2], photo3)
    
    def test_album_parents(self):
        parent = Album.objects.create(title="Parent", description="Parent album")
        child = Album.objects.create(title="Child", description="Child album", parent=parent)
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

        # Test cyclic relationship prevention
        with self.assertRaises(ValidationError):
            parent.parent = child
            parent.full_clean()


class AlbumSlugTests(TestCase):
    def test_album_created_without_slug(self):
        # Create an album without specifying a slug
        album = Album.objects.create(title="Album Without Slug", description="A test album")
        self.assertIsNotNone(album.slug)
        self.assertTrue(album.slug)

    def test_album_can_be_updated(self):
        # Create and update an album
        album = Album.objects.create(title="Initial Title", description="A test album")
        album.title = "Updated Title"
        album.save()
        self.assertEqual(album.title, "Updated Title")

    def test_album_created_with_specific_slug(self):
        # Create an album with a specific slug
        album = Album.objects.create(title="Album With Slug", description="A test album", slug="custom-slug")
        self.assertEqual(album.slug, "custom-slug")

    def test_duplicate_slug_raises_validation_error(self):
        # Create an album with a specific slug
        Album.objects.create(title="First Album", description="A test album", slug="duplicate-slug")
        
        # Attempt to create another album with the same slug
        with self.assertRaises(ValidationError):
            album = Album(title="Second Album", description="Another test album", slug="duplicate-slug")
            album.full_clean()  # Trigger validation


class PhotoInAlbumTests(TestCase):
    def test_str_shows_album_and_photo(self):
        album = Album.objects.create(title="A", description="d")
        photo = Photo.objects.create(title="P", raw_image="r.jpg")
        pia = PhotoInAlbum.objects.create(album=album, photo=photo, order=1)
        self.assertIn("A -> P", str(pia))

    def test_assign_albums_reorders_and_replaces(self):
        album = Album.objects.create(title="My Album", description="desc")

        # initial photos
        p1 = Photo.objects.create(title="P1", raw_image="1.jpg")
        p2 = Photo.objects.create(title="P2", raw_image="2.jpg")
        p3 = Photo.objects.create(title="P3", raw_image="3.jpg")

        # First assignment: add all three to the album
        for p in (p1, p2, p3):
            p.assign_albums([album])
        self.assertEqual(PhotoInAlbum.objects.filter(album=album).count(), 3)

        # New photo
        p4 = Photo.objects.create(title="P4", raw_image="4.jpg")

        # Remove p2 explicitly
        p2.assign_albums([])

        # Ensure p1, p3, p4 are assigned
        for p in (p1, p3, p4):
            p.assign_albums([album])

        # Desired new order
        new_order = [p3, p1, p4]

        # Reorder explicitly
        PhotoInAlbum.objects.filter(album=album, photo=p3).update(order=1)
        PhotoInAlbum.objects.filter(album=album, photo=p1).update(order=2)
        PhotoInAlbum.objects.filter(album=album, photo=p4).update(order=3)

        qs = PhotoInAlbum.objects.filter(album=album).order_by("order")

        # Ensure count is 3
        self.assertEqual(qs.count(), 3)

        # Ensure correct set of photos in album
        self.assertEqual(set(qs.values_list("photo", flat=True)), {p1.id, p3.id, p4.id})

        # Ensure order matches [p3, p1, p4]
        expected = [p.id for p in new_order]
        actual = list(qs.values_list("photo", flat=True))
        self.assertEqual(expected, actual)

        # Ensure no gaps or duplicates in order
        orders = list(qs.values_list("order", flat=True))
        self.assertEqual(orders, list(range(1, len(new_order) + 1)))


class SizeTests(TestCase):
    def setUp(self):
        self.size = Size.objects.create(slug="medium", max_dimension=800, can_edit=True)

    def test_str_representation(self):
        self.assertEqual(str(self.size), "medium (800px)")

    def test_cannot_delete_builtin(self):
        builtin = Size.objects.create(slug="builtin", max_dimension=100, builtin=True, can_edit=False)
        with self.assertRaises(ValidationError):
            builtin.delete()

    @mock.patch("core.tasks.generate_photo_sizes_for_size.delay_on_commit")
    def test_save_triggers_task(self, mock_generate):
        self.size.save()
        self.assertTrue(mock_generate.called)


class PhotoSizeTests(TestCase):
    def test_str_representation(self):
        photo = Photo.objects.create(title="Photo", raw_image="r.jpg")
        size = Size.objects.create(slug="small", max_dimension=400)
        ps = PhotoSize.objects.create(photo=photo, size=size, image="resized.jpg")
        self.assertIn("Photo - small", str(ps))

    def test_unique_constraint(self):
        photo = Photo.objects.create(title="Photo", raw_image="r.jpg")
        size = Size.objects.create(slug="small", max_dimension=400)
        PhotoSize.objects.create(photo=photo, size=size, image="resized.jpg")
        with self.assertRaises(Exception):
            PhotoSize.objects.create(photo=photo, size=size, image="resized2.jpg")


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


class PhotoPublishStateTests(TestCase):
    def setUp(self):
        self.photo = Photo.objects.create(
            title="Test Photo",
            slug="test-photo",
            publish_date=timezone.now(),
            hidden=False,
            _published=False,
        )

    @mock.patch("core.signals.photo_published.send")
    @mock.patch("core.signals.photo_unpublished.send")
    def test_becomes_published_updates_and_dispatches(self, mock_unpub, mock_pub):
        """When transitioning to published: updates DB and dispatches photo_published."""
        self.photo.hidden = False
        self.photo._published = False
        self.photo.publish_date = timezone.now()

        self.photo.update_published(dispatch_signals=True, update_model=True)

        self.photo.refresh_from_db()
        assert self.photo._published is True
        mock_pub.assert_called_once_with(Photo, instance=self.photo, uuid=self.photo.uuid)
        mock_unpub.assert_not_called()

    @mock.patch("core.signals.photo_published.send")
    @mock.patch("core.signals.photo_unpublished.send")
    def test_becomes_unpublished_updates_and_dispatches(self, mock_unpub, mock_pub):
        """When transitioning to unpublished: updates DB and dispatches photo_unpublished."""
        self.photo._published = True
        self.photo.hidden = True
        self.photo.save()

        self.photo.refresh_from_db()
        assert self.photo._published is False
        mock_pub.assert_not_called()
        mock_unpub.assert_called_once_with(Photo, instance=self.photo, uuid=self.photo.uuid)

    @mock.patch("core.signals.photo_published.send")
    @mock.patch("core.signals.photo_unpublished.send")
    @mock.patch.object(Photo, "save")
    def test_no_change_when_state_same(self, mock_save, mock_unpub, mock_pub):
        """No changes → no save, no signals."""
        self.photo._published = True
        self.photo.hidden = False
        self.photo.publish_date = timezone.now()

        self.photo.update_published(dispatch_signals=True, update_model=True)

        mock_save.assert_not_called()
        mock_pub.assert_not_called()
        mock_unpub.assert_not_called()

    @mock.patch("core.signals.photo_published.send")
    @mock.patch.object(Photo, "save")
    def test_no_update_model_flag_skips_save(self, mock_save, mock_pub):
        """update_model=False skips DB save but dispatches signal."""
        self.photo.hidden = False
        self.photo._published = False

        self.photo.update_published(dispatch_signals=True, update_model=False)
        self.photo.refresh_from_db()

        mock_save.assert_not_called()
        mock_pub.assert_called_once_with(Photo, instance=self.photo, uuid=self.photo.uuid)
        assert self.photo._published is False  # unchanged in-memory

    @mock.patch("core.signals.photo_published.send")
    def test_no_dispatch_flag_skips_signal(self, mock_pub):
        """dispatch=False updates DB but skips signal dispatch."""
        self.photo.hidden = False
        self.photo._published = False

        self.photo.update_published(dispatch_signals=False, update_model=True)

        self.photo.refresh_from_db()
        assert self.photo._published is True
        mock_pub.assert_not_called()
    
    @mock.patch("core.signals.photo_unpublished.send")
    def test_photo_deleted_dispatches_unpublished(self, mock_unpub):
        """Deleting a published photo dispatches photo_unpublished."""
        self.photo.hidden = False
        self.photo._published = True
        self.photo.save()

        self.photo.delete()

        mock_unpub.assert_called_once_with(Photo, instance=self.photo, uuid=self.photo.uuid)
    
    @mock.patch("core.signals.photo_unpublished.send")
    def test_photo_deleted_unpublished_no_signal_if_unpublished(self, mock_unpub):
        """Deleting an unpublished photo does not dispatch photo_unpublished."""
        self.photo.hidden = True
        self.photo._published = False
        self.photo.save()

        self.photo.delete()

        mock_unpub.assert_not_called()


class TestMigrations(TestCase):

    @property
    def app(self):
        return apps.get_containing_app_config(type(self).__module__).name

    migrate_from = None
    migrate_to = None

    def setUp(self):
        assert self.migrate_from and self.migrate_to, \
            "TestCase '{}' must define migrate_from and migrate_to properties".format(type(self).__name__)
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass


class TestMigration0003(TestMigrations):
    migrate_from = "0002_album_parent_photo_hidden"
    migrate_to = "0003_core_entity_common_base"

    def setUpBeforeMigration(self, apps):
        # Use old apps registry to create multiple pre-migration Size objects
        SizeOld = apps.get_model("core", "Size")

        self.sizes = []
        for i in range(5):
            size = SizeOld.objects.create(
                slug=f"size-{i}",
                max_dimension=100 * (i + 1),
                can_edit=True,
            )
            self.sizes.append(size)

    @skipIf(
        getattr(settings, "DB_ENGINE", None) == "sqlite",
        "Skipping test because DB_ENGINE is sqlite."
    )
    def test_size_uuids_populated_and_unique_after_migration(self):
        # Use post-migration apps registry
        SizeNew = self.apps.get_model("core", "Size")

        uuids = set()
        for old_size in self.sizes:
            size_after = SizeNew.objects.get(pk=old_size.pk)
            
            # Assert UUID exists
            self.assertTrue(hasattr(size_after, "uuid"))
            self.assertIsNotNone(size_after.uuid)
            
            # Assert UUID is unique
            self.assertNotIn(size_after.uuid, uuids)
            uuids.add(size_after.uuid)

        # Extra check: all UUIDs are unique
        self.assertEqual(len(uuids), len(self.sizes))