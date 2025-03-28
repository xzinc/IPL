#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IPL Telegram Bot - Main Entry Point
-----------------------------------
This script initializes and runs the IPL Telegram Bot with AI capabilities.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
from bot import register_handlers
from user_manager import UserManager
from admin_manager import AdminManager
from ai_engine import AIEngine
from ipl_data import IPLData

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get API credentials from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Database configuration
DB_TYPE = os.getenv('DB_TYPE', 'redis').lower()  # 'redis', 'mongodb', or 'none'
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')

# Validate required environment variables
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Missing required environment variables. Please check your .env file.")
    exit(1)

async def main():
    """Main function to run the bot"""
    logger.info("Starting IPL Telegram Bot...")
    
    # Initialize components
    logger.info("Initializing bot components...")
    
    # Initialize data directory
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Initialize IPL data with database support
    if DB_TYPE == 'none':
        logger.info("Initializing IPL data without database support")
        ipl_data = IPLData(data_dir=data_dir, use_cache=True, db_type=None)
    else:
        logger.info(f"Initializing IPL data with {DB_TYPE} database support")
        # Set environment variables for database connections
        if DB_TYPE == 'redis':
            os.environ['REDIS_URL'] = REDIS_URL
        elif DB_TYPE == 'mongodb':
            os.environ['MONGODB_URI'] = MONGODB_URI
        
        ipl_data = IPLData(data_dir=data_dir, use_cache=True, db_type=DB_TYPE)
    
    # Initialize managers and engines
    user_manager = UserManager(data_dir)
    admin_manager = AdminManager(ADMIN_IDS, data_dir)
    ai_engine = AIEngine()
    
    # Initialize Telegram client
    client = TelegramClient('ipl_bot_session', API_ID, API_HASH)
    
    # Register event handlers
    register_handlers(client, user_manager, admin_manager, ipl_data, ai_engine)
    
    # Start the client
    await client.start(bot_token=BOT_TOKEN)
    logger.info("Bot started successfully!")
    
    # Run the client until disconnected
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
