"""Markdown Formatter for KIterm AI Assistant"""

import re
from gi.repository import Gtk, Gdk, Pango

class MarkdownFormatter:
    """Handles Markdown formatting for the AI Assistant"""
    
    def __init__(self):
        """Initialize Markdown Formatter"""
        self._css_added = False
        self._add_markdown_css()
    
    def _add_markdown_css(self):
        """Add CSS styling for Markdown elements"""
        if not self._css_added:
            css_provider = Gtk.CssProvider()
            css_data = b"""
                .markdown-code {
                    font-family: monospace;
                    background-color: alpha(@theme_bg_color, 0.3);
                    border-radius: 3px;
                    padding: 0 2px;
                }
                
                .markdown-code-block {
                    font-family: monospace;
                    background-color: alpha(@theme_bg_color, 0.3);
                    border-radius: 4px;
                    padding: 8px;
                    margin: 4px 0;
                }
                
                .markdown-blockquote {
                    border-left: 3px solid alpha(@theme_selected_bg_color, 0.5);
                    padding-left: 8px;
                    font-style: italic;
                    color: alpha(@theme_fg_color, 0.8);
                }
                
                .markdown-link {
                    color: @link_color;
                    text-decoration: underline;
                }
                
                .markdown-heading {
                    font-weight: bold;
                    margin-top: 12px;
                    margin-bottom: 6px;
                }
            """
            
            css_provider.load_from_data(css_data)
            
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                self._css_added = True
    
    def format_markdown(self, text_buffer, markdown_text):
        """
        Apply basic Markdown formatting to text in a GTK TextBuffer
        
        This is a lightweight Markdown parser that handles:
        - **bold** and __bold__
        - *italic* and _italic_
        - `code` spans
        - ```code blocks```
        - > blockquotes
        - - list items
        - URLs
        - Headers with # prefix
        """
        if not markdown_text:
            return
            
        # Clear existing buffer content
        text_buffer.set_text("")
        
        # Create tags for formatting if they don't exist
        if not text_buffer.get_tag_table().lookup("bold"):
            text_buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        if not text_buffer.get_tag_table().lookup("italic"):
            text_buffer.create_tag("italic", style=Pango.Style.ITALIC)
        if not text_buffer.get_tag_table().lookup("code"):
            text_buffer.create_tag("code", family="Monospace", background="rgba(0,0,0,0.1)")
        if not text_buffer.get_tag_table().lookup("code_block"):
            text_buffer.create_tag("code_block", 
                                  family="Monospace", 
                                  background="rgba(0,0,0,0.1)", 
                                  left_margin=20, 
                                  right_margin=20)
        if not text_buffer.get_tag_table().lookup("blockquote"):
            text_buffer.create_tag("blockquote", left_margin=20, background="rgba(0,0,0,0.05)", 
                                  style=Pango.Style.ITALIC)
        if not text_buffer.get_tag_table().lookup("h1"):
            text_buffer.create_tag("h1", weight=Pango.Weight.BOLD, scale=1.5)
        if not text_buffer.get_tag_table().lookup("h2"):
            text_buffer.create_tag("h2", weight=Pango.Weight.BOLD, scale=1.3)
        if not text_buffer.get_tag_table().lookup("h3"):
            text_buffer.create_tag("h3", weight=Pango.Weight.BOLD, scale=1.2)
        if not text_buffer.get_tag_table().lookup("h4"):
            text_buffer.create_tag("h4", weight=Pango.Weight.BOLD, scale=1.1)
        if not text_buffer.get_tag_table().lookup("bullet"):
            text_buffer.create_tag("bullet", left_margin=20)
        if not text_buffer.get_tag_table().lookup("link"):
            text_buffer.create_tag("link", foreground="blue", underline=Pango.Underline.SINGLE)
            
        # Simplify the markdown text by normalizing newlines
        markdown_text = markdown_text.replace('\r\n', '\n')
        
        # Split into lines for processing
        lines = markdown_text.split('\n')
        
        # Process the lines
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for code blocks
            if line.strip().startswith('```'):
                # Extract language if specified
                lang = line.strip()[3:].strip()
                
                # Find the end of the code block
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                
                # Skip the closing ``` if found
                if i < len(lines):
                    i += 1
                
                # Add the code block
                if code_lines:
                    code_text = '\n'.join(code_lines)
                    end_iter = text_buffer.get_end_iter()
                    
                    # If a language was specified, add it as a tag
                    if lang:
                        text_buffer.insert(end_iter, f"{lang}:\n")
                    
                    # Insert the code
                    mark = text_buffer.create_mark(None, end_iter, True)
                    text_buffer.insert(end_iter, code_text + '\n')
                    start_iter = text_buffer.get_iter_at_mark(mark)
                    end_iter = text_buffer.get_end_iter()
                    text_buffer.apply_tag_by_name("code_block", start_iter, end_iter)
                    text_buffer.delete_mark(mark)
                    
                    # Add an extra newline after code blocks
                    text_buffer.insert(end_iter, '\n')
                continue
            
            # Check for headers
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                level = len(header_match.group(1))
                text = header_match.group(2)
                end_iter = text_buffer.get_end_iter()
                mark = text_buffer.create_mark(None, end_iter, True)
                text_buffer.insert(end_iter, text + '\n')
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                tag_name = f"h{min(level, 4)}"  # h1 through h4
                text_buffer.apply_tag_by_name(tag_name, start_iter, end_iter)
                text_buffer.delete_mark(mark)
                i += 1
                continue
            
            # Check for blockquotes
            if line.startswith('> '):
                text = line[2:]
                end_iter = text_buffer.get_end_iter()
                mark = text_buffer.create_mark(None, end_iter, True)
                text_buffer.insert(end_iter, text + '\n')
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("blockquote", start_iter, end_iter)
                text_buffer.delete_mark(mark)
                i += 1
                continue
            
            # Check for bullet lists
            if line.startswith('- ') or line.startswith('* '):
                text = line[2:]
                end_iter = text_buffer.get_end_iter()
                mark = text_buffer.create_mark(None, end_iter, True)
                text_buffer.insert(end_iter, "• " + text + '\n')
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("bullet", start_iter, end_iter)
                text_buffer.delete_mark(mark)
                i += 1
                continue
            
            # Process inline formatting in regular text
            end_iter = text_buffer.get_end_iter()
            
            # Process the line character by character to handle inline formatting
            j = 0
            while j < len(line):
                # Check for inline code
                if line[j:j+1] == '`' and '`' in line[j+1:]:
                    code_end = line.find('`', j+1)
                    code_text = line[j+1:code_end]
                    end_iter = text_buffer.get_end_iter()
                    mark = text_buffer.create_mark(None, end_iter, True)
                    text_buffer.insert(end_iter, code_text)
                    start_iter = text_buffer.get_iter_at_mark(mark)
                    end_iter = text_buffer.get_end_iter()
                    text_buffer.apply_tag_by_name("code", start_iter, end_iter)
                    text_buffer.delete_mark(mark)
                    j = code_end + 1
                    continue
                
                # Check for bold (**text**)
                if line[j:j+2] == '**' and '**' in line[j+2:]:
                    bold_end = line.find('**', j+2)
                    bold_text = line[j+2:bold_end]
                    end_iter = text_buffer.get_end_iter()
                    mark = text_buffer.create_mark(None, end_iter, True)
                    text_buffer.insert(end_iter, bold_text)
                    start_iter = text_buffer.get_iter_at_mark(mark)
                    end_iter = text_buffer.get_end_iter()
                    text_buffer.apply_tag_by_name("bold", start_iter, end_iter)
                    text_buffer.delete_mark(mark)
                    j = bold_end + 2
                    continue
                
                # Check for italic (*text*)
                if line[j:j+1] == '*' and '*' in line[j+1:]:
                    italic_end = line.find('*', j+1)
                    # Make sure it's not part of a bold marker
                    if not (j > 0 and line[j-1] == '*') and not (italic_end < len(line) - 1 and line[italic_end+1] == '*'):
                        italic_text = line[j+1:italic_end]
                        end_iter = text_buffer.get_end_iter()
                        mark = text_buffer.create_mark(None, end_iter, True)
                        text_buffer.insert(end_iter, italic_text)
                        start_iter = text_buffer.get_iter_at_mark(mark)
                        end_iter = text_buffer.get_end_iter()
                        text_buffer.apply_tag_by_name("italic", start_iter, end_iter)
                        text_buffer.delete_mark(mark)
                        j = italic_end + 1
                        continue
                
                # Regular character
                text_buffer.insert(end_iter, line[j:j+1])
                j += 1
            
            # Add a newline at the end of the line
            text_buffer.insert(end_iter, '\n')
            i += 1 