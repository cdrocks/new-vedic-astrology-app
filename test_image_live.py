"""
Live Test Script for Sacred Image Generator.

Usage:
    python test_image_live.py
"""

import sys
from image_service import generate_sacred_archetype, get_openai_api_key


def main():
    print("==================================================")
    print("🔮 SACRED NAKSHATRA IMAGE GENERATOR TEST")
    print("==================================================")

    # 1. Verify API Key
    key = get_openai_api_key()
    if not key:
        print("❌ Error: OPENAI_API_KEY was not found in .env or environment!")
        sys.exit(1)
    print("✅ OpenAI API Key loaded successfully from .env!")

    # 2. Pick a Nakshatra
    nakshatra = "Rohini"
    print(f"\n🎨 Requesting sacred archetype generation for: {nakshatra} Nakshatra...")
    print("   Calling OpenAI DALL-E 3 (this takes ~10-15 seconds)...")

    result = generate_sacred_archetype(nakshatra)

    if result.get("status") == "success" and result.get("image_url"):
        img_data = result.get("image_url")
        print("\n✨ GENERATION SUCCESSFUL! ✨")
        print(f"• Nakshatra:       {result.get('nakshatra')}")
        print(f"• Archetype Title: {result.get('archetype_title')}")
        print(f"• Life Focus:      {result.get('life_focus')}")

        if img_data.startswith("data:image"):
            import base64
            b64_content = img_data.split(",", 1)[1]
            output_file = "sacred_portrait_test.png"
            with open(output_file, "wb") as f:
                f.write(base64.b64decode(b64_content))
            print(f"\n🖼️  Saved full-resolution portrait locally to: {output_file}")
            print(f"👉 You can view it by running: open {output_file}\n")
        else:
            print(f"\n🖼️  Image URL (Click or copy to browser):")
            print(f"👉 {img_data}\n")
        print("==================================================")
    else:
        print(f"\n❌ Generation failed with status: {result.get('status')}")
        print(result)


if __name__ == "__main__":
    main()
