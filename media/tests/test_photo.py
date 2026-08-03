from unittest import mock
from django.test import TestCase
from django.core.exceptions import ValidationError
from media.models import *
from media.filters import PhotoFilter


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

    @mock.patch("media.tasks.post_photo_create.delay_on_commit")
    def test_save_triggers_tasks_on_create(self, mock_post_photo_create):
        p = Photo(title="Another", raw_image="raw.jpg")
        p.save(schedule_followup_tasks=True)

        self.assertTrue(mock_post_photo_create.called)

    @mock.patch("media.tasks.delete_files.delay_on_commit")
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
        self.assertFalse(self.photo.has_metadata)
        self.assertFalse(self.photo.has_sizes)

        # Add metadata
        PhotoMetadata.objects.create(photo=self.photo, camera_make="Canon")
        self.photo.refresh_from_db()
        self.assertTrue(self.photo.has_metadata)
        self.assertFalse(self.photo.has_sizes)

        # Add sizes
        for size in Size.objects.all():
            PhotoSize.objects.create(photo=self.photo, size=size, image=f"{size.slug}.jpg")
        self.photo.refresh_from_db()
        self.assertTrue(self.photo.has_metadata)
        self.assertTrue(self.photo.has_sizes)


class PhotoFormTests(TestCase):
    @mock.patch("media.tasks.post_photo_create.delay_on_commit")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    @mock.patch("PIL.Image.open")
    def test_new_photo_schedules_post_photo_create(self, mock_image_open, mock_storage_save, mock_post_photo_create):
        """Ensure for a new photo, post_photo_create is scheduled"""
        from ..forms import PhotoForm
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
            'canonical_hidden': False,
        }
        
        form = PhotoForm(data=form_data, files={'raw_image': image_file})
        self.assertTrue(form.is_valid(), form.errors)
        
        photo = form.save(commit=True)
        
        # Verify post_photo_create was called with the photo's id
        mock_post_photo_create.assert_called_once_with(photo.id)
    
    @mock.patch("media.tasks.post_photo_create.delay_on_commit")
    def test_existing_photo_does_not_schedule_post_photo_create(self, mock_post_photo_create):
        """Ensure for an existing photo, post_photo_create is not called"""
        from ..forms import PhotoForm
        
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
            'canonical_hidden': False,
        }
        
        form = PhotoForm(data=form_data, instance=photo)
        self.assertTrue(form.is_valid(), form.errors)
        
        form.save(commit=True)
        
        # Verify post_photo_create was NOT called
        mock_post_photo_create.assert_not_called()
    
    @mock.patch("media.tasks.photo_replace_image.delay_on_commit")
    @mock.patch("django.core.files.storage.FileSystemStorage.save")
    @mock.patch("PIL.Image.open")
    def test_photo_image_replaced(self, mock_image_open, mock_storage_save, mock_photo_replace_image):
        """Test that replacing a photo's image triggers photo_replace_image task"""
        from ..forms import PhotoForm
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
            'canonical_hidden': False,
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
            'canonical_hidden': False,
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
            canonical_publish_date=timezone.now() - timezone.timedelta(days=10),
            canonical_hidden=False
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
            canonical_publish_date=timezone.now() - timezone.timedelta(days=5),
            canonical_hidden=False
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
            canonical_publish_date=timezone.now() - timezone.timedelta(days=2),
            canonical_hidden=False
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
            canonical_publish_date=timezone.now() - timezone.timedelta(days=20),
            canonical_hidden=True  # canonical_hidden photo
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
    
    def test_filter_by_canonical_publish_date_range(self):
        """Test filtering photos by publish date range"""
        
        today = timezone.now().date()
        # Get photos from last 7 days
        f = PhotoFilter(data={
            'canonical_publish_date_after': (today - timezone.timedelta(days=7)).isoformat(),
            'canonical_publish_date_before': today.isoformat()
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

    def test_location_data_filter(self):
        """Test filtering photos by whether they have location data"""
        # Give photo1 and photo2 location data; leave photo3 and photo4 without
        self.photo1.latitude = 48.8566
        self.photo1.longitude = 2.3522
        self.photo1.save()

        self.photo2.latitude = 51.5074
        self.photo2.longitude = -0.1278
        self.photo2.save()

        # Filter for photos WITH location data
        f = PhotoFilter(data={'has_location_data': True}, queryset=Photo.objects.all())
        self.assertIn(self.photo1, f.qs)
        self.assertIn(self.photo2, f.qs)
        self.assertNotIn(self.photo3, f.qs)
        self.assertNotIn(self.photo4, f.qs)

        # Filter for photos WITHOUT location data
        f = PhotoFilter(data={'has_location_data': False}, queryset=Photo.objects.all())
        self.assertNotIn(self.photo1, f.qs)
        self.assertNotIn(self.photo2, f.qs)
        self.assertIn(self.photo3, f.qs)
        self.assertIn(self.photo4, f.qs)
