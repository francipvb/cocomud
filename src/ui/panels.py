# Copyright (c) 2017, LE GOFF Vincent
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

"""Module containing the several panels that can be found for CocoMUD.

MUDPanel: a panel connected to a client, generally opened for a world.
CMDPanel: a panel used for the command-line mode, no client is open.

Both types of panels are created by the ClientWindow class (ui/window.py).
They both inherit from AccessPanel and have the same accessibility
features.

"""

import re

from accesspanel import AccessPanel
from ytranslate.tools import t
import wx

from log import logger
from screenreader import ScreenReader
from scripting.key import key_name
## Constants
LAST_WORD = re.compile(r"^.*?(\w+)$", re.UNICODE | re.DOTALL)

class MUDPanel(AccessPanel):

    """The panel class connected to a client, a world, and a session."""

    def __init__(self, parent, window, engine, world, session):
        self.rich = engine.settings["options.output.richtext"]
        AccessPanel.__init__(self, parent, history=True, lock_input=True,
                ansi=self.rich, rich=self.rich)
        self.screenreader_support = engine.settings[
                "options.general.screenreader"]
        if self.rich:
            self.output.SetForegroundColour(wx.WHITE)
            self.output.SetBackgroundColour(wx.BLACK)
            ansi = self.extensions["ANSI"]
            ansi.default_foreground = wx.WHITE
            ansi.default_background = wx.BLACK
        self.window = window
        self.engine = engine
        self.client = None
        self.world = world
        self.session = session
        self.focus = True
        self.inside = True
        self.last_ac = None
        self.output.SetFocus()
        self.nb_unread = 0

        # font setup
        size = 12
        # modern is a monotype font
        family = wx.FONTFAMILY_MODERN

        font = wx.Font(size, family, wx.NORMAL, wx.NORMAL)
        # only sets the output window font
        self.output.SetFont(font)

        # Event binding
        self.output.Bind(wx.EVT_TEXT_PASTE, self.OnPaste)

    def CreateClient(self):
        """Connect the MUDPanel."""
        log = logger("client")
        session = self.session
        name = session.world and session.world.name or "unknown"
        character = session.character and session.character.name or "any"
        log.info(u"Selecting world {}, character {}".format(name, character))

        if self.client:
            self.client.disconnect()

        engine = self.engine
        world = self.world
        hostname = world.hostname
        port = world.port
        client = engine.open(hostname, port, world, self)
        client.strip_ansi = not self.rich
        world.load()
        client.commands = self.login()
        self.session.client = client
        return client

    def login(self):
        """Return the commands to login if a character has been selected."""
        if self.session.character:
            character = self.session.character
            username = character.username
            password = character.password
            post_login = character.other_commands

            # Send these commands
            commands = []

            if username:
                commands.extend(username.splitlines())
            if password:
                commands.extend(password.splitlines())
            if post_login:
                commands.extend(post_login.splitlines())
            return commands

        return []

    # Methods to handle client's events
    def handle_disconnection(self, reason=None):
        """The client has been disconnected for any reason."""
        message = u"--- {} ---".format(t("ui.client.disconnected"))
        if self:
            self.Send(message)
        ScreenReader.talk(message, interrupt=False)

    def handle_message(self, message="", mark=None):
        """The client has just received a message."""
        point = self.editing_pos
        lines = message.splitlines()
        lines = [line for line in lines if line]
        message = "\n".join(lines)
        world = self.world
        if world:
            world.feed_words(message)

        if not self:
            return

        self.Send(message, pos=mark)

        # If there's a mark, move the cursor to it
        if mark is not None:
            log = logger("ui")
            word = self.output.GetRange(point + mark, point + mark + 15)
            log.debug("A mark has been detected, move to {} : {}".format(
                    mark, repr(word)))
            self.output.SetInsertionPoint(point + mark)

        # Change the window title if not focused
        if self.focus and not self.inside:
            self.nb_unread += 1
            self.window.SetTitle("({}) {} [CocoMUD]".format(
                    self.nb_unread, world.name))

    def OnInput(self, message):
        """Some text has been sent from the input."""
        if self.world:
            self.world.reset_autocompletion()

        with self.window.lock:
            try:
                self.client.write(message)
            except Exception:
                log = logger("client")
                log.exception("An error occurred when sending a message")

    def OnPaste(self, e):
        """Paste several lines in the input field.

        This event simply sends this text to be processed.

        """
        with self.window.lock:
            clipboard = wx.TextDataObject()
            success = wx.TheClipboard.GetData(clipboard)
            if success:
                clipboard = clipboard.GetText()
                input = self.input + clipboard
                if input.endswith("\n"):
                    lines = input.splitlines()
                    for line in lines:
                        self.OnInput(line)
                    self.ClearInput()
                else:
                    e.Skip()

    def OnKeyDown(self, e):
        """A key is pressed in the window."""
        modifiers = e.GetModifiers()
        key = e.GetUnicodeKey()
        if not key:
            key = e.GetKeyCode()

        if self.world:
            # Test the different macros
            if self.client and self.client.test_macros(key, modifiers):
                self.output.SetInsertionPoint(self.editing_pos)
                return

            # Test auto-completion
            if key == wx.WXK_TAB and modifiers == wx.MOD_NONE:
                input = self.input
                last_word = LAST_WORD.search(input)
                if last_word:
                    last_word = last_word.groups()[0]
                    if self.last_ac and last_word.startswith(self.last_ac):
                        # Remove the word to be modified
                        self.output.Remove(
                                self.output.GetLastPosition() + len(
                                self.last_ac) - len(last_word),
                                self.output.GetLastPosition())
                        last_word = self.last_ac
                    else:
                        self.last_ac = last_word

                    complete = self.world.find_word(last_word, TTS=True)
                    if complete:
                        end = complete[len(last_word):]
                        self.output.AppendText(end)

        AccessPanel.OnKeyDown(self, e)


class CMDPanel(AccessPanel):

    """The CMDPanel to support command-line mode.

    Contrary to the MUDPanel, the CMDPanel is not connected to any
    client.  It has access to a global sharp engine, and can send
    commands to it.  These commands can open a new world in another tab.

    """

    def __init__(self, parent, window, engine):
        AccessPanel.__init__(self, parent, history=True, lock_input=True)
        self.window = window
        self.engine = engine
        self.focus = True
        self.inside = True
        self.output.SetFocus()

        # font setup
        size = 12
        # modern is a monotype font
        family = wx.FONTFAMILY_MODERN

        font = wx.Font(size, family, wx.NORMAL, wx.NORMAL)
        # only sets the output window font
        self.output.SetFont(font)

        # Event binding
        self.output.Bind(wx.EVT_TEXT_PASTE, self.OnPaste)

    def OnInput(self, message):
        """Some text has been sent from the input."""
        with self.window.lock:
            try:
                self.engine.sharp.send(message)
            except Exception:
                log = logger("client")
                log.exception("An error occurred when sending a message")

    def OnPaste(self, e):
        """Paste several lines in the input field.

        This event simply sends this text to be processed.

        """
        with self.window.lock:
            clipboard = wx.TextDataObject()
            success = wx.TheClipboard.GetData(clipboard)
            if success:
                clipboard = clipboard.GetText()
                input = self.input + clipboard
                if input.endswith("\n"):
                    lines = input.splitlines()
                    for line in lines:
                        self.OnInput(line)
                    self.ClearInput()
                else:
                    e.Skip()

