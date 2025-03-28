import os
import logging
import asyncio
import json
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
from telethon.tl.custom import Button
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import PeerUser, PeerChat, PeerChannel

# Import AI components
from ai_engine import AIEngine
from ipl_data import IPLData
from user_manager import UserManager
from admin_manager import AdminManager

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
ADMIN_IDS = json.loads(os.getenv('ADMIN_IDS', '[]'))  # List of admin user IDs

# Initialize the client
bot = TelegramClient('ipl_bot', API_ID, API_HASH)
bot.start(bot_token=BOT_TOKEN)

# Initialize components
ai_engine = AIEngine()
ipl_data = IPLData()
user_manager = UserManager()
admin_manager = AdminManager(ADMIN_IDS)

# Main function to register all handlers
def register_handlers(client, user_manager, admin_manager, ipl_data, ai_engine):
    """Register all event handlers with the client"""
    # Store references to managers and engines
    globals()['client'] = client
    globals()['user_manager'] = user_manager
    globals()['admin_manager'] = admin_manager
    globals()['ipl_data'] = ipl_data
    globals()['ai_engine'] = ai_engine
    
    # Register all event handlers
    client.add_event_handler(start_command)
    client.add_event_handler(help_handler)
    client.add_event_handler(stats_handler)
    client.add_event_handler(team_handler)
    client.add_event_handler(player_handler)
    client.add_event_handler(schedule_handler)
    client.add_event_handler(predict_command)
    client.add_event_handler(subscribe_handler)
    client.add_event_handler(unsubscribe_handler)
    client.add_event_handler(config_command)
    client.add_event_handler(admin_handler)
    client.add_event_handler(broadcast_handler)
    client.add_event_handler(callback_handler)
    client.add_event_handler(db_compare_handler)
    client.add_event_handler(db_explain_handler)
    client.add_event_handler(update_data_handler)
    client.add_event_handler(telugu_command_handler)
    
    # Register message handler (should be last to avoid conflicts)
    client.add_event_handler(handle_message)
    
    return client

# Command handlers
@events.register(events.NewMessage(pattern='/start'))
async def start_command(event):
    """Handle the /start command"""
    sender = await event.get_sender()
    user_id = sender.id
    
    # Check if user is blocked
    if user_manager.is_blocked(user_id):
        return
    
    # Register user if new
    if not user_manager.is_registered(user_id):
        user_manager.register_user(user_id, sender.username, sender.first_name)
        
    welcome_message = (
        f"👋 Hello, {sender.first_name}! Welcome to the IPL Bot!\n\n"
        f"I'm your AI-powered assistant for all things IPL. Here's what I can do:\n\n"
        f"🏏 Get the latest IPL news and updates\n"
        f"📊 View team and player statistics\n"
        f"🔮 Predict match outcomes\n"
        f"💬 Chat about anything IPL-related\n\n"
        f"Try these commands:\n"
        f"/stats - View team statistics\n"
        f"/predict - Predict match outcomes\n"
        f"/schedule - View upcoming matches\n"
        f"/subscribe - Get match notifications\n"
        f"/help - See all available commands\n\n"
        f"Let's talk cricket! 🏆"
    )
    
    await event.respond(welcome_message)
    
    # Log the interaction
    ai_engine.learn_from_interaction(user_id, "/start", welcome_message)

@events.register(events.NewMessage(pattern='/help'))
async def help_handler(event):
    """Handle the /help command"""
    help_text = (
        "🤖 **IPL AI Bot Commands**\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/stats - Get IPL statistics\n"
        "/team [name] - Get info about a team\n"
        "/player [name] - Get info about a player\n"
        "/schedule - View upcoming matches\n"
        "/predict [team1] vs [team2] - Predict match outcome\n"
        "/subscribe - Subscribe to match updates\n\n"
        "You can also just chat with me naturally about IPL!"
    )
    await event.respond(help_text)

@events.register(events.NewMessage(pattern='/stats'))
async def stats_handler(event):
    """Handle the /stats command"""
    stats = ipl_data.get_general_stats()
    await event.respond(stats)

