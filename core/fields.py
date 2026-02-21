import re
from django import forms
from django.core.exceptions import ValidationError


class ShutterSpeedField(forms.CharField):
    """
    Custom form field that accepts shutter speed in either decimal (0.0025) 
    or fractional notation (1/400) and converts to decimal.
    """
    
    def to_python(self, value):
        """Convert the input value to a decimal float."""
        if value in self.empty_values:
            return None
        
        value = str(value).strip()
        
        # Check if it's a fraction (e.g., "1/400")
        fraction_pattern = r'^([0-9]*\.?[0-9]+)\s*/\s*([0-9]*\.?[0-9]+)$'
        match = re.match(fraction_pattern, value)
        
        if match:
            try:
                numerator = float(match.group(1))
                denominator = float(match.group(2))
                if denominator == 0:
                    raise ValidationError('Denominator cannot be zero.')
                return numerator / denominator
            except (ValueError, ZeroDivisionError) as e:
                raise ValidationError(f'Invalid fraction format: {value}')
        
        # Otherwise, try to parse as a regular decimal
        try:
            return float(value)
        except ValueError:
            raise ValidationError(f'Enter a valid number or fraction (e.g., 0.0025 or 1/400)')


class ShutterSpeedRangeField(forms.MultiValueField):
    """
    Range field for shutter speed that accepts min and max values 
    in either decimal or fractional notation.
    """
    
    def __init__(self, *args, **kwargs):
        fields = (
            ShutterSpeedField(required=False),
            ShutterSpeedField(required=False),
        )
        super().__init__(fields=fields, require_all_fields=False, *args, **kwargs)
    
    def compress(self, data_list):
        """Compress the two values into a slice for django-filter."""
        if data_list:
            start, stop = data_list
            if start is not None or stop is not None:
                return slice(start, stop)
        return None
