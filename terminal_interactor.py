"""Terminal Interactor for KIterm"""

import re
from gi.repository import Vte

class TerminalInteractor:
    """Class to handle interactions with the VTE terminal"""
    
    def __init__(self, terminal):
        """Initialize the terminal interactor"""
        self.terminal = terminal

    def get_terminal_content(self):
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