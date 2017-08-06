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

"""This file contains the ClientWindow class."""

from __future__ import absolute_import
import os
import sys
from threading import RLock
from zipfile import ZipFile

import wx
from wx.lib.pubsub import pub, setupkwargs
from ytranslate.tools import t

from autoupdate import AutoUpdate
from log import logger
from screenreader import ScreenReader
from session import Session
from task.import_worlds import ImportWorlds
from ui.dialogs.alias import AliasDialog
from ui.dialogs.character import CharacterDialog
from ui.dialogs.connection import ConnectionDialog, EditWorldDialog
from ui.dialogs.console import ConsoleDialog
from ui.dialogs.loading import LoadingDialog
from ui.dialogs.macro import MacroDialog
from ui.dialogs.notepad import NotepadDialog
from ui.dialogs.preferences import PreferencesDialog
from ui.dialogs.trigger import TriggerDialog
from ui.dialogs.worlds import WorldsDialog
from ui.event import EVT_FOCUS, FocusEvent, myEVT_FOCUS
from ui.panels import MUDPanel, CMDPanel
from wizard.install_world import InstallWorld
from world import World
from updater import *
from version import BUILD

class ClientWindow(DummyUpdater):

    def __init__(self, engine, world=None):
        super(ClientWindow, self).__init__(None)
        self.lock = RLock()
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer = sizer
        self.main_panel = wx.Panel(self)
        self.tabs = wx.Notebook(self.main_panel)
        sizer.Add(self.tabs, 1, wx.EXPAND)
        self.main_panel.SetSizer(sizer)
        self.engine = engine
        self.focus = True
        self.interrupt = False
        self.loading = None
        self.connection = None
        self.CreateMenuBar()
        self.InitUI(world)

    @property
    def world(self):
        return self.panel and self.panel.world or None

    @property
    def panel(self):
        """Return the currently selected tab (a MUDPanel0."""
        return self.tabs.GetCurrentPage()

    def _get_client(self):
        return self.panel.client
    def _set_client(self, client):
        self.panel.client = client
    client = property(_get_client, _set_client)

    def CloseAll(self):
        """Close ALL windows (counting dialogs)."""
        windows = wx.GetTopLevelWindows()
        for window in windows:
            # The LoadingDialog needs to be destroyed to avoid confirmation
            if isinstance(window, LoadingDialog):
                window.Destroy()
            else:
                window.Close()

    def CreateMenuBar(self):
        """Create the GUI menu bar and hierarchy of menus."""
        menubar = wx.MenuBar()

        # Differemtn menus
        fileMenu = wx.Menu()
        gameMenu = wx.Menu()
        connectionMenu = wx.Menu()
        helpMenu = wx.Menu()

        ## File menu
        # New
        create = wx.MenuItem(fileMenu, -1, t("ui.menu.create"))
        self.Bind(wx.EVT_MENU, self.OnCreate, create)
        fileMenu.AppendItem(create)

        # Open
        open = wx.MenuItem(fileMenu, -1, t("ui.menu.open"))
        self.Bind(wx.EVT_MENU, self.OnOpen, open)
        fileMenu.AppendItem(open)

        # Close
        close_tab = wx.MenuItem(fileMenu, -1, t("ui.menu.close_tab"))
        self.Bind(wx.EVT_MENU, self.OnCloseTab, close_tab)
        fileMenu.AppendItem(close_tab)

        # Import
        import_world = wx.Menu()
        import_ondisk = import_world.Append(wx.ID_ANY,
                t("ui.menu.import_on_disk"))
        import_online = import_world.Append(wx.ID_ANY,
                t("ui.menu.import_online"))
        wx.MenuItem(fileMenu, -1, t("ui.menu.import"))
        self.Bind(wx.EVT_MENU, self.OnImportOndisk, import_ondisk)
        self.Bind(wx.EVT_MENU, self.OnImportOnline, import_online)
        fileMenu.AppendMenu(wx.ID_ANY, t("ui.menu.import"), import_world)

        # Preferences
        preferences = wx.MenuItem(fileMenu, -1, t("ui.menu.preferences"))
        self.Bind(wx.EVT_MENU, self.OnPreferences, preferences)
        fileMenu.AppendItem(preferences)

        # Console
        console = wx.MenuItem(fileMenu, -1, t("ui.menu.console"))
        self.Bind(wx.EVT_MENU, self.OnConsole, console)
        fileMenu.AppendItem(console)

        # Quit
        quit = wx.MenuItem(fileMenu, -1, t("ui.menu.quit"))
        self.Bind(wx.EVT_MENU, self.OnQuit, quit)
        fileMenu.AppendItem(quit)

        ## Game menu
        # Aliases
        alias = wx.MenuItem(gameMenu, -1, t("ui.menu.aliases"))
        self.Bind(wx.EVT_MENU, self.OnAlias, alias)
        gameMenu.AppendItem(alias)

        # Macros
        macro = wx.MenuItem(gameMenu, -1, t("ui.menu.macro"))
        self.Bind(wx.EVT_MENU, self.OnMacro, macro)
        gameMenu.AppendItem(macro)

        # Triggers
        triggers = wx.MenuItem(gameMenu, -1, t("ui.menu.triggers"))
        self.Bind(wx.EVT_MENU, self.OnTriggers, triggers)
        gameMenu.AppendItem(triggers)

        # Notepad
        notepad = wx.Menu()
        notepad_world = notepad.Append(wx.ID_ANY,
                t("ui.menu.notepad_world"))
        notepad_character = notepad.Append(wx.ID_ANY,
                t("ui.menu.notepad_character"))
        wx.MenuItem(gameMenu, -1, t("ui.menu.notepad"))
        self.Bind(wx.EVT_MENU, self.OnNotepadWorld, notepad_world)
        self.Bind(wx.EVT_MENU, self.OnNotepadCharacter, notepad_character)
        gameMenu.AppendMenu(wx.ID_ANY, t("ui.menu.notepad"), notepad)

        # Character
        character = wx.MenuItem(gameMenu, -1, t("ui.menu.character"))
        self.Bind(wx.EVT_MENU, self.OnCharacter, character)
        gameMenu.AppendItem(character)

        # Play sounds
        self.chk_sounds = gameMenu.Append(wx.ID_ANY, t("ui.menu.sounds"),
                t("ui.menu.sounds"), kind=wx.ITEM_CHECK)
        gameMenu.Check(self.chk_sounds.GetId(), True)
        self.Bind(wx.EVT_MENU, self.ToggleSounds, self.chk_sounds)

        ## Connection menu
        # Disconnect
        disconnect = wx.MenuItem(connectionMenu, -1, t("ui.menu.disconnect"))
        self.Bind(wx.EVT_MENU, self.OnDisconnect, disconnect)
        connectionMenu.AppendItem(disconnect)

        # Reconnect
        reconnect = wx.MenuItem(connectionMenu, -1, t("ui.menu.reconnect"))
        self.Bind(wx.EVT_MENU, self.OnReconnect, reconnect)
        connectionMenu.AppendItem(reconnect)

        ## Help menu
        # Basics
        basics = wx.MenuItem(helpMenu, -1, t("ui.menu.help_index"))
        self.Bind(wx.EVT_MENU, self.OnBasics, basics)
        helpMenu.AppendItem(basics)

        # News
        new = wx.MenuItem(helpMenu, -1, t("ui.menu.new"))
        self.Bind(wx.EVT_MENU, self.OnNew, new)
        helpMenu.AppendItem(new)

        # Check for updates
        updates = wx.MenuItem(helpMenu, -1, t("ui.menu.updates"))
        self.Bind(wx.EVT_MENU, self.OnCheckForUpdates, updates)
        helpMenu.AppendItem(updates)

        menubar.Append(fileMenu, t("ui.menu.file"))
        menubar.Append(gameMenu, t("ui.menu.game"))
        menubar.Append(connectionMenu, t("ui.menu.connection"))
        menubar.Append(helpMenu, t("ui.menu.help"))

        self.SetMenuBar(menubar)

    def InitUI(self, world=None):
        self.create_updater(just_checking=True)
        session = Session(None, None)
        if world is None:
            dialog = ConnectionDialog(self.engine, session)
            self.connection = dialog
            value = dialog.ShowModal()
            if value == wx.ID_CANCEL:
                self.Close()
                return

            world = session.world
            character = session.character

        self.connection = None
        self.tabs.AddPage(MUDPanel(self.tabs, self, self.engine, world,
                session), world.name)
        self.SetTitle("{} [CocoMUD]".format(world.name))
        self.Maximize()
        self.Show()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        self.tabs.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnTabChanged)
        pub.subscribe(self.disconnectClient, "disconnect")
        pub.subscribe(self.messageClient, "message")

    def OnCreate(self, e):
        """Open the dialog to add a new world."""
        session = Session(None, None)
        world = World("")
        dialog = EditWorldDialog(self.engine, world)
        dialog.ShowModal()
        if not world.name:
            return

        self.SetTitle("{} [CocoMUD]".format(world.name))
        panel = MUDPanel(self.tabs, self, self.engine, world, session)
        panel.CreateClient()
        self.tabs.AddPage(panel, world.name, select=True)
        panel.SetFocus()
        self.sizer.Fit(self)

    def OnOpen(self, e):
        """Open the ConnectionDialog for an additional world."""
        session = Session(None, None)
        dialog = ConnectionDialog(self.engine, session)
        value = dialog.ShowModal()
        if value == wx.ID_CANCEL:
            return

        world = session.world
        self.SetTitle("{} [CocoMUD]".format(world.name))
        panel = MUDPanel(self.tabs, self, self.engine, world, session)
        panel.CreateClient()
        self.tabs.AddPage(panel, world.name, select=True)
        panel.SetFocus()
        self.sizer.Fit(self)

    def OnCloseTab(self, e):
        """Close the current tab."""
        panel = self.panel
        if panel:
            if panel.client:
                panel.client.disconnect()

            for i, tab in enumerate(self.tabs.GetChildren()):
                if tab is panel:
                    self.tabs.DeletePage(i)
                    break

    def OnImportOndisk(self, e):
        """Import a world on disk."""
        choose_file = t("ui.button.choose_file")
        extensions = "Zip archive (*.zip)|*.zip"
        dialog = wx.FileDialog(None, choose_file,
                "", "", extensions, wx.OPEN)
        result = dialog.ShowModal()
        if result == wx.ID_OK:
            filename = dialog.GetPath()

            # Try to install the world from the archive
            archive = ZipFile(filename)
            files = {name: archive.read(name) for name in archive.namelist()}
            options = files.get("world/options.conf")
            if options:
                infos = World.get_infos(options)
                name = infos.get("connection", {}).get("name")
                wizard = InstallWorld(self.engine, name, files)
                wizard.start()

    def OnImportOnline(self, e):
        """Import a world online."""
        task = ImportWorlds()
        task.start()
        dialog = WorldsDialog(self.engine, task.worlds)
        dialog.ShowModal()

    def OnPreferences(self, e):
        """Open the preferences dialog box."""
        dialog = PreferencesDialog(self, self.engine)
        dialog.ShowModal()
        dialog.Destroy()

    def OnConsole(self, e):
        """Open the console dialog box."""
        dialog = ConsoleDialog(self.engine, self.world, self.panel)
        dialog.ShowModal()

    def OnAlias(self, e):
        """Open the alias dialog box."""
        dialog = AliasDialog(self.engine, self.world)
        dialog.ShowModal()
        dialog.Destroy()

    def OnMacro(self, e):
        """Open the macro dialog box."""
        dialog = MacroDialog(self.engine, self.world)
        dialog.ShowModal()
        dialog.Destroy()

    def OnTriggers(self, e):
        """Open the triggers dialog box."""
        dialog = TriggerDialog(self.engine, self.world)
        dialog.ShowModal()
        dialog.Destroy()

    def OnNotepadWorld(self, e):
        """The user selected the Notepad -> World... menu."""
        panel = self.panel
        world = panel.world
        notepad = world.open_notepad()
        dialog = NotepadDialog(notepad)
        dialog.ShowModal()

    def OnNotepadCharacter(self, e):
        """The user selected the Notepad -> Character... menu."""
        panel = self.panel
        character = panel.session.character
        if character is None:
            wx.MessageBox(t("ui.message.notepad.no_character"),
                    t("ui.alert.error"), wx.OK | wx.ICON_ERROR)
        else:
            notepad = character.open_notepad()
            dialog = NotepadDialog(notepad)
            dialog.ShowModal()

    def OnCharacter(self, e):
        """Open the character dialog box."""
        panel = self.panel
        session = panel.session
        dialog = CharacterDialog(self.engine, session)
        dialog.ShowModal()

    def ToggleSounds(self, e):
        """Toggle the "play sounds" checkbox."""
        self.engine.sounds = self.chk_sounds.IsChecked()

    def OnDisconnect(self, e):
        """Disconnect the current client."""
        panel = self.panel
        if panel and panel.client:
            panel.client.disconnect()

    def OnReconnect(self, e):
        """Reconnect the current client."""
        panel = self.panel
        if panel:
            panel.CreateClient()

    def OnBasics(self, e):
        """Open the Basics help file."""
        self.engine.open_help("Basics")

    def OnNew(self, e):
        """Open the Builds help file."""
        self.engine.open_help("Builds")

    def OnCheckForUpdates(self, e):
        """Open the 'check for updates' dialog box."""
        self.create_updater(just_checking=True)
        dialog = LoadingDialog(t("ui.message.update.loading"))
        self.loading = dialog
        dialog.ShowModal()

    def OnQuit(self, e):
        self.OnClose(e)

    def OnClose(self, e):
        """Properly close the interface."""
        self.Destroy()
        if self.engine:
            self.engine.stop()

    def OnActivate(self, e):
        """The window gains or loses focus."""
        if not self or not self.tabs:
            return

        self.focus = e.GetActive()

        # Set all tabs has unfocused
        for tab in self.tabs.GetChildren():
            tab.focus = False
            tab.inside = self.focus

        # Change the focus for the currently selected tab
        panel = self.panel
        if panel:
            panel.focus = True
            if self.focus:
                panel.output.SetFocus()

        if self.focus:
            # Reset the window's title
            if panel:
                world = self.world
                panel.nb_unread = 0
                self.SetTitle("{} [CocoMUD]".format(world.name))
            else:
                self.SetTitle("CocoMUD")

        e.Skip()

    def OnTabChanged(self, e):
        """The current tab has changed."""
        for page in self.tabs.GetChildren():
            page.focus = False

        tab = self.tabs.GetCurrentPage()
        tab.focus = True
        pos = tab.output.GetInsertionPoint()
        tab.output.SetInsertionPoint(pos)
        world = tab.world
        self.SetTitle("{} [CocoMUD]".format(world.name))
        e.Skip()

    def disconnectClient(self, client=None, reason=None):
        """A client disconnects."""
        if not self:
            return

        panel = client.factory.panel
        if panel:
            with self.lock:
                panel.handle_disconnection(reason)

    def messageClient(self, client, message, mark=None):
        """A client receives a message."""
        if not self:
            return

        panel = client.factory.panel
        if panel:
            with self.lock:
                panel.handle_message(message, mark=mark)

    def OnResponseUpdate(self, build=None):
        """The check for updates has returned."""
        if self.loading:
            self.loading.Destroy()
            if build is None:
                message = t("ui.message.update.noupdate")
                wx.MessageBox(message, t("ui.alert.information"),
                        wx.OK | wx.ICON_INFORMATION)

        if build is not None:
            message = t("ui.message.update.available", build=build)
            value = wx.MessageBox(message, t("ui.message.update.title"),
                    wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)

            if value == wx.YES:
                self.CloseAll()
                os.startfile("updater.exe")

