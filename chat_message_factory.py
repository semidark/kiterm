"""Chat Message Factory for KIterm AI Assistant"""

import os
import re
import time
from gi.repository import Gtk, Gdk, GLib, Pango

class ChatMessageFactory:
    """Factory class for creating chat message widgets"""
    
    def __init__(self, markdown_formatter, parent_window=None):
        """Initialize the chat message factory"""
        self.markdown_formatter = markdown_formatter
        self.parent_window = parent_window
        self._last_notification_label = None
    
    def set_parent_window(self, parent_window):
        """Set the parent window for dialogs"""
        self.parent_window = parent_window
    
    def create_message_widget(self, role, text, callbacks=None, animate=False, bold=False):
        """
        Create a message widget for the chat panel
        
        Args:
            role (str): The role of the message sender ('user', 'assistant', 'system', 'error')
            text (str): The message text content
            callbacks (dict, optional): Callbacks for code block actions
                - 'execute_callback': For executing code in the terminal
                - 'copy_callback': For copying to clipboard (optional, internal implementation used if None)
                - 'save_callback': For saving to file (optional, internal implementation used if None)
            animate (bool, optional): Whether to animate the message (for typing effect)
            bold (bool, optional): Whether to bold the role label
            
        Returns:
            Gtk.Box: The message widget
        """
        if role not in ('user', 'assistant', 'system', 'error'):
            print(f"Invalid role: {role}")
            return None
            
        # Default callbacks dictionary if none provided
        if callbacks is None:
            callbacks = {}
        
        # Create message widget
        message_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        message_container.set_name(f"{role}-message-container")
        message_container.add_css_class(f"{role}-message")
            
        # Add header with role and timestamp
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        header_box.set_hexpand(True)
        
        # Role label
        header = Gtk.Label(label=role.capitalize())
        header.set_halign(Gtk.Align.START)
        header.set_hexpand(True)
        header.set_name(f"{role}-header")
        if bold:
            header.set_markup(f"<b>{role.capitalize()}</b>")
        header_box.append(header)
        
        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        timestamp_label = Gtk.Label.new(timestamp)
        timestamp_label.set_halign(Gtk.Align.END)
        timestamp_label.add_css_class("timestamp")
        header_box.append(timestamp_label)
        
        message_container.append(header_box)
        
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
                content_buffer.set_text("Thinking...")
                message_container.append(content_view)
                
                # Return the container with animation view
                return {
                    'container': message_container,
                    'buffer': content_buffer,
                    'text_view': content_view
                }
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
                            self._add_interactive_code_block(message_container, lang, code, callbacks)
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

        return {'container': message_container}
    
    def _add_interactive_code_block(self, parent_container, language, code, callbacks):
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
        if 'copy_callback' in callbacks:
            copy_button.connect("clicked", lambda button, code=code: callbacks['copy_callback'](code))
        else:
            copy_button.connect("clicked", self._on_copy_code_clicked, code)
            
        if 'execute_callback' in callbacks:
            execute_button.connect("clicked", lambda button, code=code: callbacks['execute_callback'](code))
        else:
            execute_button.connect("clicked", lambda b, c: self._show_notification("No execute callback provided"), code)
            
        if 'save_callback' in callbacks:
            save_button.connect("clicked", lambda button, code=code, lang=language: callbacks['save_callback'](code, lang))
        else:
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
        """Create a notification to show feedback"""
        # Since we pass this as a callback, we can't rely on having a panel to show notifications
        # So we'll just print it for now - the actual notification would be shown by the controller
        print(f"Notification: {message}")
        # In a real implementation, you'd pass this back to the controller to display 