#-----------------------------------------------------------------------------
# Name:        springtabs.py
# Purpose:     Tab-bar control that pops up windows when clicked
#
# Author:      Rob McMullen
#
# Created:     2008
# RCS-ID:      $Id: $
# Copyright:   (c) 2007 Rob McMullen
# License:     wxWidgets
#-----------------------------------------------------------------------------
"""SpringTabs

This module provides popup windows from a group of tabs

"""

import os, sys, struct, Queue, threading, time, socket
from cStringIO import StringIO

import wx
import wx.stc
from wx.lib.pubsub import Publisher
from wx.lib.evtmgr import eventManager
from wx.lib.buttons import GenToggleButton

try:
    from peppy.debug import *
except:
    def dprint(txt=""):
        print txt


class FakePopupWindow(wx.MiniFrame):
    def __init__(self, parent, style=None):
        super(FakePopupWindow, self).__init__(parent, style = wx.NO_BORDER |wx.FRAME_FLOAT_ON_PARENT | wx.FRAME_NO_TASKBAR)
        #self.Bind(wx.EVT_KEY_DOWN , self.OnKeyDown)
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)

    def OnChar(self, evt):
        #print("OnChar: keycode=%s" % evt.GetKeyCode())
        self.GetParent().GetEventHandler().ProcessEvent(evt)

    def Position(self, position, size):
        #print("pos=%s size=%s" % (position, size))
        self.Move((position[0]+size[0], position[1]+size[1]))
        
    def SetPosition(self, position):
        #print("pos=%s" % (position))
        self.Move((position[0], position[1]))
        
    def ActivateParent(self):
        """Activate the parent window
        @postcondition: parent window is raised

        """
        parent = self.GetParent()
        parent.Raise()
        parent.SetFocus()

    def OnFocus(self, evt):
        """Raise and reset the focus to the parent window whenever
        we get focus.
        @param evt: event that called this handler

        """
        dprint("OnFocus: set focus to %s" % str(self.GetParent()))
        self.ActivateParent()
        evt.Skip()


class SpringTabItemRenderer(object):
    def OnPaint(self, item, evt):
        (width, height) = item.GetClientSizeTuple()
        x1 = y1 = 0
        x2 = width-1
        y2 = height-1

        dc = wx.PaintDC(item)
        if item.hover:
            self.DrawHoverBackground(item, dc)
        else:
            brush = item.GetBackgroundBrush(dc)
            if brush is not None:
                dc.SetBackground(brush)
                dc.Clear()

        item.DrawLabel(dc, width, height)
        self.DrawHoverDecorations(item, dc, width, height)
        
        #dprint("button %s: pressed=%s" % (item.GetLabel(), not item.up))
    
    def DrawHoverBackground(self, item, dc):
        brush = wx.Brush(item.faceDnClr, wx.SOLID)
        dc.SetBackground(brush)
        dc.Clear()

    def DrawHoverDecorations(self, item, dc, width, height):
        pass


class SpringTabItemHorizontalRenderer(SpringTabItemRenderer):
    default_direction = "down"
    
    def __init__(self, popup_direction="default"):
        if popup_direction == "default":
            popup_direction = self.default_direction
            
        if popup_direction == "down":
            self.popdown = True
        elif popup_direction == "up":
            self.popdown = False
        else:
            raise TypeError("popup_direction %s not valid for horizontal renderer" % popup_direction)


