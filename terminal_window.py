"""Defines the TerminalWindow class for KIterm."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')
from gi.repository import Gtk, GLib, Vte, Pango, Gdk
import os

# Import our modules
from ai_panel_controller import AIPanelController
from settings_manager import SettingsManager

class TerminalWindow(Gtk.ApplicationWindow):
    # Constants for zoom functionality
    ZOOM_STEP = 0.1  # Amount to change font scale for each zoom in/out
    MIN_FONT_SCALE = 0.5  # Minimum font scale
    MAX_FONT_SCALE = 3.0  # Maximum font scale
    DEFAULT_FONT_SCALE = 1.0  # Default font scale for reset

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize settings
        self.settings_manager = SettingsManager()

        self.set_default_size(800, 500)
        self.set_title("KIterm")

        # Create a vertical box for terminal area with command generator
        self.terminal_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Create a horizontal paned container
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_child(self.paned)

        # Terminal setup
        self.terminal = Vte.Terminal()
        
        # Configure scrollback buffer size from settings
        self.terminal.set_scrollback_lines(self.settings_manager.scrollback_lines)
        
        # Create a ScrolledWindow to contain the terminal
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.set_child(self.terminal)
        self.scrolled_window.add_css_class("terminal-scrolled-window")
        self.scrolled_window.set_vexpand(True)
        
        # Add the terminal to the terminal area
        self.terminal_area.append(self.scrolled_window)
        
        # Add command generator input
        self.command_generator_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.command_generator_box.set_margin_start(5)
        self.command_generator_box.set_margin_end(5)
        self.command_generator_box.set_margin_top(5)
        self.command_generator_box.set_margin_bottom(5)
        self.command_generator_box.add_css_class("command-generator-box")
        
        self.command_generator_entry = Gtk.Entry()
        self.command_generator_entry.set_placeholder_text("Describe command to generate (Ctrl+Shift+G)...")
        self.command_generator_entry.set_hexpand(True)
        self.command_generator_entry.connect("activate", self._on_command_generator_activate)
        self.command_generator_entry.add_css_class("command-generator-entry")
        self.command_generator_box.append(self.command_generator_entry)
        
        # Add a label to explain the command generator
        command_help_button = Gtk.Button.new_from_icon_name("help-about-symbolic")
        command_help_button.set_tooltip_text("Generate shell commands using AI. Type a description and press Enter.")
        self.command_generator_box.append(command_help_button)
        
        self.terminal_area.append(self.command_generator_box)
        
        # Add the terminal area to the paned container
        self.paned.set_start_child(self.terminal_area)
        self.paned.set_resize_start_child(True)
        
        # Create the AI Chat panel using our panel controller with settings
        self.ai_panel_controller = AIPanelController(self.terminal, self.settings_manager)
        self.chat_panel = self.ai_panel_controller.create_panel()
        
        # Add the chat panel to the paned container
        self.paned.set_end_child(self.chat_panel)
        self.paned.set_resize_end_child(True)
        
        # Set the initial position based on settings
        panel_width = self.settings_manager.default_panel_width
        window_width = self.get_default_size().width
        self.paned.set_position(window_width - panel_width)

        # Configure the terminal
        # Use font scale from settings, falling back to DEFAULT_FONT_SCALE if not set
        initial_scale = round(self.settings_manager.font_scale, 1)
        self.terminal.set_font_scale(initial_scale)
        font_desc = Pango.FontDescription.from_string("MesloLGS NF Regular 12")
        self.terminal.set_font(font_desc)

        # GTK4 way: Add key event controller for keyboard shortcuts
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.terminal.add_controller(key_controller)
        
        # Add shortcut for toggling focus between terminal and command generator
        self._setup_keyboard_shortcuts()

        # Spawn a shell
        # Determine the default shell
        shell = os.environ.get('SHELL', '/bin/zsh')
        
        if not shell or not os.path.exists(shell) or not os.access(shell, os.X_OK):
            # Fallback if SHELL is not set, invalid, or not executable
            # Common shells to try
            possible_shells = ['/bin/zsh', '/bin/bash', '/bin/sh']
            for s in possible_shells:
                if os.path.exists(s) and os.access(s, os.X_OK):
                    shell = s
                    break
            else:
                # If no suitable shell is found, this will likely fail,
                # but it's better than passing a non-existent one.
                shell = '/bin/sh'


        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,     # PTY flags
            os.environ['HOME'],       # Working directory (optional, None for current)
            [shell],                  # Command and arguments (argv)
            [],                       # Environment variables (envv, None for current)
            GLib.SpawnFlags.DEFAULT,  # Spawn flags
            None,                     # Child setup function (GLib.spawn_async_with_fds)
            None,                     # Child setup user data
            -1,                       # Timeout (milliseconds, -1 for no timeout)
            None,                     # Cancellable
            self.on_spawn_finished,   # Callback
            ()                        # Callback user data
        )

        self.terminal.connect("child-exited", self.on_child_exited)
        
        # Register settings change handler
        self.settings_manager.register_settings_change_callback(self.on_settings_changed)

    def _setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts for the window"""
        # Create a shortcut controller
        shortcut_controller = Gtk.ShortcutController()
        shortcut_controller.set_scope(Gtk.ShortcutScope.GLOBAL)
        
        # Toggle focus between terminal and command generator (Ctrl+Shift+G)
        # Using a KeyvalTrigger instead of parse method
        toggle_shortcut = Gtk.Shortcut.new(
            Gtk.KeyvalTrigger.new(Gdk.KEY_g, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK),
            Gtk.CallbackAction.new(self._toggle_focus_callback)
        )
        shortcut_controller.add_shortcut(toggle_shortcut)
        
        # Add the controller to the window
        self.add_controller(shortcut_controller)
    
    def _toggle_focus_callback(self, widget, args):
        """Toggle focus between terminal and command generator entry"""
        # Check if terminal has focus
        if self.terminal.has_focus():
            self.command_generator_entry.grab_focus()
        else:
            # If terminal doesn't have focus, give it focus
            self.terminal.grab_focus()
        return True
    
    def _on_command_generator_activate(self, entry):
        """Handle command generator entry activation (Enter key)"""
        command_request = entry.get_text()
        if command_request and self.ai_panel_controller:
            # Clear the entry
            entry.set_text("")
            # Process the command generation request
            self.ai_panel_controller.handle_command_generation(command_request)
        elif not self.ai_panel_controller:
            print("AI Panel Controller not available")

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handles key press events on the VTE Terminal using GTK4's event controller."""
        # Check for modifier keys
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        
        # Check for Ctrl+Shift+C for copy
        if ctrl and shift and keyval == Gdk.KEY_C:
            # Use the non-deprecated method for copying text to clipboard
            self.terminal.copy_clipboard_format(Vte.Format.TEXT)
            return True  # Event handled
            
        # Check for Ctrl+Shift+V for paste
        if ctrl and shift and keyval == Gdk.KEY_V:
            # Paste text from clipboard
            self.terminal.paste_clipboard()
            return True  # Event handled
            
        # Handle zoom controls if Ctrl is pressed
        if ctrl:
            current_scale = self.terminal.get_font_scale()
            
            # Zoom In: Ctrl + '+' (main keyboard or numpad)
            if keyval == Gdk.KEY_plus or keyval == Gdk.KEY_equal or keyval == Gdk.KEY_KP_Add:
                # Round to 1 decimal place to avoid floating point precision issues
                new_scale = round(min(self.MAX_FONT_SCALE, current_scale + self.ZOOM_STEP), 1)
                self.terminal.set_font_scale(new_scale)
                print(f"Zoom in: new font scale = {new_scale}")
                # Save the new scale to settings
                self.save_font_scale(new_scale)
                return True  # Event handled
            
            # Zoom Out: Ctrl + '-' (main keyboard or numpad)
            elif keyval == Gdk.KEY_minus or keyval == Gdk.KEY_KP_Subtract:
                # Round to 1 decimal place to avoid floating point precision issues
                new_scale = round(max(self.MIN_FONT_SCALE, current_scale - self.ZOOM_STEP), 1)
                self.terminal.set_font_scale(new_scale)
                print(f"Zoom out: new font scale = {new_scale}")
                # Save the new scale to settings
                self.save_font_scale(new_scale)
                return True  # Event handled
            
            # Reset Zoom: Ctrl + '0' (main keyboard or numpad)
            elif keyval == Gdk.KEY_0 or keyval == Gdk.KEY_KP_0:
                self.terminal.set_font_scale(self.DEFAULT_FONT_SCALE)
                print(f"Reset zoom: font scale = {self.DEFAULT_FONT_SCALE}")
                # Save the reset scale to settings
                self.save_font_scale(self.DEFAULT_FONT_SCALE)
                return True  # Event handled
        
        return False  # Event not handled, let VTE process it

    def save_font_scale(self, scale):
        """Save the current font scale to settings"""
        # Round to 1 decimal place for consistency
        rounded_scale = round(scale, 1)
        self.settings_manager.font_scale = rounded_scale
        self.settings_manager.save_settings()
        
    def on_settings_changed(self):
        """Handle settings changes"""
        print("Main Window: Settings changed")
        
        # Update panel width according to settings
        panel_width = self.settings_manager.default_panel_width
        current_width = self.get_width()
        
        # Ensure we don't make the panel too wide for the window
        if panel_width > current_width * 0.8:
            # Limit to 80% of window width
            panel_width = int(current_width * 0.8)
            print(f"  Panel width limited to {panel_width}px (80% of window)")
        
        # Set the new position
        new_position = current_width - panel_width
        print(f"  Updating panel position: {new_position} (window width: {current_width}, panel width: {panel_width})")
        self.paned.set_position(new_position)
        
        # Update font scale if changed through settings dialog
        current_scale = round(self.terminal.get_font_scale(), 1)
        settings_scale = round(self.settings_manager.font_scale, 1)
        if current_scale != settings_scale:
            print(f"  Updating font scale from {current_scale} to {settings_scale}")
            self.terminal.set_font_scale(settings_scale)

    def on_spawn_finished(self, terminal, pid, error, user_data=None):
        # print(f"on_spawn_finished called:")
        # print(f"  self: {self}")
        # print(f"  terminal: {terminal}")
        # print(f"  pid: {pid}")
        # print(f"  error: {error}")
        if user_data is not None:
            print(f"  user_data: {user_data}")

    def on_child_exited(self, terminal, exit_status):
        print(f"Terminal child exited with status: {exit_status}")
        # You might want to close the window or re-spawn, etc.
        # For this simple example, we'll close the window.
        self.close() 