@events.register(events.NewMessage(pattern='/team (.+)'))
async def team_handler(event):
    """Handle the /team command"""
    team_name = event.pattern_match.group(1).strip()
    team_info = ipl_data.get_team_info(team_name)
    await event.respond(team_info)

@events.register(events.NewMessage(pattern='/player (.+)'))
async def player_handler(event):
    """Handle the /player command"""
    player_name = event.pattern_match.group(1).strip()
    player_info = ipl_data.get_player_info(player_name)
    await event.respond(player_info)

@events.register(events.NewMessage(pattern='/schedule'))
async def schedule_handler(event):
    """Handle the /schedule command"""
    schedule = ipl_data.get_schedule()
    await event.respond(schedule)

@events.register(events.NewMessage(pattern='/predict'))
async def predict_command(event):
    """Handle the /predict command"""
    sender = await event.get_sender()
    user_id = sender.id
    
    # Check if user is blocked
    if user_manager.is_blocked(user_id):
        return
    
    # Get message text
    message_text = event.message.text.strip()
    
    # Check if the command includes match information
    parts = message_text.split(' ', 1)
    
    if len(parts) == 1:
        # No match provided, ask for it
        response = (
            "To predict a match outcome, please use the format:\n"
            "/predict Team1 vs Team2\n\n"
            "For example: /predict Mumbai Indians vs Chennai Super Kings\n\n"
            "You can also specify a venue:\n"
            "/predict Mumbai Indians vs Chennai Super Kings at Wankhede Stadium"
        )
        await event.respond(response)
    else:
        # Match information provided
        match_query = parts[1].strip()
        
        # Get bot configuration for prediction
        bot_config = admin_manager.get_bot_config()
        
        # Generate prediction with team support and confidence settings
        prediction = ai_engine.predict_match(match_query, bot_config)
        await event.respond(prediction)
        
        # Log the interaction
        ai_engine.learn_from_interaction(user_id, message_text, prediction)

@events.register(events.NewMessage(pattern='/subscribe'))
async def subscribe_handler(event):
    """Handle the /subscribe command"""
    user_id = event.sender_id
    result = user_manager.subscribe_user(user_id)
    await event.respond(result)

@events.register(events.NewMessage(pattern='/unsubscribe'))
async def unsubscribe_handler(event):
    """Handle the /unsubscribe command"""
    user_id = event.sender_id
    result = user_manager.unsubscribe_user(user_id)
    await event.respond(result)

@events.register(events.NewMessage(pattern='/config'))
async def config_command(event):
    """Handle the /config command for admins to configure bot settings"""
    sender = await event.get_sender()
    user_id = sender.id
    
    # Check if user is an admin
    if not admin_manager.is_admin(user_id):
        await event.respond("⚠️ This command is only available to administrators.")
        return
    
    # Get message text
    message_text = event.message.text.strip()
    parts = message_text.split(' ', 2)
    
    # Just /config - show current configuration
    if len(parts) == 1:
        config_info = admin_manager.format_bot_config()
        await event.respond(config_info)
        return
    
    # /config key value - update configuration
    if len(parts) >= 3:
        config_key = parts[1].lower()
        config_value = parts[2]
        
        try:
            admin_manager.update_bot_config(config_key, config_value, user_id)
            
            # Get updated configuration
            config_info = admin_manager.format_bot_config()
            await event.respond(f"✅ Configuration updated successfully!\n\n{config_info}")
        except ValueError as e:
            await event.respond(f"⚠️ {str(e)}")
    else:
        # Show help for config command
        help_text = (
            "📝 **Bot Configuration Help**\n\n"
            "Usage:\n"
            "/config - Show current configuration\n"
            "/config [key] [value] - Update configuration\n\n"
            "Available configuration keys:\n"
            "• supported_team - Set the team the bot supports (team name or 'neutral')\n"
            "• response_style - Set response style (balanced, enthusiastic, professional)\n"
            "• prediction_confidence - Set prediction confidence (low, medium, high)\n"
            "• learning_rate - Set learning rate (slow, normal, fast)\n\n"
            "Examples:\n"
            "/config supported_team Mumbai Indians\n"
            "/config response_style enthusiastic\n"
            "/config prediction_confidence high"
        )
        await event.respond(help_text)

