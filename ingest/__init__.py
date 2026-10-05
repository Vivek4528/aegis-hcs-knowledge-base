"""
Base parser interface for all format-specific parsers.
"""
from abc import ABC, abstractmethod
from schema import RawExtraction


class BaseParser(ABC):
    """Abstract base class for document parsers."""
    
    @abstractmethod
    def parse(self, filepath: str, file_info: dict) -> RawExtraction:
        """
        Parse a file and return a RawExtraction.
        
        Args:
            filepath: Absolute path to the file
            file_info: Dict from FILE_MANIFEST with format, trust_tier, etc.
        
        Returns:
            RawExtraction with all content, tables, diagrams, and pipeline documentation.
        """
        pass
    
    @property
    @abstractmethod
    def supported_formats(self) -> list:
        """Return list of format strings this parser handles."""
        pass
