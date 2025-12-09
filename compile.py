#!/usr/bin/env python3
"""
Merge all markdown files in /book directory into a single compiled.md file.
"""

from pathlib import Path


def merge_markdown_files(book_dir='book', output_file='compiled.md'):
    """
    Merge all .md files from book_dir into a single output_file.

    Args:
        book_dir: Directory containing markdown files (default: 'book')
        output_file: Output filename (default: 'compiled.md')
    """
    # Get the book directory path
    book_path = Path(book_dir)

    if not book_path.exists():
        print(f"Error: Directory '{book_dir}' does not exist")
        return False

    if not book_path.is_dir():
        print(f"Error: '{book_dir}' is not a directory")
        return False

    # Find all markdown files and sort alphabetically
    md_files = sorted(book_path.glob('*.md'))

    if not md_files:
        print(f"Error: No markdown files found in '{book_dir}'")
        return False

    print(f"Found {len(md_files)} markdown file(s):")
    for f in md_files:
        print(f"  - {f.name}")

    # Merge files
    output_path = Path(output_file)

    try:
        with output_path.open('w', encoding='utf-8') as outfile:
            for i, md_file in enumerate(md_files):
                print(f"\nProcessing: {md_file.name}")

                # Read the content
                content = md_file.read_text(encoding='utf-8')

                # Write to output
                outfile.write(content)

                # Add separation between files (except after the last one)
                if i < len(md_files) - 1:
                    outfile.write('\n\n---\n\n')

        print(f"\n✓ Successfully merged {len(md_files)} files into '{output_file}'")
        print(f"✓ Output size: {output_path.stat().st_size:,} bytes")
        return True

    except Exception as e:
        print(f"\n✗ Error writing to '{output_file}': {e}")
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Merge markdown files from /book directory into a single file'
    )
    parser.add_argument(
        '--book-dir',
        default='book',
        help='Directory containing markdown files (default: book)'
    )
    parser.add_argument(
        '--output',
        default='compiled.md',
        help='Output filename (default: compiled.md)'
    )

    args = parser.parse_args()

    success = merge_markdown_files(args.book_dir, args.output)

    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