# Admin commands
@events.register(events.NewMessage(pattern='/admin'))
async def admin_handler(event):
    """Handle the /admin command"""
    user_id = event.sender_id
    if admin_manager.is_admin(user_id):
        admin_panel = (
            "🔐 **Admin Panel**\n\n"
            "/broadcast [message] - Send message to all users\n"
            "/stats_users - View user statistics\n"
            "/block [user_id] - Block a user\n"
            "/unblock [user_id] - Unblock a user\n"
            "/update_data - Update IPL database\n"
            "/retrain - Retrain AI model\n"
            "/db_compare - Compare Redis and MongoDB performance\n"
            "/db_explain - Get explanation of database choice\n"
            "/telugu - Toggle Telugu language support for a user\n"
        )
        await event.respond(admin_panel)
    else:
        await event.respond("⛔ You don't have admin privileges.")

@events.register(events.NewMessage(pattern='/broadcast (.+)'))
async def broadcast_handler(event):
    """Handle the /broadcast command"""
    user_id = event.sender_id
    if admin_manager.is_admin(user_id):
        message = event.pattern_match.group(1).strip()
        users = user_manager.get_all_users()
        sent_count = 0
        
        await event.respond(f"Broadcasting message to {len(users)} users...")
        
        for user_id in users:
            try:
                await bot.send_message(user_id, f"📢 **Broadcast Message**\n\n{message}")
                sent_count += 1
                await asyncio.sleep(0.1)  # Avoid flooding
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
        
        await event.respond(f"✅ Broadcast complete. Message sent to {sent_count}/{len(users)} users.")
    else:
        await event.respond("⛔ You don't have admin privileges.")

@events.register(events.NewMessage(pattern='/db_compare'))
async def db_compare_handler(event):
    """Handle the /db_compare command to benchmark database performance"""
    user_id = event.sender_id
    if admin_manager.is_admin(user_id):
        await event.respond("🔄 Comparing database performance between Redis and MongoDB...\nThis may take a moment.")
        
        try:
            # Run the comparison
            result = ipl_data.compare_database_performance()
            
            # Send the result
            await event.respond(f"📊 **Database Performance Comparison**\n\n{result}")
        except Exception as e:
            logger.error(f"Error comparing databases: {e}")
            await event.respond(f"❌ Error comparing databases: {str(e)}")
    else:
        await event.respond("⛔ You don't have admin privileges.")

@events.register(events.NewMessage(pattern='/db_explain'))
async def db_explain_handler(event):
    """Handle the /db_explain command to explain database choice"""
    user_id = event.sender_id
    if admin_manager.is_admin(user_id):
        try:
            # Get the explanation
            explanation = ipl_data.explain_database_choice()
            
            # Send the explanation
            await event.respond(explanation)
        except Exception as e:
            logger.error(f"Error generating database explanation: {e}")
            await event.respond(f"❌ Error generating database explanation: {str(e)}")
    else:
        await event.respond("⛔ You don't have admin privileges.")

@events.register(events.NewMessage(pattern='/update_data'))
async def update_data_handler(event):
    """Handle the /update_data command to refresh IPL data"""
    user_id = event.sender_id
    if admin_manager.is_admin(user_id):
        await event.respond("🔄 Updating IPL data from sources...\nThis may take a moment.")
        
        try:
            # Force refresh the data
            await event.respond("⏳ Fetching latest data from GitHub and Kaggle...")
            ipl_data.load_data(force_refresh=True)
            
            # Save to database if configured
            if ipl_data.db_type:
                await event.respond(f"💾 Saving updated data to {ipl_data.db_type} database...")
                if ipl_data.db_type == 'redis':
                    ipl_data.save_to_redis()
                elif ipl_data.db_type == 'mongodb':
                    ipl_data.save_to_mongodb()
            
            await event.respond("✅ IPL data updated successfully!")
        except Exception as e:
            logger.error(f"Error updating IPL data: {e}")
            await event.respond(f"❌ Error updating IPL data: {str(e)}")
    else:
        await event.respond("⛔ You don't have admin privileges.")

