from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import *
from api_key.models import APIKey
import io
from PIL import Image
from django.utils import timezone
from datetime import timedelta


def create_test_image_file(filename="test.jpg"):
    """Create a simple in-memory JPEG file"""
    file = io.BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(file, "JPEG")
    file.name = filename
    file.seek(0)
    return SimpleUploadedFile(file.name, file.read(), content_type="image/jpeg")


class APISerializerTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # --- Create Sizes ---
        self.size_original = Size.objects.get(slug="original")
        self.size_medium = Size.objects.create(slug="medium", max_dimension=50, square_crop=False)

        # --- Create a Photo ---
        self.photo = Photo.objects.create(
            title="Test Photo",
            raw_image=create_test_image_file(),
        )
        self.photo.update_published(update_model=True)

        # Attach a PhotoSize for the original size
        self.photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=self.size_original,
            image=create_test_image_file("original.jpg")
        )

        # --- Create Albums ---
        self.album1 = Album.objects.create(title="Album One", description="Test album 1")
        self.album2 = Album.objects.create(title="Album Two", description="Test album 2")
        self.photo.assign_albums([self.album1, self.album2])

        # --- Create Tags ---
        self.tag1 = Tag.objects.create(name="sunset")
        self.tag2 = Tag.objects.create(name="vacation")
        PhotoTag.objects.create(photo=self.photo, tag=self.tag1)
        PhotoTag.objects.create(photo=self.photo, tag=self.tag2)

        # --- Create API Key ---
        self.api_key = APIKey.create_key("public_rest_api test key")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

    # --- Size Tests ---
    def test_sizes_exist(self):
        sizes = Size.objects.all()
        self.assertTrue(sizes.exists())
        self.assertIn(self.size_original, sizes)
        self.assertIn(self.size_medium, sizes)

    # --- Photo Tests ---
    def test_photos_exist(self):
        photos = Photo.objects.all()
        self.assertTrue(photos.exists())
        self.assertIn(self.photo, photos)

    # --- Album Tests ---
    def test_albums_exist(self):
        albums = Album.objects.all()
        self.assertTrue(albums.exists())
        self.assertIn(self.album1, albums)
        self.assertIn(self.album2, albums)

    def test_album_hierarchy(self):
        # Create parent-child relationship
        self.album2.parent = self.album1
        self.album2.save()

        # 1. Album contains reference to parent
        url = f"/api/albums/{self.album2.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("parent", data)
        self.assertIsNotNone(data["parent"])
        self.assertEqual(data["parent"]["uuid"], str(self.album1.uuid))

        # 2. Album contains children
        url = f"/api/albums/{self.album1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("children", data)
        children = data["children"] if isinstance(data["children"], list) else []
        child_uuids = [child["uuid"] for child in children]
        self.assertIn(str(self.album2.uuid), child_uuids)

    # --- Tag Tests ---
    def test_tags_exist(self):
        tags = Tag.objects.all()
        self.assertTrue(tags.exists())
        self.assertIn(self.tag1, tags)
        self.assertIn(self.tag2, tags)
    
    # --- Authentication API test ---
    def test_public_api_authentication_required(self):
        url = f"/api/photos/{self.photo.uuid}/"
        response = APIClient().get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_public_api_authentication_correct(self):
        url = f"/api/photos/{self.photo.uuid}/"
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}-NOTHAHA")
        response = api.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    # --- Photo detail API test ---
    def test_photo_detail_returns_tag_and_album_summaries(self):
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        # Verify tags are included
        tag_uuids = [tag['uuid'] for tag in data['tags']]
        self.assertIn(str(self.tag1.uuid), tag_uuids)
        self.assertIn(str(self.tag2.uuid), tag_uuids)

        # Verify albums are included
        album_uuids = [album['uuid'] for album in data['albums']]
        self.assertIn(str(self.album1.uuid), album_uuids)
        self.assertIn(str(self.album2.uuid), album_uuids)
    
    def test_photo_detail_location_null_and_notnull(self):
        # Initially should be null
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("location", data)
        self.assertIsNone(data["location"])

        # Set location and test again
        self.photo.latitude = 37.7749
        self.photo.longitude = -122.4194
        self.photo.hide_location = False
        self.photo.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("location", data)
        self.assertIsNotNone(data["location"])
        self.assertEqual(data["location"]["latitude"], 37.7749)
        self.assertEqual(data["location"]["longitude"], -122.4194)
    
    def test_photo_detail_location_hidden(self):
        # Set location and hide it
        self.photo.latitude = 37.7749
        self.photo.longitude = -122.4194
        self.photo.hide_location = True
        self.photo.save()

        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("location", data)
        self.assertIsNone(data["location"])

        self.photo.hide_location = False
        self.photo.save()
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("location", data)
        self.assertIsNotNone(data["location"])
    
    # --- Album detail API test ---
    def test_album_detail_returns_ordered_photos(self):
        url = f"/api/albums/{self.album1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Album detail should include photos
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertIn(str(self.photo.uuid), photo_uuids)

    # --- Tag detail API test ---
    def test_tag_detail_returns_related_photos(self):
        url = f"/api/tags/{self.tag1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify photos list includes our photo
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertIn(str(self.photo.uuid), photo_uuids)
    
    # --- Test hidden photos are excluded from public API ---
    def test_hidden_photos_excluded_from_public_api(self):
        # Hide the photo
        self.photo.hidden = True
        self.photo.update_published(update_model=True)

        # Check photo list does not include hidden photo
        response = self.client.get("/api/photos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [photo['uuid'] for photo in response.json()]
        self.assertNotIn(str(self.photo.uuid), photo_uuids)

        # Check photo detail returns 404
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Test with album
        url = f"/api/albums/{self.album1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertNotIn(str(self.photo.uuid), photo_uuids)
    
    def test_photo_published_shows_up(self):
        # Create a public size for testing
        public_test_size = Size.objects.create(slug="public_test", max_dimension=800, public=True)
        
        # Create a new photo with future publish date
        future_photo = Photo.objects.create(
            title="Future Photo",
            raw_image=create_test_image_file("future.jpg"),
            hidden=False,
            publish_date=timezone.now() + timedelta(hours=1)
        )
        future_photo.update_published(update_model=True)
        
        # Add a photo size for the future photo
        future_photo_size = PhotoSize.objects.create(
            photo=future_photo,
            size=public_test_size,
            image=create_test_image_file("future_original.jpg")
        )
        
        # Add it to an album and give it a tag
        future_photo.assign_albums([self.album1])
        PhotoTag.objects.create(photo=future_photo, tag=self.tag1)
        
        # Assert it does NOT show up in any API endpoint
        
        # 1. Photo list endpoint
        response = self.client.get("/api/photos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [photo['uuid'] for photo in response.json()]
        self.assertNotIn(str(future_photo.uuid), photo_uuids)
        
        # 2. Photo detail endpoint
        url = f"/api/photos/{future_photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # 3. Album detail endpoint
        url = f"/api/albums/{self.album1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertNotIn(str(future_photo.uuid), photo_uuids)
        
        # 4. Tag detail endpoint
        url = f"/api/tags/{self.tag1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertNotIn(str(future_photo.uuid), photo_uuids)
        
        # 5. Photo image endpoint
        url = f"/api/photos/{future_photo.uuid}/sizes/{public_test_size.slug}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Now set the publish date to the past
        future_photo.publish_date = timezone.now() - timedelta(hours=1)
        future_photo.update_published(update_model=True)
        
        # Assert it DOES show up in all endpoints
        
        # 1. Photo list endpoint
        response = self.client.get("/api/photos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [photo['uuid'] for photo in response.json()]
        self.assertIn(str(future_photo.uuid), photo_uuids)
        
        # 2. Photo detail endpoint
        url = f"/api/photos/{future_photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['uuid'], str(future_photo.uuid))
        
        # 3. Album detail endpoint
        url = f"/api/albums/{self.album1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertIn(str(future_photo.uuid), photo_uuids)
        
        # 4. Tag detail endpoint
        url = f"/api/tags/{self.tag1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        photo_uuids = [photo['uuid'] for photo in data.get('photos', [])]
        self.assertIn(str(future_photo.uuid), photo_uuids)
        
        # 5. Photo image endpoint
        url = f"/api/photos/{future_photo.uuid}/sizes/{public_test_size.slug}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_photo_custom_attributes_api_response(self):
        # Default (should be {})
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("custom_attributes", data)
        self.assertEqual(data["custom_attributes"], {})

        # Set arbitrary dict
        self.photo.custom_attributes = {"foo": "bar", "num": 42}
        self.photo.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["custom_attributes"], {"foo": "bar", "num": 42})

    def test_album_custom_attributes_api_response(self):
        # Default (should be {})
        url = f"/api/albums/{self.album1.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("custom_attributes", data)
        self.assertEqual(data["custom_attributes"], {})

        # Set arbitrary dict
        self.album1.custom_attributes = {"hello": "world", "x": 123}
        self.album1.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["custom_attributes"], {"hello": "world", "x": 123})


class APISizeDetailTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create API Key
        self.api_key = APIKey.create_key("size_test_key")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

        # Create a test photo
        self.photo = Photo.objects.create(
            title="Test Photo for Sizes",
            raw_image=create_test_image_file()
        )
        self.photo.update_published(update_model=True)

        # Original size for photo attachment
        self.size_original = Size.objects.get(slug="original")
        self.photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=self.size_original,
            image=create_test_image_file("original.jpg")
        )

    def test_private_size_not_listed_or_accessible(self):
        # Create a private size
        private_size = Size.objects.create(
            slug="private_size",
            max_dimension=200,
            square_crop=False,
            public=False
        )
        PhotoSize.objects.create(photo=self.photo, size=private_size, image=create_test_image_file("private.jpg"))

        # 1. Ensure private size does not show up in /api/sizes
        response = self.client.get("/api/sizes/")
        self.assertEqual(response.status_code, 200)
        size_slugs = [s['slug'] for s in response.json()]
        self.assertNotIn(private_size.slug, size_slugs)

        # 2. Ensure accessing photo size returns 404
        url = f"/api/photos/{self.photo.uuid}/sizes/{private_size.slug}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_public_size_listed_and_accessible(self):
        # Create a public size
        public_size = Size.objects.create(
            slug="public_size",
            max_dimension=300,
            square_crop=True,
            public=True
        )
        PhotoSize.objects.create(photo=self.photo, size=public_size, image=create_test_image_file("public.jpg"))

        # 1. Ensure public size shows up in /api/sizes
        response = self.client.get("/api/sizes/")
        self.assertEqual(response.status_code, 200)
        size_slugs = [s['slug'] for s in response.json()]
        self.assertIn(public_size.slug, size_slugs)

        # 1.5. Ensure UUID is present in size listing
        size_uuids = [s['uuid'] for s in response.json()]
        self.assertIn(str(public_size.uuid), size_uuids)

        # 2. Ensure accessing photo size works
        url = f"/api/photos/{self.photo.uuid}/sizes/{public_size.slug}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_photo_size_detail_(self):
        # Create a new public size
        public_size = Size.objects.create(
            slug="new_public_size",
            max_dimension=400,
            square_crop=False,
            public=True
        )
        new_photo_size = PhotoSize.objects.create(
            photo=self.photo,
            size=public_size,
            image=create_test_image_file("new_public.jpg"),
        )

        # Ensure the photo detail endpoint includes info for the new public size: slug, uuid, height, width, md5
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("sizes", data)
        sizes = data["sizes"]
        self.assertIsInstance(sizes, list)
        self.assertGreaterEqual(len(sizes), 1)

        # Verify height and width fields exist for the new public size
        new_size_info = next((s for s in sizes if s["slug"] == "new_public_size"), None)
        self.assertIsNotNone(new_size_info)
        self.assertIn("height", new_size_info)
        self.assertIn("width", new_size_info)
        self.assertIn("md5", new_size_info)


class APISiteHealthTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create API Key
        self.api_key = APIKey.create_key("size_test_key")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

        # Ensure a clean slate for sizes
        Size.objects.all().delete()
        
        # Set up sizes
        self.size_small = Size.objects.create(slug="small", max_dimension=200)
        self.size_large = Size.objects.create(slug="large", max_dimension=800)

        # Create photos
        self.photo1 = Photo.objects.create(title="Photo 1", slug="photo-1", raw_image="dummy1.jpg")
        self.photo2 = Photo.objects.create(title="Photo 2", slug="photo-2", raw_image="dummy2.jpg")
        self.photo3 = Photo.objects.create(title="Photo 3", slug="photo-3", raw_image="dummy3.jpg")

        # Photo 1: has all sizes + metadata
        PhotoSize.objects.create(photo=self.photo1, size=self.size_small, image="small1.jpg")
        PhotoSize.objects.create(photo=self.photo1, size=self.size_large, image="large1.jpg")
        PhotoMetadata.objects.create(photo=self.photo1)

        # Photo 2: missing one size, has metadata
        PhotoSize.objects.create(photo=self.photo2, size=self.size_small, image="small2.jpg")
        PhotoMetadata.objects.create(photo=self.photo2)

        # Photo 3: missing all sizes and metadata

    def test_site_health_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        # Expected values:
        # total_photos = 3
        # total_sizes = 2 -> expected PhotoSize = 3*2 = 6
        # actual PhotoSize = 3
        # pending_sizes = 6 - 3 = 3
        # photos_pending_sizes = 2 (photo2 missing large, photo3 missing both)
        # pending_metadata = 1 (photo3 has no metadata)
        self.assertEqual(data["total_photos"], 3)
        self.assertEqual(data["pending_sizes"], 3)
        self.assertEqual(data["photos_pending_sizes"], 2)
        self.assertEqual(data["pending_metadata"], 1)