class SpringTabItemVerticalRenderer(SpringTabItemRenderer):
    default_direction = "right"
    
    def __init__(self, popup_direction="default"):
        if popup_direction == "default":
            popup_direction = self.default_direction
            
        if popup_direction == "left":
            self.popleft = True
        elif popup_direction == "right":
            self.popleft = False
        else:
            raise TypeError("popup_direction %s not valid for vertical renderer" % popup_direction)
            
    def DoGetBestSize(self, item):
        """
        Overridden base class virtual.  Determines the best size of the
        button based on the label and bezel size.
        """
        h, w, useMin = item._GetLabelSize()
        width = w + 2 * item.border + item.bezelWidth - 1
        height = h + 2 * item.border + item.bezelWidth - 1
        #dprint("width=%d height=%d" % (width, height))
        return (width, height)

    def DrawLabel(self, item, dc, width, height, dx=0, dy=0):
        dc.SetFont(item.GetFont())
        if item.IsEnabled():
            dc.SetTextForeground(item.GetForegroundColour())
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        label = item.GetLabel()
        th, tw = dc.GetTextExtent(label)
        #dc.DrawText(label, (width-tw)/2+dx, (height-th)/2+dy)
        dc.DrawRotatedText(label, (width-tw)/2+dx, height + dy - item.border, 90.0)

    def showPopup(self, parent, item, show=True):
        popup, child = item.getPopup()
        if show:
            pw, ph = popup.GetSizeTuple()
            pcw, pch = popup.GetClientSizeTuple()
            cw, ch = child.GetSizeTuple()
            #dprint("popup size=%s  popup client size=%s  child=%s" % (str((pw, ph)), str((pcw, pch)), str((cw, ch))))
            
            # The client size may be smaller than the popup window if the popup
            # has a border decoration.
            diffwidth =  pw - pcw
            diffheight =  ph - pch
            
            # The popup will be at least as tall as the SpringTabs panel
            width, height = parent.GetSizeTuple()
            x, y = parent.ClientToScreenXY(width, 0)
            if ph < height:
                ph = height
            pw = cw + diffwidth
            popup.SetSize(wx.Size(pw, ph))
            
#            # Set the child size to match the popup size
#            ch = height - diffheight
#            child.SetSize(cw, ch)
            
            if self.popleft:
                x -= width + pw
            #dprint("popping up at %s" % str((x,y)))
            child.SetPosition(wx.Point(0, 0))
            popup.SetPosition(wx.Point(x, y))
            wx.CallAfter(item.showPopupCallback)
        popup.Show(show)


class SpringTabItem(GenToggleButton):
    def __init__(self, parent, id=-1, label='', **kwargs):
        self.border = 2
        self.hover = False
        
        GenToggleButton.__init__(self, parent, id, label)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)
        
        self.window_cb = kwargs['window_cb']
        self.popup = None
    
    def InitColours(self):
        faceClr = self.GetBackgroundColour()
        r, g, b = faceClr.Get()
        fr, fg, fb = max(0,r-32), max(0,g-32), max(0,b-32)
        #dprint(str((fr, fg, fb)))
        self.faceDnClr = wx.Colour(fr, fg, fb)
        sr, sg, sb = max(0,r-32), max(0,g-32), max(0,b-32)
        self.shadowPen = wx.Pen(wx.Colour(sr,sg,sb), 1, wx.SOLID)
        hr, hg, hb = min(255,r+64), min(255,g+64), min(255,b+64)
        self.highlightPen = wx.Pen(wx.Colour(hr,hg,hb), 1, wx.SOLID)
        self.focusClr = wx.Colour(hr, hg, hb)
    
    def DoGetBestSize(self):
        return self.GetParent().getRenderer().DoGetBestSize(self)

    def DrawLabel(self, dc, width, height, dx=0, dy=0):
        self.GetParent().getRenderer().DrawLabel(self, dc, width, height, dx, dy)
    
    def OnPaint(self, evt):
        self.GetParent().getRenderer().OnPaint(self, evt)
    
    def SetToggle(self, flag, check_popup=True):
        self.up = not flag
        if check_popup:
            self.GetParent().setRadio(self)
        self.Refresh()

    def OnLeftDown(self, event):
        if not self.IsEnabled():
            return
        self.saveUp = self.up
        self.up = not self.up
        self.GetParent().setRadio(self)
        self.CaptureMouse()
        self.SetFocus()
        self.Refresh()

    def OnEnter(self, evt):
        self.hover = True
        self.Refresh()
    
    def OnLeave(self, evt):
        self.hover = False
        self.Refresh()
    
    def getPopup(self):
        if self.popup is None:
            self.popup = self.GetParent().getNewPopup()
            self.popup.Bind(wx.EVT_ACTIVATE, self.OnActivate)
            
            # Create the window using the popup as the parent
            self.window_cb(self.popup, self)
        child = self.popup.GetChildren()[0]
