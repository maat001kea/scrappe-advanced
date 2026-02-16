"""Basic data extraction using CSS selectors and XPath"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup
from lxml import html
import re


class BasicExtractor:
    """
    Basic data extractor using CSS selectors and XPath
    
    Supports:
    - CSS selectors (BeautifulSoup)
    - XPath (lxml)
    - Attribute extraction
    - Text content extraction
    """
    
    def __init__(self, html_content: str):
        self.html = html_content
        self.soup = BeautifulSoup(html_content, 'lxml')
        self.tree = html.fromstring(html_content)
    
    def extract_by_css(
        self,
        selector: str,
        attribute: Optional[str] = None,
        get_all: bool = False
    ) -> Any:
        """
        Extract data using CSS selector
        
        Args:
            selector: CSS selector string
            attribute: HTML attribute to extract (None for text)
            get_all: Return all matches instead of first
        
        Returns:
            Extracted data (string, list, or None)
        """
        if get_all:
            elements = self.soup.select(selector)
            results = []
            for elem in elements:
                if attribute:
                    results.append(elem.get(attribute, ''))
                else:
                    results.append(elem.get_text(strip=True))
            return results
        else:
            element = self.soup.select_one(selector)
            if not element:
                return None
            if attribute:
                return element.get(attribute, '')
            return element.get_text(strip=True)
    
    def extract_by_xpath(
        self,
        xpath: str,
        get_all: bool = False
    ) -> Any:
        """
        Extract data using XPath
        
        Args:
            xpath: XPath expression
            get_all: Return all matches instead of first
        
        Returns:
            Extracted data (string, list, or None)
        """
        if get_all:
            elements = self.tree.xpath(xpath)
            return [elem.text_content().strip() if hasattr(elem, 'text_content') else str(elem) for elem in elements]
        else:
            element = self.tree.xpath(xpath)
            if not element:
                return None
            elem = element[0]
            return elem.text_content().strip() if hasattr(elem, 'text_content') else str(elem)
    
    def extract_by_regex(
        self,
        pattern: str,
        text: Optional[str] = None
    ) -> List[str]:
        """
        Extract data using regex pattern
        
        Args:
            pattern: Regular expression pattern
            text: Text to search (default: entire HTML)
        
        Returns:
            List of matched strings
        """
        if text is None:
            text = self.html
        return re.findall(pattern, text)
    
    def extract_all_links(
        self,
        selector: str = "a",
        attribute: str = "href"
    ) -> List[str]:
        """Extract all links matching selector"""
        return self.extract_by_css(selector, attribute, get_all=True)
    
    def extract_title(self) -> Optional[str]:
        """Extract page title"""
        title = self.soup.find('title')
        return title.get_text(strip=True) if title else None
    
    def extract_meta(
        self,
        name: Optional[str] = None,
        property_: Optional[str] = None
    ) -> Optional[str]:
        """Extract meta tag content"""
        if name:
            meta = self.soup.find('meta', attrs={'name': name})
        elif property_:
            meta = self.soup.find('meta', attrs={'property': property_})
        else:
            return None
        return meta.get('content') if meta else None


def extract_basic(html_content: str, selector: str, attribute: Optional[str] = None) -> Any:
    """Convenience function for basic extraction"""
    extractor = BasicExtractor(html_content)
    return extractor.extract_by_css(selector, attribute)
