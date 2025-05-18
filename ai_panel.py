"""AI Panel Manager for KIterm"""

import os
import time
from gi.repository import Gtk, GLib, Pango, Gdk, Vte

class AIPanelManager:
    """Manages the AI Chat panel in KIterm"""
    
    def __init__(self, terminal, settings_manager):
        """Initialize the panel manager"""
        self.terminal = terminal
        self.settings_manager = settings_manager
        self.panels = {}
        self.parent_window = None
        
        # Add CSS provider for custom styling
        self._add_css_styling()
        
        # Register for settings changes
        self.settings_manager.register_settings_change_callback(self.on_settings_changed)
    
    def _add_css_styling(self):
        """Add CSS styling for the panel components"""
        css_provider = Gtk.CssProvider()
        
        # Get the absolute path to the CSS file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        css_file_path = os.path.join(current_dir, "styles.css")
        
        try:
            css_provider.load_from_path(css_file_path)
            print(f"Loaded CSS from {css_file_path}")
        except Exception as e:
            print(f"Failed to load CSS from {css_file_path}: {str(e)}")
            # Fallback to basic built-in CSS
            basic_css = b"""
            .ai-panel { background-color: @theme_bg_color; }
            .ai-message { background-color: alpha(@theme_bg_color, 0.6); border-radius: 8px; padding: 8px; margin: 4px; }
            .user-message { background-color: alpha(@theme_selected_bg_color, 0.1); border-radius: 8px; padding: 8px; margin: 4px; }
            .system-message { color: @theme_selected_fg_color; font-style: italic; margin: 4px; font-size: 0.9em; }
            """
            css_provider.load_from_data(basic_css)
        
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
    
    def create_panel(self):
        """Create the AI assistant panel"""
        # Create the main panel
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel.set_margin_start(6)
        panel.set_margin_end(6)
        panel.set_margin_top(6)
        panel.set_margin_bottom(6)
        
        # Find the parent window for dialogs
        self.parent_window = self.terminal.get_root()
        
        # Add header with title and buttons
        header = self._create_header()
        panel.append(header)
        
        # Terminal preview section (collapsible)
        terminal_preview_expander = Gtk.Expander(label="Terminal Preview")
        terminal_preview_expander.set_expanded(False)
        
        terminal_preview_scroll = Gtk.ScrolledWindow()
        terminal_preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        terminal_preview_scroll.set_min_content_height(100)
        terminal_preview_scroll.set_max_content_height(200)
        
        terminal_preview_view = Gtk.TextView()
        terminal_preview_view.set_editable(False)
        terminal_preview_view.set_cursor_visible(False)
        terminal_preview_view.set_wrap_mode(Gtk.WrapMode.CHAR)
        terminal_preview_view.add_css_class("terminal-preview-content")
        
        # In GTK4, we use CSS classes instead of override_font
        terminal_preview_view.add_css_class("monospace-text")
        
        terminal_preview_scroll.set_child(terminal_preview_view)
        terminal_preview_expander.set_child(terminal_preview_scroll)
        
        panel.append(terminal_preview_expander)
        
        # Create chat interface with proper conversation view
        chat_scroll = Gtk.ScrolledWindow()
        chat_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        chat_scroll.set_hexpand(True)
        chat_scroll.set_vexpand(True)
        chat_scroll.add_css_class("ai-scrolled-window")
        
        # Use a VBox for the conversation container
        chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        chat_box.set_margin_start(8)
        chat_box.set_margin_end(8)
        chat_box.set_margin_top(8)
        chat_box.set_margin_bottom(8)
        
        chat_scroll.set_child(chat_box)
        panel.append(chat_scroll)
        
        # Query input
        query_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        query_box.add_css_class("ai-input")
        query_entry = Gtk.Entry()
        query_entry.set_placeholder_text("Type your question here...")
        query_entry.connect("activate", self.on_send_clicked)
        query_box.append(query_entry)
        
        send_button = Gtk.Button.new_with_label("Ask AI")
        send_button.connect("clicked", self.on_send_clicked)
        query_box.append(send_button)
        
        panel.append(query_box)
        
        # Store references to UI components
        self.panels = {
            'panel': panel,
            'chat_box': chat_box,
            'terminal_preview_view': terminal_preview_view,
            'terminal_preview_expander': terminal_preview_expander,
            'query_entry': query_entry,
            'conversation': [],
        }
        
        # Add welcome message
        self.add_system_message("Welcome to KIterm AI Assistant. Ask questions about your terminal session or for help with commands.")
        
        return panel
    
    def _create_header(self):
        """Create the header with title and buttons"""
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.add_css_class("ai-header")
        
        # Title
        title_label = Gtk.Label.new("AI Chat")
        title_label.set_hexpand(True)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_start(4)
        header_box.append(title_label)
        
        # Settings button
        settings_button = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        settings_button.set_tooltip_text("Settings")
        settings_button.connect("clicked", self.on_settings_clicked)
        header_box.append(settings_button)
        
        # Refresh button
        refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh Terminal Preview")
        refresh_button.connect("clicked", self.on_refresh_clicked)
        header_box.append(refresh_button)
        
        # Clear button
        clear_button = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
        clear_button.set_tooltip_text("Clear Conversation")
        clear_button.connect("clicked", self.on_clear_clicked)
        header_box.append(clear_button)
        
        return header_box
    
    def on_settings_clicked(self, widget):
        """Handle settings button click"""
        print("Settings button clicked")
        # Open the settings dialog
        self.settings_manager.open_settings_dialog(self.parent_window)
    
    def on_settings_changed(self):
        """Handle settings changes"""
        # Show more detailed information about settings changes
        print("AI Panel: Settings changed")
        print(f"  API URL: {self.settings_manager.api_url}")
        print(f"  Model: {self.settings_manager.model}")
        print(f"  Panel Width: {self.settings_manager.default_panel_width}px")
        print(f"  Streaming: {self.settings_manager.streaming_enabled}")
        
        # Add a system message with the updated settings
        api_info = (
            f"Settings updated:\n"
            f"• API: {self.settings_manager.api_url}\n"
            f"• Model: {self.settings_manager.model}\n" 
            f"• Panel Width: {self.settings_manager.default_panel_width}px\n"
            f"• Streaming: {'Enabled' if self.settings_manager.streaming_enabled else 'Disabled'}"
        )
        self.add_system_message(api_info)
    
    def on_refresh_clicked(self, widget):
        """Handle refresh button click"""
        print("Refresh button clicked")
        
        # Get terminal content using our dedicated method
        terminal_content = self._get_terminal_content()
        
        # Update terminal preview
        buffer = self.panels['terminal_preview_view'].get_buffer()
        buffer.set_text(terminal_content)
        
        # Always expand the preview when refreshing
        self.panels['terminal_preview_expander'].set_expanded(True)
    
    def on_clear_clicked(self, widget):
        """Handle clear button click"""
        print("Clear button clicked")
        # Clear the chat box - in GTK4 we need to remove all children
        chat_box = self.panels['chat_box']
        while chat_box.get_first_child():
            chat_box.remove(chat_box.get_first_child())
        
        # Clear the conversation array
        self.panels['conversation'] = []
        
        # Add a new welcome message
        self.add_system_message("Conversation cleared. Ask a new question.")
    
    def on_send_clicked(self, widget):
        """Handle send button click or Enter key in query entry"""
        query = self.panels['query_entry'].get_text()
        if not query.strip():
            return
        
        # Add user message to conversation
        self.add_user_message(query)
        
        # Clear the entry
        self.panels['query_entry'].set_text("")
        
        # Get terminal content for context
        terminal_content = self._get_terminal_content()
        
        # For now, just simulate a response
        # Later we'll implement real API calls with the settings
        api_info = f"API URL: {self.settings_manager.api_url}\nModel: {self.settings_manager.model}\nStreaming: {self.settings_manager.streaming_enabled}"
        self.add_ai_message(f"This is a simulated response to: '{query}'\n\nYour terminal currently contains:\n```\n{terminal_content[:100]}...\n```\n\nSettings:\n{api_info}")
    
    def _get_terminal_content(self):
        """Get the current content of the terminal"""
        try:
            # Access the VTE terminal
            vte = self.terminal
            
            try:
                # For GTK4/VTE 0.70+, this is the preferred method
                content = vte.get_text_format(Vte.Format.TEXT)
                if content:
                    return content
            except Exception as e:
                print(f"Error with get_text_format: {str(e)}")
                
                # Try alternative methods
                try:
                    # For older VTE versions
                    content = vte.get_text(None, None)
                    if content:
                        return content
                except Exception as e2:
                    print(f"Error with get_text: {str(e2)}")
                    
                    # Last resort
                    try:
                        col, row = vte.get_cursor_position()
                        content = vte.get_text_range(0, 0, row, col, None)
                        if content:
                            return content
                    except Exception as e3:
                        print(f"Error with get_text_range: {str(e3)}")
            
            print("All terminal content extraction methods failed")
            return "No terminal content available."
        except Exception as e:
            print(f"Error getting terminal content: {str(e)}")
            return f"Error retrieving terminal content: {str(e)}"
    
    def add_message(self, text, message_type):
        """Add a message to the conversation"""
        # Create a message container
        message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        message_box.add_css_class(message_type)
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        timestamp_label = Gtk.Label.new(timestamp)
        timestamp_label.set_halign(Gtk.Align.END)
        timestamp_label.add_css_class("timestamp")
        message_box.append(timestamp_label)
        
        # Create a text view for the message content
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        
        # Add the text to the buffer
        buffer = text_view.get_buffer()
        buffer.set_text(text)
        
        message_box.append(text_view)
        
        # Add to chat box
        self.panels['chat_box'].append(message_box)
        
        # Store in conversation history
        self.panels['conversation'].append({
            'type': message_type,
            'text': text,
            'timestamp': timestamp
        })
        
        # Scroll to bottom - this is a workaround for GTK4
        GLib.idle_add(self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        """Scroll the chat view to the bottom"""
        # In GTK4, we need a different approach to scroll to bottom
        chat_box = self.panels['chat_box']
        last_child = None
        
        # Find the last child
        child = chat_box.get_first_child()
        while child:
            last_child = child
            child = child.get_next_sibling()
        
        # Focus on the last child to scroll to it
        if last_child:
            last_child.grab_focus()
    
    def add_system_message(self, text):
        """Add a system message to the conversation"""
        self.add_message(text, "system-message")
    
    def add_user_message(self, text):
        """Add a user message to the conversation"""
        self.add_message(text, "user-message")
    
    def add_ai_message(self, text):
        """Add an AI message to the conversation"""
        self.add_message(text, "ai-message") 