@events.register(events.NewMessage(pattern='/telugu'))
async def telugu_command_handler(event):
    """Handle the /telugu command to toggle Telugu language support"""
    user_id = event.sender_id
    
    # Check if there are arguments
    message_text = event.message.text.strip()
    parts = message_text.split(' ', 1)
    
    if len(parts) > 1 and parts[1].strip().lower() in ['on', 'off']:
        # Enable/disable Telugu for a specific user (admin only)
        enable = parts[1].strip().lower() == 'on'
        
        if admin_manager.is_admin(user_id):
            # Update user preference
            if enable:
                user_manager.set_user_preference(user_id, 'language', 'telugu')
                await event.respond("తెలుగు భాష మద్దతు ఇప్పుడు ప్రారంభించబడింది. (Telugu language support is now enabled.)")
            else:
                user_manager.set_user_preference(user_id, 'language', 'english')
                await event.respond("Telugu language support is now disabled.")
        else:
            await event.respond("⛔ You don't have admin privileges to change language settings.")
    else:
        # Toggle Telugu support for the current user
        current_lang = user_manager.get_user_preference(user_id, 'language', 'english')
        
        if current_lang == 'telugu':
            user_manager.set_user_preference(user_id, 'language', 'english')
            await event.respond("Telugu language support is now disabled.")
        else:
            user_manager.set_user_preference(user_id, 'language', 'telugu')
            await event.respond("తెలుగు భాష మద్దతు ఇప్పుడు ప్రారంభించబడింది. (Telugu language support is now enabled.)")

# Callback query handler for inline buttons
@events.register(events.CallbackQuery())
async def callback_handler(event):
    """Handle callback queries from inline buttons"""
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    
    if data == "stats":
        stats = ipl_data.get_general_stats()
        await event.edit(stats)
    
    elif data == "teams":
        teams_info = ipl_data.get_all_teams()
        await event.edit(teams_info)
    
    elif data == "players":
        top_players = ipl_data.get_top_players()
        await event.edit(top_players)
    
    elif data == "schedule":
        schedule = ipl_data.get_schedule()
        await event.edit(schedule)
    
    elif data == "help":
        await help_handler(event)

# Message handler for natural conversations
@events.register(events.NewMessage)
async def handle_message(event):
    """Handle regular messages for conversation"""
    # Ignore commands
    if event.message.text.startswith('/'):
        return
    
    sender = await event.get_sender()
    user_id = sender.id
    
    # Check if user is blocked
    if user_manager.is_blocked(user_id):
        return
    
    # Register user if new
    if not user_manager.is_registered(user_id):
        user_manager.register_user(user_id, sender.username, sender.first_name)
    
    # Get message text
    message_text = event.message.text.strip()
    
    # Get bot configuration for conversation
    bot_config = admin_manager.get_bot_config()
    
    # Get user language preference
    user_lang = user_manager.get_user_preference(user_id, 'language', 'english')
    
    # Generate response with team support and style settings
    response = await ai_engine.generate_response(user_id, message_text, bot_config)
    
    # Send typing action
    async with bot.action(event.chat_id, 'typing'):
        # Add a small delay to simulate thinking/typing
        await asyncio.sleep(len(response) * 0.01)  # Adjust delay based on response length
        await event.respond(response)
    
    # Log the interaction
    ai_engine.learn_from_interaction(user_id, message_text, response)

# Main function to run the bot
async def main():
    """Start the bot and print some information"""
    me = await bot.get_me()
    logger.info(f"Bot started as @{me.username}")
    
    # Register all event handlers
    register_handlers(bot, user_manager, admin_manager, ipl_data, ai_engine)
    
    # Run the client until disconnected
    await bot.run_until_disconnected()

if __name__ == '__main__':
    # Start the bot
    asyncio.run(main())
