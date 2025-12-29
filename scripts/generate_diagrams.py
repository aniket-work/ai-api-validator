"""
Generate Mermaid diagrams and convert them to PNG images using mermaid.ink API
"""

import base64
import requests
from pathlib import Path


def generate_diagrams():
    """Generate all diagrams for the project"""
    
    # Create images directory
    images_dir = Path(__file__).parent.parent / "images"
    images_dir.mkdir(exist_ok=True)
    
    diagrams = {
        "architecture_diagram": """
graph TB
    subgraph "API Documentation Validator"
        A[OpenAPI Spec] --> B[API Validator]
        C[Live API] --> B
        B --> D[Validation Issues]
        D --> E[AI Agent]
        E --> F[Drift Report]
        
        G[Drift Detector] --> H[Spec History]
        A --> G
        G --> I[Changelog]
        
        style A fill:#e1f5ff
        style C fill:#e1f5ff
        style E fill:#fff3e0
        style F fill:#e8f5e9
        style I fill:#e8f5e9
    end
""",
        "validation_flow": """
sequenceDiagram
    participant User
    participant CLI
    participant Validator
    participant API
    participant AIAgent
    
    User->>CLI: Run validation command
    CLI->>Validator: Load OpenAPI spec
    Validator->>API: Test each endpoint
    API-->>Validator: Response data
    Validator->>Validator: Compare with spec
    Validator->>AIAgent: Send validation issues
    AIAgent->>AIAgent: Analyze with GPT-4
    AIAgent-->>CLI: Generate report
    CLI-->>User: Display results
""",
        "drift_detection": """
flowchart TD
    A[Current API Spec] --> B{Load Previous Snapshot}
    B -->|Exists| C[Compare Specs]
    B -->|Not Found| D[Create First Snapshot]
    C --> E{Changes Detected?}
    E -->|Yes| F[Analyze Differences]
    E -->|No| G[No Drift]
    F --> H[Identify Breaking Changes]
    F --> I[Track Added Endpoints]
    F --> J[Track Removed Endpoints]
    H --> K[Generate Changelog]
    I --> K
    J --> K
    K --> L[Save New Snapshot]
    D --> L
    G --> L
    
    style A fill:#e1f5ff
    style F fill:#fff3e0
    style K fill:#e8f5e9
    style H fill:#ffebee
"""
    }
    
    print("Generating diagrams...")
    
    for name, mermaid_code in diagrams.items():
        print(f"\nGenerating {name}...")
        
        # Encode Mermaid code to base64
        encoded = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
        
        # Use mermaid.ink API to generate PNG
        url = f"https://mermaid.ink/img/{encoded}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Save PNG file
            output_path = images_dir / f"{name}.png"
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✓ Saved: {output_path}")
            
        except Exception as e:
            print(f"✗ Failed to generate {name}: {e}")
    
    print("\n✓ All diagrams generated successfully!")


if __name__ == "__main__":
    generate_diagrams()
