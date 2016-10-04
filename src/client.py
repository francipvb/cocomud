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

"""This file contains the client that can connect to a MUD.

It is launched in a new thread, so as not to block the main thread.

"""

import os
import re
from telnetlib import Telnet, WONT, WILL, ECHO
import threading
import time

try:
    from UniversalSpeech import say, braille
except ImportError:
    say = None
    braille = None

from sharp.engine import SharpScript

# Constants
ANSI_ESCAPE = re.compile(r'\x1b[^m]*m')

class Client(threading.Thread):

    """Class to receive data from the MUD."""

    def __init__(self, host, port=4000, timeout=0.1, engine=None):
        """Connects to the MUD."""
        threading.Thread.__init__(self)
        self.client = None
        self.timeout = timeout
        self.engine = engine
        self.running = False
        self.sharp_engine = SharpScript(engine, self)
        self.triggers = []

        # Try to connect to the specified host and port
        self.client = Telnet(host, port)
        self.running = True

    def run(self):
        """Run the thread."""
        while self.running:
            time.sleep(self.timeout)
            msg = self.client.read_very_eager()
            if msg:
                for line in msg.splitlines():
                    for trigger in self.triggers:
                        trigger.feed(line)

                self.handle_message(msg)

    def handle_message(self, msg):
        """When the client receives a message."""
        pass

    def write(self, text):
        """Write text to the client."""
        if text.startswith("#"):
            self.sharp_engine.execute(text)
        else:
            self.client.write(text)


class GUIClient(Client):

    """Client specifically linked to a GUI window.

    This client proceeds to send the text it receives to the frame.

    """

    def __init__(self, host, port=4000, timeout=0.1, engine=None):
        Client.__init__(self, host, port, timeout, engine)
        self.window = None
        if self.client:
            self.client.set_option_negotiation_callback(self.handle_option)

    def load_script(self, world):
        """Load the config.set script."""
        path = world.path
        path = os.path.join(path, "config.set")
        if os.path.exists(path):
            file = open(path, "r")
            content = file.read()
            file.close()

            # Execute the script
            self.sharp_engine.execute(content)

    def link_window(self, window):
        """Link to a window (a GUI object).

        This objectt can be of various types.  The client only interacts
        with it in two ways:  First, whenever it receives a message,
        it sends it to the window's 'handle_message' method.  It also
        calls the window's 'handle_option' method whenever it receives
        a Telnet option that it can recognize.

        """
        self.window = window
        window.client = self
        self.load_script(window.world)

    def handle_message(self, msg):
        """When the client receives a message."""
        encoding = self.engine.settings["options.general.encoding"]
        msg = msg.decode(encoding, "replace")
        msg = ANSI_ESCAPE.sub('', msg)
        if self.window:
            self.window.handle_message(msg)

        # In any case, tries to find the TTS
        if self.engine.TTS_on:
            # If outside of the window
            window = self.window
            focus = window.focus if window else True
            if not focus and not self.engine.settings["options.TTS.outside"]:
                return

            if say and braille:
                say(msg, interrupt=False)
                braille(msg)

    def handle_option(self, socket, command, option):
        """Handle a received option."""
        name = ""
        if command == WILL and option == ECHO:
            name = "hide"
        elif command == WONT and option == ECHO:
            name = "show"

        if name and self.window:
            self.window.handle_option(name)
