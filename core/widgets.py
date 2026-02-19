from django import forms
from django_filters.widgets import SuffixedMultiWidget
import re


class PhotoTagWidget(forms.SelectMultiple):
    """
    Call tag_input.html template to render a text input for tags
    """
    template_name = 'core/partials/tag_input.html'


class CrispyRangeWidget(SuffixedMultiWidget):
    """
    Custom range widget that uses a template to render min/max inputs with crispy forms.
    Supports different input types via the 'type' attribute (number, date, datetime-local, etc.)
    """
    template_name = 'core/partials/range_widget.html'
    suffixes = ["min", "max"]

    def __init__(self, attrs=None, input_type='text'):
        """
        Initialize the widget with a specific input type.
        
        Args:
            attrs: Additional HTML attributes for the input fields
            input_type: HTML5 input type ('text', 'number', 'date', 'datetime-local', etc.)
        """
        if attrs is None:
            attrs = {}
        
        # Create a copy of attrs for each widget and ensure type is set
        widget_attrs = attrs.copy()
        if 'type' not in widget_attrs:
            widget_attrs['type'] = input_type
        
        # Add DaisyUI classes
        widget_attrs['class'] = widget_attrs.get('class', '') + ' input input-bordered w-full'
            
        # Create two text input widgets with the same attributes
        widgets = (forms.TextInput(attrs=widget_attrs.copy()), 
                   forms.TextInput(attrs=widget_attrs.copy()))
        
        # Pass None as attrs to parent to avoid overriding individual widget attrs
        super().__init__(widgets, attrs=None)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]


class CrispyDateRangeWidget(CrispyRangeWidget):
    """
    Date range widget using date input fields.
    """
    suffixes = ["after", "before"]
    
    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, input_type='date')


class CrispyDateTimeRangeWidget(CrispyRangeWidget):
    """
    DateTime range widget using datetime-local input fields.
    """
    suffixes = ["after", "before"]
    
    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, input_type='datetime-local')


class ShutterSpeedInput(forms.TextInput):
    """
    Custom text input for shutter speed that accepts both decimal (0.0025) 
    and fractional notation (1/400).
    """
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['pattern'] = r'[0-9]*\.?[0-9]*\/[0-9]*\.?[0-9]*?'
        attrs['title'] = 'Enter as decimal (0.0025) or fraction (1/400)'
        attrs['class'] = attrs.get('class', '') + ' input input-bordered w-full'
        super().__init__(attrs)


class CrispyShutterSpeedRangeWidget(SuffixedMultiWidget):
    """
    Range widget for shutter speed that accepts both decimal and fractional notation.
    """
    template_name = 'core/partials/range_widget.html'
    suffixes = ["min", "max"]

    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        
        # Create two ShutterSpeedInput widgets
        widgets = (ShutterSpeedInput(attrs=attrs.copy()), 
                   ShutterSpeedInput(attrs=attrs.copy()))
        
        super().__init__(widgets, attrs=None)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]
