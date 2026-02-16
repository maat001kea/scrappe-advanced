"""
Advanced Data Extraction Strategies

Supports multiple extraction methods:
- CSS Selectors
- XPath expressions
- Regex patterns
- JSONPath
- NLP-based extraction (text similarity, entity extraction)
- Multi-field extraction with validation
- List/table parsing
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from bs4 import BeautifulSoup
import lxml
from lxml import etree, html

try:
    from jsonpath_ng import parse as parse_jsonpath
    JSONPATH_AVAILABLE = True
except ImportError:
    JSONPATH_AVAILABLE = False

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class ExtractorConfig:
    """Configuration for advanced extraction"""
    # Primary extraction method
    method: str = "css"  # css, xpath, regex, jsonpath, nlp
    
    # Selectors/Patterns
    selector: str = ""
    selector_type: str = "css"  # css, xpath, regex, jsonpath
    
    # Field extraction
    extract_text: bool = True
    extract_attribute: Optional[str] = None
    extract_html: bool = False
    
    # Validation
    required: bool = False
    pattern: Optional[str] = None  # Regex pattern for validation
    min_length: int = 0
    max_length: int = 10000
    
    # List extraction
    extract_list: bool = False
    list_separator: str = ","
    
    # Cleanup
    strip_whitespace: bool = True
    remove_duplicates: bool = False
    
    # NLP settings
    similarity_threshold: float = 0.7
    entity_types: List[str] = field(default_factory=list)
    
    # Fallback
    fallback_selector: Optional[str] = None
    fallback_method: Optional[str] = None


class AdvancedExtractor:
    """
    Advanced data extractor with multiple strategies
    """
    
    def __init__(self, config: Optional[ExtractorConfig] = None):
        self.config = config or ExtractorConfig()
        self._stats: Dict[str, Any] = {
            "extracted": 0,
            "failed": 0,
            "fallback_used": 0
        }
    
    def extract(self, html: str, selector: Optional[str] = None) -> Any:
        """
        Extract data using configured method
        
        Args:
            html: HTML content
            selector: Override default selector
        
        Returns:
            Extracted data (string, list, or dict)
        """
        if selector:
            self.config.selector = selector
        
        method = self.config.method.lower()
        selector = self.config.selector
        
        try:
            if method == "css":
                result = self._extract_css(html, selector)
            elif method == "xpath":
                result = self._extract_xpath(html, selector)
            elif method == "regex":
                result = self._extract_regex(html, selector)
            elif method == "jsonpath":
                result = self._extract_jsonpath(html, selector)
            elif method == "nlp":
                result = self._extract_nlp(html, selector)
            else:
                logger.warning(f"Unknown method: {method}, trying CSS")
                result = self._extract_css(html, selector)
            
            # Post-process result
            result = self._post_process(result)
            
            self._stats["extracted"] += 1
            return result
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            self._stats["failed"] += 1
            
            # Try fallback
            if self.config.fallback_selector:
                try:
                    logger.info(f"Trying fallback selector: {self.config.fallback_selector}")
                    self._stats["fallback_used"] += 1
                    
                    fallback_method = self.config.fallback_method or self.config.method
                    if fallback_method == "xpath":
                        return self._extract_xpath(html, self.config.fallback_selector)
                    else:
                        return self._extract_css(html, self.config.fallback_selector)
                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
            
            return None
    
    def extract_multiple(
        self,
        html: str,
        fields: Dict[str, ExtractorConfig]
    ) -> Dict[str, Any]:
        """
        Extract multiple fields using different strategies
        
        Args:
            html: HTML content
            fields: Dict of field_name -> ExtractorConfig
        
        Returns:
            Dict with extracted values for each field
        """
        result = {}
        for field_name, field_config in fields.items():
            extractor = AdvancedExtractor(field_config)
            value = extractor.extract(html)
            result[field_name] = value
        
        return result
    
    def _extract_css(self, html: str, selector: str) -> Any:
        """Extract using CSS selectors"""
        soup = BeautifulSoup(html or "", "lxml")
        
        if self.config.extract_list:
            elements = soup.select(selector)
            results = []
            for elem in elements:
                if self.config.extract_html:
                    results.append(str(elem))
                elif self.config.extract_attribute:
                    results.append(elem.get(self.config.extract_attribute, ""))
                else:
                    results.append(elem.get_text(strip=True))
            return results
        else:
            elem = soup.select_one(selector)
            if not elem:
                return None
            
            if self.config.extract_html:
                return str(elem)
            elif self.config.extract_attribute:
                return elem.get(self.config.extract_attribute, "")
            else:
                return elem.get_text(strip=True)
    
    def _extract_xpath(self, html: str, selector: str) -> Any:
        """Extract using XPath expressions"""
        try:
            tree = html.fromstring(html or "")
            
            if self.config.extract_list:
                elements = tree.xpath(selector)
                results = []
                for elem in elements:
                    if hasattr(elem, 'get'):
                        if self.config.extract_attribute:
                            results.append(elem.get(self.config.extract_attribute, ""))
                        else:
                            results.append(elem.text_content().strip())
                    else:
                        results.append(str(elem))
                return results
            else:
                elements = tree.xpath(selector)
                if not elements:
                    return None
                
                elem = elements[0]
                if hasattr(elem, 'get'):
                    if self.config.extract_attribute:
                        return elem.get(self.config.extract_attribute, "")
                    else:
                        return elem.text_content().strip()
                else:
                    return str(elem)
                    
        except Exception as e:
            raise ValueError(f"XPath extraction failed: {e}")
    
    def _extract_regex(self, html: str, pattern: str) -> Any:
        """Extract using regex patterns"""
        flags = re.DOTALL | re.MULTILINE
        
        if self.config.extract_list:
            matches = re.findall(pattern, html, flags)
            if isinstance(matches[0], tuple) if matches else False:
                # Return first group if multiple groups
                matches = [m[0] for m in matches]
            return matches
        else:
            match = re.search(pattern, html, flags)
            if match:
                # Try to get named groups first
                if match.groupdict():
                    return match.groupdict()
                # Then all groups
                if match.groups():
                    return match.groups()[0] if len(match.groups()) == 1 else match.groups()
                # Finally whole match
                return match.group(0)
            return None
    
    def _extract_jsonpath(self, content: str, expression: str) -> Any:
        """Extract from JSON using JSONPath"""
        if not JSONPATH_AVAILABLE:
            raise ImportError("jsonpath-ng not installed")
        
        try:
            data = json.loads(content)
            jsonpath_expr = parse_jsonpath(expression)
            matches = [match.value for match in jsonpath_expr.find(data)]
            
            if self.config.extract_list:
                return matches
            else:
                return matches[0] if matches else None
                
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    def _extract_nlp(self, html: str, query: str) -> Any:
        """Extract using NLP similarity matching"""
        if not NLP_AVAILABLE:
            raise ImportError("scikit-learn or numpy not installed")
        
        soup = BeautifulSoup(html or "", "lxml")
        
        # Extract all text elements
        elements = soup.find_all(text=True)
        texts = [str(e).strip() for e in elements if str(e).strip()]
        texts = [t for t in texts if len(t) > 20]  # Filter short texts
        
        if not texts:
            return None
        
        # Vectorize texts
        vectorizer = TfidfVectorizer(max_features=1000)
        tfidf_matrix = vectorizer.fit_transform(texts + [query])
        
        # Calculate similarity
        query_vec = tfidf_matrix[-1:]
        text_vecs = tfidf_matrix[:-1]
        similarities = cosine_similarity(query_vec, text_vecs)[0]
        
        # Find best match
        best_idx = int(np.argmax(similarities))
        best_similarity = float(similarities[best_idx])
        
        if best_similarity >= self.config.similarity_threshold:
            return texts[best_idx]
        
        return None
    
    def _post_process(self, value: Any) -> Any:
        """Post-process extracted value"""
        if value is None:
            if self.config.required:
                raise ValueError("Required field is missing")
            return None
        
        # Handle lists
        if isinstance(value, list):
            if self.config.strip_whitespace:
                value = [str(v).strip() for v in value]
            
            if self.config.remove_duplicates:
                seen = set()
                unique = []
                for v in value:
                    if v not in seen:
                        seen.add(v)
                        unique.append(v)
                value = unique
            
            # Validate each element
            if self.config.pattern:
                regex = re.compile(self.config.pattern)
                value = [v for v in value if regex.search(str(v))]
            
            if self.config.extract_list:
                return self.config.list_separator.join(value)
            return value
        
        # Handle single values
        if isinstance(value, str):
            if self.config.strip_whitespace:
                value = value.strip()
            
            # Validate length
            if len(value) < self.config.min_length:
                if self.config.required:
                    raise ValueError(f"Value too short: {len(value)} < {self.config.min_length}")
                return None
            
            if len(value) > self.config.max_length:
                value = value[:self.config.max_length]
            
            # Validate pattern
            if self.config.pattern:
                if not re.search(self.config.pattern, value):
                    if self.config.required:
                        raise ValueError(f"Value doesn't match pattern: {self.config.pattern}")
                    return None
        
        return value
    
    def extract_table(self, html: str, table_selector: str = "table") -> List[Dict[str, str]]:
        """
        Extract table data as list of dicts
        
        Args:
            html: HTML content
            table_selector: CSS selector for table
        
        Returns:
            List of row dicts with column headers as keys
        """
        soup = BeautifulSoup(html or "", "lxml")
        table = soup.select_one(table_selector)
        
        if not table:
            return []
        
        # Extract headers
        headers = []
        header_row = table.find("tr")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
        
        # Extract rows
        rows = []
        for row in table.find_all("tr")[1:]:  # Skip header row
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            
            if cells:
                if headers:
                    row_dict = dict(zip(headers, cells))
                else:
                    row_dict = {f"col_{i}": cell for i, cell in enumerate(cells)}
                rows.append(row_dict)
        
        return rows
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics"""
        return self._stats.copy()
    
    def reset_stats(self):
        """Reset statistics"""
        self._stats = {
            "extracted": 0,
            "failed": 0,
            "fallback_used": 0
        }
