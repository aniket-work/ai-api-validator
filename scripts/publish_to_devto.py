"""
Publish article to Dev.to using API

This script reads the article markdown file and publishes it to Dev.to
using the Dev.to API with the API key from environment variables.
"""

import os
import sys
import re
import requests
from pathlib import Path
from dotenv import load_dotenv


def extract_title(content: str) -> str:
    """Extract title from markdown (first H1 heading)"""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if not match:
        raise ValueError("No title found in article (expected # heading)")
    return match.group(1).strip()


def extract_tags_from_content(content: str) -> list:
    """
    Extract tags from article content.
    For this article, we'll use predefined tags based on the content.
    """
    # Based on the article content about API validation and AI
    return ['api', 'openai', 'python', 'devops']


def prepare_article_body(content: str) -> str:
    """
    Prepare article body for Dev.to.
    Remove title (Dev.to adds it separately) but KEEP the subtitle.
    """
    # Remove first H1 heading (title)
    body = re.sub(r'^#\s+.+$', '', content, count=1, flags=re.MULTILINE)
    
    # Clean up extra newlines at the start
    body = body.lstrip('\n')
    
    return body


def publish_to_devto(article_path: str, api_key: str, published: bool = True) -> dict:
    """
    Publish article to Dev.to using their API.
    
    Args:
        article_path: Path to the markdown article file
        api_key: Dev.to API key
        published: Whether to publish immediately (True) or as draft (False)
        
    Returns:
        Response from Dev.to API
    """
    # Read article content
    with open(article_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract metadata
    title = extract_title(content)
    tags = extract_tags_from_content(content)
    body = prepare_article_body(content)
    
    # Prepare API request
    url = "https://dev.to/api/articles"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "article": {
            "title": title,
            "published": published,
            "body_markdown": body,
            "tags": tags,
            "series": None
        }
    }
    
    print(f"Publishing article to Dev.to...")
    print(f"Title: {title}")
    print(f"Tags: {', '.join(tags)}")
    print(f"Status: {'Published' if published else 'Draft'}")
    print()
    
    # Make API request
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 201:
        result = response.json()
        print(f"✓ Article published successfully!")
        print(f"URL: {result['url']}")
        print(f"ID: {result['id']}")
        return result
    else:
        print(f"✗ Failed to publish article")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        raise Exception(f"Failed to publish: {response.status_code} - {response.text}")


def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()
    
    # Get API key
    api_key = os.getenv('DEVTO_API_KEY')
    if not api_key:
        print("Error: DEVTO_API_KEY not found in environment variables")
        print("Please set DEVTO_API_KEY in your .env file")
        sys.exit(1)
    
    # Get article path
    article_path = Path(__file__).parent.parent / "article.md"
    
    if not article_path.exists():
        print(f"Error: Article not found at {article_path}")
        sys.exit(1)
    
    # Check for dry-run flag
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("DRY RUN MODE - Article will not be published")
        with open(article_path, 'r') as f:
            content = f.read()
        title = extract_title(content)
        tags = extract_tags_from_content(content)
        print(f"\nTitle: {title}")
        print(f"Tags: {', '.join(tags)}")
        print(f"Article length: {len(content)} characters")
        return
    
    # Publish article
    try:
        result = publish_to_devto(article_path, api_key, published=True)
        print("\n✓ Article published successfully to Dev.to!")
    except Exception as e:
        print(f"\n✗ Error publishing article: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
