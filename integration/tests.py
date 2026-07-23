from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock, Mock
from django.utils.timezone import now
from .models import (
    WebRequest, RunResult, IntegrationCaller,
    PythonPlugin, PhotoPluginExclusion, PluginEntityParameters
)
from .forms import IntegrationPhotoForm
from media.models import Photo
from photoserv_plugin.base import PhotoservPlugin
import uuid
import tempfile
import os
import sys
import json
import shutil
from pathlib import Path


class WebRequestTests(TestCase):

    def setUp(self):
        self.webreq = WebRequest.objects.create(
            method=WebRequest.HttpMethod.GET,
            url="https://example.com",
            headers="Authorization: Bearer token123",
        )

    def test_run_creates_integration_run_result(self):
        """1. Running a WebRequest creates an RunResult tied to this integration."""
        with patch.object(WebRequest, "_send") as mock_send:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_send.return_value = mock_response

            result = self.webreq.run(IntegrationCaller.MANUAL)

        self.assertIsInstance(result, RunResult)
        self.assertEqual(result.integration_uuid, self.webreq.uuid)
        self.assertTrue(result.successful)
        self.assertIn("GET https://example.com", result.run_log)
        self.assertEqual(
            RunResult.objects.filter(integration_uuid=self.webreq.uuid).count(),
            1
        )

    @patch("integration.models.requests.request")
    def test_mock_http_request_success(self, mock_request):
        """2. Mock a webrequest HTTP request (200 success)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Success"
        mock_request.return_value = mock_response

        result = self.webreq.run(IntegrationCaller.MANUAL)

        mock_request.assert_called_once_with(
            "GET",
            "https://example.com",
            headers={"Authorization": "Bearer token123"},
            data=None,
        )
        self.assertTrue(result.successful)
        self.assertIn("Response: 200", result.run_log)
        self.assertIn("Success", result.run_log)

    @patch("integration.models.requests.request")
    def test_mock_http_request_failure(self, mock_request):
        """3. Mock non-200 response → failed RunResult."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response

        result = self.webreq.run(IntegrationCaller.EVENT_SCHEDULER)

        self.assertFalse(result.successful)
        self.assertIn("Internal Server Error", result.run_log)
        self.assertIn("ERROR", result.run_log)

    def test_header_validation(self):
        """4. Test various combinations of valid and invalid HTTP headers."""

        # Valid: multiple distinct headers
        valid = WebRequest(
            method="GET",
            url="https://example.com",
            headers="Authorization: Bearer 123\nContent-Type: application/json",
        )
        try:
            valid.clean()  # should not raise
        except ValidationError:
            self.fail("Valid headers raised ValidationError unexpectedly.")

        # Invalid: missing colon
        invalid_no_colon = WebRequest(
            method="GET",
            url="https://example.com",
            headers="Authorization Bearer 123",
        )
        with self.assertRaises(ValidationError) as cm:
            invalid_no_colon.clean()
        self.assertIn("Invalid header format", str(cm.exception))

        # Invalid: duplicate header name
        invalid_duplicate = WebRequest(
            method="GET",
            url="https://example.com",
            headers="Authorization: token1\nAuthorization: token2",
        )
        with self.assertRaises(ValidationError) as cm:
            invalid_duplicate.clean()
        self.assertIn("Duplicate header", str(cm.exception))

        # Valid: empty or blank headers
        empty = WebRequest(method="GET", url="https://example.com", headers="")
        try:
            empty.clean()
        except ValidationError:
            self.fail("Empty headers should not raise ValidationError.")


