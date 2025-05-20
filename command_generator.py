"""Command Generator for KIterm AI Assistant"""

from gi.repository import GLib

class CommandGenerator:
    """Handles generation and explanation of shell commands."""
    def __init__(self, panel_controller):
        self.panel_controller = panel_controller
        self.api_handler = panel_controller.api_handler
        self.terminal_interactor = panel_controller.terminal_interactor
        self.view = panel_controller.view
        self.message_factory = panel_controller.message_factory
        self.settings_manager = panel_controller.settings_manager
        
        self.last_generated_command = None
        # For the specific command generation stream (which doesn't update main chat view until complete)
        self.cmd_gen_pending_stream_text = None
        self.cmd_gen_stream_update_timeout_id = None

    def handle_command_generation(self, command_request):
        """Handle a command generation request from the command generator input"""
        if not command_request:
            return
            
        print(f"CommandGenerator: Generating command for request: {command_request}")
        
        terminal_content = self.terminal_interactor.get_terminal_content()
        
        command_gen_system_prompt = (
            "You are a helpful AI assistant that generates shell commands based on user requests. "
            "The user is working in a Linux terminal environment. "
            "Generate ONLY the exact shell command that fulfills the user's request. "
            "Do not include explanations, markdown formatting, or code blocks. "
            "Return ONLY the raw command text that can be directly executed in the terminal. "
            "IMPORTANT SECURITY RULES:\n"
            "1. NEVER include newline characters (\\n) or carriage returns (\\r) in commands\n"
            "2. Prefer to use a SINGLE command rather than chained commands (with ; or &&)\n"
            "3. Avoid command substitution with backticks (`) if possible\n"
            "4. Avoid command injection risks\n"
            "If you cannot generate a suitable command, respond with 'ERROR: ' followed by a brief explanation."
        )
        
        self.panel_controller.add_system_message(f"Generating command: {command_request}")
        
        self.view.set_send_button_visible(False)
        self.view.set_stop_button_visible(True)
        
        if self.settings_manager.streaming_enabled:
            # This will show "Thinking..." in the main chat view
            self.panel_controller._prepare_for_streaming() 
        
        self.panel_controller.stream_active = True
        
        enhanced_query = f"Generate ONLY a shell command for: {command_request}. Return ONLY the command, no explanations or formatting."
        
        self.api_handler.send_request(
            query=enhanced_query,
            terminal_content=terminal_content,
            update_callback=self._update_command_streaming_text,
            complete_callback=self._on_command_generation_complete,
            error_callback=self._on_command_generation_error,
            conversation_history=None,  # As per original design for command generation
            system_prompt_override=command_gen_system_prompt
        )
    
    def _update_command_streaming_text(self, text):
        """Handle streaming updates for command generation (stores text but doesn't display)."""
        self.cmd_gen_pending_stream_text = text
        
        if self.cmd_gen_stream_update_timeout_id is None:
            self.cmd_gen_stream_update_timeout_id = GLib.timeout_add(
                self.panel_controller.stream_update_interval, 
                self._apply_command_streaming_update
            )
    
    def _apply_command_streaming_update(self):
        """Apply the streaming update for command generation (stores command)."""
        self.cmd_gen_stream_update_timeout_id = None
        
        if self.cmd_gen_pending_stream_text is not None:
            self.last_generated_command = self.cmd_gen_pending_stream_text
            self.cmd_gen_pending_stream_text = None
        
        return False # Stop the timer
    
    def _on_command_generation_complete(self, response_text):
        """Handle command generation completion."""
        self.panel_controller.stream_active = False
        self.panel_controller._stop_typing_animation()

        # Clear the "Thinking..." message from the main chat if it was displayed
        if self.panel_controller.current_response_info and self.settings_manager.streaming_enabled:
            self.panel_controller.clear_current_streaming_message()
        
        self.last_generated_command = response_text.strip()
        
        self.view.set_send_button_visible(True)
        self.view.set_stop_button_visible(False)
        
        if self.last_generated_command.startswith("ERROR:"):
            error_message = self.last_generated_command[len("ERROR:"):].strip()
            self.panel_controller.add_system_message(f"Command generation failed: {error_message}")
        else:
            success = self.terminal_interactor.insert_command(self.last_generated_command)
            
            if success:
                message = f"Generated command: `{self.last_generated_command}`\n\nCommand has been inserted into terminal. You can edit it before pressing Enter to execute."
                message_widget = self.message_factory.create_message_widget(
                    text=message, 
                    role="assistant",
                    add_explain_button=True,
                    explain_callback=self.on_explain_command_clicked # Use this class's method
                )
                
                if isinstance(message_widget, dict) and 'container' in message_widget:
                    self.view.add_message_widget(message_widget['container'])
                else:
                    print("Error: Expected a dictionary with 'container' key from create_message_widget for command success")
                
                self.panel_controller.conversation.append({
                    "role": "assistant",
                    "content": self.last_generated_command,
                    "meta": {"type": "generated_command"}
                })
            else:
                rejection_reason = "The generated command contains potentially unsafe elements (like newlines or command chaining) that could lead to unintended execution."
                safe_display_command = self.last_generated_command.replace('\n', '\\n').replace('\r', '\\r')
                
                rejection_message = (
                    f"⚠️ Command rejected for security reasons\n\n"
                    f"Generated command: `{safe_display_command}`\n\n"
                    f"{rejection_reason}\n\n"
                    f"Try asking for a simpler command or specify more clearly what you need."
                )
                
                message_widget = self.message_factory.create_message_widget(
                    text=rejection_message, 
                    role="error",
                    add_explain_button=True,
                    explain_callback=self.on_explain_command_clicked # Use this class's method
                )
                
                if isinstance(message_widget, dict) and 'container' in message_widget:
                    self.view.add_message_widget(message_widget['container'])
                else:
                    print("Error: Expected a dictionary with 'container' key from create_message_widget for command rejection")
    
    def _on_command_generation_error(self, error_message):
        """Handle command generation errors."""
        self.panel_controller.stream_active = False
        self.panel_controller._stop_typing_animation()

        # Clear the "Thinking..." message from the main chat if it was displayed
        if self.panel_controller.current_response_info and self.settings_manager.streaming_enabled:
            self.panel_controller.clear_current_streaming_message()
            
        self.view.set_send_button_visible(True)
        self.view.set_stop_button_visible(False)
        
        self.panel_controller.add_system_message(f"Command generation error: {error_message}")
    
    def on_explain_command_clicked(self, button=None, command=None): # button arg can be None if called directly
        """Handle request to explain the last generated command."""
        command_to_explain = command if command else self.last_generated_command
        
        if not command_to_explain:
            self.panel_controller.add_system_message("No command available to explain.")
            return
        
        explanation_system_prompt = (
            "You are a helpful AI assistant tasked with explaining shell commands. "
            "Provide a clear, concise explanation of what the command does, breaking down each component. "
            "Include information about options, flags, and potential side effects or risks. "
            "Format your explanation with clear section headers and bullet points where appropriate."
        )
        
        query = f"Explain this command in detail: {command_to_explain}"
        
        self.panel_controller.add_system_message(f"Generating explanation for: {command_to_explain}")
        
        self.view.set_send_button_visible(False)
        self.view.set_stop_button_visible(True)
        
        if self.settings_manager.streaming_enabled:
            self.panel_controller._prepare_for_streaming() # Uses main chat's streaming UI
        
        self.panel_controller.stream_active = True
        
        self.api_handler.send_request(
            query=query,
            terminal_content="",  # No terminal content needed for explanation
            update_callback=self.panel_controller._update_streaming_text, # Uses panel_controller's streaming update
            complete_callback=self.panel_controller._on_response_complete, # Uses panel_controller's completion logic
            error_callback=self.panel_controller._on_api_error, # Uses panel_controller's error handling
            conversation_history=None,  # Explanation is a focused task
            system_prompt_override=explanation_system_prompt
        ) 