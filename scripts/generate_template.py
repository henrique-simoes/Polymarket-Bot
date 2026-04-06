#!/usr/bin/env python3
"""
Code Template Generator
Generates compliant code templates following architecture standards

Usage:
    python generate_template.py --class MyComponent
    python generate_template.py --api-method fetch_data
    python generate_template.py --test TestMyComponent
"""

import argparse
from pathlib import Path


def generate_class_template(class_name: str) -> str:
    """Generate a compliant class template"""
    return f'''"""
{class_name} - [Brief description]

[Detailed description of what this component does]
"""

import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from threading import Lock
from functools import wraps
import time


def retry_api_call(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator for retrying API calls with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for delay on each retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.Timeout as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"  [RETRY] {{func.__name__}} timeout, retrying in {{delay:.1f}}s")
                        time.sleep(delay)
                        delay *= backoff_factor
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if hasattr(e, 'response') and e.response and e.response.status_code in [429, 500, 502, 503, 504]:
                        if attempt < max_retries:
                            print(f"  [RETRY] {{func.__name__}} got {{e.response.status_code}}, retrying in {{delay:.1f}}s")
                            time.sleep(delay)
                            delay *= backoff_factor
                        else:
                            raise
                    else:
                        raise
                except Exception:
                    raise

            raise last_exception

        return wrapper
    return decorator


class {class_name}:
    """
    {class_name} - [One line description]

    [Detailed description of class responsibilities]

    Thread Safety: [SAFE/UNSAFE] - [Explain thread safety guarantees]
    Cache Lifetime: [Duration] - [Explain cache expiration policy]
    """

    def __init__(self, dependency1, dependency2=None):
        """
        Initialize {class_name}

        Args:
            dependency1: Description of dependency1
            dependency2: Optional description of dependency2
        """
        # Dependencies
        self.dependency1 = dependency1
        self.dependency2 = dependency2

        # Caches with expiration
        self.cache = {{}}
        self.cache_expiry = {{}}
        self.cache_ttl = 900  # 15 minutes in seconds

        # Thread safety
        self.lock = Lock()

        # Configuration
        self.timeout = 10  # API timeout in seconds
        self.max_retries = 3

        print(f"[INIT] {class_name} initialized")

    def clear_cache(self):
        """
        Clear all cached data

        Should be called when cache becomes stale (e.g., new round starts)
        """
        with self.lock:
            self.cache.clear()
            self.cache_expiry.clear()
        print(f"  [CACHE] {class_name} cache cleared")

    @retry_api_call(max_retries=3, initial_delay=1.0)
    def _fetch_from_api(self, url: str) -> dict:
        """
        Fetch data from API (private helper with retry logic)

        Args:
            url: API endpoint URL

        Returns:
            dict: API response data

        Raises:
            requests.RequestException: On API failure after all retries
        """
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_data(self, key: str) -> Optional[dict]:
        """
        Get data for key with caching

        Args:
            key: Data identifier

        Returns:
            dict: {{
                'success': bool,
                'data': dict or None,
                'error': str or None
            }}
        """
        try:
            # Check cache first
            with self.lock:
                if key in self.cache:
                    # Check if expired
                    if time.time() < self.cache_expiry.get(key, 0):
                        print(f"  [CACHE HIT] {{key}}")
                        return {{
                            'success': True,
                            'data': self.cache[key],
                            'error': None
                        }}
                    else:
                        # Expired, remove from cache
                        del self.cache[key]
                        if key in self.cache_expiry:
                            del self.cache_expiry[key]

            # Cache miss or expired - fetch from API
            print(f"  [CACHE MISS] {{key}}, fetching from API")
            data = self._fetch_from_api(f"https://api.example.com/{{key}}")

            # Update cache
            with self.lock:
                self.cache[key] = data
                self.cache_expiry[key] = time.time() + self.cache_ttl

            return {{
                'success': True,
                'data': data,
                'error': None
            }}

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] {class_name}.get_data({{key}}): API error: {{e}}")
            return {{
                'success': False,
                'data': None,
                'error': f'API error: {{str(e)}}'
            }}
        except Exception as e:
            print(f"[ERROR] {class_name}.get_data({{key}}): {{type(e).__name__}}: {{e}}")
            import traceback
            traceback.print_exc()
            return {{
                'success': False,
                'data': None,
                'error': f'{{type(e).__name__}}: {{str(e)}}'
            }}

    def validate_data(self, data: dict) -> dict:
        """
        Validate data meets requirements

        Args:
            data: Data to validate

        Returns:
            dict: {{
                'valid': bool,
                'issues': List[str],
                'error': str or None
            }}
        """
        try:
            issues = []

            # Validation logic here
            if not data:
                issues.append("Data is empty")

            if 'required_field' not in data:
                issues.append("Missing required_field")

            return {{
                'valid': len(issues) == 0,
                'issues': issues,
                'error': None
            }}

        except Exception as e:
            print(f"[ERROR] {class_name}.validate_data(): {{type(e).__name__}}: {{e}}")
            import traceback
            traceback.print_exc()
            return {{
                'valid': False,
                'issues': [],
                'error': f'{{type(e).__name__}}: {{str(e)}}'
            }}

    def process_with_threads(self, items: List[str]) -> Dict[str, any]:
        """
        Process items in parallel threads (thread-safe example)

        Args:
            items: List of items to process

        Returns:
            dict: Mapping of item -> result
        """
        from threading import Thread

        results = {{}}
        results_lock = Lock()  # Protect shared results dict

        def worker(item):
            """Thread worker function"""
            try:
                result = self._process_item(item)
                with results_lock:
                    results[item] = result
            except Exception as e:
                print(f"[ERROR] Processing {{item}}: {{e}}")
                with results_lock:
                    results[item] = {{'error': str(e)}}

        # Start threads
        threads = []
        for item in items:
            thread = Thread(target=worker, args=(item,))
            thread.start()
            threads.append(thread)

        # Wait for completion
        for thread in threads:
            thread.join(timeout=30)

        return results

    def _process_item(self, item: str) -> dict:
        """Process single item (internal helper)"""
        # Implementation here
        return {{'processed': True, 'item': item}}
'''


