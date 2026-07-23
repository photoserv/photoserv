from django import template


register = template.Library()


@register.filter
def shutter_speed(value):
    if not value:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value  # return as-is if cannot convert

    if value >= 1:
        return f"{int(value)}s"
    else:
        denominator = round(1 / value)
        return f"1/{denominator}s"


@register.filter
def exposure_compensation(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value  # return as-is if cannot convert

    rounded = round(value * 3) / 3
    sign = "+" if rounded >= 0 else "-"
    abs_rounded = abs(rounded)
    whole = int(abs_rounded)
    fraction = abs_rounded - whole

    if abs(fraction) < 1e-6:
        result = f"{sign}{whole:d}"
    elif abs(fraction - 1/3) < 1e-6:
        if whole != 0:
            result = f"{sign}{whole:d}⅓"
        else:
            result = f"{sign}⅓"
    elif abs(fraction - 2/3) < 1e-6:
        if whole != 0:
            result = f"{sign}{whole:d}⅔"
        else:
            result = f"{sign}⅔"
    else:
        result = f"{rounded:+.2f}"

    return f"{result} EV"
