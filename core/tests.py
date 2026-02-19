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
from .filters import PhotoFilter


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
    
    @mock.patch("core.tasks.photo_replace_image.delay_on_commit")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    @mock.patch("PIL.Image.open")
    def test_photo_image_replaced(self, mock_image_open, mock_storage_save, mock_photo_replace_image):
        """Test that replacing a photo's image triggers photo_replace_image task"""
        from .forms import PhotoForm
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Mock PIL Image.open to avoid actual image validation
        mock_image_open.return_value.verify.return_value = None
        mock_image_open.return_value.size = (100, 100)
        mock_image_open.return_value.format = 'JPEG'
        
        # Mock storage save to return different filenames
        mock_storage_save.side_effect = ['original_image.jpg', 'replaced_image.jpg']
        
        # Create an existing photo
        original_image = SimpleUploadedFile(
            name='original.jpg',
            content=b'original fake image content',
            content_type='image/jpeg'
        )
        
        photo = Photo.objects.create(
            title="Photo to Replace",
            raw_image=original_image
        )
        
        # Reset mock to clear creation calls
        mock_photo_replace_image.reset_mock()
        
        # Test 1: Update photo WITHOUT replacing image - task should NOT be called
        form_data = {
            'title': 'Updated Title Only',
            'description': 'Updated description',
            'slug': photo.slug,
            'hidden': False,
        }
        
        form = PhotoForm(data=form_data, instance=photo)
        self.assertTrue(form.is_valid(), form.errors)
        
        form.save(commit=True)
        
        # Verify photo_replace_image was NOT called
        mock_photo_replace_image.assert_not_called()
        
        # Reset mock for next test
        mock_photo_replace_image.reset_mock()
        
        # Test 2: Update photo WITH new image - task SHOULD be called
        # Capture the old image path BEFORE creating the form
        photo.refresh_from_db()
        old_path = photo.raw_image.path
        
        new_image = SimpleUploadedFile(
            name='new_image.jpg',
            content=b'new fake image content',
            content_type='image/jpeg'
        )
        
        form_data = {
            'title': 'Updated with New Image',
            'description': 'Updated with new image',
            'slug': photo.slug,
            'hidden': False,
        }
        
        form = PhotoForm(data=form_data, files={'raw_image': new_image}, instance=photo)
        self.assertTrue(form.is_valid(), form.errors)
        
        form.save(commit=True)
        
        # Verify photo_replace_image WAS called with photo id and old path
        mock_photo_replace_image.assert_called_once()
        call_args = mock_photo_replace_image.call_args
        self.assertEqual(call_args[0][0], photo.id)
        self.assertEqual(call_args[0][1], old_path)


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


class PhotoLocationTests(TestCase):
    def test_new_photo_with_location_defined(self):
        photo = Photo.objects.create(
            title="LocPhoto",
            raw_image="raw.jpg",
            latitude=12.34,
            longitude=56.78
        )
        self.assertEqual(photo.latitude, 12.34)
        self.assertEqual(photo.longitude, 56.78)

        metadata = PhotoMetadata.objects.create(
            photo=photo,
            raw_latitude=2.0,
            raw_longitude=2.0
        )

        photo.latitude = 5.5
        photo.longitude = 6.6
        photo.save()
        photo.refresh_from_db()

        self.assertEqual(photo.latitude, 5.5)
        self.assertEqual(photo.longitude, 6.6)
    
    def test_photo_no_location_defined_initially(self):
        photo = Photo.objects.create(
            title="NoLocPhoto",
            raw_image="raw.jpg"
        )
        self.assertIsNone(photo.latitude)
        self.assertIsNone(photo.longitude)

        metadata = PhotoMetadata.objects.create(
            photo=photo,
            raw_latitude=1.1,
            raw_longitude=2.2
        )

        metadata.save()
        photo.save()
        photo.refresh_from_db()

        self.assertEqual(photo.latitude, 1.1)
        self.assertEqual(photo.longitude, 2.2)

        photo.latitude = 3.3
        photo.longitude = 4.4
        photo.save()
        photo.refresh_from_db()

        self.assertEqual(photo.latitude, 3.3)
        self.assertEqual(photo.longitude, 4.4)
    

