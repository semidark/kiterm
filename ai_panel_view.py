"""AI Panel View for KIterm"""

import os
from gi.repository import Gtk, GLib, Pango, Gdk

class AIPanelView:
    """View class for the AI chat panel UI"""
    
    def __init__(self, controller):
        """Initialize the AI panel view"""
        self.controller = controller
        self.parent_window = None
        
        # Store UI components
        self.components = {}
        
        # Add CSS provider for custom styling
        self._add_css_styling()
        
        # Initial scroll handling state
        self.is_programmatic_scroll = False
        
        # Resize handling
        self.resize_active = False
    
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
            .resize-handle { background-color: alpha(gray, 0.2); border-top: 1px solid alpha(gray, 0.4); }
            .code-block-container { border: 1px solid alpha(gray, 0.3); border-radius: 4px; margin-top: 5px; margin-bottom: 5px; }
            .code-block-header { background-color: alpha(gray, 0.1); padding: 2px 4px; border-bottom: 1px solid alpha(gray, 0.2); }
            .code-action-button { padding: 2px; min-height: 0; min-width: 0; }
            .monospace-text { font-family: monospace; }
            .terminal-preview-content { font-family: monospace; }
            .notification-message { background-color: alpha(black, 0.7); color: white; padding: 10px; border-radius: 5px; }
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
        panel.add_css_class("ai-panel")
        
        # Find the parent window for dialogs
        self.parent_window = panel.get_root()
        
        # Add header with title and buttons
        header = self._create_header()
        panel.append(header)
        
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
        key_controller.connect("key-pressed", self._on_key_pressed)
        query_entry.add_controller(key_controller)
        
        # Add all components to the query box
        query_box.append(resize_handle)
        input_button_box.append(query_scroll)
        
        send_button = Gtk.Button.new_with_label("Ask AI")
        send_button.connect("clicked", self._on_send_clicked)
        send_button.set_valign(Gtk.Align.CENTER)  # Center the button vertically
        send_button.set_vexpand(False)  # Don't let the button expand vertically
        send_button.set_size_request(-1, min_input_height)  # Match the height of the single-line input
        input_button_box.append(send_button)
        
        # Stop button (initially hidden)
        stop_button = Gtk.Button.new_with_label("Stop")
        stop_button.connect("clicked", self._on_stop_clicked)
        stop_button.set_visible(False)
        stop_button.set_valign(Gtk.Align.CENTER)  # Center the button vertically
        stop_button.set_vexpand(False)  # Don't let the button expand vertically
        stop_button.set_size_request(-1, min_input_height)  # Match the height of the single-line input
        input_button_box.append(stop_button)
        
        query_box.append(input_button_box)
        
        panel.append(query_box)
        
        # Store references to UI components
        self.components = {
            'panel': panel,
            'chat_box': chat_box,
            'chat_scroll': chat_scroll,
            'query_entry': query_entry,
            'query_scroll': query_scroll,
            'send_button': send_button,
            'stop_button': stop_button,
            'min_input_height': min_input_height
        }
        
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
        raw_button.connect("clicked", self._on_raw_clicked)
        header_box.append(raw_button)
        
        # Settings button
        settings_button = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        settings_button.set_tooltip_text("Settings")
        settings_button.connect("clicked", self._on_settings_clicked)
        header_box.append(settings_button)
        
        # Clear button
        clear_button = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
        clear_button.set_tooltip_text("Clear Conversation")
        clear_button.connect("clicked", self._on_clear_clicked)
        header_box.append(clear_button)
        
        return header_box
    
    def _on_settings_clicked(self, widget):
        """Forward settings button click to controller"""
        self.controller.on_settings_clicked()
    
    def _on_clear_clicked(self, widget):
        """Forward clear button click to controller"""
        self.controller.on_clear_clicked()
    
    def _on_raw_clicked(self, widget):
        """Forward raw message button click to controller"""
        self.controller.on_raw_message_clicked()
    
    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events in the input field"""
        # Forward to controller for processing
        return self.controller.on_key_pressed(keyval, keycode, state)
    
    def _on_send_clicked(self, widget):
        """Forward send button click to controller"""
        self.controller.on_send_clicked()
    
    def _on_stop_clicked(self, widget):
        """Forward stop button click to controller"""
        self.controller.on_stop_clicked()
    
    def get_input_text(self):
        """Get the text from the input field"""
        text_view = self.components['query_entry']
        buffer = text_view.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        return buffer.get_text(start_iter, end_iter, True).strip()
    
    def clear_input(self):
        """Clear the input field"""
        buffer = self.components['query_entry'].get_buffer()
        buffer.set_text("")
    
    def add_message_widget(self, message_widget):
        """Add a message widget to the chat box"""
        self.components['chat_box'].append(message_widget)
        self.scroll_to_bottom()
    
    def clear_chat(self):
        """Clear all messages from the chat box"""
        chat_box = self.components['chat_box']
        while chat_box.get_first_child():
            chat_box.remove(chat_box.get_first_child())
    
    def set_send_button_visible(self, visible):
        """Set visibility of send button"""
        self.components['send_button'].set_visible(visible)
    
    def set_stop_button_visible(self, visible):
        """Set visibility of stop button"""
        self.components['stop_button'].set_visible(visible)
    
    def _on_vadj_changed(self, vadj):
        """Handle scroll position changes to manage auto_scroll_locked."""
        if self.is_programmatic_scroll:
            # This change was due to our own scroll_to_bottom.
            # Do not process as a user scroll
            return
        
        # User scroll or other GTK-internal change - notify controller
        is_at_bottom_threshold = 5  # Small pixel threshold to consider "at bottom"
        # Check if scrollbar is at or very near the bottom
        is_at_bottom = vadj.get_value() >= (vadj.get_upper() - vadj.get_page_size() - is_at_bottom_threshold)
        
        # Let the controller know about scroll changes
        self.controller.on_scroll_changed(is_at_bottom)
    
    def scroll_to_bottom(self):
        """Scroll the chat view to the bottom."""
        # Schedule scrolling for after the UI has updated
        GLib.idle_add(self._do_scroll_to_bottom)
    
    def _do_scroll_to_bottom(self):
        """Perform the actual scrolling to bottom"""
        chat_scroll = self.components.get('chat_scroll')
        if not chat_scroll or not isinstance(chat_scroll, Gtk.ScrolledWindow):
            return GLib.SOURCE_REMOVE

        # Get the adjustment
        vadj = chat_scroll.get_vadjustment()
        if not vadj:
            return GLib.SOURCE_REMOVE

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
    
    def show_notification(self, message, timeout=2000):
        """Show a temporary notification message in the UI"""
        # Create a notification label
        notification_label = Gtk.Label()
        notification_label.add_css_class("notification-message")
        notification_label.set_halign(Gtk.Align.CENTER)
        notification_label.set_text(message)
        
        # Get the panel and header
        panel = self.components['panel']
        header = panel.get_first_child()
        
        # Remove any existing notification
        children = []
        child = panel.get_first_child()
        while child:
            if isinstance(child, Gtk.Label) and "notification-message" in child.get_css_classes():
                panel.remove(child)
            else:
                children.append(child)
            child = child.get_next_sibling()
        
        # Add new notification after the header
        if header:
            panel.insert_child_after(notification_label, header)
        
        # Auto-remove after timeout
        def remove_notification():
            if notification_label.get_parent():
                notification_label.get_parent().remove(notification_label)
            return False
            
        GLib.timeout_add(timeout, remove_notification)
    
    def _on_resize_begin(self, gesture, start_x, start_y):
        """Handle the start of resize drag"""
        # Store the initial height
        scroll = self.components.get('query_scroll')
        if scroll:
            # Store the initial height for calculating the change
            self.resize_initial_height = scroll.get_allocated_height()
            
            # Mark resize as active
            self.resize_active = True
    
    def _on_resize_update(self, gesture, offset_x, offset_y):
        """Track resize updates without applying them immediately"""
        # We only store the latest offset, but don't apply any changes
        # This eliminates flickering by delaying all changes until drag is complete
        if self.resize_active:
            self.current_resize_offset_y = offset_y
    
    def _on_resize_end(self, gesture, offset_x, offset_y):
        """Handle the end of resize drag by applying the final size once"""
        if not self.resize_active:
            return
            
        # Clear active state
        self.resize_active = False
        
        # Apply the final resize
        scroll = self.components.get('query_scroll')
        initial_height = getattr(self, 'resize_initial_height', 0)
        min_height = self.components.get('min_input_height', 30)
        
        if scroll and initial_height:
            # Calculate final height - move upward (negative offset) to increase height
            final_height = max(initial_height - offset_y, min_height)
            
            # Apply the size only once at the end
            scroll.set_size_request(-1, final_height)
            
            # Update buttons to match the new height
            if 'send_button' in self.components:
                self.components['send_button'].set_size_request(-1, final_height)
            if 'stop_button' in self.components:
                self.components['stop_button'].set_size_request(-1, final_height)
            
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