from typing import Optional, Dict, Any, List, Iterator
import json
from pathlib import Path
import click
from google import genai
from google.generativeai.types import GenerateContentResponse

# Constants
DEFAULT_MODEL = 'gemini-1.5-flash'
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TOP_P = 0.1
MAX_RETRIES = 3

class AIAnalyzer:
    """Handles AI-powered log file analysis using Google's Generative AI."""

    def __init__(self, api_key: str, debug: bool = False) -> None:
        """Initialize the AI analyzer.
        
        Args:
            api_key: The Google API key for authentication
            debug: Enable debug mode for verbose output
        """
        self.debug = debug
        self.client = genai.Client(api_key=api_key)
        
    # Public Methods
    def populate_log_inventory(self, log_file_list: List[Path]) -> Optional[Dict[str, Any]]:
        """Populate log inventory with AI-generated descriptions.
        
        Args:
            log_file_list: List of log files to analyze
            
        Returns:
            Optional[Dict[str, Any]]: JSON response containing file descriptions
        """
        files_str = self._format_file_list(log_file_list)
        analysis_prompt = self._create_inventory_prompt(files_str)
        
        self._debug_log("Requesting analysis from AI model")
        response_stream = self._generate_content(analysis_prompt)
        
        complete_response = self._collect_stream_response(response_stream)
        self._debug_log("Received complete response from AI model")
        print(complete_response)
        return self._try_parse_json_response(complete_response)

    def analyze_log_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze a log file using AI.
        
        Args:
            file_path: Path to the log file to analyze
            
        Returns:
            Optional[Dict[str, Any]]: JSON response with analysis results
        """
        try:
            log_file = self._upload_file(file_path)
            analysis_prompt = self._create_analysis_prompt()
            
            response_stream = self._generate_content([log_file, analysis_prompt])
            complete_response = self._collect_stream_response(response_stream)
            
            self._cleanup_file(log_file.name)
            return self._try_parse_json_response(complete_response)
            
        except Exception as e:
            self._debug_log(f"Error during analysis: {str(e)}")
            raise

    def cleanup_all_files(self) -> None:
        """Clean up all uploaded files."""
        try:
            files = self.client.files.list()
            for file in files:
                self._cleanup_file(file.name)
        except Exception as e:
            self._debug_log(f"Warning: cleanup error: {str(e)}")

    # Private Helper Methods
    def _debug_log(self, message: str) -> None:
        """Print debug messages if debug mode is enabled."""
        if self.debug:
            click.secho(f"[DEBUG] {message}", fg='blue')

    def _generate_content(self, contents: Any) -> Iterator[GenerateContentResponse]:
        """Generate content using the AI model.
        
        Args:
            contents: Content to analyze
            
        Returns:
            Iterator[GenerateContentResponse]: Stream of AI responses
        """
        return self.client.models.generate_content_stream(
            model=DEFAULT_MODEL,
            contents=contents,
            config={
                'temperature': DEFAULT_TEMPERATURE,
                'top_p': DEFAULT_TOP_P,
            }
        )

    def _format_file_list(self, files: List[Path]) -> str:
        """Format file list for the prompt."""
        return "\n".join(str(f) for f in files)

    def _create_inventory_prompt(self, files_str: str) -> str:
        """Create the inventory analysis prompt."""
        prompt = f"""Analyze the following list of log files and return a valid JSON object.  
                    Identify and include only the most relevant log files for system analysis.  
                    For each relevant file, extract:
                    - the absolute file name,  
                    - a brief description of its purpose, and  
                    - a short, unique identifier (`short_name`) to reference it programmatically.  
                    The `short_name` should be lowercase, concise, and suitable as a dictionary key (e.g., `auth_log`, `kernel_log`).  
                    Output only the JSON object, with no additional text.  
                    Use the following structure:

                    {{
                    "log_files": [
                        {{
                        "file": "absolute file name",
                        "description": "brief description of the log file purpose",
                        "short_name": "unique short name to be used as dictionary reference"
                        }}
                    ]
                    }}

                    Files to analyze:
                    {files_str}
                    """
        return prompt

    def _create_analysis_prompt(self) -> str:
        """Create the log file analysis prompt."""
        return (
            "Parse the following log file and return a valid JSON object. "
            "Include only entries with log levels: ERROR, WARNING, or CRITICAL. "
            "Sort the issues from most recent to oldest based on the timestamp. "
            "Convert all timestamps to ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ). "
            "Group duplicate issues by identical log_level and summary. "
            "For each group, include:\n\n"
            "- the most recent timestamp,\n"
            "- the number of occurrences, and\n"
            "- a list of all matching original log lines with their timestamps.\n\n"
            "Output only the JSON object, with no additional text before or after. "
            "Use the following structure:\n"
            "{\n"
            '  "issues": [\n'
            "    {\n"
            '      "index": number,\n'
            '      "log_timestamp": "Most recent timestamp in the group (ISO 8601)",\n'
            '      "log_level": "ERROR/WARNING/CRITICAL",\n'
            '      "summary": "Short description of the issue",\n'
            '      "occurrence_count": number,\n'
            '      "occurrences": [\n'
            "        {\n"
            '          "log_timestamp": "ISO 8601 timestamp",\n'
            '          "issue_original_line": "Exact log line"\n'
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

    def _upload_file(self, file_path: str) -> Any:
        """Upload a file for analysis."""
        self._debug_log(f"Uploading file: {file_path}")
        log_file = self.client.files.upload(
            file=file_path,
            config={"mime_type": "text/plain"}
        )
        self._debug_log("File uploaded successfully")
        return log_file

    def _collect_stream_response(self, response_stream: Iterator[GenerateContentResponse]) -> str:
        """Collect streaming response from the AI model."""
        full_response = []
        chunk_count = 0
        
        if self.debug:
            click.echo("\nReceiving response:")
        
        for chunk in response_stream:
            if chunk.text:
                full_response.append(chunk.text)
                chunk_count += 1
                if self.debug:
                    print(f"\rChunks received: {chunk_count}", end="", flush=True)
        
        if self.debug:
            print()
            
        return "".join(full_response)

    def _try_parse_json_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Try to parse the response as JSON with retries."""
        for attempt in range(MAX_RETRIES):
            try:
                self._debug_log(f"Parsing JSON (attempt {attempt + 1}/{MAX_RETRIES})")
                return json.loads(response_text)
            except json.JSONDecodeError:
                if attempt < MAX_RETRIES - 1:
                    fixed_text = self._fix_json_text(response_text)
                    try:
                        return json.loads(fixed_text)
                    except json.JSONDecodeError:
                        continue
        
        self._debug_log("All JSON parsing attempts failed")
        click.secho("\nFailed to parse JSON. Raw response:", fg='yellow')
        click.echo(response_text)
        return None

    def _fix_json_text(self, text: str) -> str:
        """Attempt to fix malformed JSON text."""
        self._debug_log("Attempting to fix JSON formatting")
        text = text.strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        return text[start_idx:end_idx] if start_idx != -1 and end_idx != 0 else text

    def _cleanup_file(self, file_name: str) -> None:
        """Clean up an uploaded file."""
        try:
            self._debug_log(f"Cleaning up file: {file_name}")
            # Use the files.delete attribute directly as a callable
            self.client.files.delete(file_name)
        except Exception as e:
            self._debug_log(f"Warning: cleanup error: {str(e)}")
