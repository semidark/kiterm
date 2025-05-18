# GTK4 VTE Terminal Application

A simple Python application that displays a terminal using GTK4 and VTE.

## Prerequisites

Before running this application, you need to have GTK4 and the VTE library development files installed on your system.

### For Debian/Ubuntu-based systems:

```bash
sudo apt update
sudo apt install -y libgtk-4-dev libvte-2.91-gtk4-dev libgirepository2.0-dev
```


(Note: Package names might vary slightly depending on the distribution version.)

## Setup

1.  **Clone the repository (if applicable) or create the files `main.py` and `requirements.txt` as provided.**

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

This will open a window with an embedded terminal. 