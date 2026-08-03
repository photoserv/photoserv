from unittest import mock
from django.test import TestCase
from django.core.exceptions import ValidationError
from media.models import *


class SizeTests(TestCase):
    def setUp(self):
        self.size = Size.objects.create(slug="medium", max_dimension=800, can_edit=True)

    def test_str_representation(self):
        self.assertEqual(str(self.size), "medium (800px)")

    def test_cannot_delete_builtin(self):
        builtin = Size.objects.create(slug="builtin", max_dimension=100, builtin=True, can_edit=False)
        with self.assertRaises(ValidationError):
            builtin.delete()

    @mock.patch("media.tasks.generate_photo_sizes_for_size.delay_on_commit")
    def test_save_triggers_task(self, mock_generate):
        self.size.save()
        self.assertTrue(mock_generate.called)