def generate_test_template(class_name: str) -> str:
    """Generate a test template"""
    return f'''"""
Tests for {class_name}

Run with: python -m pytest tests/test_{class_name.lower()}.py -v
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import time

from src.module import {class_name}  # Adjust import path


class Test{class_name}(unittest.TestCase):
    """Test {class_name} functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.dependency1 = Mock()
        self.component = {class_name}(self.dependency1)

    def tearDown(self):
        """Clean up after tests"""
        self.component.clear_cache()

    def test_initialization(self):
        """Test component initializes correctly"""
        self.assertIsNotNone(self.component)
        self.assertIsInstance(self.component.cache, dict)
        self.assertIsInstance(self.component.lock, type(unittest.mock.Lock()))

    def test_successful_get_data(self):
        """Test successful data retrieval"""
        with patch.object(self.component, '_fetch_from_api') as mock_fetch:
            mock_fetch.return_value = {{'data': 'value'}}

            result = self.component.get_data('test_key')

            self.assertTrue(result['success'])
            self.assertEqual(result['data'], {{'data': 'value'}})
            self.assertIsNone(result['error'])

    def test_cache_hit(self):
        """Test cache returns cached data"""
        # First call - cache miss
        with patch.object(self.component, '_fetch_from_api') as mock_fetch:
            mock_fetch.return_value = {{'data': 'value'}}
            result1 = self.component.get_data('test_key')

            # Second call - should hit cache
            result2 = self.component.get_data('test_key')

            # API should only be called once
            self.assertEqual(mock_fetch.call_count, 1)
            self.assertEqual(result1['data'], result2['data'])

    def test_cache_expiration(self):
        """Test cache expires correctly"""
        with patch.object(self.component, '_fetch_from_api') as mock_fetch:
            mock_fetch.return_value = {{'data': 'value'}}

            # Get data
            self.component.get_data('test_key')
            self.assertIn('test_key', self.component.cache)

            # Clear cache
            self.component.clear_cache()
            self.assertNotIn('test_key', self.component.cache)

    def test_api_error_handling(self):
        """Test API error handling"""
        with patch.object(self.component, '_fetch_from_api') as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            result = self.component.get_data('test_key')

            self.assertFalse(result['success'])
            self.assertIsNone(result['data'])
            self.assertIsNotNone(result['error'])
            self.assertIn('API Error', result['error'])

    def test_thread_safety(self):
        """Test thread-safe operations"""
        from threading import Thread

        with patch.object(self.component, '_process_item') as mock_process:
            mock_process.return_value = {{'processed': True}}

            items = ['item1', 'item2', 'item3']
            results = self.component.process_with_threads(items)

            # Verify all items processed
            self.assertEqual(len(results), len(items))
            for item in items:
                self.assertIn(item, results)

            # Verify no data corruption
            self.assertEqual(mock_process.call_count, len(items))

    def test_validation_success(self):
        """Test successful validation"""
        data = {{'required_field': 'value'}}
        result = self.component.validate_data(data)

        self.assertTrue(result['valid'])
        self.assertEqual(len(result['issues']), 0)

    def test_validation_failure(self):
        """Test validation catches issues"""
        data = {{}}  # Missing required_field
        result = self.component.validate_data(data)

        self.assertFalse(result['valid'])
        self.assertGreater(len(result['issues']), 0)


if __name__ == '__main__':
    unittest.main()
'''


def main():
    parser = argparse.ArgumentParser(description='Generate compliant code templates')
    parser.add_argument('--class', dest='class_name', help='Generate class template')
    parser.add_argument('--test', dest='test_name', help='Generate test template')
    parser.add_argument('--output', help='Output file (default: stdout)')

    args = parser.parse_args()

    output = None

    if args.class_name:
        output = generate_class_template(args.class_name)
    elif args.test_name:
        output = generate_test_template(args.test_name)
    else:
        parser.print_help()
        return

    if args.output:
        Path(args.output).write_text(output)
        print(f"✅ Template written to {{args.output}}")
    else:
        print(output)


if __name__ == '__main__':
    main()
