"""Tests for the capsule manager module."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from brainet.storage.models.capsule import Capsule
from brainet.storage.capsule_manager import CapsuleManager

def test_capsule_manager_initialization(tmp_path):
    """Test CapsuleManager initialization."""
    storage_dir = tmp_path / "capsules"
    manager = CapsuleManager(storage_dir)
    
    assert storage_dir.exists()
    assert storage_dir.is_dir()

def test_save_and_load_capsule(tmp_path, sample_capsule):
    """Test saving and loading capsules."""
    manager = CapsuleManager(tmp_path / "capsules")
    
    # Save the capsule
    saved_path = manager.save_capsule(sample_capsule)
    assert saved_path.exists()
    
    # Load the capsule
    loaded = manager.load_capsule(saved_path)
    assert loaded.project.name == sample_capsule.project.name
    assert loaded.metadata.version == sample_capsule.metadata.version

def test_get_latest_capsule(tmp_path, sample_capsule):
    """Test retrieving the latest capsule."""
    manager = CapsuleManager(tmp_path / "capsules")
    
    # Save multiple capsules
    manager.save_capsule(sample_capsule)
    
    # Create a newer capsule
    newer_capsule = sample_capsule.model_copy()
    newer_capsule.metadata.timestamp = datetime.utcnow() + timedelta(hours=1)
    manager.save_capsule(newer_capsule)
    
    latest = manager.get_latest_capsule()
    assert latest.metadata.timestamp == newer_capsule.metadata.timestamp

def test_list_capsules(tmp_path, sample_capsule):
    """Test listing all capsules."""
    manager = CapsuleManager(tmp_path / "capsules")
    
    # Save multiple capsules
    paths = []
    for i in range(3):
        capsule = sample_capsule.model_copy()
        capsule.metadata.timestamp += timedelta(hours=i)
        paths.append(manager.save_capsule(capsule))
    
    listed = manager.list_capsules()
    assert len(listed) == 3
    assert all(p in listed for p in paths)

def test_cleanup_old_capsules(tmp_path, sample_capsule):
    """Test cleaning up old capsules."""
    manager = CapsuleManager(tmp_path / "capsules")
    
    # Save capsules with different ages
    old_capsule = sample_capsule.model_copy()
    old_capsule.metadata.timestamp = datetime.utcnow() - timedelta(days=10)
    manager.save_capsule(old_capsule)
    
    new_capsule = sample_capsule.model_copy()
    new_capsule.metadata.timestamp = datetime.utcnow()
    manager.save_capsule(new_capsule)
    
    # Clean up capsules older than 7 days
    removed = manager.cleanup_old_capsules(timedelta(days=7))
    assert removed == 1
    
    # Verify only the new capsule remains
    capsules = manager.list_capsules()
    assert len(capsules) == 1
    loaded = manager.load_capsule(capsules[0])
    assert loaded.metadata.timestamp == new_capsule.metadata.timestamp