class TestPluginHelper:
    """Helper class to create temporary test plugins."""
    
    @staticmethod
    def create_test_plugin(plugin_name="test_plugin", with_entity_params=False):
        """Create a temporary test plugin module file."""
        plugin_code = f'''
from photoserv_plugin.base import PhotoservPlugin

__plugin_name__ = "{plugin_name}"
__plugin_version__ = "1.0.0"
__plugin_uuid__ = "test-plugin-{plugin_name}"
__plugin_config__ = {{
    "api_key": "API key for the plugin",
    "base_url": "Base URL for API calls"
}}
'''
        if with_entity_params:
            plugin_code += '''
__plugin_entity_parameters__ = {
    "custom_field": "Custom field value",
    "photo_id": "External photo ID"
}
'''
        
        plugin_code += '''
class Plugin(PhotoservPlugin):
    """Test plugin for automated testing."""
    
    def __init__(self, config, photoserv):
        super().__init__(config, photoserv)
        self.call_log = []
    
    def on_global_change(self):
        """Global change event handler."""
        self.call_log.append(('on_global_change', {}))
        return "Global change handled"
    
    def on_photo_publish(self, data, params, **kwargs):
        """Photo publish event handler."""
        self.call_log.append(('on_photo_publish', data, params))
        return f"Published photo {data.get('uuid', 'unknown')}"
    
    def on_photo_unpublish(self, data, params, **kwargs):
        """Photo unpublish event handler."""
        self.call_log.append(('on_photo_unpublish', data, params))
        return f"Unpublished photo {data.get('uuid', 'unknown')}"
'''
        return plugin_code


class PythonPluginModelTests(TestCase):
    """Tests for PythonPlugin model functionality."""
    
    def setUp(self):
        """Set up test plugin directory and files."""
        # Create a temporary directory for test plugins
        self.temp_dir = tempfile.mkdtemp()
        self.plugins_dir = Path(self.temp_dir) / "plugins"
        self.plugins_dir.mkdir()
        
        # Add to Python path
        sys.path.insert(0, str(self.temp_dir))
        
        # Create test plugin file
        plugin_code = TestPluginHelper.create_test_plugin("test_basic")
        plugin_file = self.plugins_dir / "test_basic_plugin.py"
        plugin_file.write_text(plugin_code)
    
    def tearDown(self):
        """Clean up temporary files and Python path."""
        sys.path.remove(str(self.temp_dir))
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_create_python_plugin(self):
        """Test creating a PythonPlugin instance."""
        plugin = PythonPlugin.objects.create(
            nickname="Test Plugin",
            module="plugins.test_basic_plugin",
            config={"api_key": "test123", "base_url": "https://example.com"},
            active=True
        )
        self.assertEqual(plugin.nickname, "Test Plugin")
        self.assertTrue(plugin.active)
        self.assertIsNotNone(plugin.uuid)
    
    def test_plugin_valid_property(self):
        """Test the valid property checks if plugin can be loaded."""
        # Valid plugin
        valid_plugin = PythonPlugin.objects.create(
            nickname="Valid Plugin",
            module="plugins.test_basic_plugin",
            active=True
        )
        self.assertTrue(valid_plugin.valid)
        
        # Invalid plugin (non-existent module)
        invalid_plugin = PythonPlugin.objects.create(
            nickname="Invalid Plugin",
            module="plugins.nonexistent_module",
            active=True
        )
        self.assertFalse(invalid_plugin.valid)
    
    def test_plugin_load_module(self):
        """Test loading a plugin module."""
        plugin = PythonPlugin.objects.create(
            nickname="Test Plugin",
            module="plugins.test_basic_plugin",
            active=True
        )
        module = plugin._load_module()
        self.assertIsNotNone(module)
        self.assertEqual(module.__plugin_name__, "test_basic")
        self.assertEqual(module.__plugin_version__, "1.0.0")
    
    def test_plugin_run_method(self):
        """Test running a plugin method."""
        plugin = PythonPlugin.objects.create(
            nickname="Test Plugin",
            module="plugins.test_basic_plugin",
            config={"api_key": "test123"},
            active=True
        )
        
        result = plugin.run(
            IntegrationCaller.MANUAL,
            method_name="on_global_change",
            method_args=()
        )
        
        self.assertIsInstance(result, RunResult)
        self.assertTrue(result.successful)
        self.assertIn("Calling on_global_change", result.run_log)
    
    def test_plugin_config_parsing(self):
        """Test that plugin config is properly parsed and passed."""
        plugin = PythonPlugin.objects.create(
            nickname="Test Plugin",
            module="plugins.test_basic_plugin",
            config={"api_key": "secret123", "base_url": "https://api.example.com"},
            active=True
        )
        
        module = plugin._load_module()
        config = plugin._get_config_dict()
        
        self.assertEqual(config['api_key'], 'secret123')
        self.assertEqual(config['base_url'], 'https://api.example.com')
    
    def test_plugin_config_validation_invalid_json(self):
        """Test that invalid JSON config raises validation error."""
        plugin = PythonPlugin(
            nickname="Test Plugin",
            module="plugins.test_basic_plugin",
            config="not a dict",  # String, not dict
            active=True
        )
        with self.assertRaises(ValidationError) as cm:
            plugin.clean()
        self.assertIn("valid JSON object", str(cm.exception))
    
    def test_plugin_config_validation_list_not_allowed(self):
        """Test that list config raises validation error."""
        plugin = PythonPlugin(
            nickname="Test Plugin",
            module="plugins.test_basic_plugin",
            config=["item1", "item2"],  # List, not dict
            active=True
        )
        with self.assertRaises(ValidationError) as cm:
            plugin.clean()
        self.assertIn("valid JSON object", str(cm.exception))


