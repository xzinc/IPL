# IPL AI Telegram Bot

A sophisticated Telegram bot built with Telethon that provides IPL (Indian Premier League) information, statistics, and AI-powered conversations. The bot learns from user interactions, provides match predictions, and offers admin capabilities for moderation.

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

## Features

- **AI Conversations**: Natural language processing for human-like interactions
- **IPL Data**: Comprehensive information about teams, players, and matches
- **Match Predictions**: AI-powered predictions for upcoming matches with advanced analytics
- **User Management**: Track user interactions and preferences
- **Admin Panel**: Moderation tools, broadcasting capabilities, and bot configuration
- **Learning Capability**: Improves responses based on user interactions
- **Team Support Configuration**: Admins can set the bot to support specific teams or remain neutral
- **Customizable Response Style**: Configure the bot's personality from professional to enthusiastic
- **Predictive Analytics**: Enhanced match outcome predictions based on team performance, venue statistics, and head-to-head records
- **Database Integration**: Support for both Redis and MongoDB for efficient data storage and retrieval
- **External Data Sources**: Integration with GitHub and Kaggle datasets for comprehensive IPL statistics
- **Intelligent Caching**: Automatic data refresh mechanism to ensure up-to-date information
- **Telugu Language Support**: Interact with the bot in Telugu language

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Telegram API credentials (API ID, API Hash, Bot Token)
- Heroku account (for deployment)

### Local Development Setup

1. **Clone the repository**

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   - Rename `.env.example` to `.env`
   - Fill in your Telegram API credentials:
     - `API_ID`: Your Telegram API ID
     - `API_HASH`: Your Telegram API Hash
     - `BOT_TOKEN`: Your Telegram Bot Token
     - `ADMIN_IDS`: List of admin user IDs (e.g., `123456789,987654321`)
     - `DB_TYPE`: Database type to use (`redis`, `mongodb`, or `none`)
     - `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
     - `MONGODB_URI`: MongoDB connection URI (default: `mongodb://localhost:27017/`)

4. **Run the bot**
   ```
   python main.py
   ```

### Getting Telegram API Credentials

