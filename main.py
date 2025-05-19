#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, GLib
import sys

# Import our modules
from terminal_window import TerminalWindow

class MyApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='net.semidark.KIterm')
        GLib.set_application_name('KIterm')

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = TerminalWindow(application=self)
        win.present()

def main():
    app = MyApplication()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

if __name__ == '__main__':
    main() 