﻿# Copyright (c) 2016, LE GOFF Vincent
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.

# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.

# * Neither the name of ytranslate nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


"""Auto-updater of the CocoMUD client."""

import os

from configobj import ConfigObj
from ytranslate import init, select, t
import wx
from wx.lib.pubsub import pub

from autoupdate import AutoUpdate
from version import BUILD

# Determines the user's language
AVAILABLE_LANGUAGES = ("en", "fr")
DEFAULT_LANGUAGE = "en"
path = os.path.join("settings", "options.conf")
config = ConfigObj(path)
try:
    lang = config["general"]["language"]
    assert lang in AVAILABLE_LANGUAGES
except (KeyError, AssertionError):
    lang = DEFAULT_LANGUAGE

# Translation
init(root_dir="translations")
select(lang)

# Classes

class DummyUpdater(wx.Frame):

    """Dummy updater, to which updaters should inherit."""

    def __init__(self, parent):
        wx.Frame.__init__(self, parent)
        self.autoupdater = None
        self.default_text = t("ui.message.update.loading")
        self.progress = 0

        # Event binding
        pub.subscribe(self.OnGauge, "gauge")
        pub.subscribe(self.OnText, "text")
        pub.subscribe(self.OnForceDestroy, "forceDestroy")
        pub.subscribe(self.OnResponseUpdate, "responseUpdate")

    def create_updater(self, just_checking=False):
        """Create a new autoupdater instance."""
        self.autoupdate = AutoUpdate(BUILD, self, just_checking=just_checking)
        self.autoupdate.start()

    def OnGauge(self, value=0):
        """The progress indicator changes."""
        pass

    def OnText(self, text=""):
        """The text of the indicator changes."""
        pass

    def OnForceDestroy(self):
        """Ask for the window's destruction."""
        pass

    def OnResponseUpdate(self, build=None):
        """The check for updates is complete."""
        pass

    def UpdateGauge(self, value):
        """Change the level indicator."""
        wx.CallAfter(pub.sendMessage, "gauge", value=value)

    def UpdateText(self, text):
        """Change the text."""
        wx.CallAfter(pub.sendMessage, "text", text=text)

    def AskDestroy(self):
        wx.CallAfter(pub.sendMessage, "forceDestroy")

    def ResponseUpdate(self, build):
        """The check for updates has responded.

        Note: the build parameter may be None (no update is available)
        or a number (updates are available).

        """
        wx.CallAfter(pub.sendMessage, "responseUpdate", build=build)


class Updater(DummyUpdater):

    """Graphical updater with a gauge."""

    def __init__(self, parent, just_checking=False):
        DummyUpdater.__init__(self, parent)
        self.create_updater(just_checking)
        self.InitUI()
        self.SetTitle(t("ui.message.update.updating"))
        self.Show()
        self.Center()

    def InitUI(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)
        self.text = wx.TextCtrl(panel, value=self.default_text,
                size=(600, 100), style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.gauge = wx.Gauge(panel, range=100, size=(250, 25))
        self.cancel = wx.Button(panel, wx.ID_CANCEL)

        # Window design
        sizer.Add(self.text)
        sizer.Add(self.gauge)
        sizer.Add(self.cancel)

        # Event binding
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self.cancel)

    def OnGauge(self, value=0):
        self.gauge.SetValue(value)
        text = self.default_text
        text += " ({}%)".format(value)
        self.text.SetValue(text)

    def OnText(self, text):
        self.default_text = t(text)
        self.text.SetValue(self.default_text)

    def OnForceDestroy(self):
        self.Destroy()

    def OnCancel(self, e):
        """The user clicks on 'cancel'."""
        value = wx.MessageBox(t("ui.message.update.confirm_cancel"),
                t("ui.dialog.confirm"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)

        if value == wx.YES:
            self.Destroy()


# AppMainLoop
if __name__ == "__main__":
    app = wx.App()
    frame = Updater(None)
    app.MainLoop()
