import os
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class UserManager:
    """
    Manager for user data including:
    1. User registration
    2. User preferences
    3. Subscription management
    4. Interaction logging
    """
    
    def __init__(self):
        """Initialize the User Manager"""
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load user data
        self.users = self.load_users()
        self.interactions = self.load_interactions()
        self.blocked_users = self.load_blocked_users()
    
    def load_users(self):
        """Load user data from file"""
        users_file = os.path.join(self.data_dir, 'users.json')
        
        if os.path.exists(users_file):
            try:
                with open(users_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading users data: {e}")
        
        return {}
    
    def save_users(self):
        """Save user data to file"""
        users_file = os.path.join(self.data_dir, 'users.json')
        
        try:
            with open(users_file, 'w') as f:
                json.dump(self.users, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving users data: {e}")
    
    def load_interactions(self):
        """Load user interactions from file"""
        interactions_file = os.path.join(self.data_dir, 'interactions.json')
        
        if os.path.exists(interactions_file):
            try:
                with open(interactions_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading interactions data: {e}")
        
        return {}
    
    def save_interactions(self):
        """Save user interactions to file"""
        interactions_file = os.path.join(self.data_dir, 'interactions.json')
        
        try:
            with open(interactions_file, 'w') as f:
                json.dump(self.interactions, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving interactions data: {e}")
    
    def load_blocked_users(self):
        """Load blocked users from file"""
        blocked_file = os.path.join(self.data_dir, 'blocked_users.json')
        
        if os.path.exists(blocked_file):
            try:
                with open(blocked_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading blocked users data: {e}")
        
        return []
    
    def save_blocked_users(self):
        """Save blocked users to file"""
        blocked_file = os.path.join(self.data_dir, 'blocked_users.json')
        
        try:
            with open(blocked_file, 'w') as f:
                json.dump(self.blocked_users, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving blocked users data: {e}")
    
    def register_user(self, user_id, username, first_name=None):
        """Register a new user or update existing user"""
        user_id = str(user_id)
        
        if user_id not in self.users:
            # New user
            self.users[user_id] = {
                "username": username,
                "first_name": first_name,
                "registered_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "subscribed": False,
                "preferences": {
                    "favorite_team": None,
                    "notifications": True,
                    "language": "english"
                },
                "interaction_count": 0
            }
            logger.info(f"New user registered: {username} (ID: {user_id})")
        else:
            # Update existing user
            self.users[user_id]["username"] = username
            if first_name:
                self.users[user_id]["first_name"] = first_name
            self.users[user_id]["last_active"] = datetime.now().isoformat()
        
        self.save_users()
        return self.users[user_id]
    
    def get_user(self, user_id):
        """Get user data by ID"""
        user_id = str(user_id)
        return self.users.get(user_id)
    
    def update_user_activity(self, user_id):
        """Update user's last activity timestamp"""
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]["last_active"] = datetime.now().isoformat()
            self.users[user_id]["interaction_count"] += 1
            self.save_users()
    
    def subscribe_user(self, user_id):
        """Subscribe a user to match notifications"""
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]["subscribed"] = True
            self.save_users()
            return "✅ You have successfully subscribed to IPL match notifications!"
        return "⚠️ Please start the bot with /start first."
    
    def unsubscribe_user(self, user_id):
        """Unsubscribe a user from match notifications"""
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]["subscribed"] = False
            self.save_users()
            return "✅ You have been unsubscribed from IPL match notifications."
        return "⚠️ Please start the bot with /start first."
    
    def is_subscribed(self, user_id):
        """Check if a user is subscribed to notifications"""
        user_id = str(user_id)
        if user_id in self.users:
            return self.users[user_id].get("subscribed", False)
        return False
    
    def get_all_subscribers(self):
        """Get a list of all subscribed users"""
        return [user_id for user_id, data in self.users.items() if data.get("subscribed", False)]
    
    def update_user_preference(self, user_id, preference, value):
        """Update a user preference"""
        user_id = str(user_id)
        if user_id in self.users:
            if "preferences" not in self.users[user_id]:
                self.users[user_id]["preferences"] = {}
            
            self.users[user_id]["preferences"][preference] = value
            self.save_users()
            return True
        return False
    
    def get_user_preference(self, user_id, preference, default=None):
        """Get a user preference with optional default value"""
        user_id = str(user_id)
        if user_id in self.users:
            return self.users[user_id].get("preferences", {}).get(preference, default)
        return default
    
    def set_user_preference(self, user_id, preference, value):
        """Set a user preference (alias for update_user_preference)"""
        return self.update_user_preference(user_id, preference, value)
    
    def is_registered(self, user_id):
        """Check if a user is registered"""
        user_id = str(user_id)
        return user_id in self.users
    
    def is_blocked(self, user_id):
        """Check if a user is blocked"""
        user_id = str(user_id)
        return user_id in self.blocked_users
    
    def block_user(self, user_id, blocked_by):
        """Block a user"""
        user_id = str(user_id)
        if user_id not in self.blocked_users:
            self.blocked_users.append(user_id)
            self.save_blocked_users()
            logger.info(f"User {user_id} blocked by {blocked_by}")
            return True
        return False
    
    def unblock_user(self, user_id, unblocked_by):
        """Unblock a user"""
        user_id = str(user_id)
        if user_id in self.blocked_users:
            self.blocked_users.remove(user_id)
            self.save_blocked_users()
            logger.info(f"User {user_id} unblocked by {unblocked_by}")
            return True
        return False
    
    def get_all_users(self):
        """Get a list of all user IDs"""
        return list(self.users.keys())
    
    def get_user_language(self, user_id):
        """Get a user's preferred language"""
        return self.get_user_preference(user_id, "language", "english")
    
    def set_user_language(self, user_id, language):
        """Set a user's preferred language"""
        return self.update_user_preference(user_id, "language", language)
    
    def get_user_stats(self):
        """Get statistics about users"""
        total_users = len(self.users)
        active_users = sum(1 for user_id, data in self.users.items() 
                          if datetime.now().timestamp() - datetime.fromisoformat(data["last_active"]).timestamp() < 86400 * 7)  # Active in last 7 days
        subscribed_users = len(self.get_all_subscribers())
        blocked_users = len(self.blocked_users)
        
        # Count users by language preference
        languages = {}
        for user_id, data in self.users.items():
            lang = data.get("preferences", {}).get("language", "english")
            languages[lang] = languages.get(lang, 0) + 1
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "subscribed_users": subscribed_users,
            "blocked_users": blocked_users,
            "languages": languages
        }
    
    def log_interaction(self, user_id, message):
        """Log a user interaction for learning"""
        user_id = str(user_id)
        
        # Update user activity
        self.update_user_activity(user_id)
        
        # Initialize user interactions if not exists
        if user_id not in self.interactions:
            self.interactions[user_id] = []
        
        # Add the interaction
        self.interactions[user_id].append({
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only the last 50 interactions per user to save space
        if len(self.interactions[user_id]) > 50:
            self.interactions[user_id] = self.interactions[user_id][-50:]
        
        # Save interactions
        self.save_interactions()
    
    def get_user_interactions(self, user_id, limit=10):
        """Get recent user interactions"""
        user_id = str(user_id)
        if user_id in self.interactions:
            return self.interactions[user_id][-limit:]
        return []
    
    def format_user_stats(self):
        """Format user statistics for display"""
        stats = self.get_user_stats()
        
        return (
            "👥 **User Statistics**\n\n"
            f"• Total Users: {stats['total_users']}\n"
            f"• Active Users (7d): {stats['active_users']}\n"
            f"• Subscribed Users: {stats['subscribed_users']}\n"
            f"• Blocked Users: {stats['blocked_users']}\n"
            f"• Languages: {', '.join(f'{lang}: {count}' for lang, count in stats['languages'].items())}\n"
        )
