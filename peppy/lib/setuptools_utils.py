#-----------------------------------------------------------------------------
# Name:        setuptools-utils.py
# Purpose:     utilities for the PEAK setuptools module
#
# Author:      Rob McMullen
#
# Created:     2007
# RCS-ID:      $Id: $
# Copyright:   (c) 2007 Rob McMullen
# License:     wxWidgets
#-----------------------------------------------------------------------------
"""setuptools_utils -- utilities for use with setuptools.  Er, duh.

"""
try:
    from peppy.debug import *
except:
    def dprint(txt=""):
        print txt
        return True

    class debugmixin(object):
        debuglevel = 0
        def dprint(self, txt):
            if self.debuglevel > 0:
                dprint(txt)
            return True

USE_SETUPTOOLS = False
try:
    import pkg_resources
    USE_SETUPTOOLS = True
except:
    #dprint("Setuptools unavailable; setuptools plugins will not be loaded.")
    pass


def load_plugins(entry_point):
    if USE_SETUPTOOLS:
        if not hasattr(pkg_resources, 'iter_entry_points'):
            print "Need a newer version of setuptools to load setuptools plugins."
            return
        
        try:
            for entrypoint in pkg_resources.iter_entry_points(entry_point):
                plugin_class = entrypoint.load()
                #dprint("setuptools plugin loaded: %s, class=%s" % (entrypoint.name, plugin_class))
        except ImportError, e:
            import traceback
            dprint(traceback.format_exc())
        except:
            # For now, just skip loading until I figure out how to use versions
            # of setuptools that don't have iter_entry_points
            import traceback
            dprint(traceback.format_exc())
            pass