#        child.Bind(wx.EVT_SET_FOCUS, self.OnChildFocus)
#        child.Bind(wx.EVT_KILL_FOCUS, self.OnLoseChildFocus)
        return self.popup, child

    def OnActivate(self, evt):
        dprint("Activating %s: %s" % (self.GetLabel(), evt.GetActive()))
        evt.Skip()
    
    def showPopupCallback(self):
        """Callback used each time the popup is initially displayed to the user.
        
        If the child implements the activeSprintTab method, that will be called
        to let the popup initialize its state.
        """
        popup, child = self.getPopup()
        if hasattr(child, 'activateSpringTab'):
            child.activateSpringTab()
        self.setPopupFocusCallback()
    
    def setPopupFocusCallback(self):
        """Callback for use within wx.CallAfter to prevent focus being set
        after the control has been removed.
        """
        dprint()
        popup, child = self.getPopup()
        if popup.IsShown():
            dprint("setting focus to %s" % self.GetLabel())
            child.SetFocus()

    # FIXME: This attempt, using OnChildFocus, setPopupsLoseFocusCallback, and
    # OnChildLoseFocus, was to see if I could find out when the focus was set
    # to something other than one of the popup windows.  I can not make this
    # work at the moment, so I'm relying on a call to pubsub to do the work.
    def OnChildFocus(self, evt):
        dprint("current: %s, new = %s, top=%s" % (self.GetLabel(), evt.GetWindow(), wx.GetApp().GetTopWindow()))
#        if evt.GetWindow() is not None:
#            wx.CallAfter(self.setPopupLoseFocusCallback)
    
    def setPopupLoseFocusCallback(self):
        """Callback for use within wx.CallAfter to prevent focus being set
        after the control has been removed.
        """
        dprint()
        popup, child = self.getPopup()
        if popup.IsShown():
            dprint("removing focus from %s" % self.GetLabel())
            self.GetParent().clearRadio()

    def OnLoseChildFocus(self, evt):
        dprint("current: %s, new = %s, top=%s" % (self.GetLabel(), evt.GetWindow(), wx.GetApp().GetTopWindow()))
#        if evt.GetWindow() is not None:
#            wx.CallAfter(self.setPopupLoseFocusCallback)


class SpringTabs(wx.Panel):
    def __init__(self, parent, *args, **kwargs):
        # Need to remove foreign keyword arguments
        vertical = True
        if 'orientation' in kwargs:
            if kwargs['orientation'] == 'horizontal':
                vertical = False
            del kwargs['orientation']
        popup_direction = 'default'
        if 'popup_direction' in kwargs:
            popup_direction = kwargs['popup_direction']
            del kwargs['popup_direction']
        wx.Panel.__init__(self, parent, *args, **kwargs)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)
        
        self._tabs = []
        if vertical:
            self._tab_renderer = SpringTabItemVerticalRenderer(popup_direction)
        else:
            self._tab_renderer = SpringTabItemHorizontalRenderer(popup_direction)
        self._radio = None

        # Using a real wx.PopupWindow seems prevent the focus from being set to
        # the window in the popup.
        self._popup_cls = FakePopupWindow

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        Publisher().subscribe(self.clearRadio, 'springtabs.remove')
    
    def getRenderer(self):
        return self._tab_renderer
    
    def setRadio(self, item):
        self._processing_radio = True
        if self._radio != item:
            self.clearRadio()
            self.popupItem(item)
        elif not item.GetToggle():
            self.clearRadio()
    
    def getNewPopup(self):
        popup = self._popup_cls(self)
        return popup
    
    def popupItem(self, item):
        self._radio = item
        dprint("Popping up %s" % item.GetLabel())
        self._tab_renderer.showPopup(self, item)
    
    def clearRadio(self, data=None):
        if self._radio is not None:
            dprint("Removing popup %s" % self._radio.GetLabel())
            self._tab_renderer.showPopup(self, self._radio, False)
            self._radio.SetToggle(False, check_popup=False)
        self._radio = None
    
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        
        size = self.GetClientSize()
        dc.SetFont(wx.NORMAL_FONT)
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.SetPen(wx.WHITE_PEN)
        dc.DrawRectangle(0, 0, size.x, size.y)
        dc.SetPen(wx.LIGHT_GREY_PEN)
        dc.DrawLine(0, 0, size.x, size.y)
        dc.DrawLine(0, size.y, size.x, 0)
        
        #self._tab_renderer.drawTabs(dc, size.x, self._tabs)
        evt.Skip()


    def OnEraseBackground(self, evt):
        # intentionally empty
        pass

    def OnSize(self, evt):
        self.Refresh()
        evt.Skip()

    def addTab(self, title, window_create_callback):
        tab = SpringTabItem(self, label=title, window_cb=window_create_callback)
        self.GetSizer().Add(tab, 0, wx.EXPAND)
        self._tabs.append(tab)
        
        self.Refresh()





