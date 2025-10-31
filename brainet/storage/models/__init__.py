"""
Models package for Brainet storage.

This package contains data models used for serializing and deserializing context capsules:
- capsule: Defines the structure and validation for context capsules
"""

from .capsule import Capsule, CapsuleMetadata, ProjectInfo, ContextData

__all__ = ['Capsule', 'CapsuleMetadata', 'ProjectInfo', 'ContextData']