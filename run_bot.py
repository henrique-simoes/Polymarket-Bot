"""
Main entry point for the Polymarket Trading Bot
Run this file to start the bot
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now we can import the bot
from src.bot import AdvancedPolymarketBot

if __name__ == "__main__":
    # Create and run the bot
    print("\n" + "="*80)
    print("STARTING POLYMARKET BOT WITH META-LEARNING")
    print("="*80 + "\n")

    bot = AdvancedPolymarketBot()

    # Run continuously (press Ctrl+C to stop)
    # Or specify num_rounds=4 to run for limited rounds
    bot.run(num_rounds=None)  # None = continuous mode