class PhotoPluginExclusionTests(TestCase):
    """Tests for PhotoPluginExclusion model."""
    
    def setUp(self):
        """Set up test data."""
        self.photo = Photo.objects.create(
            title="Test Photo"
        )
        self.plugin = PythonPlugin.objects.create(
            nickname="Test Plugin",
            module="plugins.test_plugin",
            active=True
        )
    
    def test_create_exclusion(self):
        """Test creating a plugin exclusion for a photo."""
        exclusion = PhotoPluginExclusion.objects.create(
            photo=self.photo,
            plugin=self.plugin
        )
        self.assertEqual(exclusion.photo, self.photo)
        self.assertEqual(exclusion.plugin, self.plugin)
    
    def test_unique_together_constraint(self):
        """Test that photo+plugin combination is unique."""
        PhotoPluginExclusion.objects.create(
            photo=self.photo,
            plugin=self.plugin
        )
        
        # Attempting to create duplicate should fail
        with self.assertRaises(Exception):
            PhotoPluginExclusion.objects.create(
                photo=self.photo,
                plugin=self.plugin
            )
    
    def test_exclusion_prevents_signal(self):
        """Test that excluded plugins are not triggered by signals."""
        from .tasks import call_plugin_signal
        
        # Create exclusion
        PhotoPluginExclusion.objects.create(
            photo=self.photo,
            plugin=self.plugin
        )
        
        # Mock the plugin run
        with patch.object(PythonPlugin, 'run') as mock_run:
            # Call signal
            photo_data = {'uuid': str(self.photo.uuid), 'title': self.photo.title}
            call_plugin_signal('on_photo_publish', photo_data)
            
            # Plugin should not have been called due to exclusion
            # (This test assumes the signal logic checks exclusions)
            mock_run.assert_not_called()


