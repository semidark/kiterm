"""API Handler for KIterm AI Assistant"""

import json
import threading
import urllib.request
import urllib.error
import http.client
import socket
import time
import asyncio
from urllib.parse import urlparse

from gi.repository import GLib

class APIHandler:
    """Handles communication with LLM API services"""
    
    def __init__(self, settings_manager):
        """Initialize the API handler with settings"""
        self.settings_manager = settings_manager
        self.update_callbacks = []
        self.active_request = None
        self.request_timeout = 60  # Default timeout in seconds
    
    def register_update_callback(self, callback):
        """Register a callback for streaming updates"""
        if callback not in self.update_callbacks:
            self.update_callbacks.append(callback)
    
    def remove_update_callback(self, callback):
        """Remove a previously registered update callback"""
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)
    
    def cancel_active_request(self):
        """Cancel any active request"""
        if self.active_request and not self.active_request.done():
            print("Cancelling active API request")
            self.active_request.cancel()
            return True
        return False
    
    def send_query(self, query, terminal_content, on_complete, on_stream_start=None):
        """Send a query to the LLM API"""
        # Cancel any existing request
        self.cancel_active_request()
        
        # Start a thread to not block the UI
        thread = threading.Thread(
            target=self._send_query_thread,
            args=(query, terminal_content, on_complete, on_stream_start)
        )
        thread.daemon = True  # Make thread daemon so it doesn't block app exit
        thread.start()
    
    def _send_query_thread(self, query, terminal_content, on_complete, on_stream_start):
        """Handle the query in a background thread"""
        try:
            # Get current settings
            api_url = self.settings_manager.api_url
            api_key = self.settings_manager.api_key
            model = self.settings_manager.model
            streaming_enabled = self.settings_manager.streaming_enabled
            
            # Prepare the prompt with system message and user query
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant for terminal users. Provide concise help with commands, explain terminal output, and suggest solutions to problems. Be direct and focus on practical advice. Make sure to always use code blocks (```) with commands in your output."},
                {"role": "user", "content": f"Here is my terminal content:\n\n{terminal_content}\n\nMy question is: {query}"}
            ]
            
            # Check if we need to adjust the URL for local LLMs like Ollama
            parsed_url = urlparse(api_url)
            
            # If this looks like Ollama (typically at localhost:11434)
            if "localhost:11434" in api_url or "127.0.0.1:11434" in api_url:
                print(f"Detected Ollama instance at {api_url}")
                
                # If the URL doesn't already end with /chat/completions, append it
                if not api_url.endswith('/chat/completions'):
                    # Remove trailing slash if present
                    if api_url.endswith('/'):
                        api_url = api_url[:-1]
                    
                    # If the URL ends with /v1, append /chat/completions
                    if api_url.endswith('/v1'):
                        api_url = f"{api_url}/chat/completions"
                    else:
                        # Otherwise, assume we need to add the full path
                        api_url = f"{api_url}/v1/chat/completions"
                
                print(f"Using adjusted Ollama URL: {api_url}")
            
            # Prepare the API request
            request_data = {
                "model": model,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.7,
                "stream": streaming_enabled
            }
            
            json_data = json.dumps(request_data).encode('utf-8')
            print(f"Sending request to {api_url} with model {model}")
            
            # Create request headers
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Add API key if using OpenAI or compatible service requiring auth
            if api_key:
                parsed_url = urlparse(api_url)
                if parsed_url.netloc == 'api.openai.com' or api_url.startswith('https://api.openai.com'):
                    headers['Authorization'] = f'Bearer {api_key}'
                else:
                    # For other providers, try both ways
                    headers['Authorization'] = f'Bearer {api_key}'
                    headers['api-key'] = api_key
            
            # Check if streaming is enabled
            if streaming_enabled:
                # Signal that streaming is starting
                if on_stream_start:
                    GLib.idle_add(on_stream_start)
                
                # Use streaming mode by handling the response differently
                # Parse the URL to get host, port and path
                parsed_url = urlparse(api_url)
                is_https = parsed_url.scheme == 'https'
                host = parsed_url.netloc
                path = parsed_url.path
                if not path:
                    path = '/'
                
                # Add query parameters if any
                if parsed_url.query:
                    path = f"{path}?{parsed_url.query}"
                
                try:
                    # Create the appropriate connection based on HTTP or HTTPS
                    if is_https:
                        conn = http.client.HTTPSConnection(host, timeout=self.request_timeout)
                    else:
                        conn = http.client.HTTPConnection(host, timeout=self.request_timeout)
                    
                    # Send the request
                    conn.request('POST', path, body=json_data, headers=headers)
                    
                    # Get the response and process the stream
                    response = conn.getresponse()
                    
                    if response.status != 200:
                        # Handle error
                        error_data = response.read().decode('utf-8')
                        error_msg = self._format_api_error(response.status, response.reason, api_url, error_data)
                        GLib.idle_add(on_complete, error_msg)
                        return
                    
                    # Process the streaming response
                    self._process_streaming_response(response, on_complete)
                    
                except socket.timeout:
                    error_msg = f"Request timed out after {self.request_timeout} seconds.\nURL: {api_url}"
                    GLib.idle_add(on_complete, error_msg)
                except socket.error as e:
                    error_msg = f"Socket Error: {str(e)}\nURL: {api_url}"
                    GLib.idle_add(on_complete, error_msg)
                except Exception as e:
                    error_msg = f"Streaming Error: {str(e)}\nURL: {api_url}"
                    GLib.idle_add(on_complete, error_msg)
                finally:
                    conn.close()
            else:
                # Use non-streaming mode
                try:
                    # Create request with timeout
                    req = urllib.request.Request(api_url, data=json_data, headers=headers, method='POST')
                    
                    # Send the request with timeout
                    with urllib.request.urlopen(req, timeout=self.request_timeout) as response:
                        response_data = json.loads(response.read().decode('utf-8'))
                        
                        # Extract the response text
                        try:
                            result = response_data['choices'][0]['message']['content']
                        except (KeyError, IndexError) as e:
                            result = f"Error parsing API response: {str(response_data)}\nError details: {str(e)}"
                    
                    # Call the completion callback with the result
                    GLib.idle_add(on_complete, result)
                    
                except urllib.error.HTTPError as e:
                    error_msg = self._format_http_error(e, api_url, json_data)
                    GLib.idle_add(on_complete, error_msg)
                except urllib.error.URLError as e:
                    if isinstance(e.reason, socket.timeout):
                        error_msg = f"Request timed out after {self.request_timeout} seconds.\nURL: {api_url}"
                    else:
                        error_msg = f"API Connection Error: {str(e.reason)}\nURL: {api_url}"
                    GLib.idle_add(on_complete, error_msg)
                except socket.timeout:
                    error_msg = f"Request timed out after {self.request_timeout} seconds.\nURL: {api_url}"
                    GLib.idle_add(on_complete, error_msg)
                except Exception as e:
                    error_msg = f"Error: {str(e)}\nURL: {api_url}"
                    GLib.idle_add(on_complete, error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            GLib.idle_add(on_complete, error_msg)
    
    def _process_streaming_response(self, response, on_complete):
        """Process the streaming API response"""
        accumulated_text = ""
        start_time = time.time()
        
        try:
            for line in response:
                # Check if we've exceeded timeout
                if time.time() - start_time > self.request_timeout:
                    print("Streaming response timeout reached")
                    break
                
                line = line.decode('utf-8').strip()
                
                # Skip empty lines
                if not line:
                    continue
                    
                # Skip data: prefix if it exists (SSE format)
                if line.startswith('data: '):
                    line = line[6:]
                    
                # Skip the [DONE] message that indicates the end of the stream
                if line == '[DONE]':
                    break
                    
                try:
                    # Parse the JSON
                    data = json.loads(line)
                    
                    # Extract the content based on where it might be in the response structure
                    delta = None
                    if 'choices' in data and len(data['choices']) > 0:
                        choice = data['choices'][0]
                        if 'delta' in choice and 'content' in choice['delta']:
                            delta = choice['delta']['content']
                        elif 'text' in choice:
                            delta = choice['text']
                    
                    # Update the UI with the new content
                    if delta:
                        accumulated_text += delta
                        self._notify_stream_update(accumulated_text)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON from line: {line}")
        
        except Exception as e:
            error_msg = f"Error during streaming: {str(e)}"
            print(error_msg)
            
        finally:
            # Call completion with the complete response
            if accumulated_text:
                GLib.idle_add(on_complete, accumulated_text)
            else:
                GLib.idle_add(on_complete, "No response received or error occurred.")
    
    def _notify_stream_update(self, text):
        """Notify all callbacks about a stream update"""
        for callback in self.update_callbacks:
            GLib.idle_add(callback, text)
    
    def _format_http_error(self, error, api_url, request_data):
        """Format HTTP error message with helpful debug information"""
        error_msg = f"API Error {error.code}: {error.reason}\nURL: {api_url}"
        
        # Add specific help for common errors
        if error.code == 404:
            error_msg += "\n\nFor Ollama, make sure to use 'http://localhost:11434/v1/chat/completions' as the API URL."
        elif error.code == 400:
            error_msg += "\n\nCheck that the model name is correct and available on your LLM instance."
        elif error.code == 401:
            error_msg += "\n\nAuthentication failed. Check your API key in settings."
        elif error.code == 429:
            error_msg += "\n\nRate limit exceeded. Wait a moment and try again."
        elif error.code == 500:
            error_msg += "\n\nServer error. The LLM service might be experiencing issues."
        
        try:
            # Try to get more error details from the response
            error_data = error.read().decode('utf-8')
            if error_data:
                try:
                    # Try to parse as JSON for more structured error info
                    error_json = json.loads(error_data)
                    if 'error' in error_json and 'message' in error_json['error']:
                        error_msg += f"\n\nError message: {error_json['error']['message']}"
                    else:
                        error_msg += f"\n\nResponse: {json.dumps(error_json, indent=2)}"
                except json.JSONDecodeError:
                    # Not valid JSON, just add the raw response
                    error_msg += f"\n\nResponse: {error_data}"
        except Exception:
            # If we can't read the response, continue without it
            pass
            
        return error_msg
    
    def _format_api_error(self, status_code, reason, api_url, error_data):
        """Format API error message with helpful debug information"""
        error_msg = f"API Error {status_code}: {reason}\nURL: {api_url}"
        
        # Add specific help for common errors
        if status_code == 404:
            error_msg += "\n\nFor Ollama, make sure to use 'http://localhost:11434/v1/chat/completions' as the API URL."
        elif status_code == 400:
            error_msg += "\n\nCheck that the model name is correct and available on your LLM instance."
        elif status_code == 401:
            error_msg += "\n\nAuthentication failed. Check your API key in settings."
        elif status_code == 429:
            error_msg += "\n\nRate limit exceeded. Wait a moment and try again."
        elif status_code == 500:
            error_msg += "\n\nServer error. The LLM service might be experiencing issues."
        
        # Try to parse error data as JSON
        if error_data:
            try:
                error_json = json.loads(error_data)
                if 'error' in error_json and 'message' in error_json['error']:
                    error_msg += f"\n\nError message: {error_json['error']['message']}"
                else:
                    error_msg += f"\n\nResponse: {json.dumps(error_json, indent=2)}"
            except json.JSONDecodeError:
                # Not valid JSON, just add the raw response
                error_msg += f"\n\nResponse: {error_data}"
        
        return error_msg 