class FilterTests(TestCase):
    """Test PhotoFilter and PhotoFilterAPI functionality"""
    
    def setUp(self):
        """Create a rich set of test data for filtering"""
        # Create albums
        self.album1 = Album.objects.create(title="Landscapes", description="Beautiful landscapes")
        self.album2 = Album.objects.create(title="Portraits", description="Portrait photos")
        self.album3 = Album.objects.create(title="Urban", description="City photography")
        
        # Create tags
        self.tag_nature = Tag.objects.create(name="nature")
        self.tag_sunset = Tag.objects.create(name="sunset")
        self.tag_portrait = Tag.objects.create(name="portrait")
        self.tag_city = Tag.objects.create(name="city")
        
        # Create photos with varying attributes
        self.photo1 = Photo.objects.create(
            title="Mountain Sunset",
            slug="mountain-sunset",
            description="A beautiful sunset over mountains",
            raw_image="mountain.jpg",
            publish_date=timezone.now() - timezone.timedelta(days=10),
            hidden=False
        )
        PhotoMetadata.objects.create(
            photo=self.photo1,
            camera_make="Canon",
            camera_model="EOS 5D Mark IV",
            lens_model="EF 24-70mm f/2.8L II USM",
            focal_length=50.0,
            focal_length_35mm=50.0,
            aperture=2.8,
            shutter_speed=0.0025,  # 1/400
            iso=200,
            rating=5,
            capture_date=timezone.now() - timezone.timedelta(days=15),
            exposure_compensation=0.0,
            exposure_program="Manual"
        )
        PhotoTag.objects.create(photo=self.photo1, tag=self.tag_nature)
        PhotoTag.objects.create(photo=self.photo1, tag=self.tag_sunset)
        PhotoInAlbum.objects.create(album=self.album1, photo=self.photo1, order=1)
        
        self.photo2 = Photo.objects.create(
            title="Urban Portrait",
            slug="urban-portrait",
            description="Street portrait in downtown",
            raw_image="portrait.jpg",
            publish_date=timezone.now() - timezone.timedelta(days=5),
            hidden=False
        )
        PhotoMetadata.objects.create(
            photo=self.photo2,
            camera_make="Sony",
            camera_model="A7R IV",
            lens_model="FE 85mm f/1.4 GM",
            focal_length=85.0,
            focal_length_35mm=85.0,
            aperture=1.4,
            shutter_speed=0.001,  # 1/1000
            iso=400,
            rating=4,
            capture_date=timezone.now() - timezone.timedelta(days=7),
            exposure_compensation=-0.3
        )
        PhotoTag.objects.create(photo=self.photo2, tag=self.tag_portrait)
        PhotoTag.objects.create(photo=self.photo2, tag=self.tag_city)
        PhotoInAlbum.objects.create(album=self.album2, photo=self.photo2, order=1)
        PhotoInAlbum.objects.create(album=self.album3, photo=self.photo2, order=1)
        
        self.photo3 = Photo.objects.create(
            title="City Lights",
            slug="city-lights",
            description="Night photography of city skyline",
            raw_image="city.jpg",
            publish_date=timezone.now() - timezone.timedelta(days=2),
            hidden=False
        )
        PhotoMetadata.objects.create(
            photo=self.photo3,
            camera_make="Nikon",
            camera_model="D850",
            lens_model="AF-S NIKKOR 14-24mm f/2.8G ED",
            focal_length=14.0,
            focal_length_35mm=14.0,
            aperture=8.0,
            shutter_speed=4.0,  # 4 seconds
            iso=100,
            rating=5,
            capture_date=timezone.now() - timezone.timedelta(days=3),
            exposure_compensation=0.7,
            flash="No Flash"
        )
        PhotoTag.objects.create(photo=self.photo3, tag=self.tag_city)
        PhotoInAlbum.objects.create(album=self.album3, photo=self.photo3, order=2)
        
        self.photo4 = Photo.objects.create(
            title="Forest Path",
            slug="forest-path",
            description="A winding path through autumn forest",
            raw_image="forest.jpg",
            publish_date=timezone.now() - timezone.timedelta(days=20),
            hidden=True  # Hidden photo
        )
        PhotoMetadata.objects.create(
            photo=self.photo4,
            camera_make="Canon",
            camera_model="EOS R5",
            lens_model="RF 15-35mm f/2.8L IS USM",
            focal_length=24.0,
            focal_length_35mm=24.0,
            aperture=5.6,
            shutter_speed=0.0125,  # 1/80
            iso=800,
            rating=3
        )
        PhotoTag.objects.create(photo=self.photo4, tag=self.tag_nature)
        PhotoInAlbum.objects.create(album=self.album1, photo=self.photo4, order=2)
    
    def test_filter_by_title_contains(self):
        """Test filtering photos by title using contains search"""
        
        # Test contains search
        f = PhotoFilter(data={'title': 'Mountain'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo1, f.qs)
        
        # Test case-insensitive
        f = PhotoFilter(data={'title': 'URBAN'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo2, f.qs)
        
        # Test partial match
        f = PhotoFilter(data={'title': 'City'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo3, f.qs)
        
        # Test substring match
        f = PhotoFilter(data={'title': 'est'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo4, f.qs)
    
    def test_filter_by_slug_contains(self):
        """Test filtering photos by slug using contains search"""
        
        f = PhotoFilter(data={'slug': 'sunset'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo1, f.qs)
        
        f = PhotoFilter(data={'slug': 'urban'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo2, f.qs)
    
    def test_filter_by_description_contains(self):
        """Test filtering photos by description using contains search"""
        
        f = PhotoFilter(data={'description': 'mountains'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo1, f.qs)
        
        f = PhotoFilter(data={'description': 'city'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo3, f.qs)
    
    def test_filter_by_publish_date_range(self):
        """Test filtering photos by publish date range"""
        
        today = timezone.now().date()
        # Get photos from last 7 days
        f = PhotoFilter(data={
            'publish_date_after': (today - timezone.timedelta(days=7)).isoformat(),
            'publish_date_before': today.isoformat()
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo2, f.qs)
        self.assertIn(self.photo3, f.qs)
        self.assertNotIn(self.photo1, f.qs)
        self.assertNotIn(self.photo4, f.qs)
    
    def test_filter_by_camera_make_contains(self):
        """Test filtering by camera make with contains search"""
        
        # Canon cameras
        f = PhotoFilter(data={'camera_make': 'Canon'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 2)
        self.assertIn(self.photo1, f.qs)
        self.assertIn(self.photo4, f.qs)
        
        # Sony cameras
        f = PhotoFilter(data={'camera_make': 'Sony'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo2, f.qs)
        
        # Case insensitive
        f = PhotoFilter(data={'camera_make': 'nikon'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo3, f.qs)
    
    def test_filter_by_camera_model_contains(self):
        """Test filtering by camera model with contains search"""
        
        f = PhotoFilter(data={'camera_model': '5D'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo1, f.qs)
        
        f = PhotoFilter(data={'camera_model': 'EOS'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 2)
        self.assertIn(self.photo1, f.qs)
        self.assertIn(self.photo4, f.qs)
    
    def test_filter_by_lens_model_contains(self):
        """Test filtering by lens model with contains search"""
        
        f = PhotoFilter(data={'lens_model': '85mm'}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertIn(self.photo2, f.qs)
        
        f = PhotoFilter(data={'lens_model': 'f/2.8'}, queryset=Photo.objects.all())
        self.assertGreaterEqual(f.qs.count(), 2)
    
    def test_filter_by_focal_length_range(self):
        """Test filtering by focal length range"""
        
        # Photos with focal length between 20 and 60mm
        f = PhotoFilter(data={
            'focal_length_min': '20',
            'focal_length_max': '60'
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo1, f.qs)  # 50mm
        self.assertIn(self.photo4, f.qs)  # 24mm
        self.assertNotIn(self.photo2, f.qs)  # 85mm
        self.assertNotIn(self.photo3, f.qs)  # 14mm
    
    def test_filter_by_aperture_range(self):
        """Test filtering by aperture range"""
        
        # Wide apertures (f/1.4 to f/2.8)
        f = PhotoFilter(data={
            'aperture_min': '1.4',
            'aperture_max': '2.8'
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo1, f.qs)  # f/2.8
        self.assertIn(self.photo2, f.qs)  # f/1.4
        self.assertNotIn(self.photo3, f.qs)  # f/8.0
    
    def test_filter_by_iso_range(self):
        """Test filtering by ISO range"""
        
        # Low ISO (100-400)
        f = PhotoFilter(data={
            'iso_min': '100',
            'iso_max': '400'
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo1, f.qs)  # ISO 200
        self.assertIn(self.photo2, f.qs)  # ISO 400
        self.assertIn(self.photo3, f.qs)  # ISO 100
        self.assertNotIn(self.photo4, f.qs)  # ISO 800
    
    def test_filter_by_shutter_speed_range(self):
        """Test filtering by shutter speed range"""
        
        # Fast shutter speeds (0.001 to 0.01)
        f = PhotoFilter(data={
            'shutter_speed_min': '0.001',
            'shutter_speed_max': '0.01'
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo1, f.qs)  # 1/400 = 0.0025
        self.assertIn(self.photo2, f.qs)  # 1/1000 = 0.001
        self.assertNotIn(self.photo3, f.qs)  # 4 seconds
    
    def test_filter_by_rating_range(self):
        """Test filtering by rating range"""
        
        # High-rated photos (4-5 stars)
        f = PhotoFilter(data={
            'rating_min': '4',
            'rating_max': '5'
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo1, f.qs)  # Rating 5
        self.assertIn(self.photo2, f.qs)  # Rating 4
        self.assertIn(self.photo3, f.qs)  # Rating 5
        self.assertNotIn(self.photo4, f.qs)  # Rating 3
    
    def test_filter_by_exposure_compensation_range(self):
        """Test filtering by exposure compensation range"""
        
        # Negative to neutral exposure compensation
        f = PhotoFilter(data={
            'exposure_compensation_min': '-1.0',
            'exposure_compensation_max': '0.0'
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo1, f.qs)  # 0.0
        self.assertIn(self.photo2, f.qs)  # -0.3
        self.assertNotIn(self.photo3, f.qs)  # 0.7
    
    def test_filter_by_capture_date_range(self):
        """Test filtering by capture date range"""
        
        today = timezone.now()
        # Photos captured in last 10 days
        f = PhotoFilter(data={
            'capture_date_after': (today - timezone.timedelta(days=10)).isoformat(),
            'capture_date_before': today.isoformat()
        }, queryset=Photo.objects.all())
        
        self.assertIn(self.photo2, f.qs)  # 7 days ago
        self.assertIn(self.photo3, f.qs)  # 3 days ago
        self.assertNotIn(self.photo1, f.qs)  # 15 days ago
    
    def test_filter_by_exposure_program_contains(self):
        """Test filtering by exposure program with contains search"""
        
        f = PhotoFilter(data={'exposure_program': 'Manual'}, queryset=Photo.objects.all())
        self.assertIn(self.photo1, f.qs)
    
    def test_filter_by_flash_contains(self):
        """Test filtering by flash with contains search"""
        
        f = PhotoFilter(data={'flash': 'No Flash'}, queryset=Photo.objects.all())
        self.assertIn(self.photo3, f.qs)
    
    def test_filter_by_albums(self):
        """Test filtering photos by albums (many-to-many)"""
        
        
        # Filter by Landscapes album
        f = PhotoFilter(data={'albums': [self.album1.id]}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 2)
        self.assertIn(self.photo1, f.qs)
        self.assertIn(self.photo4, f.qs)
        
        # Filter by Urban album
        f = PhotoFilter(data={'albums': [self.album3.id]}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 2)
        self.assertIn(self.photo2, f.qs)
        self.assertIn(self.photo3, f.qs)
        
        # Filter by multiple albums (photos in either album)
        f = PhotoFilter(data={'albums': [self.album1.id, self.album2.id]}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 3)
        self.assertIn(self.photo1, f.qs)
        self.assertIn(self.photo2, f.qs)
        self.assertIn(self.photo4, f.qs)
    
    def test_filter_by_tags(self):
        """Test filtering photos by tags (many-to-many)"""
        
        # Filter by nature tag
        f = PhotoFilter(data={'tags': [self.tag_nature.id]}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 2)
        self.assertIn(self.photo1, f.qs)
        self.assertIn(self.photo4, f.qs)
        
        # Filter by city tag
        f = PhotoFilter(data={'tags': [self.tag_city.id]}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 2)
        self.assertIn(self.photo2, f.qs)
        self.assertIn(self.photo3, f.qs)
        
        # Filter by multiple tags (photos with either tag)
        f = PhotoFilter(data={'tags': [self.tag_sunset.id, self.tag_portrait.id]}, queryset=Photo.objects.all())
        self.assertEqual(f.qs.count(), 2)
        self.assertIn(self.photo1, f.qs)
        self.assertIn(self.photo2, f.qs)
