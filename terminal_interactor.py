"""Terminal Interactor for KIterm"""

import re
from gi.repository import Vte

class TerminalInteractor:
    """Class to handle interactions with the VTE terminal"""
    
    def __init__(self, terminal, settings_manager=None):
        """Initialize the terminal interactor"""
        self.terminal = terminal
        self.settings_manager = settings_manager

    def get_terminal_content(self):
        """Get the current text content from the VTE terminal, including scrollback."""
        try:
            # Access the VTE terminal
            vte = self.terminal
            
            try:
                # Get the terminal's scrollback buffer size from settings if available
                # or use a reasonable default maximum
                if self.settings_manager:
                    max_rows = self.settings_manager.scrollback_lines
                else:
                    # If settings not available, use the terminal's current scrollback setting
                    # or fall back to a default value
                    try:
                        max_rows = vte.get_scrollback_lines()
                    except Exception:
                        max_rows = 1000  # Default fallback
                
                # Add a buffer to account for visible rows
                try:
                    visible_rows = vte.get_row_count()
                    max_rows += visible_rows
                except Exception:
                    # Add a reasonable buffer if we can't get the visible rows
                    max_rows += 100
                
                cols = vte.get_column_count()
                
                # Using get_text_range_format to fetch the entire terminal content
                # including scrollback buffer (from position 0,0 to end)
                result = vte.get_text_range_format(
                    Vte.Format.TEXT,  # Plain text format
                    0,                # start_row: beginning of scrollback
                    0,                # start_col: first column
                    max_rows,         # end_row: using configured scrollback size
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
    
    def insert_command(self, command):
        """
        Insert command text into terminal without executing it.
        This simulates typing the command but does not press Enter.
        """
        try:
            if not command:
                return False

            # Clean the command by removing comments and checking for security issues
            clean_command = self._sanitize_command(command)
            
            # If sanitization returned None, the command was rejected
            if clean_command is None:
                print("Command rejected: Contains multiple lines or other security issues")
                return False

            # Use feed_child to insert the command at the cursor position
            # This inserts the text as if typed but doesn't execute it
            self.terminal.feed_child(clean_command.encode())
            return True
        except Exception as e:
            print(f"Error inserting command in terminal: {str(e)}")
            return False
            
    def _sanitize_command(self, command):
        """
        Sanitize a command for safe insertion into the terminal.
        
        This method:
        1. Removes comments (# in shell commands)
        2. Removes newline characters
        3. Rejects multi-line commands
        4. Checks for other potentially dangerous patterns
        
        Returns:
            str: The sanitized command, or None if the command is rejected
        """
        if not command:
            return None
            
        # Check if command contains multiple lines (this is a security risk)
        if '\n' in command or '\r' in command:
            print("Security warning: Command contains newlines, which could lead to unintended execution")
            return None
            
        # Remove comments - this matches # and anything after it, unless the # is escaped or in quotes
        # This regex is a simplified version and might not catch all edge cases
        # It handles basic shell comments that start with # and aren't in quotes
        command = re.sub(r'(?<![\\\'"])#.*$', '', command)
        
        # Remove leading/trailing whitespace
        command = command.strip()
        
        # Check for other potential security issues
        # For example, commands containing certain dangerous sequences
        dangerous_patterns = [
            ';',            # Command separator
            '&&',           # Command chaining
            '||',           # Command chaining
            '`',            # Command substitution
            '$(',           # Command substitution
            '$((',          # Arithmetic expansion
            '>${',          # Output redirection to variable
            '>$((',         # Output redirection to command substitution
            '| base64',     # Encoding tricks
            'eval',         # Evaluating strings as code
            'exec',         # Replacing shell with another process
            'curl | bash',  # Piping remote content to shell
            'wget | bash',  # Piping remote content to shell
        ]
        
        # Don't outright reject these patterns as they might be legitimate
        # But log a warning about their potential risks
        for pattern in dangerous_patterns:
            if pattern in command:
                print(f"Warning: Command contains potentially risky pattern: '{pattern}'")
                # We don't return None here as these patterns may be legitimate in some contexts
                # But we log warnings to help users be cautious
        
        return command
    
    def execute_in_terminal(self, code):
        """Execute code in the terminal"""
        try:
            # Add a newline at the end if not present
            if not code.endswith('\n'):
                code += '\n'
                
            # Convert the string to a list of integer code points
            code_ints = [ord(c) for c in code]
            self.terminal.feed_child(code_ints)
            return True
        except Exception as e:
            print(f"Error executing code in terminal: {str(e)}")
            return False 