"""Settings Manager for KIterm AI Assistant"""

import os
import json
from gi.repository import Gtk, GLib

class SettingsManager:
    """Manages settings for the KIterm AI Assistant"""
    
    def __init__(self):
        """Initialize the settings manager"""
        # Set default settings
        self.api_url = 'https://api.openai.com/v1/chat/completions'
        self.api_key = ''
        self.model = 'gpt-3.5-turbo'
        self.default_panel_width = 300  # Default width of the assistant panel in pixels
        self.streaming_enabled = True  # Enable streaming by default
        self.font_scale = 1.0  # Default terminal font scale
        self.scrollback_lines = 1000  # Default scrollback buffer size
        
        # Define the settings file location
        self.config_dir = os.path.join(GLib.get_user_config_dir(), 'kiterm')
        self.settings_file = os.path.join(self.config_dir, 'settings.json')
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load settings from file or use defaults
        self.load_settings()
        
        # Register callbacks for settings changes
        self.settings_change_callbacks = []
    
    def load_settings(self):
        """Load settings from the settings file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    
                    # Apply settings from file, maintaining defaults for missing values
                    self.api_url = settings.get('api_url', self.api_url)
                    self.api_key = settings.get('api_key', self.api_key)
                    self.model = settings.get('model', self.model)
                    self.default_panel_width = int(settings.get('panel_width', self.default_panel_width))
                    self.streaming_enabled = settings.get('streaming_enabled', self.streaming_enabled)
                    self.font_scale = float(settings.get('font_scale', self.font_scale))
                    self.scrollback_lines = int(settings.get('scrollback_lines', self.scrollback_lines))
                    
                    # Convert string to boolean if needed
                    if isinstance(self.streaming_enabled, str):
                        self.streaming_enabled = self.streaming_enabled.lower() == 'true'
                        
                print(f"Settings loaded from {self.settings_file}")
        except Exception as e:
            print(f"Error loading settings: {str(e)}")
            print("Using default settings")
    
    def save_settings(self):
        """Save settings to the settings file"""
        try:
            settings_dict = {
                'api_url': self.api_url,
                'api_key': self.api_key,
                'model': self.model,
                'panel_width': self.default_panel_width,
                'streaming_enabled': self.streaming_enabled,
                'font_scale': self.font_scale,
                'scrollback_lines': self.scrollback_lines
            }
            
            with open(self.settings_file, 'w') as f:
                json.dump(settings_dict, f, indent=4)
                
            print(f"Settings saved to {self.settings_file}")
            
            # Notify listeners about settings change
            self.notify_settings_changed()
        except Exception as e:
            print(f"Error saving settings: {str(e)}")
    
    def register_settings_change_callback(self, callback):
        """Register a callback to be called when settings change"""
        if callback not in self.settings_change_callbacks:
            self.settings_change_callbacks.append(callback)
    
    def remove_settings_change_callback(self, callback):
        """Remove a previously registered callback"""
        if callback in self.settings_change_callbacks:
            self.settings_change_callbacks.remove(callback)
    
    def notify_settings_changed(self):
        """Notify all registered callbacks about settings changes"""
        for callback in self.settings_change_callbacks:
            callback()
    
    def open_settings_dialog(self, parent_window=None):
        """Open the settings dialog"""
        # Create the dialog with proper parent
        settings_dialog = Gtk.Dialog(
            title="AI Assistant Settings",
            transient_for=parent_window,
            modal=True,
            destroy_with_parent=True
        )
        
        # If no parent window was provided but we're in a GTK application,
        # try to find the active window to use as parent
        if parent_window is None:
            # First try to get the active window from the application
            app = Gtk.Application.get_default()
            if app:
                active_window = app.get_active_window()
                if active_window:
                    settings_dialog.set_transient_for(active_window)
                    print("Setting dialog parent to active application window")
        
        settings_dialog.set_default_size(500, 250)
        
        # Add buttons
        cancel_button = settings_dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        save_button = settings_dialog.add_button("Save", Gtk.ResponseType.APPLY)
        
        # Get the content area
        content_area = settings_dialog.get_content_area()
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_spacing(6)
        
        # Create settings form
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(6)
        
        # API URL
        url_label = Gtk.Label(label="API URL:")
        url_label.set_halign(Gtk.Align.START)
        grid.attach(url_label, 0, 0, 1, 1)
        
        url_entry = Gtk.Entry()
        url_entry.set_text(self.api_url)
        url_entry.set_hexpand(True)
        grid.attach(url_entry, 1, 0, 1, 1)
        
        # Help text for Ollama
        ollama_label = Gtk.Label()
        ollama_label.set_markup("<small>For Ollama use: http://localhost:11434/v1/chat/completions</small>")
        ollama_label.set_halign(Gtk.Align.START)
        grid.attach(ollama_label, 1, 1, 1, 1)
        
        # API Key
        key_label = Gtk.Label(label="API Key:")
        key_label.set_halign(Gtk.Align.START)
        grid.attach(key_label, 0, 2, 1, 1)
        
        key_entry = Gtk.Entry()
        key_entry.set_visibility(False)  # Password-style entry
        key_entry.set_text(self.api_key)
        grid.attach(key_entry, 1, 2, 1, 1)
        
        # Help text for API key
        key_help_label = Gtk.Label()
        key_help_label.set_markup("<small>Leave empty for Ollama or local LLMs</small>")
        key_help_label.set_halign(Gtk.Align.START)
        grid.attach(key_help_label, 1, 3, 1, 1)
        
        # Model
        model_label = Gtk.Label(label="Model:")
        model_label.set_halign(Gtk.Align.START)
        grid.attach(model_label, 0, 4, 1, 1)
        
        model_entry = Gtk.Entry()
        model_entry.set_text(self.model)
        grid.attach(model_entry, 1, 4, 1, 1)
        
        # Help text for model name
        model_help_label = Gtk.Label()
        model_help_label.set_markup("<small>For Ollama, use the name of your installed model (e.g., llama3)</small>")
        model_help_label.set_halign(Gtk.Align.START)
        grid.attach(model_help_label, 1, 5, 1, 1)
        
        # Panel width
        width_label = Gtk.Label(label="Panel Width:")
        width_label.set_halign(Gtk.Align.START)
        grid.attach(width_label, 0, 6, 1, 1)
        
        adjustment = Gtk.Adjustment(value=self.default_panel_width, lower=100, upper=800, step_increment=10, page_increment=50, page_size=0)
        width_spin = Gtk.SpinButton()
        width_spin.set_adjustment(adjustment)
        width_spin.set_numeric(True)
        width_spin.set_value(self.default_panel_width)
        grid.attach(width_spin, 1, 6, 1, 1)
        
        # Help text for width
        width_help_label = Gtk.Label()
        width_help_label.set_markup("<small>Default width of the assistant panel in pixels</small>")
        width_help_label.set_halign(Gtk.Align.START)
        grid.attach(width_help_label, 1, 7, 1, 1)
        
        # Streaming mode
        streaming_label = Gtk.Label(label="Streaming Mode:")
        streaming_label.set_halign(Gtk.Align.START)
        grid.attach(streaming_label, 0, 8, 1, 1)
        
        streaming_switch = Gtk.Switch()
        streaming_switch.set_active(self.streaming_enabled)
        streaming_switch.set_halign(Gtk.Align.START)
        grid.attach(streaming_switch, 1, 8, 1, 1)
        
        # Help text for streaming
        streaming_help_label = Gtk.Label()
        streaming_help_label.set_markup("<small>Enable to see AI responses as they're generated. Might not work with all LLM providers.</small>")
        streaming_help_label.set_halign(Gtk.Align.START)
        grid.attach(streaming_help_label, 1, 9, 1, 1)
        
        # Font Scale
        font_scale_label = Gtk.Label(label="Font Scale:")
        font_scale_label.set_halign(Gtk.Align.START)
        grid.attach(font_scale_label, 0, 10, 1, 1)
        
        font_scale_adjustment = Gtk.Adjustment(value=self.font_scale, lower=0.5, upper=3.0, step_increment=0.1, page_increment=0.5, page_size=0)
        font_scale_spin = Gtk.SpinButton()
        font_scale_spin.set_adjustment(font_scale_adjustment)
        font_scale_spin.set_digits(1)  # Show one decimal place
        font_scale_spin.set_numeric(True)
        font_scale_spin.set_value(self.font_scale)
        grid.attach(font_scale_spin, 1, 10, 1, 1)
        
        # Help text for font scale
        font_scale_help_label = Gtk.Label()
        font_scale_help_label.set_markup("<small>Terminal font size scale (Ctrl+Plus/Minus to change while using)</small>")
        font_scale_help_label.set_halign(Gtk.Align.START)
        grid.attach(font_scale_help_label, 1, 11, 1, 1)
        
        # Scrollback Buffer Size
        scrollback_label = Gtk.Label(label="Scrollback Lines:")
        scrollback_label.set_halign(Gtk.Align.START)
        grid.attach(scrollback_label, 0, 12, 1, 1)
        
        scrollback_adjustment = Gtk.Adjustment(value=self.scrollback_lines, lower=100, upper=100000, step_increment=100, page_increment=1000, page_size=0)
        scrollback_spin = Gtk.SpinButton()
        scrollback_spin.set_adjustment(scrollback_adjustment)
        scrollback_spin.set_numeric(True)
        scrollback_spin.set_value(self.scrollback_lines)
        grid.attach(scrollback_spin, 1, 12, 1, 1)
        
        # Help text for scrollback
        scrollback_help_label = Gtk.Label()
        scrollback_help_label.set_markup("<small>Number of lines to keep in terminal scrollback history</small>")
        scrollback_help_label.set_halign(Gtk.Align.START)
        grid.attach(scrollback_help_label, 1, 13, 1, 1)
        
        content_area.append(grid)
        
        # In GTK4, we need to connect to signals instead of using run()
        def on_response(dialog, response_id):
            if response_id == Gtk.ResponseType.APPLY:
                # Save the settings
                self.api_url = url_entry.get_text()
                self.api_key = key_entry.get_text()
                self.model = model_entry.get_text()
                self.default_panel_width = int(width_spin.get_value())
                self.streaming_enabled = streaming_switch.get_active()
                self.font_scale = float(font_scale_spin.get_value())
                self.scrollback_lines = int(scrollback_spin.get_value())
                
                # Save to file
                self.save_settings()
            
            # Close the dialog
            dialog.destroy()
        
        # Connect response signal
        settings_dialog.connect("response", on_response)
        
        # Present the dialog and make sure it gets focus
        settings_dialog.present()
        
        # Explicitly set focus to the dialog
        url_entry.grab_focus()
        
        # Make sure the dialog gets focus even if terminal has focus
        def ensure_focus():
            if url_entry and not url_entry.has_focus():
                url_entry.grab_focus()
                settings_dialog.set_focus(url_entry)
            return False
        
        # Schedule focus grab after a short delay
        GLib.timeout_add(100, ensure_focus) 