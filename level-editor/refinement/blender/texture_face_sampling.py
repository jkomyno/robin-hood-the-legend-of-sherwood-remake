"""Explicit generated-view eligibility for individually inspected receiver faces."""
import math


def face_sampling(manifest, face_counts):
    mapping = manifest.get('texture_generated_face_sampling', {})
    if not isinstance(mapping, dict) or not set(mapping) <= set(face_counts):
        raise ValueError('Generated face sampling names a foreign receiver')
    result = {}
    for name, faces in mapping.items():
        if not isinstance(faces, dict) or not faces:
            raise ValueError('Generated face sampling requires exact face indices')
        for key, setting in faces.items():
            if (not isinstance(key, str) or not key.isdigit() or str(int(key)) != key or
                    int(key) >= face_counts[name]):
                raise ValueError('Generated face sampling names an absent face')
            if (not isinstance(setting, dict) or
                    set(setting) != {'minimum_cosine', 'two_sided', 'reason'}):
                raise ValueError('Generated face sampling requires an explicit policy and reason')
            minimum = setting['minimum_cosine']
            if (isinstance(minimum, bool) or not isinstance(minimum, (float, int)) or
                    not math.isfinite(minimum) or not .01 <= minimum <= .12 or
                    type(setting['two_sided']) is not bool or
                    not isinstance(setting['reason'], str) or not setting['reason'].strip()):
                raise ValueError('Invalid bounded generated face sampling policy')
            scope = manifest.get('texture_receiver_face_indices')
            if scope is not None and int(key) not in scope.get(name, []):
                raise ValueError('Generated face sampling exceeds receiver face scope')
            result[(name, int(key))] = (float(minimum), setting['two_sided'])
    return result


def eligibility(mapping, name, face, *, legacy_two_sided=False):
    """Unlisted faces retain the existing facing floor and one-sided behavior."""
    return mapping.get((name, face), (.12, legacy_two_sided))
