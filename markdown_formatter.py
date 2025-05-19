"""Markdown Formatter for KIterm AI Assistant"""

import mistune
from gi.repository import Gtk, Gdk, Pango

class MarkdownFormatter:
    """Handles Markdown formatting for the AI Assistant using Mistune"""
    
    def __init__(self):
        """Initialize Markdown Formatter with Mistune parser"""
        # Create Mistune parser with AST output
        self.markdown_parser = mistune.create_markdown(
            renderer=None,  # No renderer means AST output
            plugins=['strikethrough', 'table', 'footnotes']  # Enable useful plugins
        )
        
        # Keep CSS provider for legacy compatibility and potential future styling
        self._css_added = False
        self._add_markdown_css()
        
        # Define bullet characters for different nesting levels
        self.bullet_chars = ["•", "◦", "▪", "▫", "⁃"]
        
        # Debug mode
        self.debug_mode = False
    
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
    
    def _ensure_pango_tags(self, text_buffer):
        """Create and ensure all necessary Pango tags for markdown formatting"""
        if not text_buffer.get_tag_table().lookup("bold"):
            text_buffer.create_tag("bold", weight=Pango.Weight.BOLD)
        
        if not text_buffer.get_tag_table().lookup("italic"):
            text_buffer.create_tag("italic", style=Pango.Style.ITALIC)
        
        if not text_buffer.get_tag_table().lookup("code"):
            text_buffer.create_tag("code", 
                                  family="Monospace", 
                                  background_rgba=Gdk.RGBA(0.9, 0.9, 0.9, 0.3))
        
        if not text_buffer.get_tag_table().lookup("code_block"):
            text_buffer.create_tag("code_block", 
                                  family="Monospace", 
                                  background_rgba=Gdk.RGBA(0.9, 0.9, 0.9, 0.3), 
                                  left_margin=20, 
                                  right_margin=20)
        
        if not text_buffer.get_tag_table().lookup("blockquote"):
            text_buffer.create_tag("blockquote", 
                                  left_margin=20, 
                                  background_rgba=Gdk.RGBA(0.9, 0.9, 0.9, 0.1), 
                                  style=Pango.Style.ITALIC)
        
        if not text_buffer.get_tag_table().lookup("h1"):
            text_buffer.create_tag("h1", 
                                  weight=Pango.Weight.BOLD, 
                                  scale=1.5, 
                                  pixels_above_lines=6, 
                                  pixels_below_lines=3)
        
        if not text_buffer.get_tag_table().lookup("h2"):
            text_buffer.create_tag("h2", 
                                  weight=Pango.Weight.BOLD, 
                                  scale=1.3, 
                                  pixels_above_lines=6, 
                                  pixels_below_lines=3)
        
        if not text_buffer.get_tag_table().lookup("h3"):
            text_buffer.create_tag("h3", 
                                  weight=Pango.Weight.BOLD, 
                                  scale=1.2, 
                                  pixels_above_lines=4, 
                                  pixels_below_lines=2)
        
        if not text_buffer.get_tag_table().lookup("h4"):
            text_buffer.create_tag("h4", 
                                  weight=Pango.Weight.BOLD, 
                                  scale=1.1, 
                                  pixels_above_lines=4, 
                                  pixels_below_lines=2)
        
        # Create bullet tags for each nesting level
        base_margin = 20
        for level in range(5):  # Support up to 5 nesting levels
            tag_name = f"bullet_level_{level}"
            if not text_buffer.get_tag_table().lookup(tag_name):
                # Increase left margin for each nesting level
                text_buffer.create_tag(tag_name, left_margin=base_margin * (level + 1))
        
        if not text_buffer.get_tag_table().lookup("link"):
            text_buffer.create_tag("link", 
                                  foreground_rgba=Gdk.RGBA(0.0, 0.3, 0.8, 1.0), 
                                  underline=Pango.Underline.SINGLE)
        
        if not text_buffer.get_tag_table().lookup("strikethrough"):
            text_buffer.create_tag("strikethrough", strikethrough=True)
    
    def format_markdown(self, text_buffer, markdown_text):
        """
        Apply Markdown formatting to text in a GTK TextBuffer using Mistune
        
        Args:
            text_buffer: The Gtk.TextBuffer to render to
            markdown_text: Text in Markdown format
        """
        if not markdown_text:
            text_buffer.set_text("")
            return
        
        # For debugging
        if self.debug_mode:
            tokens = self.markdown_parser(markdown_text)
            self._print_tokens(tokens)
        
        # Clear existing buffer content
        text_buffer.set_text("")
        
        # Ensure all Pango tags are created
        self._ensure_pango_tags(text_buffer)
        
        # Parse markdown with Mistune to get AST tokens
        tokens = self.markdown_parser(markdown_text)
        
        # Render tokens to the text buffer
        self._render_tokens_to_buffer(text_buffer, tokens)
    
    def _print_tokens(self, tokens, level=0):
        """Debug helper to print token structure recursively"""
        indent = "  " * level
        for token in tokens:
            token_type = token.get('type', 'unknown')
            if token_type == 'text':
                text = token.get('text', '')
                print(f"{indent}{token_type}: '{text}'")
            elif token_type == 'codespan':
                code = token.get('text', '')
                print(f"{indent}{token_type}: `{code}`")
            elif token_type == 'list_item':
                print(f"{indent}{token_type}:")
                children = token.get('children', [])
                self._print_tokens(children, level + 1)
            else:
                print(f"{indent}{token_type}: {token.get('raw', '')[:30]}...")
            
            children = token.get('children', [])
            if children and token_type != 'list_item':
                self._print_tokens(children, level + 1)
    
    def _render_tokens_to_buffer(self, text_buffer, tokens, list_level=0):
        """
        Render the Mistune AST tokens to a GTK text buffer
        
        Args:
            text_buffer: The Gtk.TextBuffer to render to
            tokens: Mistune AST tokens list
            list_level: Current nesting level for lists (used for indentation)
        """
        if not tokens:
            return
        
        for token in tokens:
            token_type = token.get('type')
            
            # Get current end position for inserting new content
            end_iter = text_buffer.get_end_iter()
            
            if token_type == 'paragraph':
                # Process paragraph children
                children = token.get('children', [])
                self._render_tokens_to_buffer(text_buffer, children, list_level)
                
                # Only add newline if not in a list context to prevent extra spacing
                if list_level == 0:
                    text_buffer.insert(text_buffer.get_end_iter(), "\n")
            
            elif token_type == 'text':
                # Insert plain text - try different fields to extract content
                text = token.get('text', '')
                if not text:
                    # Look for content in different fields
                    for field in ['raw', 'content', 'source']:
                        if field in token:
                            text = token[field]
                            break
                
                text_buffer.insert(end_iter, text)
            
            elif token_type == 'block_text':
                # Block text often contains the actual content in list items
                # Try different fields to extract content
                text = token.get('text', '')
                for field in ['raw', 'content', 'source']:
                    if not text and field in token:
                        text = token[field]
                        break
                
                if text:
                    text_buffer.insert(end_iter, text)
                
                # Also process any children
                children = token.get('children', [])
                if children:
                    self._render_tokens_to_buffer(text_buffer, children, list_level)
            
            elif token_type == 'strong':
                # Process bold text
                mark = text_buffer.create_mark(None, end_iter, True)
                
                # First check if there's text directly in the token
                if 'text' in token:
                    text_buffer.insert(end_iter, token['text'])
                # Otherwise process children (normal case)
                else:
                    self._render_tokens_to_buffer(text_buffer, token.get('children', []), list_level)
                
                # Apply bold formatting
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("bold", start_iter, end_iter)
                text_buffer.delete_mark(mark)
            
            elif token_type == 'emphasis':
                # Process italic text
                mark = text_buffer.create_mark(None, end_iter, True)
                self._render_tokens_to_buffer(text_buffer, token.get('children', []), list_level)
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("italic", start_iter, end_iter)
                text_buffer.delete_mark(mark)
            
            elif token_type == 'codespan':
                # Process inline code - extract the actual code text
                mark = text_buffer.create_mark(None, end_iter, True)
                
                # Try to find the code content in different fields
                code_text = token.get('text', '')
                
                # If text field is empty, try other fields
                if not code_text:
                    # Check raw field
                    raw = token.get('raw', '')
                    # If raw has backticks, extract the content between them
                    if raw:
                        if raw.startswith('`') and raw.endswith('`'):
                            code_text = raw[1:-1]
                        else:
                            code_text = raw
                
                # As a fallback, check other potential fields
                if not code_text:
                    for field in ['content', 'source']:
                        if field in token:
                            code_text = token[field]
                            break
                
                # Insert the code text
                if code_text:
                    text_buffer.insert(text_buffer.get_end_iter(), code_text)
                
                # Apply code styling
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("code", start_iter, end_iter)
                text_buffer.delete_mark(mark)
            
            elif token_type == 'block_code':
                # Process code block with language info if available
                lang = token.get('info', '')
                if lang:
                    mark_lang = text_buffer.create_mark(None, end_iter, True)
                    text_buffer.insert(end_iter, f"{lang}:\n")
                    start_iter = text_buffer.get_iter_at_mark(mark_lang)
                    end_iter = text_buffer.get_end_iter()
                    text_buffer.apply_tag_by_name("italic", start_iter, end_iter)
                    text_buffer.delete_mark(mark_lang)
                    end_iter = text_buffer.get_end_iter()
                
                # Insert and style the code
                mark = text_buffer.create_mark(None, end_iter, True)
                text_buffer.insert(end_iter, token.get('raw', ''))
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("code_block", start_iter, end_iter)
                text_buffer.delete_mark(mark)
                
                # Add newline after code block
                text_buffer.insert(text_buffer.get_end_iter(), "\n")
            
            elif token_type == 'heading':
                # Process headings (h1-h4)
                level = token.get('level', 1)
                tag_name = f"h{min(level, 4)}"  # h1 through h4
                
                mark = text_buffer.create_mark(None, end_iter, True)
                self._render_tokens_to_buffer(text_buffer, token.get('children', []), list_level)
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name(tag_name, start_iter, end_iter)
                text_buffer.delete_mark(mark)
                
                # Add newline after heading
                text_buffer.insert(text_buffer.get_end_iter(), "\n")
            
            elif token_type == 'block_quote':
                # Process blockquotes
                mark = text_buffer.create_mark(None, end_iter, True)
                self._render_tokens_to_buffer(text_buffer, token.get('children', []), list_level)
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("blockquote", start_iter, end_iter)
                text_buffer.delete_mark(mark)
            
            elif token_type == 'list':
                # Get children items to process
                list_children = token.get('children', [])
                
                # Process all list items with the current nesting level
                self._render_tokens_to_buffer(text_buffer, list_children, list_level)
                
                # Spacing management - only add extra space for top-level lists (level 0)
                # This is important to prevent the extra whitespace at transitions
                if list_level == 0:
                    # Get the current position
                    end_iter = text_buffer.get_end_iter()
                    
                    # Add a single newline after top-level lists if needed
                    last_char = text_buffer.get_text(
                        text_buffer.get_iter_at_offset(max(0, end_iter.get_offset() - 1)),
                        end_iter,
                        False
                    )
                    if not last_char.endswith('\n'):
                        text_buffer.insert(end_iter, "\n")
            
            elif token_type == 'list_item':
                # Process list items
                mark_start = text_buffer.create_mark(None, end_iter, True)
                
                # Get the appropriate bullet character for this level
                bullet_char = self.bullet_chars[min(list_level, len(self.bullet_chars) - 1)]
                
                # Insert bullet character with appropriate spacing
                text_buffer.insert(end_iter, f"{bullet_char} ")
                
                # Process item content with increased nesting level for any nested lists
                children = token.get('children', [])
                
                # Create a mark for bullet styling
                bullet_mark = text_buffer.create_mark(None, end_iter, True)
                
                # Special handling for list items:
                # The first child is often a block_text which contains the text content
                # or a paragraph with text children
                for child in children:
                    child_type = child.get('type')
                    
                    # First try block_text which often has the content directly
                    if child_type == 'block_text':
                        # Try to extract text from the children first (common structure)
                        has_rendered_text = False
                        block_children = child.get('children', [])
                        
                        # If block_text has children, process them
                        if block_children:
                            # Process each child of the block_text
                            for block_child in block_children:
                                block_child_type = block_child.get('type')
                                
                                # Handle different types of content in list items
                                if block_child_type == 'text':
                                    # Get text from the text token
                                    text_content = block_child.get('text', '')
                                    if not text_content:
                                        text_content = block_child.get('raw', '')
                                    
                                    if text_content:
                                        text_buffer.insert(text_buffer.get_end_iter(), text_content)
                                        has_rendered_text = True
                                        
                                # For strong, emphasis, codespan, etc. - handle it in the main render method
                                elif block_child_type in ['strong', 'emphasis', 'codespan', 'link', 'strikethrough']:
                                    self._render_tokens_to_buffer(text_buffer, [block_child], list_level)
                                    has_rendered_text = True
                                    
                                # For other types, also try the main render method
                                else:
                                    self._render_tokens_to_buffer(text_buffer, [block_child], list_level)
                                    has_rendered_text = True
                                    
                        # If no children with text were found, fall back to trying raw content
                        if not has_rendered_text:
                            raw_content = child.get('raw', '')
                            if raw_content:
                                # Strip leading hyphen and space if present (from the Markdown list item format)
                                if raw_content.startswith('-'):
                                    raw_content = raw_content[1:].lstrip()
                                text_buffer.insert(text_buffer.get_end_iter(), raw_content)
                    
                    # Handle paragraphs in list items
                    elif child_type == 'paragraph':
                        # Create a mark for the paragraph
                        para_mark = text_buffer.create_mark(None, text_buffer.get_end_iter(), True)
                        
                        # Check if the paragraph has children with formatting
                        para_children = child.get('children', [])
                        
                        if para_children:
                            # Process paragraph children with their proper formatting
                            self._render_tokens_to_buffer(text_buffer, para_children, list_level)
                        else:
                            # If no children, get raw text content from paragraph
                            para_content = child.get('raw', '')
                            if para_content:
                                text_buffer.insert(text_buffer.get_end_iter(), para_content)
                        
                        # Clean up
                        text_buffer.delete_mark(para_mark)
                    
                    # For nested lists, increase the nesting level
                    elif child_type == 'list':
                        # We need to add a newline before a nested list to separate parent from children
                        text_buffer.insert(text_buffer.get_end_iter(), "\n")
                        # Process the nested list with increased level
                        self._render_tokens_to_buffer(text_buffer, [child], list_level + 1)
                    
                    # Process other token types
                    else:
                        self._render_tokens_to_buffer(text_buffer, [child], list_level)
                
                # Apply indentation to the entire list item
                start_iter = text_buffer.get_iter_at_mark(mark_start)
                end_iter = text_buffer.get_end_iter()
                bullet_tag = f"bullet_level_{min(list_level, 4)}"
                text_buffer.apply_tag_by_name(bullet_tag, start_iter, end_iter)
                
                # Process content separator newlines carefully
                # This is crucial for consistent list rendering
                end_iter = text_buffer.get_end_iter()
                
                # Always ensure a single newline at the end of each list item
                # Get the last character(s) at the end
                last_char_pos = max(0, end_iter.get_offset() - 1)
                last_char = text_buffer.get_text(
                    text_buffer.get_iter_at_offset(last_char_pos),
                    end_iter,
                    False
                )
                
                # Add a newline if we don't already have one
                if not last_char.endswith('\n'):
                    text_buffer.insert(end_iter, "\n")
                
                # Clean up marks
                text_buffer.delete_mark(mark_start)
                text_buffer.delete_mark(bullet_mark)
            
            elif token_type == 'link':
                # Process links
                url = token.get('link', '')
                mark = text_buffer.create_mark(None, end_iter, True)
                
                # Render link text
                self._render_tokens_to_buffer(text_buffer, token.get('children', []), list_level)
                
                # Apply link styling
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("link", start_iter, end_iter)
                text_buffer.delete_mark(mark)
            
            elif token_type == 'strikethrough':
                # Process strikethrough text
                mark = text_buffer.create_mark(None, end_iter, True)
                self._render_tokens_to_buffer(text_buffer, token.get('children', []), list_level)
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("strikethrough", start_iter, end_iter)
                text_buffer.delete_mark(mark)
            
            elif token_type == 'linebreak':
                # Hard line break
                text_buffer.insert(end_iter, "\n")
            
            elif token_type == 'newline':
                # Soft line break usually becomes a space or newline based on context
                # We'll use a space as it's within a paragraph
                text_buffer.insert(end_iter, " ")
            
            elif token_type == 'thematic_break':
                # Horizontal rule - we'll use a line of dashes
                text_buffer.insert(end_iter, "—" * 20 + "\n")
            
            elif token_type == 'image':
                # Images aren't rendered in TextBuffer, but we can show alt text
                alt_text = token.get('alt', '')
                url = token.get('src', '')
                title = token.get('title', '')
                
                # Insert a placeholder with the alt text
                text = f"[Image: {alt_text}]"
                if title:
                    text += f" ({title})"
                
                mark = text_buffer.create_mark(None, end_iter, True)
                text_buffer.insert(end_iter, text)
                start_iter = text_buffer.get_iter_at_mark(mark)
                end_iter = text_buffer.get_end_iter()
                text_buffer.apply_tag_by_name("italic", start_iter, end_iter)
                text_buffer.delete_mark(mark)
            
            # There might be other token types to handle as Mistune evolves
            # We can add more handlers as needed
    
    def get_buffer_text(self, buffer):
        """Extract all text from a TextBuffer."""
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        return buffer.get_text(start_iter, end_iter, False) 