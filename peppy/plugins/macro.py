# peppy Copyright (c) 2006-2008 Rob McMullen
# Licenced under the GPLv2; see http://peppy.flipturn.org for more info
"""Simple macros created by recording actions

This plugin provides macro recording
"""

import os

import wx

from peppy.fundamental import FundamentalMode
from peppy.yapsy.plugins import *

from peppy.actions.base import *
from peppy.actions import *
from peppy.lib.multikey import *
from peppy.debug import *


class RecordedKeyboardAction(RecordedAction):
    def __init__(self, action, evt, multiplier):
        RecordedAction.__init__(self, action, multiplier)
        self.evt = FakeCharEvent(evt)
        
        # Hack to force SelfInsertCommand to process the character, because
        # normally it uses the evt.Skip() to force the EVT_CHAR handler to
        # insert the character.
        self.evt.is_quoted = True
    
    def __str__(self):
        return "%s: %dx%s" % (self.actioncls.__name__, self.multiplier, self.evt.GetKeyCode())
    
    def performAction(self, system_state):
        action = self.actioncls(system_state.frame, mode=system_state.mode)
        dprint(action.__class__.__name__)
        action.actionKeystroke(self.evt, self.multiplier)


class RecordedMenuAction(RecordedAction):
    def __init__(self, action, index, multiplier):
        RecordedAction.__init__(self, action, multiplier)
        self.index = index
    
    def __str__(self):
        return "%s x%d, index=%s" % (self.actioncls.__name__, self.multiplier, self.index)
    
    def performAction(self, system_state):
        action = self.actioncls(system_state.frame, mode=system_state.mode)
        dprint(action.__class__.__name__)
        action.action(self.index, self.multiplier)


class ActionRecorder(AbstractActionRecorder, debugmixin):
    def __init__(self):
        self.recording = []
    
    def __str__(self):
        summary = ''
        count = 0
        for recorded_item in self.recording:
            if hasattr(recorded_item, 'text'):
                summary += recorded_item.text + " "
                if len(summary) > 50:
                    summary = summary[0:50] + "..."
            count += 1
        if len(summary) == 0:
            summary = "%d actions" % count
        return summary
        
    def details(self):
        lines = []
        for recorded_item in self.recording:
            lines.append(str(recorded_item))
        return "\n".join(lines)
        
    def recordKeystroke(self, action, evt, multiplier):
        if action.isRecordable():
            record = RecordedKeyboardAction(action, evt, multiplier)
            self.appendRecord(record)
    
    def recordMenu(self, action, index, multiplier):
        if action.isRecordable():
            record = RecordedMenuAction(action, index, multiplier)
            self.appendRecord(record)
    
    def appendRecord(self, record):
        dprint("adding %s" % record)
        if self.recording:
            last = self.recording[-1]
            if last.canCoalesceActions(record):
                self.recording.pop()
                record = last.coalesceActions(record)
                dprint("coalesced into %s" % record)
        self.recording.append(record)
    
    def getRecordedActions(self):
        return self.recording
    
    def playback(self, frame, mode, multiplier=1):
        mode.BeginUndoAction()
        state = MacroPlaybackState(frame, mode)
        dprint(state)
        SelectAction.debuglevel = 1
        while multiplier > 0:
            for recorded_action in self.recording:
                recorded_action.performAction(state)
            multiplier -= 1
        SelectAction.debuglevel = 0
        mode.EndUndoAction()


class StartRecordingMacro(SelectAction):
    """Begin recording actions"""
    name = "Start Recording"
    key_bindings = {'default': "C-1", }
    default_menu = (("Tools/Macros", -800), 100)
    
    def action(self, index=-1, multiplier=1):
        self.frame.root_accel.startRecordingActions(ActionRecorder())


class StopRecordingMacro(SelectAction):
    """Stop recording actions"""
    name = "Stop Recording"
    key_bindings = {'default': "C-2", }
    default_menu = ("Tools/Macros", 110)
    
    @classmethod
    def isRecordable(cls):
        return False
    
    def action(self, index=-1, multiplier=1):
        if self.frame.root_accel.isRecordingActions():
            recorder = self.frame.root_accel.stopRecordingActions()
            dprint(recorder)
            ReplayLastMacro.setLastMacro(recorder)


class ReplayLastMacro(SelectAction):
    """Play back last macro that was recorded"""
    name = "Play Last Macro"
    key_bindings = {'default': "C-3", }
    default_menu = ("Tools/Macros", 110)
    
    last_recording = None
    
    def isEnabled(self):
        return bool(self.last_recording)
    
    @classmethod
    def isRecordable(cls):
        return False
    
    @classmethod
    def setLastMacro(cls, recording):
        cls.last_recording = recording
        RecentMacros.append(recording)
    
    def action(self, index=-1, multiplier=1):
        if self.frame.root_accel.isRecordingActions():
            recorder = self.frame.root_accel.stopRecordingActions()
            dprint(recorder)
            self.setLastMacro(recorder)
        dprint("Playing back %s" % self.last_recording)
        if self.last_recording:
            wx.CallAfter(self.last_recording.playback, self.frame, self.mode, multiplier)
        else:
            dprint("No recorded macro.")
        


class RecentMacros(OnDemandGlobalListAction):
    """Play a macro from the list of recently created macros
    
    Maintains a list of the recent macros and runs the selected macro if chosen
    out of the submenu.
    """
    name = "Recent Macros"
    default_menu = ("Tools/Macros", -200)
    inline = False
    
    storage = []
    
    def action(self, index=-1, multiplier=1):
        macro = self.storage[index]
        assert self.dprint("replaying macro %s" % macro)
        wx.CallAfter(macro.playback, self.frame, self.mode, 1)


class MacroPlugin(IPeppyPlugin):
    """Plugin providing the macro recording capability
    """
    def getActions(self):
        return [
            StartRecordingMacro, StopRecordingMacro, ReplayLastMacro,
            
            RecentMacros,
            ]