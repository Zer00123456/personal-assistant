"""Configuration loader - reads from .env file"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Discord Bot
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    
    # Channel IDs for INPUT (bot reads from these)
    TRENDS_INPUT_CHANNEL_ID = int(os.getenv("TRENDS_INPUT_CHANNEL_ID", "1461355576431739125"))
    CREATIVE_INPUT_CHANNEL_ID = int(os.getenv("CREATIVE_INPUT_CHANNEL_ID", "1461355492369498204"))
    COIN_DATA_CHANNEL_ID = int(os.getenv("COIN_DATA_CHANNEL_ID", "0"))  # Set this in .env
    
    # Webhooks for OUTPUT (bot sends to these)
    COIN_ALERTS_WEBHOOK = os.getenv(
        "COIN_ALERTS_WEBHOOK",
        "https://discord.com/api/webhooks/1458182965640171521/PPerO6_ga3AIanklUfFkWttae7SEZKZmQOYX8tFlcEkvMfutVl_S_Y_qs7PwXqT07yrB"
    )
    
    # Optional OpenAI for categorization
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Twitter API for scraping tweets
    TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
    
    # Database paths
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    
    @classmethod
    def validate(cls):
        """Check that required config is present"""
        if not cls.DISCORD_BOT_TOKEN:
            raise ValueError("DISCORD_BOT_TOKEN is required in .env file")
        return True


config = Config()


