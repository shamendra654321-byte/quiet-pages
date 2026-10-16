"""Validated, backwards-compatible reading positions in source-audio seconds."""
import math


def position(value, parts):
    if not isinstance(value, dict):
        value = {'index': value}
    def number(key, default=0):
        try:
            result = float(value.get(key, default))
            return result if math.isfinite(result) else default
        except (TypeError, ValueError, OverflowError):
            return default
    index = max(0, min(len(parts) - 1, int(number('index'))))
    return {'index': index, 'seconds': max(0, number('seconds')),
            'text_offset': max(0, min(len(parts[index]), int(number('text_offset')))),
            'voice': value.get('voice') if isinstance(value.get('voice'), str) else None,
            'speed': min(2, max(.5, number('speed', 1)))}


def source_seconds(start, end, due, duration, now):
    """Interpolate only the submitted block that should currently be audible."""
    fraction = min(1, max(0, (now - due) / duration)) if duration > 0 else 1
    return start + (end - start) * fraction
