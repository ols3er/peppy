# peppy Copyright (c) 2006-2009 Rob McMullen
# Licenced under the GPLv2; see http://peppy.flipturn.org for more info
"""Pike programming language editing support.

Major mode for editing Pike files.

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

class PikeMode(FundamentalMode):
    """Stub major mode for editing Pike files.

    This major mode has been automatically generated and is a boilerplate/
    placeholder major mode.  Enhancements to this mode are appreciated!
    """
    keyword = 'Pike'
    editra_synonym = 'Pike'
    stc_lexer_id = wx.stc.STC_LEX_CPP
    start_line_comment = u'//'
    end_line_comment = ''
    
    icon = 'icons/page_white.png'
    
    default_classprefs = (
        StrParam('extensions', 'pike', fullwidth=True),
        StrParam('keyword_set_0', unique_keywords[12], hidden=False, fullwidth=True),
        StrParam('keyword_set_1', unique_keywords[13], hidden=False, fullwidth=True),
        StrParam('keyword_set_2', unique_keywords[14], hidden=False, fullwidth=True),
       )


class PikeModePlugin(IPeppyPlugin):
    """Plugin to register modes and user interface for Pike
    """
   
    def getMajorModes(self):
        yield PikeMode
