"""Image renderer package.

Prefer importing concrete factories from submodules
(``app.renderers.canva_factory`` for Canva selection, ``pillow_renderer`` for
the Pillow implementation) rather than relying on re-exports here. Keeping
this module empty avoids pulling settings / pydantic into environments that
only want the pure-Pillow template functions.
"""