if __name__ == "__main__":
    import wx.calendar
    import wx.stc
    
    class FontList(wx.Panel):
        def __init__(self, parent, *args, **kwargs):
            wx.Panel.__init__(self, parent, -1)

            e = wx.FontEnumerator()
            e.EnumerateFacenames()
            list = e.GetFacenames()

            list.sort()

            self.lb1 = wx.ListBox(self, -1, wx.DefaultPosition, (200, 250),
                                 list, wx.LB_SINGLE)

            self.Bind(wx.EVT_LISTBOX, self.OnSelect, id=self.lb1.GetId())

            self.txt = wx.StaticText(self, -1, "Sample text...", (285, 50))

            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.txt, 0, wx.EXPAND)
            sizer.Add(self.lb1, 0, wx.EXPAND|wx.TOP, 20)

            self.SetSizer(sizer)
            self.Fit()
            self.Layout()
            dprint(self.GetSize())

            self.lb1.SetSelection(0)
            self.OnSelect(None)
            wx.FutureCall(300, self.SetTextSize)

        def SetTextSize(self):
            self.txt.SetSize(self.txt.GetBestSize())

        def OnSelect(self, evt):
            face = self.lb1.GetStringSelection()
            font = wx.Font(28, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False, face)
            self.txt.SetLabel(face)
            self.txt.SetFont(font)
            if wx.Platform == "__WXMAC__": self.Refresh()

    
    def ButtonCB(parent, item):
        button = GenToggleButton(parent, -1, "Whatevar!!! %s" % item.GetLabel())
    
    def CalendarCB(parent, item):
        wx.calendar.CalendarCtrl(parent, -1, wx.DateTime_Now())
        
    app = wx.PySimpleApp()
    frm = wx.Frame(None,-1,"Test",style=wx.TAB_TRAVERSAL|wx.DEFAULT_FRAME_STYLE,
                   size=(600,400))
    panel = wx.Panel(frm)
    sizer = wx.BoxSizer(wx.HORIZONTAL)
    
    # spring tabs for the left side
    tabs1 = SpringTabs(panel)
    tabs1.addTab("Calendar", CalendarCB)
    tabs1.addTab("Fonts", FontList)
    tabs1.addTab("Three", ButtonCB)
    sizer.Add(tabs1, 0, wx.EXPAND)
    
    text = wx.stc.StyledTextCtrl(panel, -1)
    text.SetText("Just a placeholder here.\nThe real action is on the borders.")
    sizer.Add(text, 1, wx.EXPAND)
    
    
    # spring tabs for the rigth side
    tabs2 = SpringTabs(panel, popup_direction="left")
    tabs2.addTab("Calendar", CalendarCB)
    tabs2.addTab("Five", ButtonCB)
    tabs2.addTab("Six", ButtonCB)
    sizer.Add(tabs2, 0, wx.EXPAND)
    
    def fixFocus(evt):
        Publisher.sendMessage('springtabs.remove')
        evt.Skip()
    text.Bind(wx.EVT_SET_FOCUS, fixFocus)
    
    panel.SetAutoLayout(True)
    panel.SetSizer(sizer)
    #sizer.Fit(panel)
    #sizer.SetSizeHints(panel)
    panel.Layout()
    app.SetTopWindow(frm)
    frm.Show()
    app.MainLoop()
