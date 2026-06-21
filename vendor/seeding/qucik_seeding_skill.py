"""
Skill Loader Test

Tests the skill loading functionality from ./skills directory
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from seed_agent.skill.skill_loader import SkillLoader, Skill


def test_skill_loader():
    """Test skill loading from ./skills directory"""
    print("=" * 60)
    print("Skill Loader Test")
    print("=" * 60)

    # Initialize loader
    loader = SkillLoader(skills_dir="./skills")
    print(f"\n📁 Skills directory: {loader.skills_dir}")
    print(f"📁 Directory exists: {loader.skills_dir.exists()}")

    # Discover skills
    print("\n🔍 Discovering skills...")
    skills = loader.discover_skills()

    print(f"\n📊 Found {len(skills)} skill(s)")

    # List all skills
    print("\n📋 Loaded skills:")
    for name in loader.list_skills():
        skill = loader.get_skill(name)
        print(f"  - {skill.name}: {skill.description}")
        print(f"    License: {skill.license}")
        print(f"    Tools: {skill.allowed_tools}")
        print(f"    Path: {skill.skill_path}")

    # Test getting metadata prompt (Progressive Disclosure Level 1)
    print("\n📝 Skills Metadata Prompt (Level 1 - Progressive Disclosure):")
    print("-" * 60)
    metadata_prompt = loader.get_skills_metadata_prompt()
    print(metadata_prompt if metadata_prompt else "(No skills loaded)")

    # Test individual skill prompt generation
    print("\n📄 Individual Skill Prompts:")
    print("-" * 60)
    for skill in skills:
        prompt = skill.to_prompt()
        print(f"\n### {skill.name} ###")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)

    return len(skills) > 0


if __name__ == "__main__":
    success = test_skill_loader()
    print("\n" + "=" * 60)
    if success:
        print("✅ Skill loader test completed successfully")
    else:
        print("⚠️  No skills found. Create SKILL.md files in ./skills directory.")
    print("=" * 60)
