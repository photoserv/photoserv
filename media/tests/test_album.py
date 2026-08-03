from django.test import TestCase
from django.core.exceptions import ValidationError
from media.models import *
from django.urls import reverse


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

        self.album.sort_method = Album.AlbumSortMethod.MANUAL
        ordered = list(self.album.get_ordered_photos())
        self.assertEqual(ordered[0], photo2)
    
    def test_get_ordered_photos_published_ascending(self):
        """Test that photos are sorted by canonical_publish_date in ascending order"""
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg", canonical_publish_date=timezone.now() - timezone.timedelta(days=2))
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg", canonical_publish_date=timezone.now() - timezone.timedelta(days=1))
        photo3 = Photo.objects.create(title="P3", raw_image="3.jpg", canonical_publish_date=timezone.now())
        
        PhotoInAlbum.objects.create(album=self.album, photo=photo3, order=1)
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=3)

        self.album.sort_method = Album.AlbumSortMethod.PUBLISHED
        self.album.sort_descending = False
        ordered = list(self.album.get_ordered_photos())
        
        self.assertEqual(len(ordered), 3)
        self.assertEqual(ordered[0], photo1)  # oldest first
        self.assertEqual(ordered[1], photo2)
        self.assertEqual(ordered[2], photo3)  # newest last
    
    def test_get_ordered_photos_published_descending(self):
        """Test that photos are sorted by canonical_publish_date in descending order"""
        photo1 = Photo.objects.create(title="P1", raw_image="1.jpg", canonical_publish_date=timezone.now() - timezone.timedelta(days=2))
        photo2 = Photo.objects.create(title="P2", raw_image="2.jpg", canonical_publish_date=timezone.now() - timezone.timedelta(days=1))
        photo3 = Photo.objects.create(title="P3", raw_image="3.jpg", canonical_publish_date=timezone.now())
        
        PhotoInAlbum.objects.create(album=self.album, photo=photo1, order=1)
        PhotoInAlbum.objects.create(album=self.album, photo=photo2, order=2)
        PhotoInAlbum.objects.create(album=self.album, photo=photo3, order=3)

        self.album.sort_method = Album.AlbumSortMethod.PUBLISHED
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

        self.album.sort_method = Album.AlbumSortMethod.CREATED
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

        self.album.sort_method = Album.AlbumSortMethod.CREATED
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

        self.album.sort_method = Album.AlbumSortMethod.MANUAL
        
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
    
    def test_album_recursion(self):
        """
        Tree structure:
            root
            ├── child_a
            │   └── grandchild
            └── child_b
        unrelated  (completely separate)

        Photos:
          p_root        → root only
          p_child_a     → child_a only
          p_grandchild  → grandchild only
          p_multi       → root AND grandchild  (in-tree duplicate → must appear once)
          p_cross       → child_b AND unrelated (in-tree via child_b, out-of-tree via unrelated)
          p_unrelated   → unrelated only

        Expected for root.get_ordered_photos(recursive=True):
          {p_root, p_child_a, p_grandchild, p_multi, p_cross}  — exactly once each
          p_unrelated must NOT appear
        """
        from django.utils import timezone
        from datetime import timedelta

        root        = Album.objects.create(title="Root Album")
        child_a     = Album.objects.create(title="Child A", parent=root)
        child_b     = Album.objects.create(title="Child B", parent=root)
        grandchild  = Album.objects.create(title="Grandchild", parent=child_a)
        unrelated   = Album.objects.create(title="Unrelated Album")

        now = timezone.now()

        def make_photo(title, days_ago):
            p = Photo.objects.create(
                title=title,
                raw_image=f"{title.lower().replace(' ', '_')}.jpg",
                canonical_publish_date=now - timedelta(days=days_ago),
            )
            return p

        p_root       = make_photo("Root Photo",       5)
        p_child_a    = make_photo("Child A Photo",    4)
        p_grandchild = make_photo("Grandchild Photo", 3)
        p_multi      = make_photo("Multi Photo",      2)   # in root AND grandchild
        p_cross      = make_photo("Cross Photo",      1)   # in child_b AND unrelated
        p_unrelated  = make_photo("Unrelated Photo",  0)

        PhotoInAlbum.objects.create(album=root,       photo=p_root,       order=1)
        PhotoInAlbum.objects.create(album=child_a,    photo=p_child_a,    order=1)
        PhotoInAlbum.objects.create(album=grandchild, photo=p_grandchild, order=1)
        PhotoInAlbum.objects.create(album=root,       photo=p_multi,      order=2)
        PhotoInAlbum.objects.create(album=grandchild, photo=p_multi,      order=2)
        PhotoInAlbum.objects.create(album=child_b,    photo=p_cross,      order=1)
        PhotoInAlbum.objects.create(album=unrelated,  photo=p_cross,      order=1)
        PhotoInAlbum.objects.create(album=unrelated,  photo=p_unrelated,  order=2)

        # --- Non-recursive: root only ---
        non_recursive = list(root.get_ordered_photos())
        self.assertIn(p_root, non_recursive)
        self.assertIn(p_multi, non_recursive)
        self.assertNotIn(p_child_a, non_recursive)
        self.assertNotIn(p_grandchild, non_recursive)
        self.assertNotIn(p_cross, non_recursive)
        self.assertNotIn(p_unrelated, non_recursive)

        # --- Recursive: full subtree ---
        recursive_qs = root.get_ordered_photos(recursive=True)
        recursive_list = list(recursive_qs)

        in_tree = {p_root, p_child_a, p_grandchild, p_multi, p_cross}
        for photo in in_tree:
            self.assertIn(photo, recursive_list)

        # p_unrelated is not in the tree
        self.assertNotIn(p_unrelated, recursive_list)

        # No duplicates — p_multi is in root AND grandchild but must appear once
        uuids = [p.uuid for p in recursive_list]
        self.assertEqual(len(uuids), len(set(uuids)), "Recursive result contains duplicate photos")

        # --- Recursive with public_only ---
        # None of the photos are published (_published=False by default), so result should be empty
        # TODO: Reimplement or move somewhere else
        # recursive_public = list(root.get_ordered_photos(recursive=True, public_only=True))
        # self.assertEqual(recursive_public, [])

        # # Publish in-tree photos and re-check
        # for p in in_tree:
        #     p._published = True
        #     p.save()

        recursive_public = list(root.get_ordered_photos(recursive=True, q_filter=Q(channels__channel__builtin=True)))
        for photo in in_tree:
            self.assertIn(photo, recursive_public)
        self.assertNotIn(p_unrelated, recursive_public)

        # --- Recursive with MANUAL sort falls back to PUBLISHED ---
        recursive_manual = list(root.get_ordered_photos(recursive=True, sort_method=Album.AlbumSortMethod.MANUAL))
        # Should not raise; falls back to PUBLISHED keeping album's sort_descending=True (newest first)
        self.assertEqual(recursive_manual[0], p_cross)  # 1 day ago (newest)
        self.assertEqual(recursive_manual[-1], p_root)  # 5 days ago (oldest)

        # --- Recursive with explicit sort_descending ---
        recursive_desc = list(root.get_ordered_photos(recursive=True, sort_descending=True))
        self.assertEqual(recursive_desc[0], p_cross)   # 1 day ago (newest)
        self.assertEqual(recursive_desc[-1], p_root)   # 5 days ago (oldest)

        # --- Unrelated album recursive: should only see p_cross and p_unrelated ---
        unrelated_recursive = list(unrelated.get_ordered_photos(recursive=True))
        self.assertIn(p_cross, unrelated_recursive)
        self.assertIn(p_unrelated, unrelated_recursive)
        for photo in {p_root, p_child_a, p_grandchild, p_multi}:
            self.assertNotIn(photo, unrelated_recursive)


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