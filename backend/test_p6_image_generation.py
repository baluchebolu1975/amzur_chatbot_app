#!/usr/bin/env python3
"""Test script for P6 image generation functionality"""
import asyncio
import sys
import json
from app.ai.image_generation import ImageGeneratorService
from app.core.config import get_settings

async def test_image_generation():
    """Test the image generation service"""
    settings = get_settings()
    print(f"Testing image generation with model: {settings.IMAGE_GEN_MODEL}")
    print(f"LiteLLM Proxy URL: {settings.LITELLM_PROXY_URL}")
    
    service = ImageGeneratorService()
    
    # Test prompts
    test_prompts = [
        "A serene mountain landscape with snow-capped peaks and a clear blue sky",
        "A futuristic city with neon lights and flying cars",
        "A beautiful sunset over the ocean",
    ]
    
    for i, prompt in enumerate(test_prompts, 1):
        try:
            print(f"\n[Test {i}/{len(test_prompts)}] Generating image for: {prompt[:50]}...")
            result = await service.generate_image(prompt)
            
            if not result.url:
                print(f"✗ FAILED: No image URL returned")
                return False
            
                if not (result.url.startswith("http") or result.url.startswith("data:")):
                    print(f"✗ FAILED: Invalid URL format: {result.url[:50]}")
                return False
            
            print(f"✓ SUCCESS: Generated image URL")
            print(f"  URL: {result.url[:80]}...")
            print(f"  Model: {result.model}")
            
        except Exception as exc:
            print(f"✗ FAILED: {str(exc)}")
            return False
    
    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60)
    return True

if __name__ == "__main__":
    success = asyncio.run(test_image_generation())
    sys.exit(0 if success else 1)
