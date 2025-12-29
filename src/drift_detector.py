"""
Drift Detector - Track API specification changes over time

This module monitors API changes and tracks specification version history,
helping teams understand when and how their APIs diverge from documentation.
"""

import json
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import difflib


@dataclass
class SpecSnapshot:
    """Represents a snapshot of API specification at a point in time"""
    timestamp: str
    spec_hash: str
    spec_version: str
    endpoints_count: int
    spec_data: Dict[str, Any]


class DriftDetector:
    """
    Detects and tracks drift between API specifications over time.
    
    This helps teams understand how their API documentation evolves
    and identify when breaking changes are introduced.
    """
    
    def __init__(self, history_dir: str = ".api_history"):
        """
        Initialize drift detector.
        
        Args:
            history_dir: Directory to store specification history
        """
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)
        self.snapshots: List[SpecSnapshot] = []
        self._load_history()
    
    def _load_history(self):
        """Load specification history from disk"""
        history_file = self.history_dir / "history.json"
        
        if history_file.exists():
            with open(history_file, 'r') as f:
                data = json.load(f)
                self.snapshots = [
                    SpecSnapshot(**snapshot) for snapshot in data
                ]
    
    def _save_history(self):
        """Save specification history to disk"""
        history_file = self.history_dir / "history.json"
        
        with open(history_file, 'w') as f:
            json.dump(
                [asdict(snapshot) for snapshot in self.snapshots],
                f,
                indent=2
            )
    
    def capture_snapshot(self, spec_data: Dict[str, Any]) -> SpecSnapshot:
        """
        Capture a snapshot of the current specification.
        
        Args:
            spec_data: OpenAPI specification data
            
        Returns:
            Created snapshot
        """
        # Calculate hash of specification
        spec_json = json.dumps(spec_data, sort_keys=True)
        spec_hash = hashlib.sha256(spec_json.encode()).hexdigest()[:12]
        
        # Count endpoints
        endpoints_count = sum(
            len(methods) for methods in spec_data.get('paths', {}).values()
        )
        
        # Create snapshot
        snapshot = SpecSnapshot(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            spec_hash=spec_hash,
            spec_version=spec_data.get('info', {}).get('version', 'unknown'),
            endpoints_count=endpoints_count,
            spec_data=spec_data
        )
        
        # Only save if different from last snapshot
        if not self.snapshots or self.snapshots[-1].spec_hash != spec_hash:
            self.snapshots.append(snapshot)
            self._save_history()
            return snapshot
        
        return self.snapshots[-1]
    
    def detect_drift(self, current_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect drift between current spec and last snapshot.
        
        Args:
            current_spec: Current OpenAPI specification
            
        Returns:
            Drift analysis report
        """
        if not self.snapshots:
            return {
                'has_drift': False,
                'message': 'No previous snapshots to compare against'
            }
        
        last_snapshot = self.snapshots[-1]
        current_snapshot = self.capture_snapshot(current_spec)
        
        if last_snapshot.spec_hash == current_snapshot.spec_hash:
            return {
                'has_drift': False,
                'message': 'No changes detected since last snapshot'
            }
        
        # Analyze differences
        drift_analysis = {
            'has_drift': True,
            'previous_version': last_snapshot.spec_version,
            'current_version': current_snapshot.spec_version,
            'previous_timestamp': last_snapshot.timestamp,
            'current_timestamp': current_snapshot.timestamp,
            'changes': self._analyze_changes(last_snapshot.spec_data, current_spec)
        }
        
        return drift_analysis
    
    def _analyze_changes(self, old_spec: Dict[str, Any], 
                        new_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze specific changes between two specifications.
        
        Args:
            old_spec: Previous specification
            new_spec: Current specification
            
        Returns:
            Detailed change analysis
        """
        changes = {
            'added_endpoints': [],
            'removed_endpoints': [],
            'modified_endpoints': [],
            'breaking_changes': []
        }
        
        old_paths = old_spec.get('paths', {})
        new_paths = new_spec.get('paths', {})
        
        # Find added endpoints
        for path in new_paths:
            if path not in old_paths:
                for method in new_paths[path]:
                    changes['added_endpoints'].append(f"{method.upper()} {path}")
        
        # Find removed endpoints
        for path in old_paths:
            if path not in new_paths:
                for method in old_paths[path]:
                    changes['removed_endpoints'].append(f"{method.upper()} {path}")
                    changes['breaking_changes'].append({
                        'type': 'endpoint_removed',
                        'endpoint': f"{method.upper()} {path}",
                        'severity': 'critical'
                    })
        
        # Find modified endpoints
        for path in old_paths:
            if path in new_paths:
                old_methods = set(old_paths[path].keys())
                new_methods = set(new_paths[path].keys())
                
                # Check for removed methods
                removed_methods = old_methods - new_methods
                for method in removed_methods:
                    changes['breaking_changes'].append({
                        'type': 'method_removed',
                        'endpoint': f"{method.upper()} {path}",
                        'severity': 'critical'
                    })
                
                # Check for modified methods
                common_methods = old_methods & new_methods
                for method in common_methods:
                    if old_paths[path][method] != new_paths[path][method]:
                        changes['modified_endpoints'].append(f"{method.upper()} {path}")
                        
                        # Check for breaking changes in parameters or responses
                        breaking = self._check_breaking_changes(
                            path, method,
                            old_paths[path][method],
                            new_paths[path][method]
                        )
                        if breaking:
                            changes['breaking_changes'].extend(breaking)
        
        return changes
    
    def _check_breaking_changes(self, path: str, method: str,
                                old_spec: Dict[str, Any],
                                new_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for breaking changes in endpoint specification"""
        breaking = []
        
        # Check for removed required parameters
        old_params = {p['name']: p for p in old_spec.get('parameters', [])}
        new_params = {p['name']: p for p in new_spec.get('parameters', [])}
        
        for param_name, param_spec in old_params.items():
            if param_spec.get('required', False):
                if param_name not in new_params:
                    breaking.append({
                        'type': 'required_parameter_removed',
                        'endpoint': f"{method.upper()} {path}",
                        'parameter': param_name,
                        'severity': 'critical'
                    })
        
        # Check for changed response schemas
        old_responses = old_spec.get('responses', {})
        new_responses = new_spec.get('responses', {})
        
        for status_code in old_responses:
            if status_code in new_responses:
                old_schema = self._extract_schema(old_responses[status_code])
                new_schema = self._extract_schema(new_responses[status_code])
                
                if old_schema != new_schema:
                    breaking.append({
                        'type': 'response_schema_changed',
                        'endpoint': f"{method.upper()} {path}",
                        'status_code': status_code,
                        'severity': 'warning'
                    })
        
        return breaking
    
    def _extract_schema(self, response_spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract schema from response specification"""
        content = response_spec.get('content', {})
        json_content = content.get('application/json', {})
        return json_content.get('schema')
    
    def generate_changelog(self, from_version: Optional[str] = None,
                          to_version: Optional[str] = None) -> str:
        """
        Generate a changelog between two specification versions.
        
        Args:
            from_version: Starting version (defaults to first snapshot)
            to_version: Ending version (defaults to latest snapshot)
            
        Returns:
            Markdown-formatted changelog
        """
        if len(self.snapshots) < 2:
            return "Not enough snapshots to generate changelog"
        
        # Find snapshots by version
        from_snapshot = self.snapshots[0] if not from_version else \
            next((s for s in self.snapshots if s.spec_version == from_version), None)
        
        to_snapshot = self.snapshots[-1] if not to_version else \
            next((s for s in self.snapshots if s.spec_version == to_version), None)
        
        if not from_snapshot or not to_snapshot:
            return "Could not find specified versions"
        
        changes = self._analyze_changes(from_snapshot.spec_data, to_snapshot.spec_data)
        
        # Generate markdown changelog
        changelog = f"""# API Changelog

**From:** Version {from_snapshot.spec_version} ({from_snapshot.timestamp})  
**To:** Version {to_snapshot.spec_version} ({to_snapshot.timestamp})

---

## Summary

- Added Endpoints: {len(changes['added_endpoints'])}
- Removed Endpoints: {len(changes['removed_endpoints'])}
- Modified Endpoints: {len(changes['modified_endpoints'])}
- Breaking Changes: {len(changes['breaking_changes'])}

"""
        
        if changes['breaking_changes']:
            changelog += "\n## Breaking Changes\n\n"
            for bc in changes['breaking_changes']:
                changelog += f"- **[{bc['severity'].upper()}]** {bc['type']}: {bc['endpoint']}\n"
        
        if changes['added_endpoints']:
            changelog += "\n## Added Endpoints\n\n"
            for endpoint in changes['added_endpoints']:
                changelog += f"- {endpoint}\n"
        
        if changes['removed_endpoints']:
            changelog += "\n## Removed Endpoints\n\n"
            for endpoint in changes['removed_endpoints']:
                changelog += f"- {endpoint}\n"
        
        if changes['modified_endpoints']:
            changelog += "\n## Modified Endpoints\n\n"
            for endpoint in changes['modified_endpoints']:
                changelog += f"- {endpoint}\n"
        
        return changelog
    
    def get_drift_summary(self) -> Dict[str, Any]:
        """Get summary of drift history"""
        if not self.snapshots:
            return {'total_snapshots': 0, 'message': 'No snapshots captured'}
        
        return {
            'total_snapshots': len(self.snapshots),
            'first_snapshot': self.snapshots[0].timestamp,
            'latest_snapshot': self.snapshots[-1].timestamp,
            'current_version': self.snapshots[-1].spec_version,
            'total_endpoints': self.snapshots[-1].endpoints_count
        }
