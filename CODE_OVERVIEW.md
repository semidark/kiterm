# KIterm Code Structure Overview

KIterm is a terminal application integrated with AI capabilities, built with Python and GTK4. 

It uses the following APIs:
- [VTE - Virtual TErminal widget](https://gnome.pages.gitlab.gnome.org/vte/gtk4/index.html)
- [GNOME Python API](https://amolenaar.pages.gitlab.gnome.org/pygobject-docs/)
- [mistune markdown formater](https://mistune.lepture.com/en/latest/api.html)

The architecture separates concerns across several key modules.

## Naming Conventions

- Files: snake_case.py (e.g., ai_panel_view.py).
- Classes: PascalCase (e.g., AIPanelView).
- Methods & Functions: snake_case (e.g., create_ui_elements).
- Instance Variables: snake_case (e.g., self.chat_box).


## Core Application Components

1. **`main.py` - Application Entry Point:**
   * Initializes the GTK4 application using the `MyApplication` class
   * Creates the main `TerminalWindow` instance

2. **`terminal_window.py` - Main Window Implementation:**
   * Manages the primary application window containing VTE Terminal and AI Panel
   * Configures the terminal (fonts, scrollback buffer, keyboard shortcuts)
   * Implements command generator input field for quick command generation
   * Handles keyboard shortcuts and window layout management

3. **`ai_panel_controller.py` - AI Panel Logic:**
   * Coordinates all AI-related functionality and components
   * Manages user interactions, API communication, and conversation history
   * Controls streaming message responses and chat display
   * Handles chat operations (send, clear, stop)
   * Coordinates with other components like `CommandGenerator` and `APIHandler`

4. **`ai_panel_view.py` - AI Chat Panel UI:**
   * Implements the graphical interface for the AI chat panel
   * Manages UI elements (chat display, input field, buttons, terminal preview)
   * Forwards user actions to the controller
   * Handles UI styling via CSS

## AI Functionality Components

5. **`api_handler.py` - AI API Communication:**
   * Manages all communication with language model APIs
   * Constructs API requests with appropriate formatting
   * Handles streaming responses and error conditions
   * Uses settings from `SettingsManager` for API configuration

6. **`ai_terminal_interactor.py` - Terminal Content Access:**
   * Retrieves and formats terminal content for AI context
   * Provides methods for scrollback buffer access
   * Implements command insertion and execution in the terminal
   * Validates commands for security concerns

7. **`command_generator.py` - Command Generation:**
   * Specialized AI functionality for generating shell commands
   * Processes natural language requests into executable commands
   * Provides command explanation feature
   * Implements security checks for generated commands

8. **`chat_message_factory.py` - Message Widget Creation:**
   * Creates GTK widgets for different message types
   * Implements interactive code blocks with copy/execute/save buttons
   * Uses `MarkdownFormatter` for text styling

9. **`markdown_formatter.py` - Text Formatting:**
   * Parses Markdown text for chat messages
   * Applies Pango text attributes for formatting

## Supporting Components

10. **`settings_manager.py` - Configuration Management:**
    * Handles loading, saving, and accessing application settings
    * Provides settings dialog for user configuration
    * Manages settings like API URL, model selection, panel width, scrollback size
    * Notifies other components of settings changes

11. **`styles.css` - Application Styling:**
    * Contains CSS styling for the application UI
    * Defines appearance for chat messages, buttons, and panels

## Key Interaction Flow

When a user submits a question to the AI:
1. Input is captured by `AIPanelView` and sent to `AIPanelController`
2. `AIPanelController` retrieves terminal context via `AiTerminalInteractor`
3. `APIHandler` formats the request and communicates with the LLM API
4. Responses are formatted by `MarkdownFormatter` and displayed via `ChatMessageFactory`
5. Code execution requests are handled by `AiTerminalInteractor`

The command generation workflow:
1. User types a command description in the command generator input
2. `CommandGenerator` processes the request via a specialized AI prompt
3. Generated commands are validated for security before insertion into terminal
4. Optional command explanations can be requested

This architecture ensures clear separation of concerns and maintainable code structure.
