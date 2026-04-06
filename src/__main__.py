"""
Entry point for running the bot as a module.
Usage: python -m src
"""

from .bot import AdvancedPolymarketBot

def main():
    """Main entry point"""
    bot = AdvancedPolymarketBot()
    bot.run(num_rounds=1)  # Test with 1 round (~15 minutes)

if __name__ == "__main__":
    main()
