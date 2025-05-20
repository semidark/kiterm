# KIterm: GTK4 based Terminal with Integrated AI Assistant

## Features

*   **🚀 Next-Gen Terminal Experience**: KIterm isn't just a terminal; it's your supercharged command-line companion, seamlessly embedding a powerful VTE based terminal.
*   **🧠 Integrated AI Assistant**:
    *   **Universal LLM Compatibility**: Effortlessly connect to Ollama, OpenAI, or your preferred Large Language Model API.
    *   **Context-Aware Assistance**: Get truly relevant help! The AI understands your current terminal session and chat history to provide pinpoint suggestions.
    *   **Real-time AI Dialogue**: Experience fluid, streaming responses for a natural and interactive chat.
    *   **Crystal-Clear Markdown Output**: AI responses are beautifully formatted with Markdown, making code blocks, emphasis, and lists easy to read.
    *   **Personalized AI Settings**: Tailor your experience with an intuitive in-app panel to configure:
        *   Your chosen API Endpoint URL.
        *   The specific AI Model you want to use.
        *   Toggle for streaming responses.
        *   Adjustable AI panel width for optimal screen real estate.
    *   **Instant Control**: Cancel AI requests on the fly with a dedicated "Stop" button or a simple Escape key press.
    *   **Smart Scrolling**: The chat view intelligently auto-scrolls but respects your manual scrolling, so you never lose your place.
    *   **Effortless Conversation Management**: Easily clear conversations and start fresh.
*   **✨ AI-Powered Command Generator**:
    *   **Intuitive Command Creation**: Type what you want to do in plain English (e.g., "find all PDF files in my downloads folder from last week") directly below your terminal.
    *   **Contextual Command Genius**: The generator leverages your terminal output and ongoing chat to craft highly relevant and accurate shell commands.
    *   **Safe & Editable Commands**: Generated commands are inserted directly into your terminal, ready for your review and modification *before* execution.
    *   **Lightning-Fast Focus**: Jump to the command generator instantly with the `Ctrl+Shift+G` shortcut.
    *   **Demystify Commands**: Got a complex command? Use the built-in "Explain Command" feature to understand its function before you hit Enter.

## Implementation Plan

Here's the implementation plan for API integration and chat functionality enhancements:

### Phase 1: API Integration
1. **Create API Handler**
   - [X] Implement `api_handler.py` based on POC's api.py
   - [X] Add proper error handling and timeout management
   - [X] Implement streaming response handling

2. **Connect Settings to API**
   - [X] Ensure settings are properly passed to the API handler

### Phase 2: Enhanced Chat Experience
1. **Markdown Formatting**
   - [X] Create a markdown renderer based on POC's markdown.py
   - [X] Improved code block interaction (copy, execute, save)
   - [X] Optimize LLM Prompt so it aligns better with the task of an Shell AI-Assistent

2. **Terminal Integration**
   - [X] Refine terminal content extraction
   - [X] Add Scrollbars to Terminal
   - [X] Refine Copy and Paste functionality vor VTE Terminal (ctrl+shift+c and ctrl+shift+v)
   - [X] Add Zoom functionality to VTE
   - [X] Make VTE Scrollback buffer size configurable
   - [X] Add Command generation Chatbox to VTE that allows the user to generate a prompt directly to the terminal.
   - [ ] Always display Scrollbar in VTE since it is an indicator how much content is send to the LLM

   
### Phase 3: Advanced Features
1. **Conversation Management**
   - [X] Improve regex Markdown Rendering with library 
   - [ ] Autmatic System Exploration script. Identifies what kind of shell we are in and if we have admin/root rights. This information is then used for Command Generation Feature and as guidance in the AI Chat 
   - [ ] Add keyboard shortcuts for Focus switching between chat and Terminal
   - [ ] Display token usage (divided by Terminal / Chat / Prompt / Systemprompt)
   - [ ] Save/load conversation history
   - [ ] Improve code block rendering with syntax highlighting
   - [ ] Export conversations
   - [ ] Implement model selection
   - [ ] Handle API key securely
   - [ ] Add support for clickable links
   - [ ] Add Tabs to have multiple Terminals availible. Just like any modern Terminal app
   - [ ] Make interface pretty
  

## Prerequisites

Before running this application, you need to have GTK4 and the VTE library development files installed on your system.

### For Debian/Ubuntu-based systems:

```bash
sudo apt update
sudo apt install -y libgtk-4-dev libvte-2.91-gtk4-dev gir1.2-vte-3.0 # Ensure correct VTE GIR package for GTK4
# libgirepository1.0-dev is also generally useful for PyGObject development
sudo apt install -y libgirepository1.0-dev
```

(Note: Package names might vary slightly depending on the distribution version. `gir1.2-vte-3.0` is typical for VTE with GTK4.)

## Setup

1.  **Clone the repository (if applicable) or ensure all project files are in place.**

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

1.  **Make sure your virtual environment is activated if you created one:**
    ```bash
    source .venv/bin/activate
    ```

2.  **Run the Python script:**
    ```bash
    python3 main.py
    ```

This will open a window with an embedded terminal and the AI assistant panel.

### Keyboard Shortcuts

KIterm supports the following keyboard shortcuts for the terminal:

* **Ctrl+Shift+C**: Copy selected text from terminal
* **Ctrl+Shift+V**: Paste text from clipboard into terminal
* **Ctrl+Plus (+)**: Zoom in (increase font size)
* **Ctrl+Minus (-)**: Zoom out (decrease font size)
* **Ctrl+0**: Reset zoom to default font size
* **Ctrl+Shift+G**: Toggle focus between terminal and command generator

### Configuring the AI Assistant

*   Upon first launch, or if the AI assistant isn't working, click the **settings icon (gear)** in the AI Chat panel.
*   **API URL**:
    *   For local Ollama: `http://localhost:11434` (the application will auto-append `/v1/chat/completions`).
    *   For OpenAI: `https://api.openai.com/v1/chat/completions`.
*   **Model**: Enter the name of the model you wish to use (e.g., `gpt-4.1-nano`, `qwen2.5-coder:32b`).
*   **API Key**: Required for services like OpenAI.
*   Adjust other settings like streaming and panel width as needed. 

### Using the Command Generator

1. Focus the command input field by pressing **Ctrl+Shift+G**
2. Enter a natural language description of the command you need (e.g., "find all files modified in the last 24 hours")
3. Press **Enter** to generate the command
4. The command will be inserted into the terminal prompt without executing it
5. Review or edit the command as needed, then press **Enter** in the terminal to execute
6. Click **Explain Command** in the AI panel to get a detailed explanation of what the command does     