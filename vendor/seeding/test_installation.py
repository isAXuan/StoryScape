"""
Test Installation

Verify that seed-agent is properly installed and can be imported from any location.
"""

from seed_agent.skill.skill_loader import SkillLoader, Skill
from seed_agent import Agent
from seed_agent.types import AgentMessage, AgentContext, AgentState, AgentTool
from seed_ai import complete, stream
from seed_ai.types import Message, AssistantMessage, Tool


def test_imports():
    print("=" * 60)
    print("Installation Test")
    print("=" * 60)

    print("\n✅ Step 1: Import seed_agent.skill")
    loader = SkillLoader(skills_dir="./skills")
    print(f"   SkillLoader initialized: {loader.skills_dir}")

    print("\n✅ Step 2: Import seed_agent.Agent")
    print(f"   Agent class available: {Agent is not None}")

    print("\n✅ Step 3: Import seed_agent.types")
    print(f"   AgentMessage: {AgentMessage}")
    print(f"   AgentContext: {AgentContext}")
    print(f"   AgentState: {AgentState}")
    print(f"   AgentTool: {AgentTool}")

    print("\n✅ Step 4: Import seed_ai functions")
    print(f"   complete function: {complete}")
    print(f"   stream function: {stream}")
    print(f"   Message type: {Message}")
    print(f"   AssistantMessage: {AssistantMessage}")
    print(f"   Tool: {Tool}")

    print("\n✅ Step 5: Discover skills")
    skills = loader.discover_skills()
    print(f"   Found {len(skills)} skill(s)")

    return True


if __name__ == "__main__":
    try:
        success = test_imports()
        print("\n" + "=" * 60)
        if success:
            print("✅ All imports successful - installation is working!")
        else:
            print("❌ Some imports failed")
        print("=" * 60)
    except ImportError as e:
        print("\n" + "=" * 60)
        print(f"❌ Import failed: {e}")
        print("\nTry running:")
        print("  pip install -e .")
        print("=" * 60)
        raise
