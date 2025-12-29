"""
AI Agent - Intelligent validation using LLM capabilities

This module uses OpenAI's GPT-4 to provide intelligent analysis of API responses,
generating human-readable reports and suggesting specification corrections.
"""

import os
import json
from typing import Dict, List, Any, Optional
from openai import OpenAI
from api_validator import ValidationIssue, ValidationSeverity


class AIValidationAgent:
    """
    AI-powered agent that analyzes API validation results and provides insights.
    
    This agent goes beyond simple schema validation by understanding context
    and providing actionable recommendations for fixing drift issues.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AI validation agent.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4"
    
    def analyze_validation_issues(self, issues: List[ValidationIssue], 
                                  spec_context: Dict[str, Any]) -> str:
        """
        Analyze validation issues using AI to provide intelligent insights.
        
        Args:
            issues: List of validation issues found
            spec_context: Context from the OpenAPI specification
            
        Returns:
            Human-readable analysis report
        """
        if not issues:
            return "No validation issues found. API is in sync with specification."
        
        # Prepare context for AI
        issues_summary = self._format_issues_for_ai(issues)
        
        prompt = f"""You are an API documentation expert analyzing drift between OpenAPI specifications and actual API implementations.

I have detected the following validation issues:

{issues_summary}

Please provide:
1. A brief executive summary of the drift severity
2. The most critical issues that need immediate attention
3. Specific recommendations for updating the OpenAPI specification
4. Potential root causes for these discrepancies

Be concise and actionable. Focus on helping developers quickly fix the drift."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert API architect specializing in OpenAPI specifications and API governance."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more focused responses
                max_tokens=1000
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            return f"AI analysis failed: {str(e)}\n\nPlease review validation issues manually."
    
    def _format_issues_for_ai(self, issues: List[ValidationIssue]) -> str:
        """Format validation issues for AI consumption"""
        formatted = []
        
        for i, issue in enumerate(issues, 1):
            issue_text = f"{i}. [{issue.severity.value.upper()}] {issue.method} {issue.endpoint}\n"
            issue_text += f"   Problem: {issue.message}\n"
            
            if issue.expected is not None:
                issue_text += f"   Expected: {issue.expected}\n"
            if issue.actual is not None:
                issue_text += f"   Actual: {issue.actual}\n"
            
            formatted.append(issue_text)
        
        return "\n".join(formatted)
    
    def suggest_spec_fix(self, endpoint: str, method: str, 
                        issue: ValidationIssue, current_spec: Dict[str, Any]) -> str:
        """
        Generate a specific OpenAPI spec fix for a validation issue.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            issue: Validation issue to fix
            current_spec: Current OpenAPI specification section
            
        Returns:
            Suggested YAML/JSON fix for the specification
        """
        prompt = f"""Given this OpenAPI specification issue:

Endpoint: {method} {endpoint}
Problem: {issue.message}
Expected: {issue.expected}
Actual: {issue.actual}

Current spec section:
```yaml
{json.dumps(current_spec, indent=2)}
```

Provide the corrected OpenAPI specification in YAML format. Only show the changed section."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an OpenAPI 3.0 specification expert. Provide only valid YAML output."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            return f"Could not generate fix: {str(e)}"
    
    def generate_drift_report(self, issues: List[ValidationIssue],
                             spec_path: str, base_url: str) -> Dict[str, Any]:
        """
        Generate a comprehensive drift report with AI insights.
        
        Args:
            issues: List of validation issues
            spec_path: Path to OpenAPI spec file
            base_url: API base URL
            
        Returns:
            Structured drift report
        """
        # Categorize issues by severity
        categorized = {
            'critical': [],
            'error': [],
            'warning': [],
            'info': []
        }
        
        for issue in issues:
            categorized[issue.severity.value].append({
                'endpoint': issue.endpoint,
                'method': issue.method,
                'message': issue.message,
                'expected': issue.expected,
                'actual': issue.actual
            })
        
        # Get AI analysis
        ai_analysis = self.analyze_validation_issues(issues, {})
        
        # Build comprehensive report
        report = {
            'metadata': {
                'spec_path': spec_path,
                'base_url': base_url,
                'total_issues': len(issues),
                'timestamp': self._get_timestamp()
            },
            'summary': {
                'critical': len(categorized['critical']),
                'error': len(categorized['error']),
                'warning': len(categorized['warning']),
                'info': len(categorized['info'])
            },
            'issues': categorized,
            'ai_analysis': ai_analysis,
            'recommendations': self._generate_recommendations(categorized)
        }
        
        return report
    
    def _generate_recommendations(self, categorized_issues: Dict[str, List]) -> List[str]:
        """Generate actionable recommendations based on issues"""
        recommendations = []
        
        if categorized_issues['critical']:
            recommendations.append("URGENT: Address critical issues immediately - these indicate major spec-implementation mismatches")
        
        if categorized_issues['error']:
            recommendations.append("Fix error-level issues before next release - these affect API contract compliance")
        
        if categorized_issues['warning']:
            recommendations.append("Review warnings - these may indicate upcoming breaking changes")
        
        if not any(categorized_issues.values()):
            recommendations.append("Excellent! API and specification are in perfect sync")
        else:
            recommendations.append("Consider implementing automated spec validation in CI/CD pipeline")
            recommendations.append("Schedule regular spec-to-implementation audits")
        
        return recommendations
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
    
    def export_report_markdown(self, report: Dict[str, Any]) -> str:
        """
        Export drift report as formatted Markdown.
        
        Args:
            report: Drift report dictionary
            
        Returns:
            Markdown-formatted report
        """
        md = f"""# API Drift Validation Report

**Generated:** {report['metadata']['timestamp']}  
**Specification:** `{report['metadata']['spec_path']}`  
**API Base URL:** `{report['metadata']['base_url']}`

---

## Executive Summary

Total Issues Found: **{report['metadata']['total_issues']}**

- Critical: {report['summary']['critical']}
- Errors: {report['summary']['error']}
- Warnings: {report['summary']['warning']}
- Info: {report['summary']['info']}

---

## AI Analysis

{report['ai_analysis']}

---

## Recommendations

"""
        for i, rec in enumerate(report['recommendations'], 1):
            md += f"{i}. {rec}\n"
        
        md += "\n---\n\n## Detailed Issues\n\n"
        
        # Add detailed issues by severity
        for severity in ['critical', 'error', 'warning', 'info']:
            issues = report['issues'][severity]
            if issues:
                md += f"\n### {severity.upper()} ({len(issues)})\n\n"
                for issue in issues:
                    md += f"**{issue['method']} {issue['endpoint']}**\n"
                    md += f"- Problem: {issue['message']}\n"
                    if issue['expected']:
                        md += f"- Expected: `{issue['expected']}`\n"
                    if issue['actual']:
                        md += f"- Actual: `{issue['actual']}`\n"
                    md += "\n"
        
        return md
