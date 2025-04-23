#!/usr/bin/env python3

# Standard library imports
import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Any

# Third-party imports
import click
from dotenv import load_dotenv
from pydantic import BaseModel
from xdg_base_dirs import xdg_cache_home

# Local imports
from file_crawler import FileCrawler
from ai_analyzer import AIAnalyzer

# Constants
CACHE_DIR = xdg_cache_home() / "log_whisperer"
CACHE_FILE = CACHE_DIR / "log_inventory.json"


class LogInventory(BaseModel):
    """Model for storing log file inventory data."""
    last_updated: str
    log_files: List[Dict[str, Any]]


class LogHandler:
    """Handles operations on log files."""
    
    def __init__(self, file_path: str) -> None:
        """Initialize the LogHandler with a file path.
        
        Args:
            file_path: Path to the log file
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If the file can't be read
        """
        self.file_path = file_path
        self._validate_file()
        
    def _validate_file(self) -> None:
        """Check if the file exists and can be read."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        if not os.access(self.file_path, os.R_OK):
            raise PermissionError(f"Cannot read file: {self.file_path}")
    
    def read_content(self) -> str:
        """Read and return the content of the log file."""
        with open(self.file_path, 'r') as f:
            return f.read()
    
    def get_file(self) -> str:
        """Return the full file path."""
        return self.file_path
    
    def get_file_name(self) -> str:
        """Return just the file name without the path."""
        return os.path.basename(self.file_path)


def initialize_log_inventory() -> None:
    """Initialize the log inventory by crawling for log files."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        crawler = FileCrawler(exclude_patterns={"*.gz", "*.old"})
        click.secho("Scanning for log files...", fg='blue')
        log_files = crawler.get_files()
        analyzer = AIAnalyzer(api_key=os.getenv('GOOGLE_API_KEY'), debug=True)
        log_available = analyzer.populate_log_inventory(log_files)

        # Extract the list from the dictionary if needed
        log_files_list = log_available.get('log_files', []) if isinstance(log_available, dict) else log_available

        # Create inventory with the correct list format
        log_inventory = LogInventory(
            last_updated=datetime.now().isoformat(),
            log_files=log_files_list
        )
        
        with open(CACHE_FILE, 'w') as f:
            f.write(log_inventory.model_dump_json(indent=2))
            
        click.secho(f"Log inventory saved to {CACHE_FILE}", fg='green')
        click.secho(f"Found {len(log_files_list)} log files", fg='blue')
        
    except Exception as e:
        msg = f"Error initializing log inventory: {str(e)}"
        click.secho(msg, fg='red', err=True)
        raise


def load_log_inventory() -> Optional[LogInventory]:
    """Load the log inventory from cache file."""
    try:
        if not CACHE_FILE.exists():
            return None
        with open(CACHE_FILE, 'r') as f:
            data = json.load(f)
            return LogInventory(**data)
    except Exception as e:
        msg = f"Error loading log inventory: {str(e)}"
        click.secho(msg, fg='red', err=True)
        return None


def display_log_inventory() -> None:
    """Display the log inventory in a formatted table."""
    inventory = load_log_inventory()
    if not inventory:
        click.secho("No log inventory found. Run --init first.", fg='yellow')
        return

    click.secho("\nLog Files Inventory:", fg='green', bold=True)
    click.secho(f"Last updated: {inventory.last_updated}", fg='blue')
    click.echo("\nAvailable logs:")
    
    for log in inventory.log_files:
        name = log.get('name', 'Unknown')
        path = log.get('path', 'Unknown')
        click.echo(f"- {name}: {path}")


def find_log_by_name(name: str) -> Optional[str]:
    """Find a log file's full path by its short name."""
    inventory = load_log_inventory()
    if not inventory:
        return None
        
    for log in inventory.log_files:
        if log.get('name') == name:
            return log.get('path')
    return None


