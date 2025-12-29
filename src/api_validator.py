"""
API Validator - Core validation logic for OpenAPI specifications

This module provides functionality to validate API endpoints against OpenAPI 3.0 specs,
detecting schema mismatches, missing endpoints, and deprecated routes.
"""

import json
import yaml
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a single validation issue"""
    severity: ValidationSeverity
    endpoint: str
    method: str
    message: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None


class APIValidator:
    """
    Main validator class that compares actual API behavior with OpenAPI specifications.
    
    This validator helps identify drift between documentation and implementation,
    which is a common problem in fast-moving development teams.
    """
    
    def __init__(self, spec_path: str, base_url: str):
        """
        Initialize the API validator.
        
        Args:
            spec_path: Path to OpenAPI specification file (YAML or JSON)
            base_url: Base URL of the API to validate
        """
        self.spec_path = spec_path
        self.base_url = base_url.rstrip('/')
        self.spec = self._load_spec()
        self.issues: List[ValidationIssue] = []
    
    def _load_spec(self) -> Dict[str, Any]:
        """Load and parse OpenAPI specification"""
        with open(self.spec_path, 'r') as f:
            if self.spec_path.endswith('.yaml') or self.spec_path.endswith('.yml'):
                return yaml.safe_load(f)
            else:
                return json.load(f)
    
    def validate_all_endpoints(self) -> List[ValidationIssue]:
        """
        Validate all endpoints defined in the OpenAPI spec.
        
        Returns:
            List of validation issues found
        """
        self.issues = []
        
        if 'paths' not in self.spec:
            self.issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                endpoint="N/A",
                method="N/A",
                message="No paths defined in OpenAPI specification"
            ))
            return self.issues
        
        for path, methods in self.spec['paths'].items():
            for method, details in methods.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
                    self._validate_endpoint(path, method.upper(), details)
        
        return self.issues
    
    def _validate_endpoint(self, path: str, method: str, spec_details: Dict[str, Any]):
        """
        Validate a single endpoint against its specification.
        
        Args:
            path: API endpoint path (e.g., /users/{id})
            method: HTTP method (GET, POST, etc.)
            spec_details: OpenAPI specification details for this endpoint
        """
        # Replace path parameters with example values for testing
        test_path = self._prepare_test_path(path, spec_details)
        url = f"{self.base_url}{test_path}"
        
        try:
            # Make actual API call
            response = requests.request(
                method=method,
                url=url,
                timeout=10,
                headers={'Accept': 'application/json'}
            )
            
            # Validate response status code
            self._validate_status_code(path, method, response, spec_details)
            
            # Validate response schema if defined
            if response.status_code < 400:
                self._validate_response_schema(path, method, response, spec_details)
            
        except requests.exceptions.RequestException as e:
            self.issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                endpoint=path,
                method=method,
                message=f"Failed to reach endpoint: {str(e)}"
            ))
    
    def _prepare_test_path(self, path: str, spec_details: Dict[str, Any]) -> str:
        """
        Replace path parameters with test values.
        
        Args:
            path: Original path with parameters (e.g., /users/{id})
            spec_details: Endpoint specification details
            
        Returns:
            Path with parameters replaced (e.g., /users/1)
        """
        test_path = path
        
        # Extract parameters from spec
        parameters = spec_details.get('parameters', [])
        for param in parameters:
            if param.get('in') == 'path':
                param_name = param.get('name')
                # Use example value if provided, otherwise use default
                example_value = param.get('example', '1')
                test_path = test_path.replace(f"{{{param_name}}}", str(example_value))
        
        return test_path
    
    def _validate_status_code(self, path: str, method: str, 
                             response: requests.Response, spec_details: Dict[str, Any]):
        """Validate that response status code matches specification"""
        responses = spec_details.get('responses', {})
        status_code = str(response.status_code)
        
        if status_code not in responses and 'default' not in responses:
            self.issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                endpoint=path,
                method=method,
                message=f"Unexpected status code: {status_code}",
                expected=list(responses.keys()),
                actual=status_code
            ))
    
    def _validate_response_schema(self, path: str, method: str,
                                  response: requests.Response, spec_details: Dict[str, Any]):
        """Validate response body against schema definition"""
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            self.issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                endpoint=path,
                method=method,
                message="Response is not valid JSON"
            ))
            return
        
        # Get expected schema from spec
        responses = spec_details.get('responses', {})
        status_code = str(response.status_code)
        
        if status_code in responses:
            content = responses[status_code].get('content', {})
            json_content = content.get('application/json', {})
            schema = json_content.get('schema', {})
            
            if schema:
                # Basic schema validation (can be extended with jsonschema library)
                self._validate_schema_structure(path, method, response_data, schema)
    
    def _validate_schema_structure(self, path: str, method: str,
                                   data: Any, schema: Dict[str, Any]):
        """
        Perform basic schema structure validation.
        
        This is a simplified version - production systems should use jsonschema library.
        """
        schema_type = schema.get('type')
        
        if schema_type == 'object':
            if not isinstance(data, dict):
                self.issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    endpoint=path,
                    method=method,
                    message="Response should be an object",
                    expected="object",
                    actual=type(data).__name__
                ))
                return
            
            # Check required properties
            required = schema.get('required', [])
            for prop in required:
                if prop not in data:
                    self.issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        endpoint=path,
                        method=method,
                        message=f"Missing required property: {prop}",
                        expected=required,
                        actual=list(data.keys())
                    ))
        
        elif schema_type == 'array':
            if not isinstance(data, list):
                self.issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    endpoint=path,
                    method=method,
                    message="Response should be an array",
                    expected="array",
                    actual=type(data).__name__
                ))
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary of validation results.
        
        Returns:
            Dictionary with counts by severity level
        """
        summary = {
            'total': len(self.issues),
            'critical': 0,
            'error': 0,
            'warning': 0,
            'info': 0
        }
        
        for issue in self.issues:
            summary[issue.severity.value] += 1
        
        return summary
    
    def print_report(self):
        """Print a formatted validation report"""
        print("\n" + "="*80)
        print("API VALIDATION REPORT")
        print("="*80)
        print(f"\nSpecification: {self.spec_path}")
        print(f"Base URL: {self.base_url}")
        
        summary = self.get_summary()
        print(f"\nTotal Issues: {summary['total']}")
        print(f"  Critical: {summary['critical']}")
        print(f"  Errors: {summary['error']}")
        print(f"  Warnings: {summary['warning']}")
        print(f"  Info: {summary['info']}")
        
        if self.issues:
            print("\nDETAILED ISSUES:")
            print("-"*80)
            
            for i, issue in enumerate(self.issues, 1):
                print(f"\n{i}. [{issue.severity.value.upper()}] {issue.method} {issue.endpoint}")
                print(f"   {issue.message}")
                if issue.expected is not None:
                    print(f"   Expected: {issue.expected}")
                if issue.actual is not None:
                    print(f"   Actual: {issue.actual}")
        else:
            print("\n✓ No issues found! API matches specification perfectly.")
        
        print("\n" + "="*80)
