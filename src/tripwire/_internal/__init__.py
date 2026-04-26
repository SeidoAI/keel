"""Internal tripwire surfaces.

The leading underscore is the standard Python signal "external callers
must not depend on this." Nothing in this package is re-exported from
``tripwire/__init__.py`` and no user-facing template, skill, doc, or
example references content under here. Skill loaders explicitly skip
this directory — see the hygiene test in
``tests/unit/internal/test_module_hygiene.py``.
"""
