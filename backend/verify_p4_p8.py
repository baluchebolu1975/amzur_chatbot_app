#!/usr/bin/env python3
"""Comprehensive P4-P8 Project Readiness Verification."""

import sys
from pathlib import Path

# P4-P8 critical packages
packages = {
    # P5: Attachments
    "python_multipart": "File upload handling",
    "aiofiles": "Async file I/O",
    "PIL": "Image processing",
    "pypdf": "PDF parsing",
    "pdfplumber": "PDF extraction",
    "unstructured": "Document parsing",
    
    # P7: RAG
    "chromadb": "Vector store",
    "langchain_community": "LangChain community",
    "sentence_transformers": "Embeddings",
    "rank_bm25": "BM25 retrieval",
    "tiktoken": "Token counting",
    
    # P8: NL-to-SQL & Vision
    "sqlparse": "SQL parsing",
    "duckdb": "DuckDB",
    "pandas": "Data frames",
    "openpyxl": "Excel handling",
    "cv2": "Computer vision",
    "pytesseract": "OCR",
    "rapidfuzz": "Fuzzy matching",
    "jsonschema": "JSON schema",
    
    # Agents
    "langchain_experimental": "LangChain experimental",
    "mcp": "MCP SDK",
    
    # Support
    "tenacity": "Retry logic",
    "structlog": "Structured logging",
    "prometheus_client": "Metrics",
    "langdetect": "Language detection",
}

print("\n" + "="*60)
print("PROJECTS 4-8 READINESS VERIFICATION")
print("="*60 + "\n")

failed = []
success_count = 0

for pkg_name, description in sorted(packages.items()):
    try:
        __import__(pkg_name)
        print(f"  ✓ {pkg_name:25} → {description}")
        success_count += 1
    except ImportError as e:
        failed_msg = str(e).split("named")[1].strip("'\"") if "named" in str(e) else str(e)[:40]
        print(f"  ✗ {pkg_name:25} → {description} [{failed_msg}]")
        failed.append((pkg_name, description))

print("\n" + "="*60)
print(f"RESULT: {success_count}/{len(packages)} packages ✓")
print("="*60 + "\n")

if failed:
    print("⚠️  FAILED PACKAGES:")
    for pkg_name, desc in failed:
        print(f"   - {pkg_name} ({desc})")
    sys.exit(1)
else:
    print("✅ ALL P4-P8 PACKAGES VERIFIED")
    print("\n🎯 Ready for Projects 4-8 implementation\n")
    sys.exit(0)
