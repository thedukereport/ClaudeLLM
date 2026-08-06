#!/usr/bin/env python3
"""
Multi-query search for Alexandria RAG
Searches with different phrasings to find more relevant results.
"""

import sys
from pathlib import Path

# Add RAG system to path
RAG_SYSTEM_PATH = Path(__file__).parent
sys.path.insert(0, str(RAG_SYSTEM_PATH))

from query_rag import RAGQuerier

def multi_search(base_query, index_dir="..", k=20):
    """Search with multiple phrasings of the same query."""

    # Different ways to phrase the search
    queries = [
        base_query,
        f"What do my books say about {base_query}?",
        f"{base_query} mentioned",
        f"Who was {base_query}?",
        f"{base_query} biography",
        f"{base_query} discussed",
        f"{base_query} role",
    ]

    try:
        querier = RAGQuerier(index_dir=index_dir)
    except Exception as e:
        print(f"Error loading index: {e}")
        return

    all_results = {}

    for query in queries:
        print(f"\n{'='*70}")
        print(f"Searching for: {query}")
        print(f"{'='*70}")

        try:
            results = querier.search(query, k=k)

            if not results:
                print("  No results found")
                continue

            print(f"\n  Found {len(results)} results:\n")

            for result in results:
                book_key = result['title']
                if book_key not in all_results:
                    all_results[book_key] = {
                        'file': result['file'],
                        'matches': 0,
                        'best_similarity': result['similarity'],
                        'preview': result['preview']
                    }
                all_results[book_key]['matches'] += 1
                if result['similarity'] > all_results[book_key]['best_similarity']:
                    all_results[book_key]['best_similarity'] = result['similarity']

                print(f"  [{result['rank']}] {result['title']}")
                print(f"      Match: {result['similarity']:.1%}")
                print(f"      Preview: {result['preview'][:100]}...")
                print()

        except Exception as e:
            print(f"  Error: {e}")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY - All Unique Books Found")
    print(f"{'='*70}\n")

    sorted_books = sorted(
        all_results.items(),
        key=lambda x: (-x[1]['matches'], -x[1]['best_similarity'])
    )

    print(f"Total unique books found: {len(sorted_books)}\n")

    for book, data in sorted_books:
        print(f"✓ {book}")
        print(f"  Matched in {data['matches']} search(es)")
        print(f"  Best match strength: {data['best_similarity']:.1%}")
        print(f"  Preview: {data['preview'][:80]}...")
        print()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python multi_search.py '<query>' [k] [index_dir]")
        print("Example: python multi_search.py 'Hanfstaengl' 20 '..'")
        sys.exit(1)

    query = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    index_dir = sys.argv[3] if len(sys.argv) > 3 else ".."

    multi_search(query, index_dir, k)