class TestIncludePhotoSummarySizes(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.api_key = APIKey.create_key("include_photo_sizes_key")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")

        # --- Create a Photo ---
        self.photo = Photo.objects.create(title="Test Photo", raw_image="test.jpg")
        self.photo.update_published(update_model=True)

        # --- Create Sizes ---
        self.public_size = Size.objects.create(slug="public_size", public=True, max_dimension=500)
        self.private_size = Size.objects.create(slug="private_size", public=False, max_dimension=500)

        # --- Create PhotoSizes ---
        self.photo_public_size = PhotoSize.objects.create(photo=self.photo, size=self.public_size, image="lala.jpg")
        self.photo_private_size = PhotoSize.objects.create(photo=self.photo, size=self.private_size, image="lalap.jpg")

        # --- Album ---
        self.album = Album.objects.create(title="Test Album")
        PhotoInAlbum.objects.create(photo=self.photo, album=self.album, order=1)

        # --- Tag ---
        self.tag = Tag.objects.create(name="Test Tag")
        PhotoTag.objects.create(photo=self.photo, tag=self.tag)

    # 1. Photo detail shows only public sizes
    def test_photo_detail_only_includes_public_size(self):
        url = f"/api/photos/{self.photo.uuid}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        size_slugs = [s["slug"] for s in data.get("sizes", [])]
        self.assertIn(self.public_size.slug, size_slugs)
        self.assertNotIn(self.private_size.slug, size_slugs)

    # 2. /api/photos without sizes shows empty list, with include_sizes=true shows only public
    def test_photo_list_include_sizes_query_param(self):
        # Without include_sizes
        response = self.client.get("/api/photos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for photo in response.json():
            self.assertEqual(photo.get("sizes", []), [])

        # With ?include_sizes=true
        response = self.client.get("/api/photos/?include_sizes=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for photo in response.json():
            size_slugs = [s["slug"] for s in photo.get("sizes", [])]
            self.assertIn(self.public_size.slug, size_slugs)
            self.assertNotIn(self.private_size.slug, size_slugs)

    # 3. Album detail with query param
    def test_album_detail_include_sizes(self):
        url = f"/api/albums/{self.album.uuid}/"

        # Without include_sizes
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for photo in response.json().get("photos", []):
            self.assertEqual(photo.get("sizes", []), [])

        # With ?include_sizes=true
        response = self.client.get(f"{url}?include_sizes=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for photo in response.json().get("photos", []):
            size_slugs = [s["slug"] for s in photo.get("sizes", [])]
            self.assertIn(self.public_size.slug, size_slugs)
            self.assertNotIn(self.private_size.slug, size_slugs)

    # 4. Tag detail with query param
    def test_tag_detail_include_sizes(self):
        url = f"/api/tags/{self.tag.uuid}/"

        # Without include_sizes
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for photo in response.json().get("photos", []):
            self.assertEqual(photo.get("sizes", []), [])

        # With ?include_sizes=true
        response = self.client.get(f"{url}?include_sizes=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for photo in response.json().get("photos", []):
            size_slugs = [s["slug"] for s in photo.get("sizes", [])]
            self.assertIn(self.public_size.slug, size_slugs)
            self.assertNotIn(self.private_size.slug, size_slugs)

class PhotoLocationQueryTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create API key
        self.api_key = APIKey.create_key("location query test key")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.api_key}")
        
        # Create photos with various locations
        # Photo 1: New York City (40.7128, -74.0060)
        self.photo_nyc = Photo.objects.create(
            title="NYC Photo",
            raw_image=create_test_image_file("nyc.jpg"),
            latitude=40.7128,
            longitude=-74.0060,
            hide_location=False
        )
        self.photo_nyc.update_published(update_model=True)
        
        # Photo 2: Los Angeles (34.0522, -118.2437)
        self.photo_la = Photo.objects.create(
            title="LA Photo",
            raw_image=create_test_image_file("la.jpg"),
            latitude=34.0522,
            longitude=-118.2437,
            hide_location=False
        )
        self.photo_la.update_published(update_model=True)
        
        # Photo 3: London (51.5074, -0.1278)
        self.photo_london = Photo.objects.create(
            title="London Photo",
            raw_image=create_test_image_file("london.jpg"),
            latitude=51.5074,
            longitude=-0.1278,
            hide_location=False
        )
        self.photo_london.update_published(update_model=True)
        
        # Photo 4: Tokyo (35.6762, 139.6503)
        self.photo_tokyo = Photo.objects.create(
            title="Tokyo Photo",
            raw_image=create_test_image_file("tokyo.jpg"),
            latitude=35.6762,
            longitude=139.6503,
            hide_location=False
        )
        self.photo_tokyo.update_published(update_model=True)
        
        # Photo 5: Hidden location (should never appear in filtered results)
        self.photo_hidden = Photo.objects.create(
            title="Hidden Location Photo",
            raw_image=create_test_image_file("hidden.jpg"),
            latitude=40.0,
            longitude=-75.0,
            hide_location=True
        )
        self.photo_hidden.update_published(update_model=True)
        
        # Photo 6: No location (should never appear in filtered results)
        self.photo_no_location = Photo.objects.create(
            title="No Location Photo",
            raw_image=create_test_image_file("no_location.jpg"),
            latitude=None,
            longitude=None,
            hide_location=False
        )
        self.photo_no_location.update_published(update_model=True)
    
    def test_no_filters_returns_all_photos(self):
        """Without any filters, all published photos should be returned."""
        response = self.client.get("/api/photos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        self.assertEqual(len(photo_uuids), 6)
    
    def test_latitude_filter_only(self):
        """Filter by latitude bounds (30-45 degrees) - should get NYC and LA."""
        url = "/api/photos/?latitude_lower_bound=30&latitude_upper_bound=45"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertIn(str(self.photo_nyc.uuid), photo_uuids)
        self.assertIn(str(self.photo_la.uuid), photo_uuids)
        self.assertIn(str(self.photo_tokyo.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_london.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_hidden.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_no_location.uuid), photo_uuids)
    
    def test_longitude_filter_only(self):
        """Filter by longitude bounds (-120 to -70) - should get NYC and LA."""
        url = "/api/photos/?longitude_lower_bound=-120&longitude_upper_bound=-70"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertIn(str(self.photo_nyc.uuid), photo_uuids)
        self.assertIn(str(self.photo_la.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_london.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_tokyo.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_hidden.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_no_location.uuid), photo_uuids)
    
    def test_both_filters_active(self):
        """Filter by both latitude and longitude - should get only NYC."""
        url = "/api/photos/?latitude_lower_bound=39&latitude_upper_bound=42&longitude_lower_bound=-75&longitude_upper_bound=-73"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertIn(str(self.photo_nyc.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_la.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_london.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_tokyo.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_hidden.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_no_location.uuid), photo_uuids)
    
    def test_no_photos_meet_filter(self):
        """Filter with bounds that don't match any photos."""
        url = "/api/photos/?latitude_lower_bound=70&latitude_upper_bound=80"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        self.assertEqual(len(photo_uuids), 0)
    
    def test_swapped_bounds_impossible_range(self):
        """Test with lower bound > upper bound (impossible range) - should return no results."""
        url = "/api/photos/?latitude_lower_bound=45&latitude_upper_bound=30"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        self.assertEqual(len(photo_uuids), 0)
    
    def test_only_latitude_lower_bound_returns_400(self):
        """Providing only latitude_lower_bound should return 400."""
        url = "/api/photos/?latitude_lower_bound=30"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())
    
    def test_only_latitude_upper_bound_returns_400(self):
        """Providing only latitude_upper_bound should return 400."""
        url = "/api/photos/?latitude_upper_bound=45"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())
    
    def test_only_longitude_lower_bound_returns_400(self):
        """Providing only longitude_lower_bound should return 400."""
        url = "/api/photos/?longitude_lower_bound=-120"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())
    
    def test_only_longitude_upper_bound_returns_400(self):
        """Providing only longitude_upper_bound should return 400."""
        url = "/api/photos/?longitude_upper_bound=-70"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())
    
    def test_invalid_numeric_value_returns_400(self):
        """Providing non-numeric values should return 400."""
        url = "/api/photos/?latitude_lower_bound=abc&latitude_upper_bound=45"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())
    
    def test_hidden_location_excluded_from_results(self):
        """Photos with hide_location=True should never appear in filtered results."""
        # This filter would include the hidden photo's coordinates, but it should still be excluded
        url = "/api/photos/?latitude_lower_bound=39&latitude_upper_bound=41&longitude_lower_bound=-76&longitude_upper_bound=-74"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertIn(str(self.photo_nyc.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_hidden.uuid), photo_uuids)
    
    def test_null_location_excluded_from_results(self):
        """Photos without location data should never appear in filtered results."""
        url = "/api/photos/?latitude_lower_bound=0&latitude_upper_bound=90"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertNotIn(str(self.photo_no_location.uuid), photo_uuids)
    
    def test_exact_boundary_match(self):
        """Test that photos exactly on boundaries are included."""
        # Set bounds to exactly match NYC coordinates
        url = f"/api/photos/?latitude_lower_bound={self.photo_nyc.latitude}&latitude_upper_bound={self.photo_nyc.latitude}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertIn(str(self.photo_nyc.uuid), photo_uuids)
    
    def test_negative_longitude_range(self):
        """Test filtering across negative longitude values (Western hemisphere)."""
        url = "/api/photos/?longitude_lower_bound=-180&longitude_upper_bound=0"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertIn(str(self.photo_nyc.uuid), photo_uuids)
        self.assertIn(str(self.photo_la.uuid), photo_uuids)
        self.assertIn(str(self.photo_london.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_tokyo.uuid), photo_uuids)
    
    def test_positive_longitude_range(self):
        """Test filtering across positive longitude values (Eastern hemisphere)."""
        url = "/api/photos/?longitude_lower_bound=1&longitude_upper_bound=180"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        photo_uuids = [p['uuid'] for p in response.json()]
        
        self.assertNotIn(str(self.photo_nyc.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_la.uuid), photo_uuids)
        self.assertNotIn(str(self.photo_london.uuid), photo_uuids)
        self.assertIn(str(self.photo_tokyo.uuid), photo_uuids)
    
    def test_combine_with_include_sizes_parameter(self):
        """Test that location filtering works alongside other parameters."""
        url = "/api/photos/?latitude_lower_bound=30&latitude_upper_bound=45&include_sizes=true"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return photos with location filters applied
        photo_uuids = [p['uuid'] for p in response.json()]
        self.assertIn(str(self.photo_nyc.uuid), photo_uuids)
        self.assertIn(str(self.photo_la.uuid), photo_uuids)
