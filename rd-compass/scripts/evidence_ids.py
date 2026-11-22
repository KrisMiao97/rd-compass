"""Keep evidence identifiers stable while producing safe, reversible HTML anchors."""
import re


def evidence_anchor(identifier):
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError('Evidence ID must be nonempty text')
    if re.fullmatch(r'[A-Za-z0-9_.-]+', identifier):
        return identifier
    try:
        return '~' + identifier.encode('utf-8').hex()
    except UnicodeEncodeError as exc:
        raise ValueError('Evidence ID must be valid Unicode') from exc