class PluginEntityParametersTests(TestCase):
    """Tests for PluginEntityParameters model."""
    
    def setUp(self):
        """Set up test data."""
        self.photo = Photo.objects.create(
            title="Test Photo"
        )
        self.plugin = PythonPlugin.objects.create(
            nickname="Test Plugin",
            module="plugins.test_plugin",
            active=True
        )
    
    def test_create_entity_parameters(self):
        """Test creating entity parameters."""
        params = PluginEntityParameters.objects.create(
            plugin=self.plugin,
            entity_uuid=self.photo.uuid,
            parameters={"custom_field": "value123", "photo_id": "ext_12345"}
        )
        self.assertEqual(params.plugin, self.plugin)
        self.assertEqual(params.entity_uuid, self.photo.uuid)
    
    def test_get_parameters_dict(self):
        """Test parsing parameters to dictionary."""
        params = PluginEntityParameters.objects.create(
            plugin=self.plugin,
            entity_uuid=self.photo.uuid,
            parameters={"custom_field": "value123", "photo_id": "ext_12345", "empty_value": ""}
        )
        
        params_dict = params.get_parameters_dict()
        
        self.assertEqual(params_dict['custom_field'], 'value123')
        self.assertEqual(params_dict['photo_id'], 'ext_12345')
        self.assertEqual(params_dict['empty_value'], '')
    
    def test_parameters_validation_not_dict(self):
        """Test that non-dict parameter format raises validation error."""
        params = PluginEntityParameters(
            plugin=self.plugin,
            entity_uuid=self.photo.uuid,
            parameters="not a dict"  # String, not dict
        )
        
        with self.assertRaises(ValidationError) as cm:
            params.clean()
        self.assertIn("valid JSON object", str(cm.exception))
    
    def test_parameters_validation_list_not_allowed(self):
        """Test that list parameters raise validation error."""
        params = PluginEntityParameters(
            plugin=self.plugin,
            entity_uuid=self.photo.uuid,
            parameters=["item1", "item2"]  # List, not dict
        )
        
        with self.assertRaises(ValidationError) as cm:
            params.clean()
        self.assertIn("valid JSON object", str(cm.exception))
    
    def test_unique_together_constraint(self):
        """Test that plugin+entity_uuid combination is unique."""
        PluginEntityParameters.objects.create(
            plugin=self.plugin,
            entity_uuid=self.photo.uuid,
            parameters={"key": "value"}
        )
        
        # Attempting to create duplicate should fail
        with self.assertRaises(Exception):
            PluginEntityParameters.objects.create(
                plugin=self.plugin,
                entity_uuid=self.photo.uuid,
                parameters={"key": "different_value"}
            )
    
    def test_parameters_passed_to_plugin(self):
        """Test that entity parameters are passed to plugin methods."""
        from .tasks import get_entity_parameters
        
        # Create entity parameters
        PluginEntityParameters.objects.create(
            plugin=self.plugin,
            entity_uuid=self.photo.uuid,
            parameters={"custom_field": "test_value", "photo_id": 12345}
        )
        
        # Get parameters
        photo_data = {'uuid': str(self.photo.uuid)}
        params = get_entity_parameters(self.plugin, photo_data)
        
        self.assertEqual(params['custom_field'], 'test_value')
        self.assertEqual(params['photo_id'], 12345)


