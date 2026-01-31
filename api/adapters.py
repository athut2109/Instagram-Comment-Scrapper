"""api/adapters.py
Thin adapter layer to reuse existing scraper/detector modules without copying code.
"""
from typing import List, Dict

# Lazy imports to avoid heavy deps at module import time

def scrape_post(post_url: str, max_scrolls: int = 50, scroll_delay: int = 1500) -> List[Dict]:
    try:
        from scraper import scrape_comments
    except Exception as e:
        raise RuntimeError(f"Scraper import failed: {e}")

    comments = scrape_comments(post_url, max_scrolls=max_scrolls, scroll_delay=scroll_delay)
    # Ensure returned items have keys: 'text', 'username', 'link'
    normalized = []
    for c in comments:
        normalized.append({
            "text": c.get("text", ""),
            "username": c.get("username", ""),
            "link": c.get("link", "")
        })
    return normalized


def detect_comments(comments: List[Dict], mode: str = "ml", threshold: float = 0.7) -> Dict:
    """Detect abusive comments.
    Returns a dict with keys: "mode", "timestamp", "abusive_comments" (list)
    """
    from detector import is_abusive, find_abusive_words
    results = {"mode": mode, "timestamp": None, "abusive_comments": []}

    texts = [c.get('text', '') for c in comments]

    if mode == 'keyword':
        for c in comments:
            if is_abusive(c.get('text', '')):
                results['abusive_comments'].append({
                    'original': c.get('text', ''),
                    'username': c.get('username', ''),
                    'link': c.get('link', ''),
                    'matched_words': find_abusive_words(c.get('text', ''))
                })
        return results

    # Try ML-based detection (if available)
    try:
        import ml_detector
        # analyze_batch returns list of dicts with keys including 'original', 'max_score', 'max_category', 'is_abusive'
        all_results = ml_detector.analyze_batch(texts, show_progress=False)
        abusive = ml_detector.get_abusive_comments(all_results, threshold=threshold)
        # attach metadata
        for r in abusive:
            text = r['original']
            meta = next((c for c in comments if c.get('text','') == text), {})
            r['username'] = meta.get('username', '')
            r['link'] = meta.get('link', '')
        results['abusive_comments'] = abusive
        return results
    except Exception:
        # Fallback to keyword on error
        for c in comments:
            if is_abusive(c.get('text', '')):
                results['abusive_comments'].append({
                    'original': c.get('text', ''),
                    'username': c.get('username', ''),
                    'link': c.get('link', ''),
                    'matched_words': find_abusive_words(c.get('text', ''))
                })
        return results
