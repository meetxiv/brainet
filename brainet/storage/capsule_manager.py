"""
Context capsule management module.

This module handles storing, loading, and managing context capsules,
including versioning and cleanup of old capsules.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .models.capsule import Capsule

class CapsuleManager:
    """Manages storage and retrieval of context capsules."""
    
    def __init__(self, storage_dir: Path):
        """
        Initialize the capsule manager.
        
        Args:
            storage_dir: Directory to store capsules in
        """
        self.storage_dir = storage_dir
        self._ensure_storage_dir()
    
    def save_capsule(self, capsule: Capsule) -> Path:
        """
        Save a context capsule to storage.
        
        Args:
            capsule: The capsule to save
            
        Returns:
            Path: Path to the saved capsule file
        """
        return capsule.save(self.storage_dir)
    
    def load_capsule(self, capsule_path: Path) -> Capsule:
        """
        Load a capsule from storage.
        
        Args:
            capsule_path: Path to the capsule file
            
        Returns:
            Capsule: The loaded capsule
            
        Raises:
            FileNotFoundError: If the capsule file doesn't exist
            json.JSONDecodeError: If the capsule file is invalid
        """
        return Capsule.load(capsule_path)
    
    def get_latest_capsule(self) -> Optional[Capsule]:
        """
        Get the most recent capsule.
        
        Returns:
            Optional[Capsule]: The most recent capsule, or None if no capsules exist
        """
        capsules = self.list_capsules()
        if not capsules:
            return None
        
        latest = max(capsules, key=lambda p: p.stem)
        return self.load_capsule(latest)
    
    def list_capsules(self) -> List[Path]:
        """
        List all capsule files in storage.
        
        Returns:
            List[Path]: List of paths to capsule files
        """
        return sorted(
            self.storage_dir.glob("capsule_*.json"),
            key=lambda p: p.stem
        )
    
    def cleanup_old_capsules(self, max_age: timedelta = timedelta(days=7)) -> int:
        """
        Remove capsules older than max_age.
        
        Args:
            max_age: Maximum age of capsules to keep
            
        Returns:
            int: Number of capsules removed
        """
        cutoff = datetime.utcnow() - max_age
        removed = 0
        
        for capsule_path in self.list_capsules():
            try:
                capsule = self.load_capsule(capsule_path)
                if capsule.metadata.timestamp < cutoff:
                    capsule_path.unlink()
                    removed += 1
            except (json.JSONDecodeError, FileNotFoundError):
                # Remove corrupt or missing capsules
                try:
                    capsule_path.unlink()
                    removed += 1
                except FileNotFoundError:
                    pass
        
        return removed
    
    def _ensure_storage_dir(self):
        """Create the storage directory if it doesn't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)