# KIterm: GTK4 VTE Terminal with Integrated AI Assistant

A Python application that displays a terminal using GTK4 and VTE, now featuring an integrated AI assistant panel.

## Features

*   **Embedded VTE Terminal**: A fully functional terminal embedded within the GTK4 application.
*   **Integrated AI Chat Panel**:
    *   Connects to Ollama, OpenAI, or other compatible Large Language Model (LLM) APIs.
    *   Provides contextual assistance by using the current content of your terminal.
    *   Supports streaming responses for real-time interaction.
    *   Renders AI responses in Markdown for clear formatting (including code blocks, bold, italics, etc.).
    *   In-app settings panel to configure:
        *   API Endpoint URL.
        *   Model name.
        *   Streaming mode (enable/disable).
        *   AI panel width.
    *   Cancellable AI requests via a "Stop" button or the Escape key.
    *   Intelligent auto-scrolling that respects manual scrolling in the chat view.
    *   Terminal preview within the AI panel.
    *   Conversation clearing and settings refresh options.

## Implementation Plan

Based on the POC code and the current state of the application, here's a plan to implement the API calls and enhance the chat functionality:

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
   - [ ] Add context management
   - [ ] Refine Copy and Paste functionality (ctrl+shift+c and ctrl+shift+v)
   - [ ] Add Scrollbars to Terminal
   
### Phase 3: Advanced Features
1. **Conversation Management**
   - [ ] Save/load conversation history
   - [ ] Improve code block rendering with syntax highlighting
   - [ ] Export conversations
   - [ ] Add keyboard shortcuts
   - [ ] Implement model selection
   - [ ] Handle API key securely
   - [ ] Add support for clickable links

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

### Configuring the AI Assistant

*   Upon first launch, or if the AI assistant isn't working, click the **settings icon (gear)** in the AI Chat panel.
*   **API URL**:
    *   For local Ollama: `http://localhost:11434` (the application will auto-append `/v1/chat/completions`).
    *   For OpenAI: `https://api.openai.com/v1/chat/completions`.
*   **Model**: Enter the name of the model you wish to use (e.g., `llama3`, `gpt-4o`, `qwen2.5-coder:32b`).
*   **API Key**: Required for services like OpenAI.
*   Adjust other settings like streaming and panel width as needed. 