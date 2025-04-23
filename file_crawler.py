#!/usr/bin/env python3
from pathlib import Path
from typing import List, Set


class FileCrawler:
    def __init__(
        self,
        root_path: str = "/var/log",
        exclude_patterns: Set[str] = None
    ):
        """Initialize the FileCrawler.
        
        Args:
            root_path (str): The root directory to start crawling from
            exclude_patterns (Set[str]): Set of patterns to exclude
                (e.g., {"*.gz", "*.old"})
        """
        self.root_path = Path(root_path)
        self.exclude_patterns = exclude_patterns or set()
        
    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded based on patterns.
        
        Args:
            path (Path): The path to check
            
        Returns:
            bool: True if the path should be excluded
        """
        return any(path.match(pattern) for pattern in self.exclude_patterns)
    
    def get_files(self) -> List[Path]:
        """Get a recursive list of all files from the root path.
        
        Returns:
            List[Path]: List of Path objects for all found files
            
        Raises:
            PermissionError: If access is denied to any directory
            FileNotFoundError: If the root path doesn't exist
        """
        if not self.root_path.exists():
            raise FileNotFoundError(
                f"Root path does not exist: {self.root_path}"
            )
        
        files = []
        try:
            for entry in self.root_path.rglob("*"):
                try:
                    # Skip if matches exclude pattern
                    if self._should_exclude(entry):
                        continue
                    
                    # Only add files, not directories
                    if entry.is_file():
                        files.append(entry)
                        
                except PermissionError as e:
                    print(f"Permission denied accessing {entry}: {e}")
                    continue
                    
        except PermissionError as e:
            print(
                f"Permission denied accessing root path {self.root_path}: {e}"
            )
            raise
            
        return sorted(files)
    
    def get_file_paths(self) -> List[str]:
        """Get a recursive list of all file paths as strings.
        
        Returns:
            List[str]: List of string paths for all found files
        """
        return [str(f) for f in self.get_files()]