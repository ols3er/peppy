# peppy Copyright (c) 2006-2009 Rob McMullen
# Licenced under the GPLv2; see http://peppy.flipturn.org for more info
"""DOS Batch Script programming language editing support.

Major mode for editing DOS Batch Script files.

Supporting actions and minor modes should go here only if they are uniquely
applicable to this major mode and can't be used in other major modes.  If
actions can be used with multiple major modes, they should be put in a
separate plugin in the peppy/plugins directory.
"""

import os

import wx
import wx.stc

from peppy.lib.foldexplorer import *
from peppy.lib.autoindent import *
from peppy.yapsy.plugins import *
from peppy.major import *
from peppy.editra.style_specs import unique_keywords
from peppy.fundamental import FundamentalMode

class DOSBatchScriptMode(FundamentalMode):
    """Stub major mode for editing DOS Batch Script files.

    This major mode has been automatically generated and is a boilerplate/
    placeholder major mode.  Enhancements to this mode are appreciated!
    """
    keyword = 'DOS Batch Script'
    editra_synonym = 'DOS Batch Script'
    stc_lexer_id = wx.stc.STC_LEX_BATCH
    start_line_comment = u'rem '
    end_line_comment = ''
    
    icon = 'icons/page_white.png'
    
    default_classprefs = (
        StrParam('extensions', 'bat cmd', fullwidth=True),
        StrParam('keyword_set_0', unique_keywords[108], hidden=False, fullwidth=True),
       )


class DOSBatchScriptModePlugin(IPeppyPlugin):
    """Plugin to register modes and user interface for DOS Batch Script
    """
   
    def getMajorModes(self):
        yield DOSBatchScriptMode