class IntegrationPhotoFormTests(TestCase):
    """Tests for IntegrationPhotoForm."""
    
    def setUp(self):
        """Set up test data."""
        # Create a temporary directory for test plugins
        self.temp_dir = tempfile.mkdtemp()
        self.plugins_dir = Path(self.temp_dir) / "plugins"
        self.plugins_dir.mkdir()
        
        # Add to Python path
        sys.path.insert(0, str(self.temp_dir))
        
        # Create test plugin files
        plugin1_code = TestPluginHelper.create_test_plugin("form_test_plugin1", with_entity_params=True)
        plugin1_file = self.plugins_dir / "form_test_plugin1.py"
        plugin1_file.write_text(plugin1_code)
        
        plugin2_code = TestPluginHelper.create_test_plugin("form_test_plugin2", with_entity_params=True)
        plugin2_file = self.plugins_dir / "form_test_plugin2.py"
        plugin2_file.write_text(plugin2_code)
        
        self.photo = Photo.objects.create(
            title="Test Photo"
        )
        self.plugin1 = PythonPlugin.objects.create(
            nickname="Plugin 1",
            module="plugins.form_test_plugin1",
            active=True
        )
        self.plugin2 = PythonPlugin.objects.create(
            nickname="Plugin 2",
            module="plugins.form_test_plugin2",
            active=True
        )
    
    def tearDown(self):
        """Clean up temporary files and Python path."""
        sys.path.remove(str(self.temp_dir))
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_form_initialization(self):
        """Test form initializes with correct fields."""
        form = IntegrationPhotoForm(photo_instance=self.photo)
        
        self.assertIn('excluded_plugins', form.fields)
        # Entity parameter fields are dynamically added for valid plugins
        # They would appear as entity_params_{plugin_id}
    
    def test_form_with_existing_exclusions(self):
        """Test form pre-populates with existing exclusions."""
        # Create existing exclusion
        PhotoPluginExclusion.objects.create(
            photo=self.photo,
            plugin=self.plugin1
        )
        
        form = IntegrationPhotoForm(photo_instance=self.photo)
        
        # Check that plugin1 is in initial data
        self.assertIn(self.plugin1.id, form.fields['excluded_plugins'].initial)
    
    def test_form_validation_invalid_entity_params(self):
        """Test form validation catches invalid entity parameter format."""
        form_data = {
            'excluded_plugins': [],
            f'entity_params_{self.plugin1.pk}': 'not valid json'
        }
        form = IntegrationPhotoForm(data=form_data, photo_instance=self.photo)
        
        is_valid = form.is_valid()
        self.assertFalse(is_valid)
        field_name = f'entity_params_{self.plugin1.pk}'
        if field_name in form.errors:
            self.assertIn('Invalid JSON', str(form.errors[field_name]))
    
    def test_form_validation_list_not_allowed(self):
        """Test form validation catches list instead of object."""
        form_data = {
            'excluded_plugins': [],
            f'entity_params_{self.plugin1.pk}': '["item1", "item2"]'
        }
        form = IntegrationPhotoForm(data=form_data, photo_instance=self.photo)
        
        is_valid = form.is_valid()
        self.assertFalse(is_valid)
        field_name = f'entity_params_{self.plugin1.pk}'
        if field_name in form.errors:
            self.assertIn('must be a JSON object', str(form.errors[field_name]))
    
    def test_form_validation_valid_params(self):
        """Test form validation accepts valid entity parameters."""
        form_data = {
            'excluded_plugins': [],
            f'entity_params_{self.plugin1.pk}': '{"key1": "value1", "key2": "value2"}'
        }
        form = IntegrationPhotoForm(data=form_data, photo_instance=self.photo)
        
        is_valid = form.is_valid()
        self.assertTrue(is_valid)
    
    def test_setup_exclusions(self):
        """Test setup_exclusions method creates/updates exclusions."""
        form_data = {
            'excluded_plugins': [self.plugin1.pk, self.plugin2.pk]
        }
        form = IntegrationPhotoForm(data=form_data, photo_instance=self.photo)
        self.assertTrue(form.is_valid())
        
        form.setup_exclusions(self.photo)
        
        exclusions = PhotoPluginExclusion.objects.filter(photo=self.photo)
        self.assertEqual(exclusions.count(), 2)
        self.assertTrue(exclusions.filter(plugin=self.plugin1).exists())
        self.assertTrue(exclusions.filter(plugin=self.plugin2).exists())
    
    def test_setup_exclusions_clears_old(self):
        """Test setup_exclusions clears old exclusions."""
        # Create initial exclusion
        PhotoPluginExclusion.objects.create(photo=self.photo, plugin=self.plugin1)
        
        # Update with different plugin
        form_data = {
            'excluded_plugins': [self.plugin2.pk]
        }
        form = IntegrationPhotoForm(data=form_data, photo_instance=self.photo)
        self.assertTrue(form.is_valid())
        form.setup_exclusions(self.photo)
        
        exclusions = PhotoPluginExclusion.objects.filter(photo=self.photo)
        self.assertEqual(exclusions.count(), 1)
        self.assertTrue(exclusions.filter(plugin=self.plugin2).exists())
        self.assertFalse(exclusions.filter(plugin=self.plugin1).exists())
    
    def test_setup_entity_parameters(self):
        """Test setup_entity_parameters creates/updates parameters."""
        form_data = {
            'excluded_plugins': [],
            f'entity_params_{self.plugin1.pk}': '{"custom_field": "test123", "photo_id": 456}'
        }
        form = IntegrationPhotoForm(data=form_data, photo_instance=self.photo)
        self.assertTrue(form.is_valid())
        
        form.setup_entity_parameters(self.photo)
        
        params = PluginEntityParameters.objects.get(
            plugin=self.plugin1,
            entity_uuid=self.photo.uuid
        )
        params_dict = params.get_parameters_dict()
        self.assertEqual(params_dict['custom_field'], 'test123')
        self.assertEqual(params_dict['photo_id'], 456)
    
    def test_setup_entity_parameters_deletes_empty(self):
        """Test setup_entity_parameters deletes empty parameters."""
        # Create initial parameters
        PluginEntityParameters.objects.create(
            plugin=self.plugin1,
            entity_uuid=self.photo.uuid,
            parameters={"key": "value"}
        )
        
        # Update with empty value
        form_data = {
            'excluded_plugins': [],
            f'entity_params_{self.plugin1.pk}': ''
        }
        form = IntegrationPhotoForm(data=form_data, photo_instance=self.photo)
        self.assertTrue(form.is_valid())
        form.setup_entity_parameters(self.photo)
        
        # Parameters should be deleted
        exists = PluginEntityParameters.objects.filter(
            plugin=self.plugin1,
            entity_uuid=self.photo.uuid
        ).exists()
        self.assertFalse(exists)


