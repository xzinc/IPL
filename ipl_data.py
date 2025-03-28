import os
import json
import logging
import requests
from datetime import datetime
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import kagglehub
import urllib.request

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class IPLData:
    """Class to manage IPL data from various sources"""
    
    def __init__(self, data_dir='data', use_cache=True, db_type='redis'):
        """
        Initialize IPL data manager
        
        Parameters:
        - data_dir: Directory to store cached data
        - use_cache: Whether to use cached data if available
        - db_type: Database type to use ('redis', 'mongodb', or None)
        """
        self.data_dir = data_dir
        self.use_cache = use_cache
        self.db_type = db_type
        
        # Create data directory if it doesn't exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # Initialize data structures
        self.teams_data = {}
        self.players_data = {}
        self.venues_data = {}
        self.matches_data = pd.DataFrame()
        
        # Initialize database clients
        self.redis_client = None
        self.mongo_client = None
        self.mongo_db = None
        
        if db_type == 'redis':
            self.init_redis_client()
        elif db_type == 'mongodb':
            self.init_mongo_client()
        
        # Load data from sources or cache
        self.load_data()
    
    def load_data(self):
        """Load IPL data from cache, database, or online sources"""
        data_loaded = False
        
        # Try loading from database first if configured
        if self.db_type and self.use_cache:
            logger.info(f"Attempting to load data from {self.db_type}...")
            data_loaded = self.load_from_database(self.db_type)
        
        # If database loading failed or not configured, try file cache
        if not data_loaded and self.use_cache:
            logger.info("Attempting to load data from file cache...")
            data_loaded = self.load_from_cache()
        
        # If cache loading failed or cache not used, load from sources
        if not data_loaded:
            logger.info("Loading data from online sources...")
            self.load_from_sources()
            self.process_data()
            
            # Save to cache and database
            self.save_to_cache()
            if self.db_type:
                self.save_to_database(self.db_type)
        
        # If no data loaded (all methods failed), use default data
        if not self.teams_data:
            logger.warning("Failed to load data from any source, using default data")
            self.set_default_data()
    
    def load_from_cache(self):
        """Load data from cached files if they exist and are recent"""
        cache_files = {
            'github_data': os.path.join(self.data_dir, 'github_data.csv'),
            'kaggle_data': os.path.join(self.data_dir, 'kaggle_data.csv'),
            'matches_data': os.path.join(self.data_dir, 'matches_processed.csv'),
            'teams_data': os.path.join(self.data_dir, 'teams.json'),
            'players_data': os.path.join(self.data_dir, 'players.json'),
            'venues_data': os.path.join(self.data_dir, 'venues.json')
        }
        
        # Check if all cache files exist
        if not all(os.path.exists(file) for file in cache_files.values()):
            return False
        
        # Check if cache is recent (less than 1 day old)
        cache_time = os.path.getmtime(cache_files['matches_data'])
        cache_age = (datetime.now().timestamp() - cache_time) / 3600  # in hours
        if cache_age > 24:
            logger.info(f"Cache is {cache_age:.1f} hours old, refreshing data")
            return False
        
        try:
            # Load cached data
            self.github_data = pd.read_csv(cache_files['github_data'])
            self.kaggle_data = pd.read_csv(cache_files['kaggle_data'])
            self.matches_data = pd.read_csv(cache_files['matches_data'])
            
            with open(cache_files['teams_data'], 'r') as f:
                self.teams_data = json.load(f)
            
            with open(cache_files['players_data'], 'r') as f:
                self.players_data = json.load(f)
            
            with open(cache_files['venues_data'], 'r') as f:
                self.venues_data = json.load(f)
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading from cache: {e}")
            return False
    
    def load_from_sources(self):
        """Load data from GitHub and Kaggle sources"""
        # Load GitHub data
        github_url = "https://raw.githubusercontent.com/12345k/IPL-Dataset/master/IPL/data.csv"
        try:
            self.github_data = pd.read_csv(github_url)
            logger.info(f"Loaded GitHub data: {len(self.github_data)} rows")
        except Exception as e:
            logger.error(f"Error loading GitHub data: {e}")
            # Create empty DataFrame with expected columns
            self.github_data = pd.DataFrame(columns=['id', 'season', 'city', 'date', 'team1', 'team2', 'toss_winner', 'toss_decision', 'result', 'winner'])
        
        # Load Kaggle data
        try:
            kaggle_path = kagglehub.dataset_download("patrickb1912/ipl-complete-dataset-20082020")
            logger.info(f"Downloaded Kaggle data to: {kaggle_path}")
            
            # Find the matches.csv file in the downloaded directory
            matches_file = None
            for root, dirs, files in os.walk(kaggle_path):
                for file in files:
                    if file.lower() == 'matches.csv':
                        matches_file = os.path.join(root, file)
                        break
            
            if matches_file:
                self.kaggle_data = pd.read_csv(matches_file)
                logger.info(f"Loaded Kaggle matches data: {len(self.kaggle_data)} rows")
            else:
                logger.error("Could not find matches.csv in Kaggle dataset")
                self.kaggle_data = pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error loading Kaggle data: {e}")
            self.kaggle_data = pd.DataFrame()
    
    def process_data(self):
        """Process and merge datasets to create unified data structures"""
        # Process matches data
        if not self.github_data.empty and not self.kaggle_data.empty:
            # Merge datasets, preferring Kaggle data where there's overlap
            # This is a simplified approach - in a real implementation, you'd do more sophisticated merging
            self.matches_data = pd.concat([self.github_data, self.kaggle_data]).drop_duplicates(subset=['id'], keep='last')
        elif not self.github_data.empty:
            self.matches_data = self.github_data
        elif not self.kaggle_data.empty:
            self.matches_data = self.kaggle_data
        else:
            # If both sources failed, create an empty DataFrame
            self.matches_data = pd.DataFrame()
        
        # Extract teams data
        self.extract_teams_data()
        
        # Extract players data
        self.extract_players_data()
        
        # Extract venues data
        self.extract_venues_data()
    
    def extract_teams_data(self):
        """Extract team information from matches data"""
        if self.matches_data.empty:
            self.teams_data = self.get_default_teams()
            return
        
        # Get unique team names
        team_names = set()
        if 'team1' in self.matches_data.columns:
            team_names.update(self.matches_data['team1'].dropna().unique())
        if 'team2' in self.matches_data.columns:
            team_names.update(self.matches_data['team2'].dropna().unique())
        
        # Create team data structure
        self.teams_data = {}
        for team in team_names:
            if pd.isna(team) or team == '':
                continue
                
            team_matches = self.matches_data[(self.matches_data['team1'] == team) | (self.matches_data['team2'] == team)]
            team_wins = self.matches_data[self.matches_data['winner'] == team]
            
            self.teams_data[team] = {
                'name': team,
                'matches_played': len(team_matches),
                'wins': len(team_wins),
                'losses': len(team_matches) - len(team_wins),
                'win_percentage': round(len(team_wins) / len(team_matches) * 100, 2) if len(team_matches) > 0 else 0,
                'titles': 0,  # Would need additional data
                'captain': "Unknown",  # Would need additional data
                'home_ground': "Unknown",  # Would need additional data
                'key_players': []  # Would need additional data
            }
        
        # If no teams were found, use default data
        if not self.teams_data:
            self.teams_data = self.get_default_teams()
    
    def extract_players_data(self):
        """Extract player information from available data"""
        # In a real implementation, you would extract player data from the datasets
        # For now, we'll use default data
        self.players_data = self.get_default_players()
    
    def extract_venues_data(self):
        """Extract venue information from matches data"""
        if self.matches_data.empty or 'venue' not in self.matches_data.columns:
            self.venues_data = self.get_default_venues()
            return
        
        # Get unique venues
        venues = self.matches_data['venue'].dropna().unique()
        
        # Create venue data structure
        self.venues_data = {}
        for venue in venues:
            if pd.isna(venue) or venue == '':
                continue
                
            venue_matches = self.matches_data[self.matches_data['venue'] == venue]
            
            self.venues_data[venue] = {
                'name': venue,
                'city': venue_matches['city'].iloc[0] if 'city' in venue_matches.columns and not venue_matches['city'].empty else "Unknown",
                'matches_hosted': len(venue_matches),
                'avg_first_innings_score': 165,  # Would need ball-by-ball data
                'avg_second_innings_score': 155,  # Would need ball-by-ball data
                'highest_score': 220,  # Would need ball-by-ball data
                'lowest_score': 80,  # Would need ball-by-ball data
                'pitch_type': "balanced"  # Would need additional data
            }
        
        # If no venues were found, use default data
        if not self.venues_data:
            self.venues_data = self.get_default_venues()
    
    def save_to_cache(self):
        """Save processed data to cache files"""
        try:
            # Save DataFrames
            if not self.github_data.empty:
                self.github_data.to_csv(os.path.join(self.data_dir, 'github_data.csv'), index=False)
            
            if not self.kaggle_data.empty:
                self.kaggle_data.to_csv(os.path.join(self.data_dir, 'kaggle_data.csv'), index=False)
            
            if not self.matches_data.empty:
                self.matches_data.to_csv(os.path.join(self.data_dir, 'matches_processed.csv'), index=False)
            
            # Save JSON data
            with open(os.path.join(self.data_dir, 'teams.json'), 'w') as f:
                json.dump(self.teams_data, f, indent=4)
            
            with open(os.path.join(self.data_dir, 'players.json'), 'w') as f:
                json.dump(self.players_data, f, indent=4)
            
            with open(os.path.join(self.data_dir, 'venues.json'), 'w') as f:
                json.dump(self.venues_data, f, indent=4)
            
            logger.info("Saved all data to cache")
        
        except Exception as e:
            logger.error(f"Error saving data to cache: {e}")
    
    def initialize_default_data(self):
        """Initialize data with default values if loading fails"""
        self.teams_data = self.get_default_teams()
        self.players_data = self.get_default_players()
        self.venues_data = self.get_default_venues()
    
    def get_default_teams(self):
        """Return default team data"""
        return {
            "Mumbai Indians": {
                "name": "Mumbai Indians",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 5,
                "captain": "Rohit Sharma",
                "home_ground": "Wankhede Stadium",
                "key_players": ["Rohit Sharma", "Hardik Pandya", "Kieron Pollard"]
            },
            "Chennai Super Kings": {
                "name": "Chennai Super Kings",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 5,
                "captain": "MS Dhoni",
                "home_ground": "M. A. Chidambaram Stadium",
                "key_players": ["MS Dhoni", "Suresh Raina", "Ravindra Jadeja"]
            },
            "Royal Challengers Bangalore": {
                "name": "Royal Challengers Bangalore",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 0,
                "captain": "Faf du Plessis",
                "home_ground": "M. Chinnaswamy Stadium",
                "key_players": ["Faf du Plessis", "Virat Kohli", "AB de Villiers"]
            },
            "Kolkata Knight Riders": {
                "name": "Kolkata Knight Riders",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 2,
                "captain": "Shreyas Iyer",
                "home_ground": "Eden Gardens",
                "key_players": ["Shreyas Iyer", "Andre Russell", "Sunil Narine"]
            },
            "Delhi Capitals": {
                "name": "Delhi Capitals",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 0,
                "captain": "Rishabh Pant",
                "home_ground": "Arun Jaitley Stadium",
                "key_players": ["Rishabh Pant", "Shreyas Iyer", "Prithvi Shaw"]
            },
            "Punjab Kings": {
                "name": "Punjab Kings",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 0,
                "captain": "Mayank Agarwal",
                "home_ground": "PCA Stadium",
                "key_players": ["Mayank Agarwal", "KL Rahul", "Chris Gayle"]
            },
            "Rajasthan Royals": {
                "name": "Rajasthan Royals",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 1,
                "captain": "Sanju Samson",
                "home_ground": "Sawai Mansingh Stadium",
                "key_players": ["Sanju Samson", "Ben Stokes", "Jofra Archer"]
            },
            "Sunrisers Hyderabad": {
                "name": "Sunrisers Hyderabad",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 1,
                "captain": "Kane Williamson",
                "home_ground": "Rajiv Gandhi International Cricket Stadium",
                "key_players": ["Kane Williamson", "David Warner", "Jonny Bairstow"]
            },
            "Gujarat Titans": {
                "name": "Gujarat Titans",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 1,
                "captain": "Hardik Pandya",
                "home_ground": "Narendra Modi Stadium",
                "key_players": ["Hardik Pandya", "Rashid Khan", "Shubman Gill"]
            },
            "Lucknow Super Giants": {
                "name": "Lucknow Super Giants",
                "matches_played": 0,
                "wins": 0,
                "losses": 0,
                "win_percentage": 0,
                "titles": 0,
                "captain": "KL Rahul",
                "home_ground": "BRSABV Ekana Cricket Stadium",
                "key_players": ["KL Rahul", "Quinton de Kock", "Marcus Stoinis"]
            }
        }
    
    def get_default_players(self):
        """Return default player data"""
        return {
            "Virat Kohli": {
                "name": "Virat Kohli",
                "team": "Royal Challengers Bangalore",
                "role": "Batsman",
                "batting_style": "Right-handed",
                "bowling_style": "Right-arm medium",
                "nationality": "Indian",
                "stats": {
                    "matches": 223,
                    "runs": 6624,
                    "average": 36.2,
                    "strike_rate": 129.2,
                    "fifties": 44,
                    "hundreds": 5
                }
            },
            "MS Dhoni": {
                "name": "MS Dhoni",
                "team": "Chennai Super Kings",
                "role": "Wicket-keeper Batsman",
                "batting_style": "Right-handed",
                "bowling_style": "Right-arm medium",
                "nationality": "Indian",
                "stats": {
                    "matches": 220,
                    "runs": 4746,
                    "average": 39.2,
                    "strike_rate": 135.8,
                    "fifties": 23,
                    "hundreds": 0
                }
            },
            "Rohit Sharma": {
                "name": "Rohit Sharma",
                "team": "Mumbai Indians",
                "role": "Batsman",
                "batting_style": "Right-handed",
                "bowling_style": "Right-arm off break",
                "nationality": "Indian",
                "stats": {
                    "matches": 213,
                    "runs": 5611,
                    "average": 31.2,
                    "strike_rate": 130.4,
                    "fifties": 40,
                    "hundreds": 1
                }
            },
            "Jasprit Bumrah": {
                "name": "Jasprit Bumrah",
                "team": "Mumbai Indians",
                "role": "Bowler",
                "batting_style": "Right-handed",
                "bowling_style": "Right-arm fast",
                "nationality": "Indian",
                "stats": {
                    "matches": 106,
                    "wickets": 130,
                    "economy": 7.42,
                    "average": 23.03,
                    "best_bowling": "5/10"
                }
            },
            "AB de Villiers": {
                "name": "AB de Villiers",
                "team": "Royal Challengers Bangalore",
                "role": "Batsman",
                "batting_style": "Right-handed",
                "bowling_style": "Right-arm medium",
                "nationality": "South African",
                "stats": {
                    "matches": 184,
                    "runs": 5162,
                    "average": 39.7,
                    "strike_rate": 151.7,
                    "fifties": 40,
                    "hundreds": 3
                }
            }
        }
    
    def get_default_venues(self):
        """Return default venue data"""
        return {
            "Wankhede Stadium": {
                "name": "Wankhede Stadium",
                "city": "Mumbai",
                "matches_hosted": 0,
                "avg_first_innings_score": 165,
                "avg_second_innings_score": 155,
                "highest_score": 220,
                "lowest_score": 80,
                "pitch_type": "balanced"
            },
            "M. A. Chidambaram Stadium": {
                "name": "M. A. Chidambaram Stadium",
                "city": "Chennai",
                "matches_hosted": 0,
                "avg_first_innings_score": 160,
                "avg_second_innings_score": 150,
                "highest_score": 210,
                "lowest_score": 90,
                "pitch_type": "spin-friendly"
            },
            "M. Chinnaswamy Stadium": {
                "name": "M. Chinnaswamy Stadium",
                "city": "Bangalore",
                "matches_hosted": 0,
                "avg_first_innings_score": 170,
                "avg_second_innings_score": 160,
                "highest_score": 230,
                "lowest_score": 100,
                "pitch_type": "batting-friendly"
            },
            "Eden Gardens": {
                "name": "Eden Gardens",
                "city": "Kolkata",
                "matches_hosted": 0,
                "avg_first_innings_score": 155,
                "avg_second_innings_score": 145,
                "highest_score": 200,
                "lowest_score": 85,
                "pitch_type": "seam-friendly"
            },
            "Arun Jaitley Stadium": {
                "name": "Arun Jaitley Stadium",
                "city": "Delhi",
                "matches_hosted": 0,
                "avg_first_innings_score": 160,
                "avg_second_innings_score": 150,
                "highest_score": 210,
                "lowest_score": 90,
                "pitch_type": "balanced"
            },
            "PCA Stadium": {
                "name": "PCA Stadium",
                "city": "Mohali",
                "matches_hosted": 0,
                "avg_first_innings_score": 165,
                "avg_second_innings_score": 155,
                "highest_score": 220,
                "lowest_score": 80,
                "pitch_type": "batting-friendly"
            },
            "Sawai Mansingh Stadium": {
                "name": "Sawai Mansingh Stadium",
                "city": "Jaipur",
                "matches_hosted": 0,
                "avg_first_innings_score": 155,
                "avg_second_innings_score": 145,
                "highest_score": 200,
                "lowest_score": 85,
                "pitch_type": "spin-friendly"
            },
            "Rajiv Gandhi International Cricket Stadium": {
                "name": "Rajiv Gandhi International Cricket Stadium",
                "city": "Hyderabad",
                "matches_hosted": 0,
                "avg_first_innings_score": 160,
                "avg_second_innings_score": 150,
                "highest_score": 210,
                "lowest_score": 90,
                "pitch_type": "balanced"
            },
            "Narendra Modi Stadium": {
                "name": "Narendra Modi Stadium",
                "city": "Ahmedabad",
                "matches_hosted": 0,
                "avg_first_innings_score": 170,
                "avg_second_innings_score": 160,
                "highest_score": 230,
                "lowest_score": 100,
                "pitch_type": "batting-friendly"
            },
            "BRSABV Ekana Cricket Stadium": {
                "name": "BRSABV Ekana Cricket Stadium",
                "city": "Lucknow",
                "matches_hosted": 0,
                "avg_first_innings_score": 165,
                "avg_second_innings_score": 155,
                "highest_score": 220,
                "lowest_score": 80,
                "pitch_type": "balanced"
            }
        }

    def get_team_info(self, team_name):
        """Get information about a specific team"""
        try:
            # Find the team (case-insensitive)
            team_key = None
            for key in self.teams_data.keys():
                if key.lower() == team_name.lower():
                    team_key = key
                    break
            
            if not team_key:
                return f"Sorry, I couldn't find information about '{team_name}'. Please check the team name and try again."
            
            team_data = self.teams_data[team_key]
            
            # Format the response
            team_info = (
                f"🏏 **{team_key}**\n\n"
                f"**Matches Played:** {team_data['matches_played']}\n"
                f"**Wins:** {team_data['wins']}\n"
                f"**Losses:** {team_data['losses']}\n"
                f"**Win Percentage:** {team_data['win_percentage']}%\n"
                f"**Titles:** {team_data['titles']}\n"
                f"**Captain:** {team_data['captain']}\n"
                f"**Home Ground:** {team_data['home_ground']}\n\n"
            )
            
            if team_data.get('key_players'):
                team_info += "**Key Players:**\n"
                for player in team_data['key_players']:
                    team_info += f"• {player}\n"
            
            return team_info
        except Exception as e:
            logger.error(f"Error getting team info: {e}")
            return f"Sorry, I encountered an error while retrieving information about '{team_name}'."

    def get_player_info(self, player_name):
        """Get information about a specific player"""
        try:
            # Find the player (case-insensitive)
            player_key = None
            for key in self.players_data.keys():
                if key.lower() == player_name.lower():
                    player_key = key
                    break
            
            if not player_key:
                return f"Sorry, I couldn't find information about '{player_name}'. Please check the player name and try again."
            
            player_data = self.players_data[player_key]
            
            # Format the response based on player role
            player_info = (
                f"👤 **{player_key}**\n\n"
                f"**Team:** {player_data['team']}\n"
                f"**Role:** {player_data['role']}\n"
                f"**Nationality:** {player_data['nationality']}\n"
                f"**Batting Style:** {player_data['batting_style']}\n"
                f"**Bowling Style:** {player_data['bowling_style']}\n\n"
            )
            
            # Add stats based on player role
            if "Batsman" in player_data['role'] or "All-rounder" in player_data['role']:
                stats = player_data.get('stats', {})
                player_info += (
                    f"**Batting Stats:**\n"
                    f"• Matches: {stats.get('matches', 'N/A')}\n"
                    f"• Runs: {stats.get('runs', 'N/A')}\n"
                    f"• Average: {stats.get('average', 'N/A')}\n"
                    f"• Strike Rate: {stats.get('strike_rate', 'N/A')}\n"
                    f"• 50s/100s: {stats.get('fifties', 'N/A')}/{stats.get('hundreds', 'N/A')}\n"
                )
            
            if "Bowler" in player_data['role'] or "All-rounder" in player_data['role']:
                stats = player_data.get('stats', {})
                player_info += (
                    f"**Bowling Stats:**\n"
                    f"• Wickets: {stats.get('wickets', 'N/A')}\n"
                    f"• Economy: {stats.get('economy', 'N/A')}\n"
                    f"• Average: {stats.get('bowling_average', 'N/A')}\n"
                    f"• Best Bowling: {stats.get('best_bowling', 'N/A')}\n"
                )
            
            return player_info
        except Exception as e:
            logger.error(f"Error getting player info: {e}")
            return f"Sorry, I encountered an error while retrieving information about '{player_name}'."

    def get_venue_info(self, venue_name):
        """Get information about a specific venue"""
        try:
            # Find the venue (case-insensitive)
            venue_key = None
            for key in self.venues_data.keys():
                if key.lower() == venue_name.lower():
                    venue_key = key
                    break
            
            if not venue_key:
                return f"Sorry, I couldn't find information about '{venue_name}'. Please check the venue name and try again."
            
            venue_data = self.venues_data[venue_key]
            
            # Format the response
            venue_info = (
                f"🏟️ **{venue_key}**\n\n"
                f"**City:** {venue_data['city']}\n"
                f"**Matches Hosted:** {venue_data['matches_hosted']}\n"
                f"**Avg. First Innings Score:** {venue_data['avg_first_innings_score']}\n"
                f"**Avg. Second Innings Score:** {venue_data['avg_second_innings_score']}\n"
                f"**Highest Score:** {venue_data['highest_score']}\n"
                f"**Lowest Score:** {venue_data['lowest_score']}\n"
                f"**Pitch Type:** {venue_data['pitch_type']}\n"
            )
            
            return venue_info
        except Exception as e:
            logger.error(f"Error getting venue info: {e}")
            return f"Sorry, I encountered an error while retrieving information about '{venue_name}'."

    def get_schedule(self):
        """Get the upcoming IPL match schedule"""
        try:
            if self.matches_data.empty:
                return "Sorry, there are no upcoming matches scheduled at the moment."
            
            # Filter for upcoming matches (matches with future dates)
            today = datetime.now()
            upcoming_matches = self.matches_data[
                pd.to_datetime(self.matches_data['date'], errors='coerce') > today
            ].sort_values('date').head(5)
            
            if len(upcoming_matches) == 0:
                return "Sorry, there are no upcoming matches scheduled at the moment."
            
            schedule_message = "🗓️ **Upcoming IPL Matches**\n\n"
            
            for _, match in upcoming_matches.iterrows():
                match_date = pd.to_datetime(match['date'])
                formatted_date = match_date.strftime("%d %b %Y, %I:%M %p")
                
                team1 = match['team1'] if 'team1' in match else "TBD"
                team2 = match['team2'] if 'team2' in match else "TBD"
                venue = match['venue'] if 'venue' in match else "TBD"
                
                schedule_message += (
                    f"**Match:** {team1} vs {team2}\n"
                    f"📍 {venue}\n"
                    f"🕒 {formatted_date}\n\n"
                )
            
            schedule_message += "Use /subscribe to get match notifications!"
            
            return schedule_message
        except Exception as e:
            logger.error(f"Error getting schedule: {e}")
            return "Sorry, I couldn't retrieve the IPL schedule at the moment."

    def get_team_head_to_head(self, team1, team2):
        """Get head-to-head statistics between two teams"""
        try:
            # Find the team keys (case-insensitive)
            team1_key = None
            team2_key = None
            
            for key in self.teams_data.keys():
                if key.lower() == team1.lower():
                    team1_key = key
                if key.lower() == team2.lower():
                    team2_key = key
            
            if not team1_key or not team2_key:
                return f"Sorry, I couldn't find one or both teams: '{team1}' and '{team2}'. Please check the team names and try again."
            
            # Filter matches between these two teams
            if self.matches_data.empty:
                # If no match data, return a generic message
                return f"Head-to-head statistics between {team1_key} and {team2_key} are not available at the moment."
            
            h2h_matches = self.matches_data[
                ((self.matches_data['team1'] == team1_key) & (self.matches_data['team2'] == team2_key)) |
                ((self.matches_data['team1'] == team2_key) & (self.matches_data['team2'] == team1_key))
            ]
            
            total_matches = len(h2h_matches)
            
            if total_matches == 0:
                return f"No matches found between {team1_key} and {team2_key}."
            
            team1_wins = len(h2h_matches[h2h_matches['winner'] == team1_key])
            team2_wins = len(h2h_matches[h2h_matches['winner'] == team2_key])
            no_results = total_matches - team1_wins - team2_wins
            
            # Format the response
            h2h_info = (
                f"🏆 **Head-to-Head: {team1_key} vs {team2_key}**\n\n"
                f"**Total Matches:** {total_matches}\n"
                f"**{team1_key} Wins:** {team1_wins}\n"
                f"**{team2_key} Wins:** {team2_wins}\n"
                f"**No Result/Tie:** {no_results}\n\n"
            )
            
            # Add recent matches
            recent_matches = h2h_matches.sort_values('date', ascending=False).head(3)
            
            if len(recent_matches) > 0:
                h2h_info += "**Recent Encounters:**\n"
                
                for _, match in recent_matches.iterrows():
                    match_date = pd.to_datetime(match['date'])
                    formatted_date = match_date.strftime("%d %b %Y")
                    winner = match['winner'] if 'winner' in match and not pd.isna(match['winner']) else "No Result"
                    
                    h2h_info += f"• {formatted_date}: {match['team1']} vs {match['team2']} - Winner: {winner}\n"
            
            return h2h_info
        except Exception as e:
            logger.error(f"Error getting head-to-head stats: {e}")
            return f"Sorry, I encountered an error while retrieving head-to-head statistics between '{team1}' and '{team2}'."

    def get_team_performance_at_venue(self, team, venue):
        """Get a team's performance at a specific venue"""
        try:
            # Find the team and venue keys (case-insensitive)
            team_key = None
            venue_key = None
            
            for key in self.teams_data.keys():
                if key.lower() == team.lower():
                    team_key = key
                    break
            
            for key in self.venues_data.keys():
                if key.lower() == venue.lower():
                    venue_key = key
                    break
            
            if not team_key:
                return f"Sorry, I couldn't find the team: '{team}'. Please check the team name and try again."
            
            if not venue_key:
                return f"Sorry, I couldn't find the venue: '{venue}'. Please check the venue name and try again."
            
            # Filter matches for this team at this venue
            if self.matches_data.empty or 'venue' not in self.matches_data.columns:
                # If no match data, return a generic message
                return f"Performance statistics for {team_key} at {venue_key} are not available at the moment."
            
            venue_matches = self.matches_data[
                (((self.matches_data['team1'] == team_key) | (self.matches_data['team2'] == team_key)) &
                 (self.matches_data['venue'] == venue_key))
            ]
            
            total_matches = len(venue_matches)
            
            if total_matches == 0:
                return f"No matches found for {team_key} at {venue_key}."
            
            team_wins = len(venue_matches[venue_matches['winner'] == team_key])
            win_percentage = round((team_wins / total_matches) * 100, 2)
            
            # Format the response
            venue_info = (
                f"🏟️ **{team_key} at {venue_key}**\n\n"
                f"**Matches Played:** {total_matches}\n"
                f"**Matches Won:** {team_wins}\n"
                f"**Win Percentage:** {win_percentage}%\n\n"
            )
            
            # Add recent matches
            recent_matches = venue_matches.sort_values('date', ascending=False).head(3)
            
            if len(recent_matches) > 0:
                venue_info += "**Recent Matches:**\n"
                
                for _, match in recent_matches.iterrows():
                    match_date = pd.to_datetime(match['date'])
                    formatted_date = match_date.strftime("%d %b %Y")
                    opponent = match['team2'] if match['team1'] == team_key else match['team1']
                    winner = match['winner'] if 'winner' in match and not pd.isna(match['winner']) else "No Result"
                    result = "Won" if winner == team_key else ("Lost" if winner != "No Result" else "No Result")
                    
                    venue_info += f"• {formatted_date}: vs {opponent} - {result}\n"
            
            return venue_info
        except Exception as e:
            logger.error(f"Error getting team performance at venue: {e}")
            return f"Sorry, I encountered an error while retrieving performance statistics for '{team}' at '{venue}'."

    def predict_match_outcome(self, team1, team2, venue=None, bot_config=None):
        """
        Predict the outcome of a match between two teams
        
        Parameters:
        - team1: First team name
        - team2: Second team name
        - venue: Optional venue name
        - bot_config: Optional bot configuration for team support and prediction confidence
        
        Returns:
        - A formatted prediction message
        """
        try:
            # Find the team keys (case-insensitive)
            team1_key = None
            team2_key = None
            venue_key = None
            
            for key in self.teams_data.keys():
                if key.lower() == team1.lower():
                    team1_key = key
                if key.lower() == team2.lower():
                    team2_key = key
            
            if venue:
                for key in self.venues_data.keys():
                    if key.lower() == venue.lower():
                        venue_key = key
                        break
            
            if not team1_key or not team2_key:
                return f"Sorry, I couldn't find one or both teams: '{team1}' and '{team2}'. Please check the team names and try again."
            
            # Get team data
            team1_data = self.teams_data[team1_key]
            team2_data = self.teams_data[team2_key]
            
            # Calculate base win probabilities based on overall performance
            team1_win_pct = team1_data['win_percentage'] if team1_data['matches_played'] > 0 else 50
            team2_win_pct = team2_data['win_percentage'] if team2_data['matches_played'] > 0 else 50
            
            # Adjust for head-to-head record
            h2h_advantage = 0
            if not self.matches_data.empty:
                h2h_matches = self.matches_data[
                    ((self.matches_data['team1'] == team1_key) & (self.matches_data['team2'] == team2_key)) |
                    ((self.matches_data['team1'] == team2_key) & (self.matches_data['team2'] == team1_key))
                ]
                
                total_h2h = len(h2h_matches)
                if total_h2h > 0:
                    team1_h2h_wins = len(h2h_matches[h2h_matches['winner'] == team1_key])
                    team1_h2h_pct = (team1_h2h_wins / total_h2h) * 100
                    h2h_advantage = team1_h2h_pct - 50  # Positive means team1 has h2h advantage
            
            # Adjust for venue advantage if provided
            venue_advantage = 0
            if venue_key and not self.matches_data.empty and 'venue' in self.matches_data.columns:
                # Team 1 at venue
                team1_venue_matches = self.matches_data[
                    (((self.matches_data['team1'] == team1_key) | (self.matches_data['team2'] == team1_key)) &
                     (self.matches_data['venue'] == venue_key))
                ]
                
                team1_venue_total = len(team1_venue_matches)
                if team1_venue_total > 0:
                    team1_venue_wins = len(team1_venue_matches[team1_venue_matches['winner'] == team1_key])
                    team1_venue_pct = (team1_venue_wins / team1_venue_total) * 100
                else:
                    team1_venue_pct = 50
                
                # Team 2 at venue
                team2_venue_matches = self.matches_data[
                    (((self.matches_data['team1'] == team2_key) | (self.matches_data['team2'] == team2_key)) &
                     (self.matches_data['venue'] == venue_key))
                ]
                
                team2_venue_total = len(team2_venue_matches)
                if team2_venue_total > 0:
                    team2_venue_wins = len(team2_venue_matches[team2_venue_matches['winner'] == team2_key])
                    team2_venue_pct = (team2_venue_wins / team2_venue_total) * 100
                else:
                    team2_venue_pct = 50
                
                venue_advantage = team1_venue_pct - team2_venue_pct
            
            # Calculate final win probabilities
            # Base: 60% on overall record, 25% on head-to-head, 15% on venue
            team1_prob = 0.6 * team1_win_pct + 0.25 * (50 + h2h_advantage) + 0.15 * (50 + venue_advantage)
            team2_prob = 100 - team1_prob
            
            # Apply team support bias if configured
            supported_team = bot_config.get('supported_team', 'neutral') if bot_config else 'neutral'
            if supported_team != 'neutral':
                support_bias = 5  # 5% bias towards supported team
                if supported_team.lower() == team1_key.lower():
                    team1_prob += support_bias
                    team2_prob -= support_bias
                elif supported_team.lower() == team2_key.lower():
                    team1_prob -= support_bias
                    team2_prob += support_bias
                
                # Ensure probabilities are within bounds
                team1_prob = max(min(team1_prob, 95), 5)
                team2_prob = 100 - team1_prob
            
            # Adjust confidence level based on configuration
            prediction_confidence = bot_config.get('prediction_confidence', 'medium') if bot_config else 'medium'
            
            if prediction_confidence == 'low':
                # Make probabilities closer to 50-50
                team1_prob = 0.7 * team1_prob + 0.3 * 50
                team2_prob = 100 - team1_prob
            elif prediction_confidence == 'high':
                # Exaggerate the difference
                if team1_prob > 50:
                    team1_prob = team1_prob + (team1_prob - 50) * 0.3
                else:
                    team1_prob = team1_prob - (50 - team1_prob) * 0.3
                team1_prob = max(min(team1_prob, 95), 5)
                team2_prob = 100 - team1_prob
            
            # Round probabilities
            team1_prob = round(team1_prob, 1)
            team2_prob = round(team2_prob, 1)
            
            # Determine predicted winner
            predicted_winner = team1_key if team1_prob > team2_prob else team2_key
            
            # Format the prediction message
            prediction = (
                f"🔮 **Match Prediction: {team1_key} vs {team2_key}**\n\n"
            )
            
            if venue_key:
                prediction += f"**Venue:** {venue_key}\n\n"
            
            prediction += (
                f"**Win Probability:**\n"
                f"• {team1_key}: {team1_prob}%\n"
                f"• {team2_key}: {team2_prob}%\n\n"
                f"I predict that **{predicted_winner}** will win this match.\n\n"
            )
            
            # Add factors considered
            prediction += "**Factors Considered:**\n"
            prediction += f"• Overall team performance\n"
            
            if h2h_advantage != 0:
                favored_team = team1_key if h2h_advantage > 0 else team2_key
                prediction += f"• Head-to-head record (favors {favored_team})\n"
            else:
                prediction += f"• Head-to-head record\n"
            
            if venue_key:
                favored_team = team1_key if venue_advantage > 0 else team2_key
                prediction += f"• Performance at {venue_key} (favors {favored_team})\n"
            
            # Add disclaimer
            prediction += "\n*Note: This prediction is based on historical data and statistical analysis. Cricket is unpredictable, and upsets can happen!*"
            
            return prediction
        except Exception as e:
            logger.error(f"Error predicting match outcome: {e}")
            return f"Sorry, I encountered an error while predicting the outcome between '{team1}' and '{team2}'."

    def update_data_from_sources(self):
        """Update IPL data from online sources"""
        try:
            logger.info("Starting IPL data update from sources...")
            
            # Clear cache to force reload from sources
            self.github_data = None
            self.kaggle_data = None
            
            # Load from sources
            self.load_from_sources()
            
            # Process and merge datasets
            self.process_data()
            
            # Save to cache
            self.save_to_cache()
            
            return "IPL data has been updated successfully from online sources."
        except Exception as e:
            logger.error(f"Error updating IPL data: {e}")
            return "Sorry, I encountered an error while updating the IPL data from online sources."

    # Database Integration Methods
    def init_redis_client(self):
        """Initialize Redis client for data storage"""
        try:
            import redis
            from urllib.parse import urlparse
            
            # Get Redis URL from environment or use default
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            
            # Parse the URL
            parsed_url = urlparse(redis_url)
            
            # Connect to Redis
            self.redis_client = redis.Redis(
                host=parsed_url.hostname or 'localhost',
                port=parsed_url.port or 6379,
                password=parsed_url.password or None,
                db=int(parsed_url.path.replace('/', '') or 0),
                decode_responses=True  # Return strings instead of bytes
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
            return True
        except ImportError:
            logger.warning("Redis package not installed. Redis storage will not be available.")
            self.redis_client = None
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
            return False
    
    def init_mongo_client(self):
        """Initialize MongoDB client for data storage"""
        try:
            import pymongo
            
            # Get MongoDB URL from environment or use default
            mongo_url = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
            
            # Connect to MongoDB
            self.mongo_client = pymongo.MongoClient(mongo_url)
            
            # Get database (create if not exists)
            self.mongo_db = self.mongo_client['ipl_bot']
            
            # Test connection
            self.mongo_client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            return True
        except ImportError:
            logger.warning("PyMongo package not installed. MongoDB storage will not be available.")
            self.mongo_client = None
            self.mongo_db = None
            return False
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.mongo_client = None
            self.mongo_db = None
            return False
    
    def save_to_redis(self):
        """Save IPL data to Redis"""
        if not self.redis_client:
            logger.warning("Redis client not initialized. Cannot save data to Redis.")
            return False
        
        try:
            import json
            
            # Save teams data
            for team_name, team_data in self.teams_data.items():
                key = f"team:{team_name}"
                self.redis_client.set(key, json.dumps(team_data))
            
            # Save players data
            for player_name, player_data in self.players_data.items():
                key = f"player:{player_name}"
                self.redis_client.set(key, json.dumps(player_data))
            
            # Save venues data
            for venue_name, venue_data in self.venues_data.items():
                key = f"venue:{venue_name}"
                self.redis_client.set(key, json.dumps(venue_data))
            
            # Save matches data (convert DataFrame to dict for JSON serialization)
            if not self.matches_data.empty:
                matches_dict = self.matches_data.to_dict(orient='records')
                self.redis_client.set("matches", json.dumps(matches_dict))
            
            # Save last update timestamp
            self.redis_client.set("last_update", datetime.now().isoformat())
            
            logger.info("Successfully saved IPL data to Redis")
            return True
        except Exception as e:
            logger.error(f"Error saving data to Redis: {e}")
            return False
    
    def load_from_redis(self):
        """Load IPL data from Redis"""
        if not self.redis_client:
            logger.warning("Redis client not initialized. Cannot load data from Redis.")
            return False
        
        try:
            import json
            import pandas as pd
            
            # Check if data exists in Redis
            if not self.redis_client.exists("last_update"):
                logger.info("No data found in Redis")
                return False
            
            # Get last update timestamp
            last_update = self.redis_client.get("last_update")
            last_update_dt = datetime.fromisoformat(last_update)
            
            # Check if data is stale (older than 24 hours)
            if (datetime.now() - last_update_dt).total_seconds() > 86400:  # 24 hours
                logger.info("Redis data is stale (older than 24 hours)")
                return False
            
            # Load teams data
            self.teams_data = {}
            team_keys = self.redis_client.keys("team:*")
            for key in team_keys:
                team_name = key.split(":", 1)[1]
                team_data = json.loads(self.redis_client.get(key))
                self.teams_data[team_name] = team_data
            
            # Load players data
            self.players_data = {}
            player_keys = self.redis_client.keys("player:*")
            for key in player_keys:
                player_name = key.split(":", 1)[1]
                player_data = json.loads(self.redis_client.get(key))
                self.players_data[player_name] = player_data
            
            # Load venues data
            self.venues_data = {}
            venue_keys = self.redis_client.keys("venue:*")
            for key in venue_keys:
                venue_name = key.split(":", 1)[1]
                venue_data = json.loads(self.redis_client.get(key))
                self.venues_data[venue_name] = venue_data
            
            # Load matches data
            matches_json = self.redis_client.get("matches")
            if matches_json:
                matches_list = json.loads(matches_json)
                self.matches_data = pd.DataFrame(matches_list)
            else:
                self.matches_data = pd.DataFrame()
            
            logger.info("Successfully loaded IPL data from Redis")
            return True
        except Exception as e:
            logger.error(f"Error loading data from Redis: {e}")
            return False
    
    def save_to_mongodb(self):
        """Save IPL data to MongoDB"""
        if not self.mongo_db:
            logger.warning("MongoDB client not initialized. Cannot save data to MongoDB.")
            return False
        
        try:
            # Get collections
            teams_collection = self.mongo_db['teams']
            players_collection = self.mongo_db['players']
            venues_collection = self.mongo_db['venues']
            matches_collection = self.mongo_db['matches']
            metadata_collection = self.mongo_db['metadata']
            
            # Clear existing data
            teams_collection.delete_many({})
            players_collection.delete_many({})
            venues_collection.delete_many({})
            matches_collection.delete_many({})
            
            # Save teams data
            teams_docs = []
            for team_name, team_data in self.teams_data.items():
                team_doc = team_data.copy()
                team_doc['_id'] = team_name
                teams_docs.append(team_doc)
            
            if teams_docs:
                teams_collection.insert_many(teams_docs)
            
            # Save players data
            players_docs = []
            for player_name, player_data in self.players_data.items():
                player_doc = player_data.copy()
                player_doc['_id'] = player_name
                players_docs.append(player_doc)
            
            if players_docs:
                players_collection.insert_many(players_docs)
            
            # Save venues data
            venues_docs = []
            for venue_name, venue_data in self.venues_data.items():
                venue_doc = venue_data.copy()
                venue_doc['_id'] = venue_name
                venues_docs.append(venue_doc)
            
            if venues_docs:
                venues_collection.insert_many(venues_docs)
            
            # Save matches data
            if not self.matches_data.empty:
                matches_docs = self.matches_data.to_dict(orient='records')
                if matches_docs:
                    matches_collection.insert_many(matches_docs)
            
            # Save last update timestamp
            metadata_collection.update_one(
                {'_id': 'last_update'},
                {'$set': {'timestamp': datetime.now()}},
                upsert=True
            )
            
            logger.info("Successfully saved IPL data to MongoDB")
            return True
        except Exception as e:
            logger.error(f"Error saving data to MongoDB: {e}")
            return False
    
    def load_from_mongodb(self):
        """Load IPL data from MongoDB"""
        if not self.mongo_db:
            logger.warning("MongoDB client not initialized. Cannot load data from MongoDB.")
            return False
        
        try:
            import pandas as pd
            
            # Get collections
            teams_collection = self.mongo_db['teams']
            players_collection = self.mongo_db['players']
            venues_collection = self.mongo_db['venues']
            matches_collection = self.mongo_db['matches']
            metadata_collection = self.mongo_db['metadata']
            
            # Check if data exists in MongoDB
            last_update_doc = metadata_collection.find_one({'_id': 'last_update'})
            if not last_update_doc:
                logger.info("No data found in MongoDB")
                return False
            
            # Check if data is stale (older than 24 hours)
            last_update_dt = last_update_doc['timestamp']
            if (datetime.now() - last_update_dt).total_seconds() > 86400:  # 24 hours
                logger.info("MongoDB data is stale (older than 24 hours)")
                return False
            
            # Load teams data
            self.teams_data = {}
            teams_cursor = teams_collection.find({})
            for team_doc in teams_cursor:
                team_name = team_doc.pop('_id')
                self.teams_data[team_name] = team_doc
            
            # Load players data
            self.players_data = {}
            players_cursor = players_collection.find({})
            for player_doc in players_cursor:
                player_name = player_doc.pop('_id')
                self.players_data[player_name] = player_doc
            
            # Load venues data
            self.venues_data = {}
            venues_cursor = venues_collection.find({})
            for venue_doc in venues_cursor:
                venue_name = venue_doc.pop('_id')
                self.venues_data[venue_name] = venue_doc
            
            # Load matches data
            matches_cursor = matches_collection.find({})
            matches_list = list(matches_cursor)
            if matches_list:
                for match in matches_list:
                    if '_id' in match:
                        del match['_id']  # Remove MongoDB _id field
                self.matches_data = pd.DataFrame(matches_list)
            else:
                self.matches_data = pd.DataFrame()
            
            logger.info("Successfully loaded IPL data from MongoDB")
            return True
        except Exception as e:
            logger.error(f"Error loading data from MongoDB: {e}")
            return False
    
    def save_to_database(self, db_type='redis'):
        """Save IPL data to the specified database"""
        if db_type.lower() == 'redis':
            if not self.redis_client and not self.init_redis_client():
                logger.error("Failed to initialize Redis client")
                return False
            return self.save_to_redis()
        elif db_type.lower() == 'mongodb':
            if not self.mongo_db and not self.init_mongo_client():
                logger.error("Failed to initialize MongoDB client")
                return False
            return self.save_to_mongodb()
        else:
            logger.error(f"Unsupported database type: {db_type}")
            return False
    
    def load_from_database(self, db_type='redis'):
        """Load IPL data from the specified database"""
        if db_type.lower() == 'redis':
            if not self.redis_client and not self.init_redis_client():
                logger.error("Failed to initialize Redis client")
                return False
            return self.load_from_redis()
        elif db_type.lower() == 'mongodb':
            if not self.mongo_db and not self.init_mongo_client():
                logger.error("Failed to initialize MongoDB client")
                return False
            return self.load_from_mongodb()
        else:
            logger.error(f"Unsupported database type: {db_type}")
            return False

    def compare_database_performance(self):
        """
        Compare performance between Redis and MongoDB for IPL data operations
        Returns a formatted string with comparison results
        """
        try:
            import time
            
            # Initialize both database clients if not already initialized
            if not self.redis_client:
                self.init_redis_client()
            if not self.mongo_db:
                self.init_mongo_client()
            
            if not self.redis_client or not self.mongo_db:
                return "Cannot compare database performance: One or both database clients failed to initialize."
            
            results = {
                "redis": {"save": 0, "load": 0, "team_lookup": 0, "player_lookup": 0},
                "mongodb": {"save": 0, "load": 0, "team_lookup": 0, "player_lookup": 0}
            }
            
            # Test Redis performance
            logger.info("Testing Redis performance...")
            
            # Save operation
            start_time = time.time()
            self.save_to_redis()
            results["redis"]["save"] = time.time() - start_time
            
            # Load operation
            start_time = time.time()
            self.load_from_redis()
            results["redis"]["load"] = time.time() - start_time
            
            # Team lookup (10 random lookups)
            total_time = 0
            team_names = list(self.teams_data.keys())
            import random
            for _ in range(10):
                team_name = random.choice(team_names)
                start_time = time.time()
                self.redis_client.get(f"team:{team_name}")
                total_time += time.time() - start_time
            results["redis"]["team_lookup"] = total_time / 10
            
            # Player lookup (10 random lookups)
            total_time = 0
            player_names = list(self.players_data.keys())
            for _ in range(10):
                player_name = random.choice(player_names)
                start_time = time.time()
                self.redis_client.get(f"player:{player_name}")
                total_time += time.time() - start_time
            results["redis"]["player_lookup"] = total_time / 10
            
            # Test MongoDB performance
            logger.info("Testing MongoDB performance...")
            
            # Save operation
            start_time = time.time()
            self.save_to_mongodb()
            results["mongodb"]["save"] = time.time() - start_time
            
            # Load operation
            start_time = time.time()
            self.load_from_mongodb()
            results["mongodb"]["load"] = time.time() - start_time
            
            # Team lookup (10 random lookups)
            total_time = 0
            teams_collection = self.mongo_db['teams']
            for _ in range(10):
                team_name = random.choice(team_names)
                start_time = time.time()
                teams_collection.find_one({"_id": team_name})
                total_time += time.time() - start_time
            results["mongodb"]["team_lookup"] = total_time / 10
            
            # Player lookup (10 random lookups)
            total_time = 0
            players_collection = self.mongo_db['players']
            for _ in range(10):
                player_name = random.choice(player_names)
                start_time = time.time()
                players_collection.find_one({"_id": player_name})
                total_time += time.time() - start_time
            results["mongodb"]["player_lookup"] = total_time / 10
            
            # Format results
            comparison = "📊 **Database Performance Comparison: Redis vs MongoDB**\n\n"
            
            comparison += "**Operation Times (seconds):**\n\n"
            comparison += f"| Operation | Redis | MongoDB | Difference |\n"
            comparison += f"|-----------|-------|---------|------------|\n"
            
            for operation in ["save", "load", "team_lookup", "player_lookup"]:
                redis_time = results["redis"][operation]
                mongo_time = results["mongodb"][operation]
                diff_pct = ((mongo_time - redis_time) / redis_time) * 100
                
                comparison += f"| {operation.replace('_', ' ').title()} | {redis_time:.4f} | {mongo_time:.4f} | "
                if diff_pct > 0:
                    comparison += f"Redis is {abs(diff_pct):.1f}% faster |\n"
                else:
                    comparison += f"MongoDB is {abs(diff_pct):.1f}% faster |\n"
            
            # Add analysis
            comparison += "\n**Analysis:**\n\n"
            
            # Overall winner
            redis_total = sum(results["redis"].values())
            mongo_total = sum(results["mongodb"].values())
            
            if redis_total < mongo_total:
                comparison += f"- **Overall:** Redis is {((mongo_total - redis_total) / redis_total * 100):.1f}% faster than MongoDB for IPL data operations.\n"
            else:
                comparison += f"- **Overall:** MongoDB is {((redis_total - mongo_total) / mongo_total * 100):.1f}% faster than Redis for IPL data operations.\n"
            
            # Specific strengths
            comparison += "- **Redis Strengths:** "
            redis_strengths = [op.replace('_', ' ').title() for op, time in results["redis"].items() 
                              if time < results["mongodb"][op]]
            comparison += ", ".join(redis_strengths) if redis_strengths else "None"
            comparison += "\n"
            
            comparison += "- **MongoDB Strengths:** "
            mongo_strengths = [op.replace('_', ' ').title() for op, time in results["mongodb"].items() 
                              if time < results["redis"][op]]
            comparison += ", ".join(mongo_strengths) if mongo_strengths else "None"
            comparison += "\n\n"
            
            # Recommendations
            comparison += "**Recommendations:**\n\n"
            comparison += "- **Use Redis when:** You need fast real-time data access, simple key-value lookups, and minimal query complexity. Redis is ideal for caching and real-time applications where speed is critical.\n\n"
            comparison += "- **Use MongoDB when:** You need complex queries, flexible schema design, and don't require sub-millisecond response times. MongoDB is better for complex data relationships and advanced querying needs.\n\n"
            
            comparison += "*Note: This comparison is based on a simple benchmark and may vary depending on data size, server configuration, and specific use cases.*"
            
            return comparison
        except Exception as e:
            logger.error(f"Error comparing database performance: {e}")
            return f"Error comparing database performance: {str(e)}"

    def initialize_default_data(self):
        """Initialize data with default values if loading fails"""
        self.set_default_data()

    def explain_database_choice(self):
        """
        Explain the rationale behind choosing Redis over MongoDB for the IPL Telegram Bot
        Returns a formatted explanation
        """
        explanation = "# Redis vs MongoDB for IPL Telegram Bot\n\n"
        
        explanation += "## Why Redis is Preferred for this Bot\n\n"
        
        explanation += "### 1. Real-time Data Access\n"
        explanation += "The IPL Telegram Bot needs to respond quickly to user queries about teams, players, and match predictions. "
        explanation += "Redis excels at providing sub-millisecond response times for key-value lookups, which is perfect for retrieving "
        explanation += "pre-computed data like team statistics, player profiles, and venue information.\n\n"
        
        explanation += "### 2. Data Structure\n"
        explanation += "The IPL data we're working with has a relatively simple structure with well-defined entities (teams, players, venues) "
        explanation += "that can be easily serialized to JSON and stored as key-value pairs. Redis's key-value storage model is a natural fit "
        explanation += "for this type of data organization.\n\n"
        
        explanation += "### 3. Caching Layer\n"
        explanation += "Redis functions as both a primary database and a caching layer. When new data is fetched from external sources "
        explanation += "(GitHub, Kaggle), it can be processed once and cached in Redis, reducing the need for repeated processing and "
        explanation += "improving response times for subsequent requests.\n\n"
        
        explanation += "### 4. Memory Efficiency\n"
        explanation += "Redis stores all data in-memory, which provides extremely fast access. The IPL dataset is relatively small "
        explanation += "(teams, players, venues, and matches), making it feasible to keep the entire dataset in memory without "
        explanation += "significant resource constraints.\n\n"
        
        explanation += "### 5. Simplicity\n"
        explanation += "Redis has a simpler setup and maintenance overhead compared to MongoDB. For a Telegram bot that doesn't "
        explanation += "require complex queries or schema flexibility, Redis provides a more straightforward solution.\n\n"
        
        explanation += "## When MongoDB Would Be Better\n\n"
        
        explanation += "### 1. Complex Queries\n"
        explanation += "If the bot needed to perform complex queries like aggregations, joins, or text searches across the dataset, "
        explanation += "MongoDB would be more suitable with its powerful query capabilities.\n\n"
        
        explanation += "### 2. Schema Evolution\n"
        explanation += "If the data structure needed to evolve over time with new fields and relationships, MongoDB's flexible "
        explanation += "document model would make this easier to manage without requiring schema migrations.\n\n"
        
        explanation += "### 3. Large Dataset Growth\n"
        explanation += "If we expected the dataset to grow significantly (e.g., storing detailed ball-by-ball data for all matches "
        explanation += "or user interaction histories), MongoDB's disk-based storage would be more scalable than Redis's in-memory approach.\n\n"
        
        explanation += "### 4. Complex Relationships\n"
        explanation += "If we needed to model and query complex relationships between entities (e.g., player performance against specific "
        explanation += "teams at specific venues), MongoDB's document model would be better suited.\n\n"
        
        explanation += "## Conclusion\n\n"
        explanation += "For the IPL Telegram Bot's current requirements—fast access to pre-processed data with simple query patterns—Redis "
        explanation += "is the optimal choice. It provides the speed and simplicity needed for real-time interactions while being sufficient "
        explanation += "for the data complexity we're working with.\n\n"
        
        explanation += "However, we've implemented support for both Redis and MongoDB, allowing for flexibility if the bot's requirements "
        explanation += "evolve in the future. The database comparison method can help evaluate performance differences in your specific "
        explanation += "deployment environment."
        
        return explanation