def format_issue_header(issue: Dict[str, Any]) -> str:
    """Format the issue header with index, log level, and timestamp."""
    return f"|{issue['index']}|{issue['log_level']}|{issue['log_timestamp']}|"


def print_formatted_issues(json_response: Dict[str, Any]) -> None:
    """Print issues in a formatted way with colored output.
    
    Args:
        json_response: Dictionary containing the analysis results
    """
    if 'issues' not in json_response:
        return

    level_colors = {
        'ERROR': 'red',
        'WARNING': 'yellow',
        'INFO': 'blue'
    }
    
    for issue in json_response['issues']:
        header_color = level_colors.get(issue['log_level'], 'blue')
        click.secho(format_issue_header(issue), fg=header_color, bold=True)
        click.secho(f"Summary: {issue['summary']}", fg='cyan')
        click.secho(f"Original: {issue['issue_original_line']}", fg='white')
        click.echo("")


def try_parse_json_response(response_text: str, max_retries: int = 3) -> Optional[Dict]:
    """Try to parse the response as JSON, with retries and formatting fixes."""
    for _ in range(max_retries):
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx > 0:
                try:
                    return json.loads(response_text[start_idx:end_idx])
                except json.JSONDecodeError:
                    continue
    return None


def collect_stream_response(response_stream: Any) -> str:
    """Collect and display streaming response while building complete text."""
    full_response = []
    chunk_count = 0
    
    click.echo("\nReceiving response:")
    print("\rChunks received: 0", end="", flush=True)
    
    for chunk in response_stream:
        if chunk.text:
            full_response.append(chunk.text)
            chunk_count += 1
            print(f"\rChunks received: {chunk_count}", end="", flush=True)
    
    print()
    return "".join(full_response)


@click.command()
@click.option(
    '--init', '-i', 
    is_flag=True, 
    help='Initialize log file inventory'
)
@click.option(
    '--file', '-f',
    type=str, 
    help='Full path to the log file to analyze'
)
@click.option(
    '--name', '-n',
    type=str, 
    help='Short name of the log file from inventory'
)
@click.option('--list', '-l', is_flag=True, help='List available log files')
@click.option('--verbose', '-v', is_flag=True, help='Show verbose output')
def cli(init: bool, file: str, name: str, list: bool, verbose: bool) -> None:
    """CLI tool for analyzing log files with AI."""
    if init:
        try:
            click.secho("Initializing log inventory...", fg='blue')
            initialize_log_inventory()
        except Exception as e:
            msg = f"Initialization failed: {str(e)}"
            click.secho(msg, fg='red', err=True)
            return

    if list:
        display_log_inventory()
        return

    if name:
        # Try to find the file by short name
        if full_path := find_log_by_name(name):
            file = full_path
        else:
            click.secho(
                f"No log file found with short name: {name}", 
                fg='red',
                err=True
            )
            return

    if file:
        try:
            log_handler = LogHandler(file)
            click.secho(
                f"Analyzing file: {log_handler.get_file()}...", 
                fg='blue'
            )
            
            analyzer = AIAnalyzer(
                api_key=os.getenv('GOOGLE_API_KEY'), 
                debug=verbose
            )
            if json_response := analyzer.analyze_log_file(
                log_handler.get_file()
            ):
                click.secho("\nAnalysis Results:", fg='green', bold=True)
                print_formatted_issues(json_response)
            else:
                click.secho("Failed to parse analysis results.", fg='red')
                
        except (FileNotFoundError, PermissionError) as e:
            click.secho(f"File error: {str(e)}", fg='red', err=True)
        except Exception as e:
            msg = f"Error ({type(e).__name__}): {str(e)}"
            click.secho(msg, fg='red', err=True)

    if not any([init, list, file, name]):
        msg = "No action specified. Use --help for usage information."
        click.secho(msg, fg='yellow')


if __name__ == '__main__':
    load_dotenv()
    cli()
