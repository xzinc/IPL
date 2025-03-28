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

class AdminManager:
    """
    Manager for admin operations including:
    1. Admin authentication
    2. Admin commands
    3. System operations
    4. Bot configuration
    """
    
    def __init__(self, admin_ids=None):
        """Initialize the Admin Manager"""
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Set initial admin IDs
        self.admin_ids = admin_ids or []
        
        # Load admin data
        self.admin_data = self.load_admin_data()
        
        # Load bot configuration
        self.bot_config = self.load_bot_config()
        
        # Add initial admin IDs to the admin data
        for admin_id in self.admin_ids:
            if str(admin_id) not in self.admin_data:
                self.admin_data[str(admin_id)] = {
                    "added_at": datetime.now().isoformat(),
                    "permissions": ["full"],
                    "added_by": "system"
                }
        
        # Save updated admin data
        self.save_admin_data()
    
    def load_admin_data(self):
        """Load admin data from file"""
        admin_file = os.path.join(self.data_dir, 'admins.json')
        
        if os.path.exists(admin_file):
            try:
                with open(admin_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading admin data: {e}")
        
        return {}
    
    def save_admin_data(self):
        """Save admin data to file"""
        admin_file = os.path.join(self.data_dir, 'admins.json')
        
        try:
            with open(admin_file, 'w') as f:
                json.dump(self.admin_data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving admin data: {e}")
    
    def is_admin(self, user_id):
        """Check if a user is an admin"""
        return str(user_id) in self.admin_data
    
    def add_admin(self, user_id, added_by, permissions=None):
        """Add a new admin"""
        user_id = str(user_id)
        
        if user_id in self.admin_data:
            return False, "User is already an admin."
        
        self.admin_data[user_id] = {
            "added_at": datetime.now().isoformat(),
            "permissions": permissions or ["broadcast", "stats", "block"],
            "added_by": str(added_by)
        }
        
        self.save_admin_data()
        return True, f"User {user_id} has been added as an admin."
    
    def remove_admin(self, user_id, removed_by):
        """Remove an admin"""
        user_id = str(user_id)
        
        if user_id not in self.admin_data:
            return False, "User is not an admin."
        
        # Check if the user being removed is the original admin
        if "system" in self.admin_data[user_id].get("added_by", ""):
            return False, "Cannot remove the original admin."
        
        del self.admin_data[user_id]
        self.save_admin_data()
        
        return True, f"User {user_id} has been removed from admins."
    
    def has_permission(self, user_id, permission):
        """Check if an admin has a specific permission"""
        user_id = str(user_id)
        
        if not self.is_admin(user_id):
            return False
        
        admin_permissions = self.admin_data[user_id].get("permissions", [])
        return "full" in admin_permissions or permission in admin_permissions
    
    def grant_permission(self, user_id, permission, granted_by):
        """Grant a permission to an admin"""
        user_id = str(user_id)
        
        if not self.is_admin(user_id):
            return False, "User is not an admin."
        
        if permission in self.admin_data[user_id].get("permissions", []):
            return False, f"Admin already has the '{permission}' permission."
        
        self.admin_data[user_id].setdefault("permissions", []).append(permission)
        self.save_admin_data()
        
        # Log the permission change
        self.log_admin_action(granted_by, f"Granted '{permission}' permission to {user_id}")
        
        return True, f"Permission '{permission}' granted to admin {user_id}."
    
    def revoke_permission(self, user_id, permission, revoked_by):
        """Revoke a permission from an admin"""
        user_id = str(user_id)
        
        if not self.is_admin(user_id):
            return False, "User is not an admin."
        
        if permission not in self.admin_data[user_id].get("permissions", []):
            return False, f"Admin does not have the '{permission}' permission."
        
        if permission == "full" and "system" in self.admin_data[user_id].get("added_by", ""):
            return False, "Cannot revoke 'full' permission from the original admin."
        
        self.admin_data[user_id]["permissions"].remove(permission)
        self.save_admin_data()
        
        # Log the permission change
        self.log_admin_action(revoked_by, f"Revoked '{permission}' permission from {user_id}")
        
        return True, f"Permission '{permission}' revoked from admin {user_id}."
    
    def log_admin_action(self, admin_id, action):
        """Log an admin action"""
        log_file = os.path.join(self.data_dir, 'admin_logs.json')
        
        # Load existing logs
        logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            except Exception as e:
                logger.error(f"Error loading admin logs: {e}")
        
        # Add new log entry
        logs.append({
            "admin_id": str(admin_id),
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only the last 1000 logs to save space
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        # Save logs
        try:
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving admin logs: {e}")
    
    def get_admin_logs(self, limit=50):
        """Get recent admin logs"""
        log_file = os.path.join(self.data_dir, 'admin_logs.json')
        
        if not os.path.exists(log_file):
            return []
        
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
            return logs[-limit:]
        except Exception as e:
            logger.error(f"Error reading admin logs: {e}")
            return []
    
    def get_all_admins(self):
        """Get a list of all admins with their permissions"""
        return self.admin_data
    
    def format_admin_list(self):
        """Format admin list for display"""
        if not self.admin_data:
            return "No admins configured."
        
        admin_list = "👑 **Admin List**\n\n"
        
        for admin_id, data in self.admin_data.items():
            permissions = ", ".join(data.get("permissions", []))
            added_at = data.get("added_at", "Unknown")[:10]  # Just the date part
            added_by = data.get("added_by", "Unknown")
            
            admin_list += (
                f"**Admin ID:** {admin_id}\n"
                f"• Permissions: {permissions}\n"
                f"• Added on: {added_at}\n"
                f"• Added by: {added_by}\n\n"
            )
        
        return admin_list
    
    def load_bot_config(self):
        """Load bot configuration from file"""
        config_file = os.path.join(self.data_dir, 'bot_config.json')
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading bot configuration: {e}")
        
        # Default configuration
        default_config = {
            "supported_team": "neutral",  # Can be a team name or "neutral"
            "response_style": "balanced",  # balanced, enthusiastic, professional
            "prediction_confidence": "medium",  # low, medium, high
            "learning_rate": "normal",  # slow, normal, fast
            "last_updated": datetime.now().isoformat(),
            "updated_by": "system"
        }
        
        # Save default configuration
        try:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving default bot configuration: {e}")
        
        return default_config
    
    def save_bot_config(self):
        """Save bot configuration to file"""
        config_file = os.path.join(self.data_dir, 'bot_config.json')
        
        try:
            with open(config_file, 'w') as f:
                json.dump(self.bot_config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving bot configuration: {e}")
    
    def get_bot_config(self):
        """Get the current bot configuration"""
        return self.bot_config
    
    def update_bot_config(self, config_key, config_value, updated_by):
        """Update a bot configuration setting"""
        if config_key not in self.bot_config:
            return False, f"Invalid configuration key: {config_key}"
        
        # Validate input based on config key
        if config_key == "supported_team":
            valid_teams = [
                "neutral", "Mumbai Indians", "Chennai Super Kings", 
                "Royal Challengers Bangalore", "Kolkata Knight Riders",
                "Delhi Capitals", "Punjab Kings", "Rajasthan Royals",
                "Sunrisers Hyderabad", "Gujarat Titans", "Lucknow Super Giants"
            ]
            if config_value not in valid_teams:
                return False, f"Invalid team name. Choose from: {', '.join(valid_teams)}"
        
        elif config_key == "response_style":
            valid_styles = ["balanced", "enthusiastic", "professional"]
            if config_value not in valid_styles:
                return False, f"Invalid style. Choose from: {', '.join(valid_styles)}"
        
        elif config_key == "prediction_confidence":
            valid_levels = ["low", "medium", "high"]
            if config_value not in valid_levels:
                return False, f"Invalid level. Choose from: {', '.join(valid_levels)}"
        
        elif config_key == "learning_rate":
            valid_rates = ["slow", "normal", "fast"]
            if config_value not in valid_rates:
                return False, f"Invalid rate. Choose from: {', '.join(valid_rates)}"
        
        # Update the configuration
        self.bot_config[config_key] = config_value
        self.bot_config["last_updated"] = datetime.now().isoformat()
        self.bot_config["updated_by"] = str(updated_by)
        
        # Save the updated configuration
        self.save_bot_config()
        
        # Log the configuration change
        self.log_admin_action(updated_by, f"Updated bot configuration: {config_key} = {config_value}")
        
        return True, f"Bot configuration updated: {config_key} = {config_value}"
    
    def format_bot_config(self):
        """Format bot configuration for display"""
        config = self.bot_config
        
        return (
            "⚙️ **Bot Configuration**\n\n"
            f"• Supported Team: {config['supported_team']}\n"
            f"• Response Style: {config['response_style']}\n"
            f"• Prediction Confidence: {config['prediction_confidence']}\n"
            f"• Learning Rate: {config['learning_rate']}\n\n"
            f"Last updated: {config['last_updated'][:10]} by {config['updated_by']}"
        )
