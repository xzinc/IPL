import os
import json
import logging
import pymongo
import redis
from urllib.parse import urlparse
from datetime import datetime
import random

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manager for multiple database connections to store user interactions.
    Supports automatic failover between databases when storage limits are reached.
    """
    
    def __init__(self):
        """Initialize the Database Manager with multiple database connections"""
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize database connections
        self.db_connections = {}
        self.active_db = None
        self.fallback_to_file = False
        
        # Load database configuration
        self.db_config = self.load_db_config()
        
        # Initialize all configured databases
        self.initialize_databases()
        
        # Set the active database
        self.set_active_database()
        
        # Load database stats
        self.db_stats = self.load_db_stats()
    
    def load_db_config(self):
        """Load database configuration from file or environment variables"""
        db_config_file = os.path.join(self.data_dir, 'db_config.json')
        
        # Default configuration
        default_config = {
            "databases": [
                {
                    "name": "primary_mongodb",
                    "type": "mongodb",
                    "uri": os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/iplbot'),
                    "priority": 1,
                    "collection": "user_interactions",
                    "max_size_mb": 500  # Default limit for free MongoDB Atlas
                },
                {
                    "name": "secondary_mongodb",
                    "type": "mongodb",
                    "uri": os.environ.get('SECONDARY_MONGODB_URI', ''),
                    "priority": 2,
                    "collection": "user_interactions",
                    "max_size_mb": 500
                },
                {
                    "name": "redis_cache",
                    "type": "redis",
                    "uri": os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
                    "priority": 3,
                    "max_size_mb": 30  # Default limit for free Redis Cloud
                }
            ],
            "auto_failover": True,
            "learning_enabled": True
        }
        
        # Try to load custom configuration
        if os.path.exists(db_config_file):
            try:
                with open(db_config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with default config to ensure all fields exist
                    if "databases" not in config:
                        config["databases"] = default_config["databases"]
                    if "auto_failover" not in config:
                        config["auto_failover"] = default_config["auto_failover"]
                    if "learning_enabled" not in config:
                        config["learning_enabled"] = default_config["learning_enabled"]
                    return config
            except Exception as e:
                logger.error(f"Error loading database configuration: {e}")
        
        return default_config
    
    def save_db_config(self):
        """Save database configuration to file"""
        db_config_file = os.path.join(self.data_dir, 'db_config.json')
        
        try:
            with open(db_config_file, 'w') as f:
                json.dump(self.db_config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving database configuration: {e}")
    
    def load_db_stats(self):
        """Load database statistics from file"""
        db_stats_file = os.path.join(self.data_dir, 'db_stats.json')
        
        if os.path.exists(db_stats_file):
            try:
                with open(db_stats_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading database stats: {e}")
        
        # Initialize empty stats for each database
        stats = {}
        for db_config in self.db_config["databases"]:
            stats[db_config["name"]] = {
                "status": "unknown",
                "size_mb": 0,
                "document_count": 0,
                "last_updated": datetime.now().isoformat(),
                "error_count": 0,
                "last_error": None
            }
        
        return stats
    
    def save_db_stats(self):
        """Save database statistics to file"""
        db_stats_file = os.path.join(self.data_dir, 'db_stats.json')
        
        try:
            with open(db_stats_file, 'w') as f:
                json.dump(self.db_stats, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving database stats: {e}")
    
    def initialize_databases(self):
        """Initialize all configured database connections"""
        for db_config in self.db_config["databases"]:
            db_name = db_config["name"]
            db_type = db_config["type"]
            db_uri = db_config["uri"]
            
            # Skip if URI is empty
            if not db_uri:
                logger.info(f"Skipping database {db_name} as URI is empty")
                continue
            
            try:
                if db_type == "mongodb":
                    self.initialize_mongodb(db_name, db_config)
                elif db_type == "redis":
                    self.initialize_redis(db_name, db_config)
                else:
                    logger.warning(f"Unsupported database type: {db_type}")
            except Exception as e:
                logger.error(f"Error initializing database {db_name}: {e}")
                self.db_stats[db_name]["status"] = "error"
                self.db_stats[db_name]["error_count"] += 1
                self.db_stats[db_name]["last_error"] = str(e)
                self.db_stats[db_name]["last_updated"] = datetime.now().isoformat()
    
    def initialize_mongodb(self, db_name, db_config):
        """Initialize a MongoDB connection"""
        try:
            # Connect to MongoDB
            client = pymongo.MongoClient(db_config["uri"])
            
            # Extract database name from URI or use default
            parsed_uri = urlparse(db_config["uri"])
            path = parsed_uri.path.strip('/')
            mongo_db_name = path if path else "iplbot"
            
            # Get database and collection
            db = client[mongo_db_name]
            collection = db[db_config["collection"]]
            
            # Test connection
            client.admin.command('ping')
            
            # Store connection
            self.db_connections[db_name] = {
                "client": client,
                "db": db,
                "collection": collection,
                "type": "mongodb",
                "config": db_config
            }
            
            # Update stats
            self.update_mongodb_stats(db_name)
            
            logger.info(f"Successfully connected to MongoDB: {db_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB {db_name}: {e}")
            raise
    
    def initialize_redis(self, db_name, db_config):
        """Initialize a Redis connection"""
        try:
            # Parse Redis URL
            parsed_url = urlparse(db_config["uri"])
            
            # Extract host, port, password, and db number
            host = parsed_url.hostname or 'localhost'
            port = parsed_url.port or 6379
            password = parsed_url.password or None
            db_number = int(parsed_url.path.replace('/', '') or 0)
            
            # Connect to Redis
            client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db_number,
                decode_responses=True
            )
            
            # Test connection
            client.ping()
            
            # Store connection
            self.db_connections[db_name] = {
                "client": client,
                "type": "redis",
                "config": db_config
            }
            
            # Update stats
            self.update_redis_stats(db_name)
            
            logger.info(f"Successfully connected to Redis: {db_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis {db_name}: {e}")
            raise
    
    def update_mongodb_stats(self, db_name):
        """Update MongoDB statistics"""
        if db_name not in self.db_connections:
            return
        
        try:
            conn = self.db_connections[db_name]
            if conn["type"] != "mongodb":
                return
            
            # Get collection stats
            stats = conn["db"].command("collStats", conn["config"]["collection"])
            
            # Update stats
            self.db_stats[db_name] = {
                "status": "connected",
                "size_mb": stats.get("size", 0) / (1024 * 1024),
                "document_count": stats.get("count", 0),
                "last_updated": datetime.now().isoformat(),
                "error_count": self.db_stats[db_name].get("error_count", 0),
                "last_error": self.db_stats[db_name].get("last_error", None)
            }
            
            self.save_db_stats()
        except Exception as e:
            logger.error(f"Error updating MongoDB stats for {db_name}: {e}")
            self.db_stats[db_name]["status"] = "error"
            self.db_stats[db_name]["error_count"] += 1
            self.db_stats[db_name]["last_error"] = str(e)
            self.db_stats[db_name]["last_updated"] = datetime.now().isoformat()
            self.save_db_stats()
    
    def update_redis_stats(self, db_name):
        """Update Redis statistics"""
        if db_name not in self.db_connections:
            return
        
        try:
            conn = self.db_connections[db_name]
            if conn["type"] != "redis":
                return
            
            # Get Redis info
            info = conn["client"].info("memory")
            
            # Update stats
            self.db_stats[db_name] = {
                "status": "connected",
                "size_mb": info.get("used_memory", 0) / (1024 * 1024),
                "document_count": conn["client"].dbsize(),
                "last_updated": datetime.now().isoformat(),
                "error_count": self.db_stats[db_name].get("error_count", 0),
                "last_error": self.db_stats[db_name].get("last_error", None)
            }
            
            self.save_db_stats()
        except Exception as e:
            logger.error(f"Error updating Redis stats for {db_name}: {e}")
            self.db_stats[db_name]["status"] = "error"
            self.db_stats[db_name]["error_count"] += 1
            self.db_stats[db_name]["last_error"] = str(e)
            self.db_stats[db_name]["last_updated"] = datetime.now().isoformat()
            self.save_db_stats()
    
    def set_active_database(self):
        """Set the active database based on priority and availability"""
        # Sort databases by priority
        sorted_dbs = sorted(self.db_config["databases"], key=lambda x: x["priority"])
        
        for db_config in sorted_dbs:
            db_name = db_config["name"]
            
            # Skip if database is not connected
            if db_name not in self.db_connections:
                continue
            
            # Check if database is below size limit
            if self.is_database_available(db_name):
                self.active_db = db_name
                logger.info(f"Set active database to {db_name}")
                return
        
        # If no database is available, fall back to file storage
        logger.warning("No database available, falling back to file storage")
        self.active_db = None
        self.fallback_to_file = True
    
    def is_database_available(self, db_name):
        """Check if a database is available and below size limit"""
        if db_name not in self.db_connections:
            return False
        
        conn = self.db_connections[db_name]
        db_config = conn["config"]
        
        # Check if database is connected
        if self.db_stats[db_name]["status"] != "connected":
            return False
        
        # Check if database is below size limit
        current_size = self.db_stats[db_name]["size_mb"]
        max_size = db_config.get("max_size_mb", float('inf'))
        
        return current_size < max_size
    
    def store_interaction(self, user_id, message, response, chat_type="private", group_id=None, feedback=None):
        """Store a user interaction in the active database"""
        # Skip if learning is disabled
        if not self.db_config.get("learning_enabled", True):
            return
        
        # Create interaction document
        interaction = {
            "user_id": str(user_id),
            "message": message,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "chat_type": chat_type,
            "feedback": feedback
        }
        
        # Add group_id if present
        if group_id:
            interaction["group_id"] = str(group_id)
        
        # Try to store in active database
        if self.active_db and not self.fallback_to_file:
            try:
                success = self._store_in_database(self.active_db, interaction)
                if not success and self.db_config.get("auto_failover", True):
                    # Try failover to another database
                    self._failover_to_next_database()
                    if self.active_db:
                        success = self._store_in_database(self.active_db, interaction)
            except Exception as e:
                logger.error(f"Error storing interaction in {self.active_db}: {e}")
                if self.db_config.get("auto_failover", True):
                    self._failover_to_next_database()
                    if self.active_db:
                        self._store_in_database(self.active_db, interaction)
        
        # Fall back to file storage if no database is available
        if self.fallback_to_file or not self.active_db:
            self._store_in_file(interaction)
    
    def _store_in_database(self, db_name, interaction):
        """Store an interaction in a specific database"""
        if db_name not in self.db_connections:
            return False
        
        conn = self.db_connections[db_name]
        
        try:
            if conn["type"] == "mongodb":
                # Store in MongoDB
                conn["collection"].insert_one(interaction)
                # Update stats
                self.update_mongodb_stats(db_name)
                return True
            elif conn["type"] == "redis":
                # Store in Redis
                # Use a unique key with timestamp and random suffix
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                random_suffix = ''.join(random.choices('0123456789', k=6))
                key = f"interaction:{interaction['user_id']}:{timestamp}:{random_suffix}"
                
                # Store as JSON string
                conn["client"].set(key, json.dumps(interaction))
                
                # Set expiration to 30 days (to manage storage)
                conn["client"].expire(key, 60 * 60 * 24 * 30)
                
                # Update stats
                self.update_redis_stats(db_name)
                return True
            else:
                logger.warning(f"Unsupported database type for {db_name}")
                return False
        except Exception as e:
            logger.error(f"Error storing in database {db_name}: {e}")
            # Update error stats
            self.db_stats[db_name]["status"] = "error"
            self.db_stats[db_name]["error_count"] += 1
            self.db_stats[db_name]["last_error"] = str(e)
            self.db_stats[db_name]["last_updated"] = datetime.now().isoformat()
            self.save_db_stats()
            return False
    
    def _store_in_file(self, interaction):
        """Store an interaction in a file"""
        # Get user ID
        user_id = interaction["user_id"]
        
        # Create user interactions directory
        interactions_dir = os.path.join(self.data_dir, 'interactions')
        os.makedirs(interactions_dir, exist_ok=True)
        
        # Create user-specific file
        user_file = os.path.join(interactions_dir, f"{user_id}.json")
        
        # Load existing interactions
        interactions = []
        if os.path.exists(user_file):
            try:
                with open(user_file, 'r') as f:
                    interactions = json.load(f)
            except Exception as e:
                logger.error(f"Error loading interactions for user {user_id}: {e}")
        
        # Add new interaction
        interactions.append(interaction)
        
        # Keep only the last 100 interactions to save space
        if len(interactions) > 100:
            interactions = interactions[-100:]
        
        # Save interactions
        try:
            with open(user_file, 'w') as f:
                json.dump(interactions, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving interactions for user {user_id}: {e}")
    
    def _failover_to_next_database(self):
        """Failover to the next available database"""
        # Get current active database priority
        current_priority = float('inf')
        if self.active_db:
            for db_config in self.db_config["databases"]:
                if db_config["name"] == self.active_db:
                    current_priority = db_config["priority"]
                    break
        
        # Find next database with higher priority
        next_db = None
        next_priority = float('inf')
        
        for db_config in self.db_config["databases"]:
            priority = db_config["priority"]
            db_name = db_config["name"]
            
            # Skip current database and databases with lower priority
            if priority <= current_priority:
                continue
            
            # Skip if database is not connected
            if db_name not in self.db_connections:
                continue
            
            # Check if database is available
            if self.is_database_available(db_name) and priority < next_priority:
                next_db = db_name
                next_priority = priority
        
        if next_db:
            logger.info(f"Failing over from {self.active_db} to {next_db}")
            self.active_db = next_db
        else:
            logger.warning("No failover database available, falling back to file storage")
            self.active_db = None
            self.fallback_to_file = True
    
    def get_user_interactions(self, user_id, limit=10):
        """Get recent user interactions from all databases"""
        user_id = str(user_id)
        interactions = []
        
        # Try to get from all databases
        for db_name, conn in self.db_connections.items():
            try:
                if conn["type"] == "mongodb":
                    # Get from MongoDB
                    cursor = conn["collection"].find(
                        {"user_id": user_id},
                        {"_id": 0}  # Exclude MongoDB ID
                    ).sort("timestamp", -1).limit(limit)
                    
                    for doc in cursor:
                        interactions.append(doc)
                
                elif conn["type"] == "redis":
                    # Get from Redis
                    # This is less efficient for Redis, but works
                    pattern = f"interaction:{user_id}:*"
                    keys = conn["client"].keys(pattern)
                    
                    # Sort keys by timestamp (embedded in the key)
                    keys.sort(reverse=True)
                    
                    # Get the most recent interactions
                    for key in keys[:limit]:
                        interaction_json = conn["client"].get(key)
                        if interaction_json:
                            interaction = json.loads(interaction_json)
                            interactions.append(interaction)
            except Exception as e:
                logger.error(f"Error getting interactions from {db_name}: {e}")
        
        # Get from file if needed
        if not interactions or len(interactions) < limit:
            file_interactions = self._get_interactions_from_file(user_id, limit)
            interactions.extend(file_interactions)
        
        # Sort by timestamp and limit
        interactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return interactions[:limit]
    
    def _get_interactions_from_file(self, user_id, limit=10):
        """Get user interactions from file"""
        user_id = str(user_id)
        interactions_dir = os.path.join(self.data_dir, 'interactions')
        user_file = os.path.join(interactions_dir, f"{user_id}.json")
        
        if os.path.exists(user_file):
            try:
                with open(user_file, 'r') as f:
                    interactions = json.load(f)
                    return interactions[-limit:]
            except Exception as e:
                logger.error(f"Error loading interactions for user {user_id}: {e}")
        
        return []
    
    def get_group_interactions(self, group_id, limit=50):
        """Get recent interactions from a group chat"""
        group_id = str(group_id)
        interactions = []
        
        # Try to get from all databases
        for db_name, conn in self.db_connections.items():
            try:
                if conn["type"] == "mongodb":
                    # Get from MongoDB
                    cursor = conn["collection"].find(
                        {"group_id": group_id},
                        {"_id": 0}  # Exclude MongoDB ID
                    ).sort("timestamp", -1).limit(limit)
                    
                    for doc in cursor:
                        interactions.append(doc)
                
                elif conn["type"] == "redis":
                    # Get from Redis - this is less efficient
                    # We need to scan all keys and filter
                    cursor = 0
                    pattern = "interaction:*"
                    
                    while True:
                        cursor, keys = conn["client"].scan(cursor, pattern, 100)
                        
                        for key in keys:
                            interaction_json = conn["client"].get(key)
                            if interaction_json:
                                interaction = json.loads(interaction_json)
                                if interaction.get("group_id") == group_id:
                                    interactions.append(interaction)
                        
                        if cursor == 0:
                            break
            except Exception as e:
                logger.error(f"Error getting group interactions from {db_name}: {e}")
        
        # Sort by timestamp and limit
        interactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return interactions[:limit]
    
    def get_database_stats(self):
        """Get statistics about all databases"""
        # Update stats for all databases
        for db_name in self.db_connections:
            conn = self.db_connections[db_name]
            if conn["type"] == "mongodb":
                self.update_mongodb_stats(db_name)
            elif conn["type"] == "redis":
                self.update_redis_stats(db_name)
        
        return self.db_stats
    
    def get_active_database(self):
        """Get the currently active database"""
        if self.fallback_to_file:
            return "file_storage"
        return self.active_db
    
    def close_connections(self):
        """Close all database connections"""
        for db_name, conn in self.db_connections.items():
            try:
                if conn["type"] == "mongodb":
                    conn["client"].close()
                # Redis connections are automatically closed
            except Exception as e:
                logger.error(f"Error closing connection to {db_name}: {e}")
    
    def get_language_stats(self):
        """Get statistics about language usage from interactions"""
        language_stats = {'english': 0, 'telugu': 0, 'unknown': 0}
        
        try:
            # Try to get stats from MongoDB
            if 'mongodb' in self.db_connections:
                try:
                    # Aggregate language counts
                    pipeline = [
                        {"$group": {"_id": "$language", "count": {"$sum": 1}}},
                        {"$sort": {"count": -1}}
                    ]
                    results = self.db_connections['mongodb']['collection'].aggregate(pipeline)
                    
                    for result in results:
                        language = result['_id'] if result['_id'] else 'unknown'
                        language_stats[language] = result['count']
                    
                    return language_stats
                except Exception as e:
                    logger.error(f"Error getting language stats from MongoDB: {e}")
            
            # Try to get stats from Redis
            if 'redis' in self.db_connections:
                try:
                    # Get all interaction keys
                    interaction_keys = self.db_connections['redis']['client'].keys('interaction:*')
                    
                    # Count languages
                    for key in interaction_keys:
                        interaction = self.db_connections['redis']['client'].get(key)
                        if interaction:
                            interaction = json.loads(interaction)
                            language = interaction.get('language', 'unknown')
                            language_stats[language] = language_stats.get(language, 0) + 1
                    
                    return language_stats
                except Exception as e:
                    logger.error(f"Error getting language stats from Redis: {e}")
            
            # Fall back to file storage
            if self.fallback_to_file:
                try:
                    interactions_file = os.path.join(self.data_dir, 'interactions.json')
                    if os.path.exists(interactions_file):
                        with open(interactions_file, 'r', encoding='utf-8') as f:
                            interactions = json.load(f)
                            
                            for interaction in interactions:
                                language = interaction.get('language', 'unknown')
                                language_stats[language] = language_stats.get(language, 0) + 1
                except Exception as e:
                    logger.error(f"Error getting language stats from file: {e}")
        
        except Exception as e:
            logger.error(f"Error getting language stats: {e}")
        
        return language_stats
