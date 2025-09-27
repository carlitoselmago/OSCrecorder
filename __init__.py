"""Blender entry point for the OSC Minimal Recorder add-on.

Keep discovery lightweight: expose bl_info here and import main lazily
during enable/disable so errors in main.py don't hide the add-on.
"""

bl_info = {
    "name": "OSC Minimal Recorder",
    "author": "Carlos Carbonell (htmlfiesta.com)",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "Sidebar > OSC",
    "description": "Receive OSC (UDP) into an internal reader object; live + record to keyframes; driver-friendly.",
    "category": "System",
}


def register():
    from . import main  # lazy import on enable
    main.register()


def unregister():
    from . import main  # lazy import on disable
    main.unregister()
