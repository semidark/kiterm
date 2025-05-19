"""AI Panel Controller for KIterm"""

import os
import time
from gi.repository import Gtk, GLib, Gdk

from ai_panel_view import AIPanelView
from terminal_interactor import TerminalInteractor
from chat_message_factory import ChatMessageFactory
from api_handler import APIHandler
from markdown_formatter import MarkdownFormatter

class AIPanelController:
    """Controller class for the AI chat panel"""
    
    def __init__(self, terminal, settings_manager):
        """Initialize the panel controller"""
        self.terminal = terminal
        self.settings_manager = settings_manager
        
        # Create Markdown formatter
        self.markdown_formatter = MarkdownFormatter()
        
        # Create terminal interactor with settings manager
        self.terminal_interactor = TerminalInteractor(terminal, settings_manager)
        
        # Create chat message factory
        self.message_factory = ChatMessageFactory(self.markdown_formatter)
        
        # Create API handler
        self.api_handler = APIHandler(settings_manager)
        
        # Create the view
        self.view = AIPanelView(self)
        
        # Conversation history
        self.conversation = []
        
        # Streaming state
        self.stream_active = False
        self.last_stream_update_time = 0
        self.stream_update_interval = 50  # Minimum ms between updates
        self.pending_stream_text = None
        self.stream_update_timeout_id = None
        self.typing_animation_active = False
        self.typing_animation_id = None
        self.current_response_info = None  # Will store info about current response during streaming
        
        # Scroll handling
        self.auto_scroll_locked = False
        
        # Raw message for display
        self.last_full_response = None
        
        # Register for settings changes
        self.settings_manager.register_settings_change_callback(self.on_settings_changed)
        
        # Debug mode - set to False for production
        self.debug_mode = False
    
    def create_panel(self):
        """Create and return the AI panel"""
        print("AIPanelController: Creating panel...")
        # Create the panel via the view
        panel = self.view.create_panel()
        
        # Set the parent window in the message factory for dialogs
        self.message_factory.set_parent_window(panel.get_root())
        
        # Add welcome message
        self.add_system_message("Welcome to KIterm AI Assistant. Ask questions about your terminal session or for help with commands.")
        
        return panel
    
    def on_settings_clicked(self):
        """Handle settings button click"""
        print("Settings button clicked")
        # Get parent window from view (may be None initially)
        parent_window = self.view.parent_window
        # Open the settings dialog
        self.settings_manager.open_settings_dialog(parent_window)
    
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
    
    def on_clear_clicked(self):
        """Handle clear button click"""
        print("Clear button clicked")
        
        # Clear the chat via view
        self.view.clear_chat()
        
        # Clear the conversation history
        self.conversation = []
        
        # Add a new welcome message
        self.add_system_message("Conversation cleared. Ask a new question.")
    
    def on_raw_message_clicked(self):
        """Handle raw message button click"""
        if hasattr(self, 'last_full_response') and self.last_full_response:
            self._show_raw_message_dialog(self.last_full_response)
        else:
            self.view.show_notification("No API response available yet")
    
    def _show_raw_message_dialog(self, message):
        """Show a dialog with the raw message content for debugging"""
        dialog = Gtk.Dialog(
            title="Raw Message Content",
            parent=self.view.parent_window,
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
    
    def on_key_pressed(self, keyval, keycode, state):
        """Handle key press events"""
        # Check for ESC key (GDK_KEY_Escape = 65307)
        if keyval == 65307:
            self.stop_active_request()
            return True  # Signal that the event was handled
        
        # Check for Enter key to send message (without Shift)
        if (keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter):
            # Check if Shift modifier is NOT pressed
            if not (state & Gdk.ModifierType.SHIFT_MASK):
                self.on_send_clicked()  # Process the send action
                return True  # Event handled, don't insert a newline
            # If Shift+Enter, let the default handler add a newline
        
        return False  # Allow other handlers to process the event
    
    def on_send_clicked(self):
        """Handle send button click"""
        # Get text from the input field via view
        query = self.view.get_input_text()
        
        if not query:
            return
        
        # Add user message to conversation
        self.add_user_message(query)
        
        # Clear the input field
        self.view.clear_input()
        
        # Toggle buttons
        self.view.set_send_button_visible(False)
        self.view.set_stop_button_visible(True)
        
        # Get terminal content for context
        terminal_content = self.terminal_interactor.get_terminal_content()
        
        # Set stream active flag
        self.stream_active = True
        
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
            conversation_history=self.conversation
        )
    
    def on_stop_clicked(self):
        """Handle stop button click"""
        self.stop_active_request()
    
    def stop_active_request(self):
        """Stop the active API request"""
        if not self.stream_active:
            return
            
        # Cancel the API request
        self.api_handler.cancel_active_request()
        
        # Clear the stream active flag
        self.stream_active = False
        
        # Stop typing animation if it's running
        self._stop_typing_animation()
        
        # Cancel any pending stream updates
        if self.stream_update_timeout_id:
            GLib.source_remove(self.stream_update_timeout_id)
            self.stream_update_timeout_id = None
        
        # Update buttons via view
        self.view.set_send_button_visible(True)
        self.view.set_stop_button_visible(False)
        
        # Add a note that the request was canceled
        if self.current_response_info:
            # Get the current response buffer
            buffer = self.current_response_info.get('buffer')
            
            if buffer:
                # Try to get the current text in the buffer
                text_view = self.current_response_info.get('text_view')
                if text_view:
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
            
            # Clear the current response info
            self.current_response_info = None
            
        return True  # Signal that cancellation was successful
    
    def on_scroll_changed(self, is_at_bottom):
        """Handle scroll position changes"""
        # Only update auto_scroll_locked if the state changes
        if is_at_bottom and self.auto_scroll_locked:
            self.auto_scroll_locked = False
        elif not is_at_bottom and not self.auto_scroll_locked:
            self.auto_scroll_locked = True
    
    def _prepare_for_streaming(self):
        """Prepare for streaming response"""
        # Create empty AI message box that will be updated during streaming
        message_widget = self.message_factory.create_message_widget('assistant', "", animate=True)
        
        # Add to chat box via view
        self.view.add_message_widget(message_widget['container'])
        
        # Store reference to the streaming components
        self.current_response_info = message_widget
        
        # Start typing animation
        self._start_typing_animation()
    
    def _start_typing_animation(self):
        """Start the typing indicator animation"""
        if not self.current_response_info or 'buffer' not in self.current_response_info:
            return
            
        buffer = self.current_response_info['buffer']
        self.typing_animation_active = True
        self.typing_indicator_pos = 0
        
        def update_indicator():
            if not self.typing_animation_active:
                return False  # Stop the animation
                
            indicators = ["Thinking.", "Thinking..", "Thinking..."]
            pos = self.typing_indicator_pos
            buffer.set_text(indicators[pos])
            
            self.typing_indicator_pos = (pos + 1) % len(indicators)
            return True  # Continue the animation
        
        # Run animation every 500ms
        self.typing_animation_id = GLib.timeout_add(500, update_indicator)
    
    def _stop_typing_animation(self):
        """Stop the typing indicator animation"""
        self.typing_animation_active = False
        if self.typing_animation_id:
            GLib.source_remove(self.typing_animation_id)
            self.typing_animation_id = None
    
    def _update_streaming_text(self, text):
        """Update the streaming text in the UI with rate limiting"""
        if not self.stream_active:
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
            
        if not self.stream_active or self.pending_stream_text is None:
            return False
            
        if self.current_response_info and 'buffer' in self.current_response_info:
            # Stop typing animation if it's running
            self._stop_typing_animation()
            
            # Update the buffer with the new text and apply markdown formatting
            buffer = self.current_response_info['buffer']
            self.markdown_formatter.format_markdown(buffer, self.pending_stream_text)
            
            # Scroll to bottom if not locked
            if not self.auto_scroll_locked:
                self.view.scroll_to_bottom()
            
            # Update timestamp
            self.last_stream_update_time = time.time() * 1000
        
        return False  # Don't repeat
    
    def _on_response_complete(self, response_text):
        """Handle the complete response from the API"""
        # Set flags to indicate streaming is no longer active
        self.stream_active = False
        
        # Update the button state
        self.view.set_send_button_visible(True)
        self.view.set_stop_button_visible(False)
        
        # Store the response text for raw message display
        self.last_full_response = response_text
        
        # For streaming responses, we need to remove the streaming view
        # and create a new properly formatted response with interactive code blocks
        if self.settings_manager.streaming_enabled and '```' in response_text:
            # Remove the streaming text view if it exists
            widget_to_remove = None
            if self.current_response_info and 'container' in self.current_response_info:
                widget_to_remove = self.current_response_info['container']
            
            # Only try to remove if we found a widget and it has a parent
            if widget_to_remove and widget_to_remove.get_parent():
                widget_to_remove.get_parent().remove(widget_to_remove)
                
            # Clear references to streaming components
            self.current_response_info = None
                    
            # Add a new properly formatted message
            self.add_ai_message(response_text)
            return
        
        # If no code blocks or not streaming, just update the existing buffer
        if self.current_response_info and 'buffer' in self.current_response_info:
            buffer = self.current_response_info['buffer']
            self.markdown_formatter.format_markdown(buffer, response_text)
            
            # For the final response content, ensure it's visible by scrolling to bottom
            # temporarily override auto_scroll_locked
            original_auto_scroll_locked = self.auto_scroll_locked
            self.auto_scroll_locked = False
            self.view.scroll_to_bottom()
            self.auto_scroll_locked = original_auto_scroll_locked
            
            # Add the completed response to the conversation history
            self.conversation.append({"role": "assistant", "content": response_text})
            
            # Clear the current response info
            self.current_response_info = None
    
    def _on_api_error(self, error_message):
        """Handle API errors"""
        # Stop typing animation if it's running
        self._stop_typing_animation()
        
        # Clear stream active flag
        self.stream_active = False
        
        # Update button state
        self.view.set_send_button_visible(True)
        self.view.set_stop_button_visible(False)
        
        # Remove any pending streaming response
        if self.current_response_info and 'container' in self.current_response_info:
            widget_to_remove = self.current_response_info['container']
            if widget_to_remove and widget_to_remove.get_parent():
                widget_to_remove.get_parent().remove(widget_to_remove)
            
        # Clear references
        self.current_response_info = None
        
        # Add error message
        self.add_message('error', f"API Error: {error_message}")
    
    def add_message(self, role, text, animate=False, bold=False):
        """Add a message to the chat panel"""
        # Create message widget with appropriate callbacks
        callbacks = {
            'execute_callback': self._execute_code_in_terminal,
            'copy_callback': self._copy_to_clipboard,
            'save_callback': self._save_code_to_file
        }
        
        message_widget = self.message_factory.create_message_widget(
            role=role,
            text=text,
            callbacks=callbacks,
            animate=animate,
            bold=bold
        )
        
        if not message_widget:
            print(f"Failed to create message widget for role: {role}")
            return False
        
        # Add widget to the chat box
        self.view.add_message_widget(message_widget['container'])
        
        # Add to conversation history if it's a user, system, or assistant message
        if role in ('user', 'assistant', 'system') and text and not animate:
            self.conversation.append({"role": role, "content": text})
        
        return True
    
    def add_system_message(self, text):
        """Add a system message to the conversation"""
        self.add_message('system', text)
    
    def add_user_message(self, text):
        """Add a user message to the conversation"""
        self.add_message('user', text)
    
    def add_ai_message(self, text):
        """Add an AI message to the conversation"""
        self.add_message('assistant', text)
    
    def _execute_code_in_terminal(self, code):
        """Execute code in the terminal"""
        success = self.terminal_interactor.execute_in_terminal(code)
        if success:
            self.view.show_notification("Code executed in terminal")
        else:
            self.view.show_notification("Failed to execute code in terminal")
        return success
    
    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)
        self.view.show_notification("Text copied to clipboard")
        return True
    
    def _save_code_to_file(self, code, language=None):
        """Save code to a file (just delegates to message factory)"""
        # The ChatMessageFactory already has the implementation for this
        # with a file selection dialog, but we could add additional logic here
        # if needed
        return True 