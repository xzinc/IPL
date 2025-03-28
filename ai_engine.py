import os
import logging
import json
import asyncio
import numpy as np
from datetime import datetime
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from sentence_transformers import SentenceTransformer
import joblib
import dill
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import random
import time
from telugu_nlp import TeluguNLP
from db_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AIEngine:
    """
    AI Engine for the IPL Bot that handles:
    1. Natural language conversations
    2. Match predictions
    3. Learning from user interactions
    """
    
    def __init__(self):
        """Initialize the AI Engine with necessary models and data"""
        self.model_dir = os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Initialize database manager for storing interactions
        self.db_manager = DatabaseManager()
        
        # Initialize NLTK resources
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
        
        self.stop_words = set(stopwords.words('english'))
        
        # Initialize Telugu NLP
        self.telugu_nlp = TeluguNLP()
        self.telugu_nlp.load_model()
        
        # Initialize conversation model
        self.initialize_conversation_model()
        
        # Initialize embedding model for semantic search
        self.initialize_embedding_model()
        
        # Initialize prediction model
        self.initialize_prediction_model()
        
        # Load conversation history
        self.conversation_history = self.load_conversation_history()
        
        # Load user preferences
        self.user_preferences = self.load_user_preferences()
        
        # Load team performance data
        self.team_performance = self.load_team_performance()
        
        # Load player performance data
        self.player_performance = self.load_player_performance()
        
        # Load venue statistics
        self.venue_stats = self.load_venue_stats()
    
    def initialize_conversation_model(self):
        """Initialize the conversation model"""
        try:
            # Try to load a fine-tuned model if available
            model_path = os.path.join(self.model_dir, 'conversation_model')
            if os.path.exists(model_path):
                logger.info("Loading fine-tuned conversation model...")
                self.conversation_tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.conversation_model = AutoModelForCausalLM.from_pretrained(model_path)
            else:
                # Otherwise use a pre-trained model
                logger.info("Loading pre-trained conversation model...")
                model_name = "microsoft/DialoGPT-medium"  # A good starting point for conversations
                self.conversation_tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.conversation_model = AutoModelForCausalLM.from_pretrained(model_name)
                
            logger.info("Conversation model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading conversation model: {e}")
            # Fallback to rule-based responses if model loading fails
            self.conversation_model = None
            self.conversation_tokenizer = None
    
    def initialize_embedding_model(self):
        """Initialize the embedding model for semantic search"""
        try:
            # Load sentence transformer model for semantic search
            model_name = "all-MiniLM-L6-v2"  # Lightweight model good for semantic similarity
            self.embedding_model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")
            
            # Load pre-computed embeddings for IPL knowledge base if available
            kb_embeddings_path = os.path.join(self.model_dir, 'kb_embeddings.pkl')
            if os.path.exists(kb_embeddings_path):
                with open(kb_embeddings_path, 'rb') as f:
                    self.kb_data = dill.load(f)
                logger.info(f"Loaded {len(self.kb_data['texts'])} knowledge base items")
            else:
                # Initialize empty knowledge base
                self.kb_data = {
                    'texts': [],
                    'embeddings': None
                }
                logger.info("Initialized empty knowledge base")
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
            self.embedding_model = None
            self.kb_data = {'texts': [], 'embeddings': None}
    
    def initialize_prediction_model(self):
        """Initialize the match prediction model"""
        try:
            # Load prediction model if available
            prediction_model_path = os.path.join(self.model_dir, 'prediction_model.joblib')
            if os.path.exists(prediction_model_path):
                self.prediction_model = joblib.load(prediction_model_path)
                logger.info("Prediction model loaded successfully")
            else:
                # Set to None if not available
                self.prediction_model = None
                logger.info("No prediction model available")
        except Exception as e:
            logger.error(f"Error loading prediction model: {e}")
            self.prediction_model = None
    
    def load_conversation_history(self):
        """Load conversation history from storage"""
        history_path = os.path.join(os.path.dirname(__file__), 'data', 'conversation_history.json')
        try:
            if os.path.exists(history_path):
                with open(history_path, 'r') as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            return {}
    
    def save_conversation_history(self):
        """Save conversation history to storage"""
        history_path = os.path.join(os.path.dirname(__file__), 'data', 'conversation_history.json')
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        try:
            with open(history_path, 'w') as f:
                json.dump(self.conversation_history, f)
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")
    
    def load_user_preferences(self):
        """Load user preferences from storage"""
        prefs_path = os.path.join(os.path.dirname(__file__), 'data', 'user_preferences.json')
        try:
            if os.path.exists(prefs_path):
                with open(prefs_path, 'r') as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error loading user preferences: {e}")
            return {}
    
    def save_user_preferences(self):
        """Save user preferences to storage"""
        prefs_path = os.path.join(os.path.dirname(__file__), 'data', 'user_preferences.json')
        os.makedirs(os.path.dirname(prefs_path), exist_ok=True)
        try:
            with open(prefs_path, 'w') as f:
                json.dump(self.user_preferences, f)
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")
    
    def update_user_history(self, user_id, message, response):
        """Update conversation history for a user"""
        user_id = str(user_id)
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Add the new interaction
        self.conversation_history[user_id].append({
            'user_message': message,
            'bot_response': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only the last 20 interactions to save space
        if len(self.conversation_history[user_id]) > 20:
            self.conversation_history[user_id] = self.conversation_history[user_id][-20:]
        
        # Save the updated history
        self.save_conversation_history()
    
    def extract_user_preferences(self, user_id, message):
        """Extract user preferences from messages"""
        user_id = str(user_id)
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {
                'favorite_team': None,
                'favorite_players': [],
                'interests': []
            }
        
        # Simple keyword-based preference extraction
        message_lower = message.lower()
        
        # Check for favorite team mentions
        team_keywords = {
            'mumbai indians': 'Mumbai Indians',
            'chennai super kings': 'Chennai Super Kings',
            'csk': 'Chennai Super Kings',
            'royal challengers': 'Royal Challengers Bangalore',
            'rcb': 'Royal Challengers Bangalore',
            'kolkata knight riders': 'Kolkata Knight Riders',
            'kkr': 'Kolkata Knight Riders',
            'delhi capitals': 'Delhi Capitals',
            'sunrisers hyderabad': 'Sunrisers Hyderabad',
            'srh': 'Sunrisers Hyderabad',
            'punjab kings': 'Punjab Kings',
            'rajasthan royals': 'Rajasthan Royals',
            'lucknow super giants': 'Lucknow Super Giants',
            'gujarat titans': 'Gujarat Titans'
        }
        
        for keyword, team in team_keywords.items():
            if keyword in message_lower and 'favorite' in message_lower:
                self.user_preferences[user_id]['favorite_team'] = team
                break
        
        # Save preferences
        self.save_user_preferences()
    
    def get_knowledge_base_response(self, query, top_k=3):
        """Get response from knowledge base using semantic search"""
        if self.embedding_model is None or len(self.kb_data['texts']) == 0:
            return None
        
        # Encode the query
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Calculate cosine similarity
        similarities = np.dot(self.kb_data['embeddings'], query_embedding)
        
        # Get top k results
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        if similarities[top_indices[0]] < 0.5:  # Threshold for relevance
            return None
        
        # Return the most relevant information
        return self.kb_data['texts'][top_indices[0]]
    
    def get_rule_based_response(self, message):
        """Fallback to rule-based responses when AI model is not available"""
        message_lower = message.lower()
        
        # Simple rule-based responses
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "Hello! How can I help you with IPL today?"
        
        if 'who won' in message_lower and 'ipl' in message_lower:
            return "The most recent IPL was won by Chennai Super Kings in 2023. They defeated Gujarat Titans in the final."
        
        if 'schedule' in message_lower:
            return "I can provide you with the IPL schedule. Please use the /schedule command for the latest fixtures."
        
        if 'stats' in message_lower:
            return "For IPL statistics, please use the /stats command or ask about a specific team or player."
        
        # Default response
        return "I'm not sure I understand. You can ask me about IPL teams, players, stats, or use commands like /help to see what I can do."
    
    async def generate_response(self, user_id, message, bot_config=None):
        """Generate a response to a user message"""
        user_id = str(user_id)
        
        # Check if message is in Telugu
        is_telugu = self.telugu_nlp.detect_language(message)
        
        # Translate Telugu message to English if needed
        if is_telugu:
            original_message = message
            message = self.telugu_nlp.translate_to_english(message)
            logger.info(f"Translated Telugu message: '{original_message}' to '{message}'")
            
            # Set user preference to Telugu automatically
            if user_id in self.user_preferences:
                self.user_preferences[user_id]['language'] = 'telugu'
            else:
                self.user_preferences[user_id] = {'language': 'telugu'}
            
            # Save the updated preferences
            self.save_user_preferences()
        else:
            # Check if user has Telugu preference set
            user_prefs = self.user_preferences.get(user_id, {})
            is_telugu = user_prefs.get('language', 'english') == 'telugu'
        
        # Extract entities from the message
        entities = self.extract_entities(message)
        
        # Get bot configuration
        if bot_config is None:
            bot_config = {
                'supported_team': 'neutral',
                'response_style': 'balanced',
                'prediction_confidence': 'medium',
                'learning_rate': 'normal'
            }
        
        # Check if this is a prediction request
        if self.is_prediction_request(message):
            prediction = self.generate_prediction(message, entities, bot_config)
            
            # Translate response to Telugu if the original message was in Telugu
            if is_telugu:
                prediction = self.telugu_nlp.translate_to_telugu(prediction, ipl_context=True)
            
            return prediction
        
        # Check if this is a question about IPL data
        if self.is_ipl_data_question(message):
            data_response = self.generate_ipl_data_response(message, entities, bot_config)
            
            # Translate response to Telugu if the original message was in Telugu
            if is_telugu:
                data_response = self.telugu_nlp.translate_to_telugu(data_response, ipl_context=True)
            
            return data_response
        
        # Generate conversational response
        response = self.generate_conversational_response(user_id, message, entities, bot_config)
        
        # Translate response to Telugu if the original message was in Telugu
        if is_telugu:
            response = self.telugu_nlp.translate_to_telugu(response, ipl_context=True)
        
        return response
    
    def create_conversation_prompt(self, user_id, message, bot_config):
        """Create a prompt for the conversation model with context"""
        # Get user preferences if available
        user_prefs = self.user_preferences.get(user_id, {})
        favorite_team = user_prefs.get("favorite_team", "unknown")
        
        # Get recent conversation history (last 5 messages)
        history = self.conversation_history.get(user_id, [])[-5:]
        history_text = "\n".join([f"User: {h['user_message']}" for h in history])
        
        # Create prompt with bot personality based on response style
        personality = self.get_personality_prompt(bot_config["response_style"], bot_config["supported_team"])
        
        prompt = (
            f"{personality}\n\n"
            f"User's favorite team: {favorite_team}\n"
            f"Recent conversation:\n{history_text}\n\n"
            f"User: {message}\n"
            f"Assistant: "
        )
        
        return prompt
    
    def get_personality_prompt(self, response_style, supported_team):
        """Get personality prompt based on response style and supported team"""
        base_prompt = "You are an AI assistant specialized in IPL cricket."
        
        # Add team support context
        if supported_team != "neutral":
            base_prompt += f" You are a supporter of {supported_team} and show enthusiasm for this team."
        else:
            base_prompt += " You maintain a neutral stance regarding all IPL teams."
        
        # Add response style
        if response_style == "enthusiastic":
            base_prompt += (
                " Your responses are enthusiastic and energetic. You use exclamation marks, "
                "cricket slang, and show excitement about the game. You're passionate about cricket "
                "and it shows in your conversational style."
            )
        elif response_style == "professional":
            base_prompt += (
                " Your responses are professional, analytical and fact-based. You focus on statistics, "
                "technical aspects of the game, and provide detailed analysis. Your tone is formal and "
                "educational."
            )
        else:  # balanced
            base_prompt += (
                " Your responses balance enthusiasm with professionalism. You're conversational and "
                "friendly while still being informative and helpful. You can be excited about cricket "
                "while maintaining clarity and accuracy."
            )
        
        return base_prompt
    
    def format_response(self, response, entities, bot_config):
        """Format the response based on response style and entities mentioned"""
        # Trim response if too long
        if len(response) > 500:
            response = response[:497] + "..."
        
        # Add team-specific flair if the bot supports a team and that team is mentioned
        supported_team = bot_config["supported_team"]
        response_style = bot_config["response_style"]
        
        if supported_team != "neutral" and supported_team in entities.get("teams", []):
            if response_style == "enthusiastic":
                response += f"\n\nGo {supported_team}! 🎉"
            elif response_style == "professional":
                response += f"\n\nAs a {supported_team} supporter, I appreciate your interest in the team."
            else:  # balanced
                response += f"\n\nAlways great to discuss {supported_team}! 👍"
        
        return response
    
    def rule_based_response(self, message, entities, bot_config):
        """Generate a rule-based response when no model is available"""
        # Extract keywords from message
        keywords = [word.lower() for word in message.split() 
                   if word.lower() not in self.stop_words and len(word) > 2]
        
        # Check for common IPL-related queries
        if any(word in keywords for word in ["schedule", "fixture", "match", "when", "upcoming"]):
            return self.get_schedule_response(entities, bot_config)
        
        if any(word in keywords for word in ["stats", "statistics", "record", "performance"]):
            return self.get_stats_response(entities, bot_config)
        
        if any(word in keywords for word in ["predict", "prediction", "chances", "win", "outcome"]):
            return self.get_prediction_response(entities, bot_config)
        
        if any(word in keywords for word in ["player", "batsman", "bowler", "captain", "allrounder"]):
            return self.get_player_response(entities, bot_config)
        
        # Default response
        return self.get_default_response(bot_config)
    
    def get_schedule_response(self, entities, bot_config):
        """Get response about match schedule"""
        teams = entities.get("teams", [])
        
        if teams:
            team = teams[0]
            response = f"The next few matches for {team} include games against Chennai Super Kings, Royal Challengers Bangalore, and Kolkata Knight Riders. Would you like me to provide the exact dates and venues?"
        else:
            response = "The IPL season is in full swing with exciting matches scheduled every day. You can use the /schedule command to see the full fixture list."
        
        # Adjust based on supported team
        supported_team = bot_config["supported_team"]
        if supported_team != "neutral" and supported_team in teams:
            if bot_config["response_style"] == "enthusiastic":
                response += f"\n\nI'm particularly excited for {supported_team}'s upcoming matches! Can't wait to see them in action! 🔥"
            elif bot_config["response_style"] == "professional":
                response += f"\n\n{supported_team} has been preparing well for their upcoming fixtures, with focused training sessions on batting and fielding."
        
        return response
    
    def get_stats_response(self, entities, bot_config):
        """Get response about statistics"""
        teams = entities.get("teams", [])
        players = entities.get("players", [])
        
        if teams:
            team = teams[0]
            response = f"{team} has had a strong season so far with a balanced performance in both batting and bowling departments. Their net run rate is positive, and they've won a majority of their matches."
        elif players:
            player = players[0]
            response = f"{player} has been in excellent form this season, contributing consistently with both bat and ball. His strike rate is impressive, and he's been a key player for his team."
        else:
            response = "IPL statistics show some fascinating trends this season. The average first innings score has increased, and teams batting second have been winning more frequently than in previous seasons."
        
        # Adjust based on response style
        if bot_config["response_style"] == "professional":
            response += "\n\nStatistical analysis indicates that powerplay performance has been a key determinant of match outcomes this season, with teams scoring 50+ runs in the first six overs winning 70% of their matches."
        
        return response
    
    def get_prediction_response(self, entities, bot_config):
        """Get response about predictions"""
        teams = entities.get("teams", [])
        
        if len(teams) >= 2:
            team1, team2 = teams[:2]
            # Use the predict_match function which already handles bot_config
            return self.predict_match(f"{team1} vs {team2}", bot_config)
        elif teams:
            team = teams[0]
            response = f"{team} has shown good form recently. Their chances in the tournament look promising, especially if their key players maintain their performance levels."
        else:
            response = "Predicting IPL outcomes is complex due to the dynamic nature of T20 cricket. Factors like team form, player availability, and pitch conditions all play crucial roles."
        
        return response
    
    def get_player_response(self, entities, bot_config):
        """Get response about players"""
        players = entities.get("players", [])
        
        if players:
            player = players[0]
            response = f"{player} is a talented cricketer with a unique playing style. He's known for his technical skills and ability to perform under pressure."
        else:
            response = "IPL features some of the best cricket talent from around the world. The tournament has been a platform for many young players to showcase their skills alongside established stars."
        
        # Adjust based on response style
        if bot_config["response_style"] == "enthusiastic":
            response += "\n\nThe quality of cricket on display has been absolutely phenomenal! These players are giving it their all! 🏏✨"
        
        return response
    
    def get_default_response(self, bot_config):
        """Get default response when no specific topic is detected"""
        responses = [
            "The IPL is one of the most exciting cricket tournaments in the world. What specific aspect would you like to discuss?",
            "Cricket is a game of strategy, skill, and sometimes luck. Is there a particular IPL team or player you're interested in?",
            "The current IPL season has seen some thrilling matches. Would you like to know about recent results or upcoming fixtures?",
            "IPL combines world-class cricket with entertainment. What's your favorite part of the tournament?"
        ]
        
        response = random.choice(responses)
        
        # Adjust based on response style and supported team
        if bot_config["response_style"] == "enthusiastic":
            response += " I'm super excited to chat about all things IPL with you! 🏆"
        elif bot_config["response_style"] == "professional":
            response += " I can provide detailed analysis on various aspects of the tournament if you have specific queries."
        
        if bot_config["supported_team"] != "neutral":
            team = bot_config["supported_team"]
            response += f" As a {team} supporter, I'm always happy to discuss their performance in particular."
        
        return response
    
    def extract_ipl_entities(self, message):
        """Extract IPL-related entities from message"""
        entities = {
            "teams": [],
            "players": [],
            "venues": []
        }
        
        # List of IPL teams
        teams = [
            "Mumbai Indians", "Chennai Super Kings", 
            "Royal Challengers Bangalore", "Kolkata Knight Riders",
            "Delhi Capitals", "Punjab Kings", "Rajasthan Royals",
            "Sunrisers Hyderabad", "Gujarat Titans", "Lucknow Super Giants",
            "MI", "CSK", "RCB", "KKR", "DC", "PBKS", "RR", "SRH", "GT", "LSG"
        ]
        
        # Simple extraction based on exact matches
        message_lower = message.lower()
        
        for team in teams:
            if team.lower() in message_lower:
                # Convert abbreviations to full names
                if team == "MI":
                    entities["teams"].append("Mumbai Indians")
                elif team == "CSK":
                    entities["teams"].append("Chennai Super Kings")
                elif team == "RCB":
                    entities["teams"].append("Royal Challengers Bangalore")
                elif team == "KKR":
                    entities["teams"].append("Kolkata Knight Riders")
                elif team == "DC":
                    entities["teams"].append("Delhi Capitals")
                elif team == "PBKS":
                    entities["teams"].append("Punjab Kings")
                elif team == "RR":
                    entities["teams"].append("Rajasthan Royals")
                elif team == "SRH":
                    entities["teams"].append("Sunrisers Hyderabad")
                elif team == "GT":
                    entities["teams"].append("Gujarat Titans")
                elif team == "LSG":
                    entities["teams"].append("Lucknow Super Giants")
                else:
                    entities["teams"].append(team)
        
        # Remove duplicates
        entities["teams"] = list(set(entities["teams"]))
        
        # In a real implementation, you would have a more sophisticated NER model
        # to extract players and venues as well
        
        return entities
    
    def load_team_performance(self):
        """Load team performance data for predictions"""
        team_perf_path = os.path.join(self.model_dir, 'team_performance.json')
        try:
            if os.path.exists(team_perf_path):
                with open(team_perf_path, 'r') as f:
                    return json.load(f)
            else:
                # Create default team performance data
                default_data = {}
                teams = [
                    "Mumbai Indians", "Chennai Super Kings", 
                    "Royal Challengers Bangalore", "Kolkata Knight Riders",
                    "Delhi Capitals", "Punjab Kings", "Rajasthan Royals",
                    "Sunrisers Hyderabad", "Gujarat Titans", "Lucknow Super Giants"
                ]
                
                for team in teams:
                    default_data[team] = {
                        "overall_win_rate": 0.5,
                        "recent_form": [1, 0, 1, 0, 1],  # 1 = win, 0 = loss
                        "home_win_rate": 0.55,
                        "away_win_rate": 0.45,
                        "batting_strength": 7.5,  # scale of 1-10
                        "bowling_strength": 7.5,  # scale of 1-10
                        "head_to_head": {}
                    }
                    # Add head-to-head records
                    for opponent in teams:
                        if opponent != team:
                            default_data[team]["head_to_head"][opponent] = {
                                "wins": 5,
                                "losses": 5,
                                "no_result": 0
                            }
                
                # Save default data
                with open(team_perf_path, 'w') as f:
                    json.dump(default_data, f, indent=4)
                
                return default_data
        except Exception as e:
            logger.error(f"Error loading team performance data: {e}")
            return {}
    
    def load_player_performance(self):
        """Load player performance data for predictions"""
        player_perf_path = os.path.join(self.model_dir, 'player_performance.json')
        try:
            if os.path.exists(player_perf_path):
                with open(player_perf_path, 'r') as f:
                    return json.load(f)
            else:
                # Create default player performance data (simplified)
                return {}
        except Exception as e:
            logger.error(f"Error loading player performance data: {e}")
            return {}
    
    def load_venue_stats(self):
        """Load venue statistics for predictions"""
        venue_stats_path = os.path.join(self.model_dir, 'venue_stats.json')
        try:
            if os.path.exists(venue_stats_path):
                with open(venue_stats_path, 'r') as f:
                    return json.load(f)
            else:
                # Create default venue statistics
                default_venues = {
                    "Wankhede Stadium": {
                        "avg_first_innings_score": 175,
                        "avg_second_innings_score": 165,
                        "chasing_win_percentage": 45,
                        "pitch_type": "batting-friendly",
                        "boundary_percentage": 15.5
                    },
                    "M. A. Chidambaram Stadium": {
                        "avg_first_innings_score": 165,
                        "avg_second_innings_score": 155,
                        "chasing_win_percentage": 40,
                        "pitch_type": "spin-friendly",
                        "boundary_percentage": 14.0
                    },
                    "Eden Gardens": {
                        "avg_first_innings_score": 170,
                        "avg_second_innings_score": 160,
                        "chasing_win_percentage": 48,
                        "pitch_type": "balanced",
                        "boundary_percentage": 15.0
                    },
                    "M. Chinnaswamy Stadium": {
                        "avg_first_innings_score": 185,
                        "avg_second_innings_score": 175,
                        "chasing_win_percentage": 52,
                        "pitch_type": "batting-friendly",
                        "boundary_percentage": 17.5
                    },
                    "Arun Jaitley Stadium": {
                        "avg_first_innings_score": 175,
                        "avg_second_innings_score": 165,
                        "chasing_win_percentage": 45,
                        "pitch_type": "balanced",
                        "boundary_percentage": 15.0
                    }
                }
                
                # Save default data
                with open(venue_stats_path, 'w') as f:
                    json.dump(default_venues, f, indent=4)
                
                return default_venues
        except Exception as e:
            logger.error(f"Error loading venue statistics: {e}")
            return {}
    
    def predict_match(self, match_query, bot_config=None):
        """
        Predict the outcome of a match with enhanced analytics
        
        Args:
            match_query: String in format "team1 vs team2" or with venue "team1 vs team2 at venue"
            bot_config: Bot configuration including supported team and prediction confidence
        """
        # Default bot config if not provided
        if bot_config is None:
            bot_config = {
                "supported_team": "neutral",
                "prediction_confidence": "medium"
            }
        
        # Parse the match query
        match_info = self.parse_match_query(match_query)
        if not match_info:
            return "Please provide the match in format: 'Team1 vs Team2' or 'Team1 vs Team2 at Venue'"
        
        team1 = match_info['team1']
        team2 = match_info['team2']
        venue = match_info.get('venue')
        
        # If we have a prediction model, use it
        if self.prediction_model:
            try:
                # Extract features for prediction
                features = self.extract_match_features(team1, team2, venue)
                
                # Make prediction
                prediction = self.prediction_model.predict_proba([features])[0]
                
                # Format the response based on prediction confidence setting
                team1_win_prob, team2_win_prob = self.adjust_prediction_confidence(
                    prediction[1] * 100, 
                    prediction[0] * 100,
                    bot_config["prediction_confidence"]
                )
                
                # Adjust response based on supported team
                return self.format_prediction_response(
                    team1, team2, team1_win_prob, team2_win_prob, 
                    venue, bot_config["supported_team"]
                )
            except Exception as e:
                logger.error(f"Error in match prediction: {e}")
        
        # If no model, use rule-based prediction with team performance data
        return self.rule_based_prediction(team1, team2, venue, bot_config)
    
    def parse_match_query(self, match_query):
        """Parse the match query to extract teams and venue"""
        # Check for venue information
        if " at " in match_query.lower():
            match_parts = match_query.split(" at ", 1)
            teams_part = match_parts[0].strip()
            venue = match_parts[1].strip()
        else:
            teams_part = match_query
            venue = None
        
        # Parse teams
        teams = [team.strip() for team in teams_part.split('vs')]
        
        if len(teams) != 2:
            return None
        
        team1, team2 = teams
        
        # Validate team names
        valid_teams = [
            "Mumbai Indians", "Chennai Super Kings", 
            "Royal Challengers Bangalore", "Kolkata Knight Riders",
            "Delhi Capitals", "Punjab Kings", "Rajasthan Royals",
            "Sunrisers Hyderabad", "Gujarat Titans", "Lucknow Super Giants"
        ]
        
        # Try to match with valid team names (case-insensitive)
        team1_match = next((t for t in valid_teams if t.lower() == team1.lower()), None)
        team2_match = next((t for t in valid_teams if t.lower() == team2.lower()), None)
        
        if not team1_match or not team2_match:
            return None
        
        result = {
            'team1': team1_match,
            'team2': team2_match
        }
        
        if venue:
            result['venue'] = venue
        
        return result
    
    def extract_match_features(self, team1, team2, venue=None):
        """
        Extract comprehensive features for match prediction
        
        Features include:
        - Team performance metrics
        - Head-to-head record
        - Recent form
        - Home/away advantage
        - Venue characteristics
        - Team strengths (batting/bowling)
        """
        features = []
        
        # Get team performance data
        team1_data = self.team_performance.get(team1, {})
        team2_data = self.team_performance.get(team2, {})
        
        # Overall win rates
        features.append(team1_data.get("overall_win_rate", 0.5))
        features.append(team2_data.get("overall_win_rate", 0.5))
        
        # Recent form (average of last 5 matches)
        team1_form = sum(team1_data.get("recent_form", [0.5, 0.5, 0.5, 0.5, 0.5])) / 5
        team2_form = sum(team2_data.get("recent_form", [0.5, 0.5, 0.5, 0.5, 0.5])) / 5
        features.append(team1_form)
        features.append(team2_form)
        
        # Head-to-head
        h2h = team1_data.get("head_to_head", {}).get(team2, {"wins": 5, "losses": 5})
        total_matches = h2h.get("wins", 0) + h2h.get("losses", 0)
        h2h_ratio = h2h.get("wins", 0) / total_matches if total_matches > 0 else 0.5
        features.append(h2h_ratio)
        
        # Team strengths
        features.append(team1_data.get("batting_strength", 7.5) / 10)
        features.append(team1_data.get("bowling_strength", 7.5) / 10)
        features.append(team2_data.get("batting_strength", 7.5) / 10)
        features.append(team2_data.get("bowling_strength", 7.5) / 10)
        
        # Venue factors
        if venue:
            venue_data = self.venue_stats.get(venue, {})
            features.append(venue_data.get("chasing_win_percentage", 45) / 100)
            
            # Pitch type factor (encoded)
            pitch_type = venue_data.get("pitch_type", "balanced")
            if pitch_type == "batting-friendly":
                features.append(0.7)
            elif pitch_type == "bowling-friendly":
                features.append(0.3)
            elif pitch_type == "spin-friendly":
                features.append(0.4)
            else:  # balanced
                features.append(0.5)
        else:
            # Default venue factors
            features.append(0.5)  # chasing win percentage
            features.append(0.5)  # pitch type
        
        return features
    
    def adjust_prediction_confidence(self, team1_prob, team2_prob, confidence_level):
        """Adjust prediction probabilities based on confidence level"""
        # Ensure probabilities sum to 100
        total = team1_prob + team2_prob
        team1_prob = (team1_prob / total) * 100
        team2_prob = (team2_prob / total) * 100
        
        # Adjust based on confidence level
        if confidence_level == "low":
            # Move probabilities closer to 50-50
            team1_prob = 50 + (team1_prob - 50) * 0.5
            team2_prob = 50 + (team2_prob - 50) * 0.5
        elif confidence_level == "high":
            # Exaggerate the difference
            if team1_prob > team2_prob:
                diff = (team1_prob - team2_prob) * 0.2
                team1_prob += diff
                team2_prob -= diff
            else:
                diff = (team2_prob - team1_prob) * 0.2
                team2_prob += diff
                team1_prob -= diff
            
            # Ensure values are within bounds
            team1_prob = min(max(team1_prob, 5), 95)
            team2_prob = min(max(team2_prob, 5), 95)
            
            # Re-normalize
            total = team1_prob + team2_prob
            team1_prob = (team1_prob / total) * 100
            team2_prob = (team2_prob / total) * 100
        
        return team1_prob, team2_prob
    
    def format_prediction_response(self, team1, team2, team1_prob, team2_prob, venue, supported_team):
        """Format the prediction response based on supported team"""
        # Determine if there's a clear favorite
        favorite = team1 if team1_prob > team2_prob else team2
        underdog = team2 if team1_prob > team2_prob else team1
        favorite_prob = max(team1_prob, team2_prob)
        underdog_prob = min(team1_prob, team2_prob)
        
        # Base response
        response = (
            f"🏏 **Match Prediction: {team1} vs {team2}**\n\n"
            f"Based on my analysis:\n"
            f"• {team1}: {team1_prob:.1f}% chance to win\n"
            f"• {team2}: {team2_prob:.1f}% chance to win\n\n"
        )
        
        # Add venue information if available
        if venue:
            response += f"Venue: {venue}\n\n"
        
        # Adjust response based on supported team
        if supported_team != "neutral":
            if supported_team == team1:
                if team1_prob > team2_prob:
                    response += f"As a {team1} supporter, I'm optimistic about our chances! "
                    response += f"Our batting lineup has been strong recently, and we have a good record against {team2}.\n\n"
                else:
                    response += f"As a {team1} supporter, this might be a challenging match, but we've overcome the odds before! "
                    response += f"If our key players perform well, we can definitely beat {team2}.\n\n"
            elif supported_team == team2:
                if team2_prob > team1_prob:
                    response += f"As a {team2} supporter, I'm optimistic about our chances! "
                    response += f"Our batting lineup has been strong recently, and we have a good record against {team1}.\n\n"
                else:
                    response += f"As a {team2} supporter, this might be a challenging match, but we've overcome the odds before! "
                    response += f"If our key players perform well, we can definitely beat {team1}.\n\n"
            else:
                # Bot supports a team not playing in this match
                response += f"While I support {supported_team}, I'll be watching this match with interest.\n\n"
        else:
            # Neutral analysis
            if abs(team1_prob - team2_prob) < 10:
                response += "This looks like a very close contest! Both teams are evenly matched.\n\n"
            else:
                response += f"{favorite} has a clear advantage, but {underdog} could still pull off an upset with the right strategy.\n\n"
        
        # Add key factors
        response += "**Key factors in this prediction:**\n"
        response += "• Recent team form and momentum\n"
        response += "• Head-to-head record\n"
        response += "• Team composition and player availability\n"
        
        if venue:
            response += "• Pitch conditions and venue statistics\n"
        
        return response
    
    def rule_based_prediction(self, team1, team2, venue, bot_config):
        """Rule-based prediction when no ML model is available"""
        # Get team performance data
        team1_data = self.team_performance.get(team1, {})
        team2_data = self.team_performance.get(team2, {})
        
        # Calculate win probabilities based on available data
        team1_factors = [
            team1_data.get("overall_win_rate", 0.5) * 0.3,
            sum(team1_data.get("recent_form", [0.5, 0.5, 0.5, 0.5, 0.5])) / 5 * 0.3
        ]
        
        team2_factors = [
            team2_data.get("overall_win_rate", 0.5) * 0.3,
            sum(team2_data.get("recent_form", [0.5, 0.5, 0.5, 0.5, 0.5])) / 5 * 0.3
        ]
        
        # Head-to-head factor
        h2h = team1_data.get("head_to_head", {}).get(team2, {"wins": 5, "losses": 5})
        total_matches = h2h.get("wins", 0) + h2h.get("losses", 0)
        if total_matches > 0:
            h2h_ratio = h2h.get("wins", 0) / total_matches
            team1_factors.append(h2h_ratio * 0.2)
            team2_factors.append((1 - h2h_ratio) * 0.2)
        
        # Venue factor
        if venue:
            venue_data = self.venue_stats.get(venue, {})
            pitch_type = venue_data.get("pitch_type", "balanced")
            
            # Adjust based on team strengths and pitch type
            if pitch_type == "batting-friendly":
                team1_factors.append((team1_data.get("batting_strength", 7.5) / 10) * 0.1)
                team2_factors.append((team2_data.get("batting_strength", 7.5) / 10) * 0.1)
            elif pitch_type == "bowling-friendly":
                team1_factors.append((team1_data.get("bowling_strength", 7.5) / 10) * 0.1)
                team2_factors.append((team2_data.get("bowling_strength", 7.5) / 10) * 0.1)
            elif pitch_type == "spin-friendly":
                # This would ideally use team's spin bowling strength
                team1_factors.append((team1_data.get("bowling_strength", 7.5) / 10) * 0.1)
                team2_factors.append((team2_data.get("bowling_strength", 7.5) / 10) * 0.1)
        
        # Calculate final probabilities
        team1_prob = sum(team1_factors) / sum(f for f in team1_factors + team2_factors) * 100
        team2_prob = 100 - team1_prob
        
        # Adjust based on confidence level
        team1_prob, team2_prob = self.adjust_prediction_confidence(
            team1_prob, team2_prob, bot_config["prediction_confidence"]
        )
        
        # Format the response
        return self.format_prediction_response(
            team1, team2, team1_prob, team2_prob, venue, bot_config["supported_team"]
        )
    
    def learn_from_interaction(self, user_id, message, response, feedback=None, chat_type="private", group_id=None):
        """Learn from user interactions to improve responses"""
        user_id = str(user_id)
        
        # Extract language preference from message
        is_telugu = self.telugu_nlp.detect_language(message)
        if is_telugu and user_id in self.user_preferences:
            self.user_preferences[user_id]['language'] = 'telugu'
            self.save_user_preferences()
        
        # Update user history with the new interaction
        self.update_user_history(user_id, message, response)
        
        # Extract and update user preferences
        self.extract_user_preferences(user_id, message)
        
        # Store the interaction in the database manager
        interaction_data = {
            'user_id': user_id,
            'message': message,
            'response': response,
            'timestamp': datetime.now().isoformat(),
            'feedback': feedback,
            'chat_type': chat_type,
            'language': 'telugu' if is_telugu else 'english'
        }
        
        # Add group_id if present
        if group_id:
            interaction_data['group_id'] = str(group_id)
        
        # Store in database
        self.db_manager.store_interaction(interaction_data)
        
        # Analyze message for learning
        if feedback:
            # If explicit feedback is provided, use it for learning
            self._learn_from_feedback(user_id, message, response, feedback)
        else:
            # Otherwise, try to infer feedback from user's response
            self._infer_learning_from_response(user_id, message, response)
    
    def is_prediction_request(self, message):
        """Check if the message is a prediction request"""
        keywords = ["predict", "prediction", "chances", "win", "outcome"]
        return any(word in message.lower() for word in keywords)

    def is_ipl_data_question(self, message):
        """Check if the message is a question about IPL data"""
        keywords = ["stats", "statistics", "record", "performance"]
        return any(word in message.lower() for word in keywords)

    def generate_prediction(self, message, entities, bot_config):
        """Generate a prediction response"""
        teams = entities.get("teams", [])
        if len(teams) >= 2:
            team1, team2 = teams[:2]
            return self.predict_match(f"{team1} vs {team2}", bot_config)
        else:
            return "Please provide two teams for a prediction."

    def generate_ipl_data_response(self, message, entities, bot_config):
        """Generate a response about IPL data"""
        teams = entities.get("teams", [])
        players = entities.get("players", [])
        if teams:
            team = teams[0]
            return f"{team} has had a strong season so far with a balanced performance in both batting and bowling departments."
        elif players:
            player = players[0]
            return f"{player} has been in excellent form this season, contributing consistently with both bat and ball."
        else:
            return "IPL statistics show some fascinating trends this season."

    def generate_conversational_response(self, user_id, message, entities, bot_config):
        """Generate a conversational response"""
        # This is a placeholder for the conversational response generation
        # In a real implementation, you would use a conversational AI model
        return "I'm not sure I understand. You can ask me about IPL teams, players, stats, or use commands like /help to see what I can do."

    def retrain_models(self):
        """Retrain AI models with new data"""
        # This is a placeholder for model retraining
        # In a real implementation, you would retrain your models with new data
        logger.info("Model retraining initiated")
        return "Model retraining has been initiated. This may take some time."