1. Visit [my.telegram.org](https://my.telegram.org/auth) and log in
2. Go to "API development tools"
3. Create a new application
4. Note your API ID and API Hash
5. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram to get a Bot Token

### Heroku Deployment

You can deploy this bot to Heroku with one click using the button below:

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

#### Manual Heroku Deployment

1. Create a Heroku account if you don't have one
2. Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
3. Login to Heroku:
   ```bash
   heroku login
   ```
4. Create a new Heroku app:
   ```bash
   heroku create your-app-name
   ```
5. Add Heroku Redis addon:
   ```bash
   heroku addons:create heroku-redis:hobby-dev
   ```
6. Configure environment variables:
   ```bash
   heroku config:set API_ID=your_api_id
   heroku config:set API_HASH=your_api_hash
   heroku config:set BOT_TOKEN=your_bot_token
   heroku config:set ADMIN_IDS=your_user_id
   heroku config:set DB_TYPE=redis
   ```
7. Deploy the code:
   ```bash
   git push heroku main
   ```
8. Start the bot:
   ```bash
   heroku ps:scale web=1
   ```

## Bot Commands

- `/start` - Start the bot
- `/help` - Show help message
- `/stats` - Get IPL statistics
- `/team [name]` - Get info about a team
- `/player [name]` - Get info about a player
- `/schedule` - View upcoming matches
- `/predict [team1] vs [team2]` - Predict match outcome
- `/predict [team1] vs [team2] at [venue]` - Predict match with venue consideration
- `/subscribe` - Subscribe to match updates
- `/unsubscribe` - Unsubscribe from match updates
- `/h2h [team1] vs [team2]` - Get head-to-head statistics between teams
- `/venue [venue_name]` - Get information about a venue
- `/team_at_venue [team] [venue]` - Get team's performance at a specific venue
- `/telugu` - Toggle Telugu language support

### Admin Commands

- `/admin` - Access admin panel
- `/broadcast [message]` - Send message to all users
- `/config` - View current bot configuration
- `/config [key] [value]` - Update bot configuration
- `/block [user_id]` - Block a user
- `/unblock [user_id]` - Unblock a user
- `/update_data` - Update IPL database
- `/retrain` - Retrain AI model
- `/db_compare` - Compare Redis and MongoDB performance
- `/db_explain` - Get explanation of database choice

## Admin Configuration Options

Admins can configure the bot's behavior using the `/config` command:

- **supported_team**: Set which team the bot supports (e.g., "Mumbai Indians") or "neutral"
- **response_style**: Set the bot's personality ("balanced", "enthusiastic", or "professional")
- **prediction_confidence**: Set how confident predictions appear ("low", "medium", or "high")
- **learning_rate**: Control how quickly the bot adapts to new interactions ("slow", "normal", or "fast")
- **db_type**: Set the database type to use ("redis", "mongodb", or "none")

## Project Structure

- `main.py` - Entry point that initializes and runs the bot
- `bot.py` - Command handlers and event registration
- `ai_engine.py` - AI conversation and prediction engine
- `ipl_data.py` - IPL data management and database integration
- `user_manager.py` - User management and tracking
- `admin_manager.py` - Admin functionality and bot configuration
- `data/` - Directory for storing data files
- `models/` - Directory for AI models
- `telugu_nlp.py` - Telugu language processing capabilities

## Predictive Analytics

The bot uses a sophisticated prediction system that considers:

- Team performance metrics and recent form
- Head-to-head records between teams
- Venue statistics and pitch conditions
- Team strengths in batting and bowling
- Historical performance patterns

Predictions can be adjusted based on confidence level and team support settings.

## Data Management

The bot integrates with multiple data sources and database systems:

### Data Sources

- **GitHub**: IPL dataset with historical match data
- **Kaggle**: Comprehensive IPL dataset (2008-2020) with detailed statistics
- **Default Data**: Fallback data in case external sources are unavailable

### Database Options

- **Redis**: In-memory database for fast data access and simple key-value operations
- **MongoDB**: Document-oriented database for complex queries and flexible schema
- **File Cache**: Local JSON storage as a fallback option

### Data Types

The system manages the following data types:
- Teams (statistics, players, performance metrics)
- Players (personal info, statistics, team affiliations)
- Venues (location, pitch conditions, historical scores)
- Matches (results, scorecards, predictions)

### Database Selection

Redis is recommended for most deployments due to:
- Faster response times for simple data retrieval
- Simpler setup and maintenance
- Efficient memory usage for the IPL dataset size
- Built-in caching capabilities

MongoDB is better suited when:
- Complex queries are needed
- Data schema needs to evolve frequently
- Dataset grows significantly larger
- Advanced relationships between entities must be modeled

Use the `/db_compare` admin command to benchmark performance in your environment.

## Telugu Language Support

The bot includes natural language processing capabilities for Telugu, one of India's major languages:

- **Language Detection**: Automatically detects when users write in Telugu
- **Translation**: Translates Telugu queries to English for processing and English responses back to Telugu
- **IPL-Specific Vocabulary**: Handles cricket and IPL terminology in Telugu
- **User Preferences**: Users can set their language preference with the `/telugu` command

The Telugu NLP module uses a specialized dataset for cricket terminology and leverages machine learning for improved translations.

## Customization

- Modify `ipl_data.py` to update team and player information
- Adjust conversation model parameters in `ai_engine.py`
- Add new commands in `bot.py`
- Customize team performance data in `models/team_performance.json`
- Update venue statistics in `models/venue_stats.json`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [Telethon](https://github.com/LonamiWebs/Telethon) - MTProto API Telegram client library
- [Transformers](https://github.com/huggingface/transformers) - State-of-the-art NLP
- [scikit-learn](https://scikit-learn.org/) - Machine learning library
