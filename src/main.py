"""
Main CLI - Command-line interface for API validation

This is the main entry point for the API documentation validator.
Provides commands for validation, drift detection, and report generation.
"""

import argparse
import sys
import os
import json
from pathlib import Path
from api_validator import APIValidator
from ai_agent import AIValidationAgent
from drift_detector import DriftDetector


def validate_command(args):
    """Execute validation command"""
    print(f"\nValidating API against specification...")
    print(f"Spec: {args.spec}")
    print(f"Base URL: {args.base_url}\n")
    
    # Create validator
    validator = APIValidator(args.spec, args.base_url)
    
    # Run validation
    issues = validator.validate_all_endpoints()
    
    # Print report
    validator.print_report()
    
    # Generate AI analysis if enabled
    if args.ai_analysis and os.getenv('OPENAI_API_KEY'):
        print("\n" + "="*80)
        print("AI-POWERED ANALYSIS")
        print("="*80 + "\n")
        
        try:
            agent = AIValidationAgent()
            analysis = agent.analyze_validation_issues(issues, validator.spec)
            print(analysis)
        except Exception as e:
            print(f"AI analysis failed: {e}")
    
    # Export report if requested
    if args.output:
        export_report(validator, issues, args.output, args.format)
    
    # Return exit code based on issues
    summary = validator.get_summary()
    if summary['critical'] > 0 or summary['error'] > 0:
        return 1
    return 0


def detect_drift_command(args):
    """Execute drift detection command"""
    print(f"\nDetecting specification drift...")
    print(f"Spec: {args.spec}\n")
    
    # Load current spec
    import yaml
    with open(args.spec, 'r') as f:
        if args.spec.endswith('.yaml') or args.spec.endswith('.yml'):
            current_spec = yaml.safe_load(f)
        else:
            current_spec = json.load(f)
    
    # Create drift detector
    detector = DriftDetector(args.history_dir)
    
    # Detect drift
    drift = detector.detect_drift(current_spec)
    
    # Print results
    print("="*80)
    print("DRIFT DETECTION REPORT")
    print("="*80 + "\n")
    
    if not drift['has_drift']:
        print("✓ No drift detected. Specification is unchanged.")
    else:
        print(f"⚠ Drift detected!")
        print(f"\nPrevious Version: {drift['previous_version']}")
        print(f"Current Version: {drift['current_version']}")
        print(f"\nChanges Summary:")
        print(f"  Added Endpoints: {len(drift['changes']['added_endpoints'])}")
        print(f"  Removed Endpoints: {len(drift['changes']['removed_endpoints'])}")
        print(f"  Modified Endpoints: {len(drift['changes']['modified_endpoints'])}")
        print(f"  Breaking Changes: {len(drift['changes']['breaking_changes'])}")
        
        if drift['changes']['breaking_changes']:
            print("\n⚠ BREAKING CHANGES DETECTED:")
            for bc in drift['changes']['breaking_changes']:
                print(f"  - [{bc['severity'].upper()}] {bc['type']}: {bc['endpoint']}")
    
    # Generate changelog if requested
    if args.changelog:
        changelog = detector.generate_changelog()
        print("\n" + "="*80)
        print(changelog)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(changelog)
            print(f"\nChangelog saved to: {args.output}")
    
    return 0


def generate_report_command(args):
    """Execute report generation command"""
    print(f"\nGenerating comprehensive validation report...")
    
    # Run validation
    validator = APIValidator(args.spec, args.base_url)
    issues = validator.validate_all_endpoints()
    
    # Generate AI-powered report
    if os.getenv('OPENAI_API_KEY'):
        try:
            agent = AIValidationAgent()
            report = agent.generate_drift_report(issues, args.spec, args.base_url)
            
            # Export as markdown
            markdown = agent.export_report_markdown(report)
            
            # Save to file
            output_path = args.output or "validation_report.md"
            with open(output_path, 'w') as f:
                f.write(markdown)
            
            print(f"\n✓ Report generated: {output_path}")
            
            # Also save JSON version
            json_path = output_path.replace('.md', '.json')
            with open(json_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            print(f"✓ JSON report: {json_path}")
            
        except Exception as e:
            print(f"Error generating AI report: {e}")
            return 1
    else:
        print("Error: OPENAI_API_KEY not set. AI-powered reports require OpenAI API access.")
        return 1
    
    return 0


def export_report(validator, issues, output_path, format_type):
    """Export validation report to file"""
    if format_type == 'json':
        report = {
            'spec': validator.spec_path,
            'base_url': validator.base_url,
            'summary': validator.get_summary(),
            'issues': [
                {
                    'severity': issue.severity.value,
                    'endpoint': issue.endpoint,
                    'method': issue.method,
                    'message': issue.message,
                    'expected': issue.expected,
                    'actual': issue.actual
                }
                for issue in issues
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
    
    elif format_type == 'markdown':
        # Simple markdown export
        md = f"""# API Validation Report

**Specification:** {validator.spec_path}  
**Base URL:** {validator.base_url}

## Summary

Total Issues: {validator.get_summary()['total']}

"""
        for issue in issues:
            md += f"\n### [{issue.severity.value.upper()}] {issue.method} {issue.endpoint}\n\n"
            md += f"{issue.message}\n\n"
            if issue.expected:
                md += f"**Expected:** `{issue.expected}`\n\n"
            if issue.actual:
                md += f"**Actual:** `{issue.actual}`\n\n"
        
        with open(output_path, 'w') as f:
            f.write(md)
    
    print(f"\n✓ Report exported to: {output_path}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='AI-Powered API Documentation Validator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate API against specification
  python main.py validate --spec openapi.yaml --base-url https://api.example.com
  
  # Validate with AI analysis
  python main.py validate --spec openapi.yaml --base-url https://api.example.com --ai-analysis
  
  # Detect specification drift
  python main.py detect-drift --spec openapi.yaml
  
  # Generate comprehensive report
  python main.py generate-report --spec openapi.yaml --base-url https://api.example.com
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate API against specification')
    validate_parser.add_argument('--spec', required=True, help='Path to OpenAPI specification file')
    validate_parser.add_argument('--base-url', required=True, help='Base URL of the API')
    validate_parser.add_argument('--ai-analysis', action='store_true', help='Enable AI-powered analysis')
    validate_parser.add_argument('--output', help='Output file for report')
    validate_parser.add_argument('--format', choices=['json', 'markdown'], default='json', help='Report format')
    
    # Detect drift command
    drift_parser = subparsers.add_parser('detect-drift', help='Detect specification drift')
    drift_parser.add_argument('--spec', required=True, help='Path to OpenAPI specification file')
    drift_parser.add_argument('--history-dir', default='.api_history', help='Directory for history storage')
    drift_parser.add_argument('--changelog', action='store_true', help='Generate changelog')
    drift_parser.add_argument('--output', help='Output file for changelog')
    
    # Generate report command
    report_parser = subparsers.add_parser('generate-report', help='Generate comprehensive validation report')
    report_parser.add_argument('--spec', required=True, help='Path to OpenAPI specification file')
    report_parser.add_argument('--base-url', required=True, help='Base URL of the API')
    report_parser.add_argument('--output', help='Output file for report (default: validation_report.md)')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    try:
        if args.command == 'validate':
            return validate_command(args)
        elif args.command == 'detect-drift':
            return detect_drift_command(args)
        elif args.command == 'generate-report':
            return generate_report_command(args)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