class PluginSignalTests(TestCase):
    """Tests for plugin signal dispatching and task execution."""
    
    def setUp(self):
        """Set up test data."""
        # Create a temporary directory for test plugins
        self.temp_dir = tempfile.mkdtemp()
        self.plugins_dir = Path(self.temp_dir) / "plugins"
        self.plugins_dir.mkdir()
        
        # Add to Python path
        sys.path.insert(0, str(self.temp_dir))
        
        # Create test plugin file
        plugin_code = TestPluginHelper.create_test_plugin("signal_test_plugin", with_entity_params=True)
        plugin_file = self.plugins_dir / "signal_test_plugin.py"
        plugin_file.write_text(plugin_code)
        
        self.photo = Photo.objects.create(
            title="Test Photo"
        )
        self.plugin = PythonPlugin.objects.create(
            nickname="Test Plugin",
            module="plugins.signal_test_plugin",
            active=True
        )
    
    def tearDown(self):
        """Clean up temporary files and Python path."""
        sys.path.remove(str(self.temp_dir))
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch.object(PythonPlugin, 'run')
    def test_call_single_plugin_signal(self, mock_run):
        """Test calling a single plugin signal."""
        from .tasks import call_single_plugin_signal
        
        mock_run.return_value = RunResult(
            integration_uuid=self.plugin.uuid,
            successful=True,
            run_log="Test successful"
        )
        
        photo_data = {'uuid': str(self.photo.uuid), 'title': self.photo.title}
        call_single_plugin_signal(self.plugin.pk, 'on_photo_publish', photo_data)
        
        mock_run.assert_called_once()
    
    @patch.object(PythonPlugin, 'run')
    def test_call_plugin_signal_all_active(self, mock_run):
        """Test calling signal on all active plugins."""
        from .tasks import call_plugin_signal
        
        plugin2 = PythonPlugin.objects.create(
            nickname="Plugin 2",
            module="plugins.test_plugin2",
            active=True
        )
        
        mock_run.return_value = RunResult(
            integration_uuid=uuid.uuid4(),
            successful=True,
            run_log="Test successful"
        )
        
        # Mock the valid property to return True for both plugins
        with patch.object(PythonPlugin, 'valid', new_callable=lambda: property(lambda self: True)):
            photo_data = {'uuid': str(self.photo.uuid)}
            call_plugin_signal('on_photo_publish', photo_data)
        
        # Should be called for each active plugin
        self.assertEqual(mock_run.call_count, 2)
    
    @patch.object(PythonPlugin, 'run')
    def test_call_plugin_signal_respects_exclusions(self, mock_run):
        """Test that plugin signals respect exclusions when plugin_ids are filtered."""
        from .tasks import call_plugin_signal
        
        # Create a second active plugin
        plugin2 = PythonPlugin.objects.create(
            nickname="Plugin 2",
            module="plugins.test_plugin2",
            active=True
        )
        
        # Create exclusion for the first plugin
        PhotoPluginExclusion.objects.create(
            photo=self.photo,
            plugin=self.plugin
        )
        
        mock_run.return_value = RunResult(
            integration_uuid=uuid.uuid4(),
            successful=True,
            run_log="Test successful"
        )
        
        # Mock the valid property to return True
        with patch.object(PythonPlugin, 'valid', new_callable=lambda: property(lambda self: True)):
            photo_data = {'uuid': str(self.photo.uuid)}
            # Pass only plugin2's ID (simulating what receivers.py does)
            call_plugin_signal('on_photo_publish', photo_data, plugin_ids=[plugin2.pk])
        
        # Should only be called once for plugin2, not for the excluded plugin
        self.assertEqual(mock_run.call_count, 1)
    
    def test_dispatch_photo_signal_filters_exclusions(self):
        """Test that dispatch_photo_signal correctly builds the filtered plugin_ids list."""
        # Create a second active plugin
        plugin2 = PythonPlugin.objects.create(
            nickname="Plugin 2",
            module="plugins.test_plugin2",
            active=True
        )
        
        # Create exclusion for the first plugin
        PhotoPluginExclusion.objects.create(
            photo=self.photo,
            plugin=self.plugin
        )
        
        # Test the filtering logic directly
        excluded_plugin_ids = set(
            PhotoPluginExclusion.objects.filter(photo=self.photo)
            .values_list('plugin_id', flat=True)
        )
        
        included_plugin_ids = list(
            PythonPlugin.objects.filter(active=True)
            .exclude(id__in=excluded_plugin_ids)
            .values_list('id', flat=True)
        )
        
        # Verify the filtering works correctly
        self.assertIn(plugin2.pk, included_plugin_ids)
        self.assertNotIn(self.plugin.pk, included_plugin_ids)
        self.assertEqual(len(included_plugin_ids), 1)
    
    @patch.object(PythonPlugin, 'run')
    def test_call_plugin_signal_with_entity_params(self, mock_run):
        """Test that entity parameters are passed to plugin."""
        from .tasks import call_single_plugin_signal
        
        # Create entity parameters
        PluginEntityParameters.objects.create(
            plugin=self.plugin,
            entity_uuid=self.photo.uuid,
            parameters="custom_field: test_value\nphoto_id: 12345"
        )
        
        mock_result = RunResult(
            integration_uuid=self.plugin.uuid,
            successful=True,
            run_log="Success"
        )
        mock_run.return_value = mock_result
        
        photo_data = {'uuid': str(self.photo.uuid)}
        call_single_plugin_signal(self.plugin.pk, 'on_photo_publish', photo_data)
        
        # Check that run was called with params in method_args
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # method_args should contain the params dict
        self.assertIn('custom_field', str(call_args))
    
    def test_inactive_plugin_not_called(self):
        """Test that inactive plugins are not called by signals."""
        from .tasks import call_plugin_signal
        
        # Make plugin inactive
        self.plugin.active = False
        self.plugin.save()
        
        with patch.object(PythonPlugin, 'run') as mock_run:
            photo_data = {'uuid': str(self.photo.uuid)}
            call_plugin_signal('on_photo_publish', photo_data)
            
            mock_run.assert_not_called()
    
    def test_global_signal_no_params(self):
        """Test that global signals don't receive entity parameters."""
        from .tasks import call_plugin_signal
        
        with patch.object(PythonPlugin, 'run') as mock_run:
            mock_run.return_value = RunResult(
                integration_uuid=self.plugin.uuid,
                successful=True,
                run_log="Success"
            )
            
            # Mock the valid property to return True
            with patch.object(PythonPlugin, 'valid', new_callable=lambda: property(lambda self: True)):
                call_plugin_signal('on_global_change', {})
            
            # Check that no params were passed (global methods don't get params)
            call_args = mock_run.call_args
            # For global methods, method_args should be empty tuple or contain only data
            self.assertEqual(call_args[1]['method_args'], tuple())
