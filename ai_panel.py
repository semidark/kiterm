"""AI Panel Manager for KIterm"""

import os
import time
import re
from gi.repository import Gtk, GLib, Pango, Gdk, Vte
from api_handler import APIHandler
from markdown_formatter import MarkdownFormatter

class AIPanelManager:
    """Manages the AI Chat panel in KIterm"""
    
    def __init__(self, terminal, settings_manager):
        """Initialize the panel manager"""
        self.terminal = terminal
        self.settings_manager = settings_manager
        self.panels = {}
        self.parent_window = None
        
        # Create API handler
        self.api_handler = APIHandler(settings_manager)
        
        # Create markdown formatter
        self.markdown_formatter = MarkdownFormatter()
        
        # Add CSS provider for custom styling
        self._add_css_styling()
        
        # Register for settings changes
        self.settings_manager.register_settings_change_callback(self.on_settings_changed)
        
        # Streaming update rate limiting
        self.last_stream_update_time = 0
        self.stream_update_interval = 50  # Minimum ms between updates
        self.pending_stream_text = None
        self.stream_update_timeout_id = None
        
        # Scroll handling
        self.last_scroll_time = 0
        self.scroll_timeout_id = None
        self.auto_scroll_locked = False  # True if user has scrolled up
        self.is_programmatic_scroll = False  # True during our own scroll operations
        
        # Resize handling
        self.resize_timeout_id = None
        self.resize_active = False
        self.last_resize_height = 0
        
        # Debug mode - set to False for production
        self.debug_mode = False
    
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
        
        # Connect to vadjustment changes to detect user scrolling
        vadj = chat_scroll.get_vadjustment()
        if vadj:
            vadj.connect("value-changed", self._on_vadj_changed)
        
        # Use a VBox for the conversation container
        chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        chat_box.set_margin_start(8)
        chat_box.set_margin_end(8)
        chat_box.set_margin_top(8)
        chat_box.set_margin_bottom(8)
        
        chat_scroll.set_child(chat_box)
        panel.append(chat_scroll)
        
        # Query input
        query_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        query_box.add_css_class("ai-input")
        
        # Create a horizontal box for the input field and buttons
        input_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        # Replace Entry with TextView inside a ScrolledWindow
        query_entry = Gtk.TextView()
        query_entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        query_entry.set_accepts_tab(False)  # Allow tabbing out of the TextView
        query_entry.set_hexpand(True)
        query_entry.set_vexpand(False)  # Don't allow text view to expand by default

        # Create scrolled window for the input field
        query_scroll = Gtk.ScrolledWindow()
        query_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC) # No hbar, vbar auto
        query_scroll.set_child(query_entry)
        query_scroll.set_hexpand(True)
        query_scroll.set_vexpand(False)  # Don't expand vertically by default
        
        # Calculate dynamic starting height for the input area
        context = query_entry.get_pango_context()
        font_description = context.get_font_description() 
        if font_description is None: # Fallback if no font description yet
            font_description = Pango.FontDescription.from_string("Sans 10") # A sensible default

        language = Pango.Language.get_default() # language can be None
        metrics = context.get_metrics(font_description, language) 
        
        single_line_height_pango = metrics.get_ascent() + metrics.get_descent()
        single_line_height_pixels = single_line_height_pango / Pango.SCALE
        
        input_padding = 12  # Total vertical padding (e.g., 6px top + 6px bottom)
        min_input_height = int(single_line_height_pixels + input_padding)

        # Set initial height using fixed height constraint
        query_scroll.set_size_request(-1, min_input_height) # Width: unchanged, Height: single line
        
        # Add a resize handle above the input field
        resize_handle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        resize_handle.set_size_request(-1, 6)  # Height of 6 pixels
        resize_handle.add_css_class("resize-handle")
        
        # Make the handle draggable
        drag_controller = Gtk.GestureDrag.new()
        drag_controller.connect("drag-begin", self._on_resize_begin)
        drag_controller.connect("drag-update", self._on_resize_update)
        drag_controller.connect("drag-end", self._on_resize_end)
        resize_handle.add_controller(drag_controller)
        
        # Add cursor change to indicate resize handle
        motion_controller = Gtk.EventControllerMotion.new()
        motion_controller.connect("enter", self._on_handle_enter)
        motion_controller.connect("leave", self._on_handle_leave)
        resize_handle.add_controller(motion_controller)
        
        # Add key event controller for keyboard shortcuts
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        query_entry.add_controller(key_controller)
        
        # Add all components to the query box
        query_box.append(resize_handle)
        input_button_box.append(query_scroll)
        
        send_button = Gtk.Button.new_with_label("Ask AI")
        send_button.connect("clicked", self.on_send_clicked)
        send_button.set_valign(Gtk.Align.CENTER)  # Center the button vertically
        send_button.set_vexpand(False)  # Don't let the button expand vertically
        send_button.set_size_request(-1, min_input_height)  # Match the height of the single-line input
        input_button_box.append(send_button)
        
        # Stop button (initially hidden)
        stop_button = Gtk.Button.new_with_label("Stop")
        stop_button.connect("clicked", self.on_stop_clicked)
        stop_button.set_visible(False)
        stop_button.set_valign(Gtk.Align.CENTER)  # Center the button vertically
        stop_button.set_vexpand(False)  # Don't let the button expand vertically
        stop_button.set_size_request(-1, min_input_height)  # Match the height of the single-line input
        input_button_box.append(stop_button)
        
        query_box.append(input_button_box)
        
        panel.append(query_box)
        
        # Store references to UI components
        self.panels = {
            'panel': panel,
            'chat_box': chat_box,
            'chat_scroll': chat_scroll,  # Store direct reference to ScrolledWindow
            'terminal_preview_view': terminal_preview_view,
            'terminal_preview_expander': terminal_preview_expander,
            'query_entry': query_entry,
            'query_scroll': query_scroll,  # Store reference to the ScrolledWindow
            'send_button': send_button,
            'stop_button': stop_button,
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
        
        # Raw message button (keeping this as it's useful for development)
        raw_button = Gtk.Button.new_from_icon_name("dialog-information-symbolic")
        raw_button.set_tooltip_text("Show Raw Message")
        raw_button.connect("clicked", self._on_show_raw_clicked)
        header_box.append(raw_button)
        
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
    
    def _show_raw_message_dialog(self, message):
        """Show a dialog with the raw message content for debugging"""
        dialog = Gtk.Dialog(
            title="Raw Message Content",
            parent=self.parent_window,
            modal=True
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(600, 400)
        
        content_area = dialog.get_content_area()
        
        # Add a label with instructions
        label = Gtk.Label(label="This is the raw message content received from the API:")
        label.set_margin_top(10)
        label.set_margin_bottom(10)
        label.set_margin_start(10)
        label.set_margin_end(10)
        content_area.append(label)
        
        # Create a scrolled window for the text view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_margin_bottom(10)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        
        # Create a text view for the message content
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.add_css_class("monospace-text")
        
        buffer = text_view.get_buffer()
        buffer.set_text(message)
        
        scrolled.set_child(text_view)
        content_area.append(scrolled)
        
        # Connect response signal
        dialog.connect("response", lambda dialog, response_id: dialog.destroy())
        
        # Show the dialog
        dialog.present()
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events in GTK4"""
        # Check for ESC key (GDK_KEY_Escape = 65307)
        if keyval == 65307:
            self.stop_active_request()
            return True  # Signal that the event was handled
        
        # Check for Enter key to send message (without Shift)
        if (keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter):
            # Check if Shift modifier is NOT pressed
            if not (state & Gdk.ModifierType.SHIFT_MASK):
                self.on_send_clicked(None)  # Pass None as widget argument
                return True  # Event handled, don't insert a newline
            # If Shift+Enter, let the default handler add a newline
        
        return False  # Allow other handlers to process the event
    
    def on_stop_clicked(self, widget):
        """Handle stop button click"""
        self.stop_active_request()
    
    def stop_active_request(self):
        """Stop the active API request"""
        if not self.panels.get('stream_active', False):
            return
            
        # Cancel the API request
        self.api_handler.cancel_active_request()
        
        # Clear the stream active flag
        self.panels['stream_active'] = False
        
        # Stop typing animation if it's running
        self._stop_typing_animation()
        
        # Cancel any pending stream updates
        if self.stream_update_timeout_id:
            GLib.source_remove(self.stream_update_timeout_id)
            self.stream_update_timeout_id = None
            
        # Cancel any pending scroll updates
        if self.scroll_timeout_id:
            GLib.source_remove(self.scroll_timeout_id)
            self.scroll_timeout_id = None
        
        # Update the UI to show the send button
        self._update_button_state()
        
        # Add a note that the request was canceled
        if 'current_response_buffer' in self.panels and self.panels['current_response_buffer']:
            buffer = self.panels['current_response_buffer']
            
            # Try to get the current text in the buffer
            try:
                current_text = self.markdown_formatter.get_buffer_text(buffer)
            except AttributeError:
                # Fallback if get_buffer_text is not available
                start_iter = buffer.get_start_iter()
                end_iter = buffer.get_end_iter()
                current_text = buffer.get_text(start_iter, end_iter, False)
            
            # Save the partial response for raw message display
            if current_text.strip():
                # Store the partial response with a note about cancelation
                self.last_full_response = current_text + "\n\n[Response canceled by user]"
                
                # Append cancelation note to the displayed message
                updated_text = current_text + "\n\n*Request canceled by user*"
                self.markdown_formatter.format_markdown(buffer, updated_text)
            else:
                # If there was no response yet, just show the cancellation note
                self.markdown_formatter.format_markdown(buffer, "*Request canceled by user*")
                self.last_full_response = "[Response canceled by user before any content was received]"
            
            # Remove the current buffer reference
            del self.panels['current_response_buffer']
            
        return True  # Signal that cancellation was successful
    
    def on_send_clicked(self, widget):
        """Handle send button click or Enter key in query entry"""
        # Get text from TextView buffer
        text_view = self.panels['query_entry']
        buffer = text_view.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        query = buffer.get_text(start_iter, end_iter, True).strip() # True to include hidden chars
        
        if not query:
            return
        
        # Add user message to conversation
        self.add_user_message(query)
        
        # Clear the TextView buffer
        buffer.set_text("")
        
        # Toggle buttons
        if 'send_button' in self.panels and 'stop_button' in self.panels:
            self.panels['send_button'].set_visible(False)
            self.panels['stop_button'].set_visible(True)
        
        # Get terminal content for context
        terminal_content = self._get_terminal_content()
        
        # Get conversation history
        conversation_history = self.panels.get('conversation', [])
        
        # Prepare for streaming if enabled
        if self.settings_manager.streaming_enabled:
            self._prepare_for_streaming()
        
        # Send query to API handler
        self.api_handler.send_request(
            query=query,
            terminal_content=terminal_content,
            update_callback=self._update_streaming_text,
            complete_callback=self._on_response_complete,
            error_callback=self._on_api_error,
            conversation_history=conversation_history
        )
    
    def _prepare_for_streaming(self):
        """Prepare for streaming response"""
        # Create empty AI message box that will be updated during streaming
        message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        message_box.add_css_class("ai-message")
        
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
        
        # Add typing indicator 
        buffer = text_view.get_buffer()
        buffer.set_text("Thinking...")
        
        message_box.append(text_view)
        
        # Add to chat box
        self.panels['chat_box'].append(message_box)
        
        # Store reference to this message for streaming updates
        self.panels['current_response_box'] = message_box
        self.panels['current_response_buffer'] = buffer
        self.panels['current_text_view'] = text_view
        self.panels['stream_active'] = True
        
        # Start typing animation
        self._start_typing_animation(buffer)
        
        # Schedule scrolling after the UI has been updated
        GLib.idle_add(self._scroll_to_bottom)
    
    def _start_typing_animation(self, buffer):
        """Start the typing indicator animation"""
        self.panels['typing_animation_active'] = True
        self.panels['typing_indicator_pos'] = 0
        
        def update_indicator():
            if not self.panels.get('typing_animation_active', False):
                return False  # Stop the animation
                
            indicators = ["Thinking.", "Thinking..", "Thinking..."]
            pos = self.panels['typing_indicator_pos']
            buffer.set_text(indicators[pos])
            
            self.panels['typing_indicator_pos'] = (pos + 1) % len(indicators)
            return True  # Continue the animation
        
        # Run animation every 500ms
        self.panels['typing_animation_id'] = GLib.timeout_add(500, update_indicator)
    
    def _stop_typing_animation(self):
        """Stop the typing indicator animation"""
        self.panels['typing_animation_active'] = False
        if 'typing_animation_id' in self.panels and self.panels['typing_animation_id']:
            GLib.source_remove(self.panels['typing_animation_id'])
            self.panels['typing_animation_id'] = None
    
    def _on_stream_start(self):
        """Handle stream start event"""
        print("Stream starting...")
    
    def _update_streaming_text(self, text):
        """Update the streaming text in the UI with rate limiting"""
        if not self.panels.get('stream_active', False):
            return
            
        # Store the latest text
        self.pending_stream_text = text
        
        # Also store the latest text for raw message display
        # This ensures we have the most recent content even if canceled
        self.last_full_response = text
        
        # If no update is scheduled, schedule one
        if self.stream_update_timeout_id is None:
            current_time = time.time() * 1000  # Convert to ms
            elapsed = current_time - self.last_stream_update_time
            
            if elapsed >= self.stream_update_interval:
                # Update immediately
                self._apply_streaming_update()
            else:
                # Schedule update after the remaining interval
                delay = max(1, int(self.stream_update_interval - elapsed))
                self.stream_update_timeout_id = GLib.timeout_add(
                    delay, self._apply_streaming_update)
    
    def _apply_streaming_update(self):
        """Apply the pending streaming update to the UI"""
        if self.stream_update_timeout_id:
            GLib.source_remove(self.stream_update_timeout_id)
            self.stream_update_timeout_id = None
            
        if not self.panels.get('stream_active', False) or self.pending_stream_text is None:
            return False
            
        if 'current_response_buffer' in self.panels and self.panels['current_response_buffer']:
            # Stop typing animation if it's running
            self._stop_typing_animation()
            
            # Update the buffer with the new text and apply markdown formatting
            buffer = self.panels['current_response_buffer']
            self.markdown_formatter.format_markdown(buffer, self.pending_stream_text)
            
            # For streaming updates, use the delayed scroll method
            # This will respect the auto_scroll_locked flag
            self._delayed_scroll_to_bottom()
            
            # Update timestamp
            self.last_stream_update_time = time.time() * 1000
        
        return False  # Don't repeat
    
    def _delayed_scroll_to_bottom(self):
        """Schedule a scroll with debouncing for streaming updates"""
        # Cancel any pending scroll
        if self.scroll_timeout_id:
            GLib.source_remove(self.scroll_timeout_id)
            self.scroll_timeout_id = None
        
        # Schedule a new scroll with a short delay to let the UI update
        self.scroll_timeout_id = GLib.timeout_add(30, lambda: GLib.idle_add(self._scroll_to_bottom))
    
    def _on_response_complete(self, response_text):
        """Handle the complete response from the API"""
        # If streaming was active, update the UI to reflect completion
        self.panels['stream_active'] = False

        # Update the button state
        self._update_button_state()
        
        # Store the response text for raw message display
        self.last_full_response = response_text
        
        # For streaming responses, we need to remove the streaming view
        # and create a new properly formatted response with interactive code blocks
        if self.settings_manager.streaming_enabled and '```' in response_text:
            # Remove the streaming text view if it exists
            if 'current_response_box' in self.panels and self.panels['current_response_box']:
                streaming_box = self.panels['current_response_box'] 
                if streaming_box.get_parent():
                    streaming_box.get_parent().remove(streaming_box)
                
                # Clear references to streaming components
                if 'current_response_buffer' in self.panels:
                    del self.panels['current_response_buffer']
                if 'current_text_view' in self.panels:
                    del self.panels['current_text_view']
                if 'current_response_box' in self.panels:
                    del self.panels['current_response_box']
                    
                # Add a new properly formatted message
                self.add_message('assistant', response_text)
                return
        
        # If no code blocks or not streaming, just update the existing buffer
        if 'current_response_buffer' in self.panels and self.panels['current_response_buffer']:
            self.markdown_formatter.format_markdown(
                self.panels['current_response_buffer'], 
                response_text
            )
            
            # For the final response content, ensure it's visible
            # by temporarily unlocking auto-scrolling
            if self.auto_scroll_locked:
                self.auto_scroll_locked = False
                
            # Use delayed scrolling after completion too
            self._delayed_scroll_to_bottom()
            
            # Add the completed response to the conversation history
            # even though we didn't create a new UI element
            if 'conversation' in self.panels and response_text:
                self.panels['conversation'].append({"role": "assistant", "content": response_text})
    
    def _clean_terminal_content(self, content):
        """
        Clean terminal content by:
        1. Consolidating consecutive empty lines to a single line
        2. Trimming excessive whitespace at the end
        """
        if not content:
            return ""
             
        # Step 1: Trim trailing whitespace at the end of the content
        content = content.rstrip()
        
        # Step 2: Replace multiple consecutive newlines with a single newline
        # This regex finds any newline followed by one or more empty lines
        # (which are newlines possibly with whitespace in between)
        # and replaces them with just two newlines
        content = re.sub(r'\n(\s*\n)+', '\n\n', content)
        
        return content

    def _get_terminal_content(self):
        """Get the current text content from the VTE terminal, including scrollback."""
        try:
            # Access the VTE terminal
            vte = self.terminal
            
            try:
                # Instead of using get_row_count(), use a very large number to ensure
                # we capture the entire scrollback buffer regardless of window size
                # VTE will automatically stop when it reaches the actual end of content
                max_rows = 100000  # Large enough to capture any reasonable scrollback
                cols = vte.get_column_count()
                
                # Using get_text_range_format to fetch the entire terminal content
                # including scrollback buffer (from position 0,0 to end)
                result = vte.get_text_range_format(
                    Vte.Format.TEXT,  # Plain text format
                    0,                # start_row: beginning of scrollback
                    0,                # start_col: first column
                    max_rows,         # end_row: using large number instead of row_count
                    cols              # end_col: full content width
                )
                
                # get_text_range_format returns a tuple, we need to extract the text
                # The first element is typically the actual text content
                if result and isinstance(result, tuple) and len(result) > 0:
                    content = result[0] if result[0] else ""
                    return self._clean_terminal_content(content)
                    
            except Exception as e:
                print(f"Error getting terminal content with scrollback: {str(e)}")
                # Fall back to other methods if this fails
                
                # Try alternative methods
                try:
                    # For GTK4/VTE 0.70+, this is the preferred method
                    content = vte.get_text_format(Vte.Format.TEXT)
                    if content:
                        return self._clean_terminal_content(content)
                except Exception as e:
                    print(f"Error with get_text_format: {str(e)}")
                    
                    # Try alternative methods
                    try:
                        # For older VTE versions
                        content = vte.get_text(None, None)
                        if content:
                            return self._clean_terminal_content(content)
                    except Exception as e2:
                        print(f"Error with get_text: {str(e2)}")
                        
                        # Last resort
                        try:
                            col, row = vte.get_cursor_position()
                            content = vte.get_text_range(0, 0, row, col, None)
                            if content:
                                return self._clean_terminal_content(content)
                        except Exception as e3:
                            print(f"Error with get_text_range: {str(e3)}")
            
            print("All terminal content extraction methods failed")
            return "No terminal content available."
        except Exception as e:
            print(f"Error getting terminal content: {str(e)}")
            return f"Error retrieving terminal content: {str(e)}"
    
    def add_message(self, role, text, animate=False, bold=False):
        """Add a message to the chat panel"""
        if 'chat_box' not in self.panels:
            return False

        if role not in ('user', 'assistant', 'system', 'error'):
            print(f"Invalid role: {role}")
            return False

        # For new complete messages (not streaming updates), we want to ensure they're visible
        # by temporarily unlocking auto-scrolling
        if self.auto_scroll_locked:
            self.auto_scroll_locked = False

        # Create message widget
        message_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        message_container.set_name(f"{role}-message-container")
        self.panels['chat_box'].append(message_container)

        # Add header with role
        header = Gtk.Label(label=role.capitalize())
        header.set_halign(Gtk.Align.START)
        header.set_name(f"{role}-header")
        if bold:
            header.set_markup(f"<b>{role.capitalize()}</b>")
        message_container.append(header)
        
        # Add to conversation history if it's a user, system, or assistant message (not error)
        # Don't add empty or animation messages
        if role in ('user', 'system', 'assistant') and text and not animate:
            # Add message to conversation history for context
            self.panels['conversation'].append({"role": role, "content": text})
        
        # Apply markdown formatting or special handling depending on role
        if role != 'user':
            # Handle animation if requested
            if animate:
                content_view = Gtk.TextView()
                content_view.set_name(f"{role}-content")
                content_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                content_view.set_editable(False)
                content_view.set_cursor_visible(False)
                content_view.set_left_margin(10)
                content_view.set_right_margin(10)
                content_view.set_top_margin(5)
                content_view.set_bottom_margin(5)
                
                content_buffer = content_view.get_buffer()
                content_buffer.set_text("▋")  # Typing indicator
                message_container.append(content_view)
                
                self.panels['typing_view'] = content_view
                self.panels['typing_buffer'] = content_buffer
                self.panels['current_response_text'] = ""
                self.panels['current_response_buffer'] = content_buffer
                self._start_typing_animation()
            else:
                # Extract code blocks manually with better handling of different formats
                code_blocks = []
                if '```' in text and role == 'assistant':
                    # Find all ```segments in the text
                    segments = text.split('```')
                    
                    # Skip the first segment (before the first ```)
                    for i in range(1, len(segments) - 1, 2):
                        # This is a code block segment (content between ```)
                        code_segment = segments[i]
                        
                        # Try to extract language and code
                        # Check for first newline to separate language from code
                        nl_pos = code_segment.find('\n')
                        
                        if nl_pos > 0:
                            # There's a newline - language might be before it
                            first_line = code_segment[:nl_pos].strip()
                            rest_of_code = code_segment[nl_pos+1:]
                            
                            # List of common language/shell identifiers
                            known_languages = [
                                'bash', 'sh', 'shell', 'zsh', 'fish', 
                                'python', 'py', 'python3',
                                'javascript', 'js', 'typescript', 'ts',
                                'java', 'c', 'cpp', 'c++', 'cs', 'c#',
                                'go', 'rust', 'ruby', 'perl', 'php',
                                'sql', 'html', 'css', 'xml', 'json',
                                'yaml', 'ini', 'toml', 'conf',
                                'makefile', 'dockerfile'
                            ]
                            
                            # Check if the first line is just a language identifier
                            if first_line.lower() in known_languages or first_line.startswith('language-'):
                                lang = first_line
                                code = rest_of_code
                            else:
                                # If first line doesn't look like a language identifier,
                                # it's probably part of the code - include whole segment as code
                                lang = ""
                                code = code_segment
                        else:
                            # No newline - check if there's a space to separate language
                            space_pos = code_segment.find(' ')
                            if space_pos > 0 and space_pos < 20:  # Language ID shouldn't be too long
                                lang_candidate = code_segment[:space_pos].strip().lower()
                                # Only treat as language if it's in our known languages list
                                if lang_candidate in ['bash', 'sh', 'shell', 'zsh', 'fish', 
                                                     'python', 'py', 'python3',
                                                     'javascript', 'js', 'typescript', 'ts',
                                                     'java', 'c', 'cpp', 'c++', 'cs', 'c#',
                                                     'go', 'rust', 'ruby', 'perl', 'php',
                                                     'sql', 'html', 'css', 'xml', 'json',
                                                     'yaml', 'ini', 'toml', 'conf',
                                                     'makefile', 'dockerfile']:
                                    lang = lang_candidate
                                    code = code_segment[space_pos+1:]
                                else:
                                    # Not a recognized language, treat whole segment as code
                                    lang = ""
                                    code = code_segment
                            else:
                                # No clear language separator, treat whole segment as code
                                lang = ""
                                code = code_segment
                        
                        code_blocks.append((lang, code))
                
                if code_blocks and role == 'assistant':
                    # Process text to replace code blocks with placeholders
                    processed_text = text
                    placeholder_map = {}
                    
                    # Use a better approach for replacement - collect positions of all ``` markers
                    positions = []
                    for m in re.finditer(r'```', processed_text):
                        positions.append(m.start())
                    
                    # Pair start/end positions
                    block_ranges = []
                    for i in range(0, len(positions), 2):
                        if i+1 < len(positions):
                            block_ranges.append((positions[i], positions[i+1]+3))  # +3 to include the closing ```
                    
                    # Sort ranges by start position (to ensure we replace from start to end)
                    block_ranges.sort(reverse=True)
                    
                    # Replace blocks with placeholders (work backwards to avoid index shifting)
                    for i, (start, end) in enumerate(block_ranges):
                        placeholder = f"__CODE_BLOCK_{len(block_ranges)-1-i}__"  # Reverse the index to preserve original order
                        block_content = processed_text[start:end]
                            
                        # Replace this specific block with the placeholder
                        processed_text = processed_text[:start] + placeholder + processed_text[end:]
                        
                        # Use the extracted language and code from our manual parsing
                        if i < len(code_blocks):
                            lang, code = code_blocks[len(code_blocks)-1-i]  # Use reversed index here too to match placeholder order
                            placeholder_map[placeholder] = (lang, code)
                        else:
                            # Fallback if something went wrong with our counting
                            placeholder_map[placeholder] = ("", block_content[3:-3])
                    
                    # Split by placeholders
                    parts = re.split(r'(__CODE_BLOCK_\d+__)', processed_text)
                    
                    for part in parts:
                        if part in placeholder_map:
                            # This is a code block placeholder
                            lang, code = placeholder_map[part]
                            self._add_interactive_code_block(message_container, lang, code)
                        else:
                            # This is regular text
                            if part.strip():
                                text_view = Gtk.TextView()
                                text_view.set_name(f"{role}-content")
                                text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                                text_view.set_editable(False)
                                text_view.set_cursor_visible(False)
                                text_view.set_left_margin(10)
                                text_view.set_right_margin(10)
                                text_view.set_top_margin(5)
                                text_view.set_bottom_margin(5)
                                
                                buffer = text_view.get_buffer()
                                self.markdown_formatter.format_markdown(buffer, part)
                                message_container.append(text_view)
                else:
                    # Standard markdown for the entire content
                    content_view = Gtk.TextView()
                    content_view.set_name(f"{role}-content")
                    content_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
                    content_view.set_editable(False)
                    content_view.set_cursor_visible(False)
                    content_view.set_left_margin(10)
                    content_view.set_right_margin(10)
                    content_view.set_top_margin(5)
                    content_view.set_bottom_margin(5)
                    
                    content_buffer = content_view.get_buffer()
                    self.markdown_formatter.format_markdown(content_buffer, text)
                    message_container.append(content_view)
        else:
            # Simple text for user messages
            content_view = Gtk.TextView()
            content_view.set_name(f"{role}-content")
            content_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            content_view.set_editable(False)
            content_view.set_cursor_visible(False)
            content_view.set_left_margin(10)
            content_view.set_right_margin(10)
            content_view.set_top_margin(5)
            content_view.set_bottom_margin(5)
            
            content_buffer = content_view.get_buffer()
            content_buffer.set_text(text)
            message_container.append(content_view)

        # Scroll to the bottom
        self._delayed_scroll_to_bottom()
        
        return True
        
    def _add_interactive_code_block(self, parent_container, language, code):
        """Add an interactive code block with buttons for copy, execute, and save"""
        # Create a container for the code block
        code_block_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        code_block_container.set_margin_start(10)
        code_block_container.set_margin_end(10)
        code_block_container.set_margin_top(5)
        code_block_container.set_margin_bottom(5)
        code_block_container.add_css_class("code-block-container")
        
        # Create header with language info and buttons
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header_box.add_css_class("code-block-header")
        
        # Language label
        language = language.strip().lower() if language else ""
        lang_label = Gtk.Label()
        if language:
            lang_label.set_markup(f"<span size='small'>{language}</span>")
        else:
            # Fixed markup to use valid style values
            lang_label.set_markup(f"<span size='small' style='italic'>code</span>")
        lang_label.set_halign(Gtk.Align.START)
        lang_label.set_hexpand(True)
        header_box.append(lang_label)
        
        # Action buttons
        copy_button = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
        copy_button.set_tooltip_text("Copy to clipboard")
        copy_button.add_css_class("code-action-button")
        copy_button.set_valign(Gtk.Align.CENTER)
        
        execute_button = Gtk.Button.new_from_icon_name("system-run-symbolic")
        execute_button.set_tooltip_text("Execute in terminal")
        execute_button.add_css_class("code-action-button")
        execute_button.set_valign(Gtk.Align.CENTER)
        
        save_button = Gtk.Button.new_from_icon_name("document-save-symbolic")
        save_button.set_tooltip_text("Save to file")
        save_button.add_css_class("code-action-button")
        save_button.set_valign(Gtk.Align.CENTER)
        
        header_box.append(copy_button)
        header_box.append(execute_button)
        header_box.append(save_button)
        
        code_block_container.append(header_box)
        
        # Code TextView with monospace font
        code_view = Gtk.TextView()
        code_view.set_editable(False)
        code_view.set_cursor_visible(False)
        code_view.set_wrap_mode(Gtk.WrapMode.NONE)
        code_view.add_css_class("monospace-text")
        code_view.add_css_class("code-block-content")
        
        # Create scrolled window for code
        code_scroll = Gtk.ScrolledWindow()
        code_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        # Calculate height based on content
        line_count = code.count('\n')+1
        
        # Get font metrics to calculate line height
        context = code_view.get_pango_context()
        font_description = context.get_font_description() 
        if font_description is None:
            font_description = Pango.FontDescription.from_string("Monospace 10")
            
        language = Pango.Language.get_default()
        metrics = context.get_metrics(font_description, language) 
        
        line_height_pango = metrics.get_ascent() + metrics.get_descent()
        line_height_pixels = line_height_pango / Pango.SCALE
        
        # Add some padding (e.g., 2px per line)
        padding_per_line = 2
        content_height = int(line_count * (line_height_pixels + padding_per_line))
        
        # Set a reasonable minimum height (for single line code)
        min_height = int(line_height_pixels + 10)  # 10px for padding
        content_height = max(content_height, min_height)
        
        # Don't set max height - let it grow with content
        code_scroll.set_min_content_height(content_height)
        
        code_scroll.set_child(code_view)
        
        # Set the code content
        code_buffer = code_view.get_buffer()
        code_buffer.set_text(code)
        
        code_block_container.append(code_scroll)
        
        # Connect button signals
        copy_button.connect("clicked", self._on_copy_code_clicked, code)
        execute_button.connect("clicked", self._on_execute_code_clicked, code)
        save_button.connect("clicked", self._on_save_code_clicked, code, language)
        
        # Add the code block to the parent container
        parent_container.append(code_block_container)
        
        # Return the container to allow for further manipulation
        return code_block_container
    
    def _on_copy_code_clicked(self, button, code):
        """Handle copy code button click"""
        # For GTK4
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(code)
        
        # Visual feedback - temporarily change button icon
        original_icon = button.get_icon_name()
        button.set_icon_name("emblem-ok-symbolic")
        
        # Set timer to revert icon
        def restore_icon():
            button.set_icon_name(original_icon)
            return False
            
        GLib.timeout_add(800, restore_icon)
        
        # Show a brief notification
        self._show_notification("Code copied to clipboard")
    
    def _on_execute_code_clicked(self, button, code):
        """Handle execute code button click"""
        if self.terminal:
            # Visual feedback - temporarily change button icon
            original_icon = button.get_icon_name()
            button.set_icon_name("emblem-system-symbolic")
            
            # Set timer to revert icon
            def restore_icon():
                button.set_icon_name(original_icon)
                return False
                
            GLib.timeout_add(800, restore_icon)
            
            # Add a newline at the end if not present
            if not code.endswith('\n'):
                code += '\n'
                
            try:
                # Convert the string to a list of integer code points
                code_ints = [ord(c) for c in code]
                self.terminal.feed_child(code_ints)
                self._show_notification("Code executed in terminal")
            except Exception as e:
                self._show_notification(f"Error executing code: {str(e)}")
        else:
            self._show_notification("Terminal not available")
    
    def _on_save_code_clicked(self, button, code, language=None):
        """Handle save code button click"""
        # Create a file chooser dialog
        dialog = Gtk.FileChooserDialog(
            title="Save Code Block",
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SAVE
        )
        
        # Add buttons
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.ACCEPT)
        
        # Set default filename based on language
        default_filename = "code"
        if language:
            extensions = {
                "python": ".py",
                "javascript": ".js",
                "typescript": ".ts",
                "html": ".html",
                "css": ".css",
                "bash": ".sh",
                "shell": ".sh",
                "zsh": ".sh",
                "c": ".c",
                "cpp": ".cpp",
                "java": ".java",
                "go": ".go",
                "rust": ".rs",
                "ruby": ".rb",
                "php": ".php",
            }
            ext = extensions.get(language.lower(), ".txt")
            default_filename += ext
        else:
            default_filename += ".txt"
            
        dialog.set_current_name(default_filename)
        
        # Connect to response signal
        dialog.connect("response", self._on_save_dialog_response, code)
        
        # Show the dialog
        dialog.present()
    
    def _on_save_dialog_response(self, dialog, response_id, code):
        """Handle response from the save dialog"""
        if response_id == Gtk.ResponseType.ACCEPT:
            # Get the selected file path
            file_path = dialog.get_file().get_path()
            
            try:
                # Save the code to the file
                with open(file_path, 'w') as f:
                    f.write(code)
                self._show_notification(f"Saved to {os.path.basename(file_path)}")
            except Exception as e:
                self._show_notification(f"Error saving file: {str(e)}")
        
        # Close the dialog
        dialog.destroy()
    
    def _show_notification(self, message, timeout=2000):
        """Show a temporary notification message in the UI"""
        # Check if we already have a notification
        if hasattr(self, '_notification_label'):
            # Remove the existing notification if present
            if self._notification_label.get_parent():
                self._notification_label.get_parent().remove(self._notification_label)
        else:
            # Create a notification label
            self._notification_label = Gtk.Label()
            self._notification_label.add_css_class("notification-message")
            self._notification_label.set_halign(Gtk.Align.CENTER)
        
        # Set the message
        self._notification_label.set_text(message)
        
        # Add to the panel
        if 'panel' in self.panels:
            # Get the first child which should be the header
            header = self.panels['panel'].get_first_child()
            if header:
                # Insert after the header
                self.panels['panel'].insert_child_after(self._notification_label, header)
        
        # Auto-remove after timeout
        def remove_notification():
            if self._notification_label.get_parent():
                self._notification_label.get_parent().remove(self._notification_label)
            return False
            
        GLib.timeout_add(timeout, remove_notification)
    
    def _scroll_to_bottom(self):
        """Scroll the chat view to the bottom if auto-scroll is not locked."""
        chat_scroll = self.panels.get('chat_scroll')
        if not chat_scroll or not isinstance(chat_scroll, Gtk.ScrolledWindow):
            return GLib.SOURCE_REMOVE

        # Get the adjustment
        vadj = chat_scroll.get_vadjustment()
        if not vadj:
            return GLib.SOURCE_REMOVE

        # Check if user has scrolled up and locked auto-scrolling
        if self.auto_scroll_locked:
            # Before bailing, check if we are already at the bottom (e.g., content shrunk)
            is_at_bottom_threshold = 5
            is_at_bottom = vadj.get_value() >= (vadj.get_upper() - vadj.get_page_size() - is_at_bottom_threshold)
            if is_at_bottom:
                # If we're already at the bottom, unlock auto-scroll
                self.auto_scroll_locked = False
            else:
                return GLib.SOURCE_REMOVE  # Skip scrolling when locked and not at bottom

        # Set the programmatic scroll flag to prevent _on_vadj_changed from responding
        self.is_programmatic_scroll = True
        try:
            # Calculate the target position (maximum scroll position)
            target_value = max(vadj.get_lower(), vadj.get_upper() - vadj.get_page_size())
            
            # Make sure we don't go below the minimum value
            if target_value < vadj.get_lower():
                target_value = vadj.get_lower()
                
            # Set the scroll position
            vadj.set_value(target_value)
        finally:
            # Always reset the programmatic scroll flag
            self.is_programmatic_scroll = False
            
        # Return GLib.SOURCE_REMOVE when used with idle_add
        # This ensures the function runs only once per scheduled call
        return GLib.SOURCE_REMOVE
    
    def add_system_message(self, text):
        """Add a system message to the conversation"""
        self.add_message('system', text)
    
    def add_user_message(self, text):
        """Add a user message to the conversation"""
        self.add_message('user', text)
    
    def add_ai_message(self, text):
        """Add an AI message to the conversation"""
        self.add_message('assistant', text)

    def add_error_message(self, text):
        """Add an error message to the conversation"""
        self.add_message('error', text)

    def _update_button_state(self):
        """Update the button state based on the current streaming state"""
        if self.panels.get('stream_active', False):
            self.panels['send_button'].set_visible(False)
            self.panels['stop_button'].set_visible(True)
        else:
            self.panels['send_button'].set_visible(True)
            self.panels['stop_button'].set_visible(False)

    def process_input(self):
        """Process the input from the entry field"""
        if 'query_entry' not in self.panels:
            return
            
        # Get the text from the TextView input field
        text_view = self.panels['query_entry']
        buffer = text_view.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        text = buffer.get_text(start_iter, end_iter, True).strip()
        
        if not text:
            return
            
        # Clear the input field
        buffer.set_text("")
        
        # Add user message to the conversation
        self.add_user_message(text)
        
        # Update button state
        self.panels['stream_active'] = True
        self._update_button_state()
        
        # Add a placeholder for the AI response with typing animation
        self.add_message('assistant', "", animate=True)
        
        # Get terminal content to include in the prompt
        terminal_content = self._get_terminal_content()
        
        # Get conversation history
        conversation_history = self.panels.get('conversation', [])
        
        # Send to API handler
        self.api_handler.send_request(
            query=text,
            terminal_content=terminal_content,
            update_callback=self._update_streaming_text,
            complete_callback=self._on_response_complete,
            error_callback=self._on_api_error,
            conversation_history=conversation_history
        )

    def _on_api_error(self, error_message):
        """Handle API errors"""
        # Stop typing animation if it's running
        self._stop_typing_animation()
        
        # Clear stream active flag
        self.panels['stream_active'] = False
        
        # Update button state
        self._update_button_state()
        
        # Remove any pending streaming response
        if 'current_response_buffer' in self.panels:
            del self.panels['current_response_buffer']
        
        # Add error message
        self.add_error_message(f"API Error: {error_message}")

    def _on_vadj_changed(self, vadj):
        """Handle scroll position changes to manage auto_scroll_locked."""
        if self.is_programmatic_scroll:
            # This change was due to our own _scroll_to_bottom.
            # Programmatic scrolls are intended to go to the bottom, so unlock auto-scroll.
            if self.auto_scroll_locked:
                self.auto_scroll_locked = False
            return  # Do not proceed to user scroll logic

        # User scroll or other GTK-internal change
        is_at_bottom_threshold = 5  # Small pixel threshold to consider "at bottom"
        # Check if scrollbar is at or very near the bottom
        is_at_bottom = vadj.get_value() >= (vadj.get_upper() - vadj.get_page_size() - is_at_bottom_threshold)

        if not is_at_bottom:
            if not self.auto_scroll_locked:  # Lock only if it wasn't already
                self.auto_scroll_locked = True
        else:  # User is at or scrolled to the bottom
            if self.auto_scroll_locked:  # Unlock only if it was locked
                self.auto_scroll_locked = False 

    def _on_show_raw_clicked(self, button):
        """Show the raw message from the last API response"""
        if hasattr(self, 'last_full_response'):
            self._show_raw_message_dialog(self.last_full_response)
        else:
            self._show_notification("No API response available yet")

    # Add these new methods for resize handling
    def _on_resize_begin(self, gesture, start_x, start_y):
        """Handle the start of resize drag"""
        # Store the initial height
        scroll = self.panels.get('query_scroll')
        if scroll:
            # Just store the initial height, we'll use it at the end
            self.panels['resize_initial_height'] = scroll.get_allocated_height()
            
            # Mark resize as active - we won't perform any updates until resize is complete
            self.resize_active = True
    
    def _on_resize_update(self, gesture, offset_x, offset_y):
        """Track resize updates without applying them immediately"""
        # We only store the latest offset, but don't apply any changes
        # This eliminates flickering by delaying all changes until drag is complete
        if self.resize_active:
            self.panels['current_resize_offset_y'] = offset_y
    
    def _on_resize_end(self, gesture, offset_x, offset_y):
        """Handle the end of resize drag by applying the final size once"""
        if not self.resize_active:
            return
            
        # Clear active state
        self.resize_active = False
        
        # Apply the final resize
        scroll = self.panels.get('query_scroll')
        initial_height = self.panels.get('resize_initial_height', 0)
        
        if scroll and initial_height:
            # Calculate final height - move upward (negative offset) to increase height
            final_height = max(initial_height - offset_y, 30)  # Minimum height of 30px
            
            # Apply the size only once at the end
            scroll.set_size_request(-1, final_height)
            
            # Update buttons to match the new height
            if 'send_button' in self.panels:
                self.panels['send_button'].set_size_request(-1, final_height)
            if 'stop_button' in self.panels:
                self.panels['stop_button'].set_size_request(-1, final_height)
            
            # Make sure the scroll window is refreshed
            scroll.queue_resize()
    
    def _on_handle_enter(self, controller, x, y):
        """Change cursor when mouse enters the resize handle"""
        window = self.parent_window
        if window:
            display = window.get_display()
            cursor = Gdk.Cursor.new_from_name("ns-resize", None)
            window.set_cursor(cursor)
    
    def _on_handle_leave(self, controller):
        """Reset cursor when mouse leaves the resize handle"""
        window = self.parent_window
        if window:
            window.set_cursor(None) 