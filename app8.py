import logging
import os
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import json
import requests
from fuzzywuzzy import process
import re
import pytz
import time
import statistics

# Initialize Flask app with session support
app = Flask(__name__)
app.secret_key = 'nba-chat2-secret-key-2025'  # Secret key for session encryption
app.permanent_session_lifetime = timedelta(minutes=30)  # Session lasts 30 minutes

# Configure logging for Render environment
logger = logging.getLogger(__name__)  # Logger for this module
LOG_FILE = 'nba_chat2_app8.log'  # Updated log file name
logging.basicConfig(
    level=logging.DEBUG,  # Log all debug and higher messages
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log format with timestamp, level, message
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(LOG_FILE, mode='a')  # Append to log file
    ]
)
logger.debug(f"Logging initialized to file: {LOG_FILE}")

# Hardcode API keys
XAI_API_KEY = 'xai-lY6JXMlP8jvE3CAgqkn2EiRlMZ444mzFQS0JLKIv4p6ZcoGGxW2Mk6EIMs72dLXylw0Kg4MLyOHGDj6c'
ODDS_API_KEY = '7217ef3eabc663d12eb65dce31a2c1c1'
BETTING_SITE_URL = 'https://www.example.com/bets'
logger.debug(f"Using XAI_API_KEY: {XAI_API_KEY[:10]}...")
logger.debug(f"Using ODDS_API_KEY: {ODDS_API_KEY[:10]}...")

# File to store popular bets
POPULAR_BETS_FILE = 'popular_bets.json'

# Team name mapping for normalizing user queries
TEAM_NAME_MAPPING = {
    "lakers": "Los Angeles Lakers",
    "lalakers": "Los Angeles Lakers",
    "lkaers": "Los Angeles Lakers",
    "knicks": "New York Knicks",
    "knicsk": "New York Knicks",
    "nicks": "New York Knicks",
    "celtics": "Boston Celtics",
    "celtcs": "Boston Celtics",
    "celics": "Boston Celtics",
    "heat": "Miami Heat",
    "miami heat": "Miami Heat",
    "heats": "Miami Heat",
    "warriors": "Golden State Warriors",
    "dubs": "Golden State Warriors",
    "rockets": "Houston Rockets",
    "thunder": "Oklahoma City Thunder",
    "grizzlies": "Memphis Grizzlies",
    "nuggets": "Denver Nuggets",
    "clippers": "LA Clippers",
    "pacers": "Indiana Pacers",
    "bucks": "Milwaukee Bucks",
    "jazz": "Utah Jazz",
    "utah jazz": "Utah Jazz",
    "jazzs": "Utah Jazz",
    "jaz": "Utah Jazz",
    "kings": "Sacramento Kings",
    "sac kings": "Sacramento Kings",
    "kngs": "Sacramento Kings",
    "pelicans": "New Orleans Pelicans",
    "new orleans pelicans": "New Orleans Pelicans",
    "pelican": "New Orleans Pelicans",
    "suns": "Phoenix Suns",
    "trail blazers": "Portland Trail Blazers",
    "trailblazers": "Portland Trail Blazers",
    "trailbalzers": "Portland Trail Blazers",
    "pistons": "Detroit Pistons",
    "timberwolves": "Minnesota Timberwolves",
    "wolves": "Minnesota Timberwolves",
    "minnesota timberwolves": "Minnesota Timberwolves",
    "magic": "Orlando Magic",
    "cavaliers": "Cleveland Cavaliers",
}

# Team ID to name mapping for API compatibility
TEAM_ID_TO_NAME = {
    1610612738: "Boston Celtics",
    1610612739: "Cleveland Cavaliers",
    1610612743: "Denver Nuggets",
    1610612744: "Golden State Warriors",
    1610612745: "Houston Rockets",
    1610612746: "LA Clippers",
    1610612747: "Los Angeles Lakers",
    1610612748: "Miami Heat",
    1610612749: "Milwaukee Bucks",
    1610612750: "Minnesota Timberwolves",
    1610612752: "New York Knicks",
    1610612753: "Orlando Magic",
    1610612754: "Indiana Pacers",
    1610612760: "Oklahoma City Thunder",
    1610612763: "Memphis Grizzlies",
    1610612765: "Detroit Pistons",
}

# Known series statuses for quick query responses (updated for May 9, 2025)
KNOWN_SERIES = {
    "Los Angeles Lakers vs Minnesota Timberwolves 2025-04-30": "Timberwolves lead 3-1",
    "Minnesota Timberwolves vs Los Angeles Lakers 2025-05-02": "Timberwolves lead 3-1",
    "Los Angeles Lakers vs Minnesota Timberwolves 2025-05-04": "Timberwolves lead 3-1",
    "Los Angeles Lakers vs Minnesota Timberwolves 2025-05-06": "Timberwolves win 4-3",
    "Miami Heat vs Cleveland Cavaliers 2025-04-28": "Cavaliers win 4-0",
    "New York Knicks vs Detroit Pistons 2025-04-24": "Knicks lead 2-1",
    "New York Knicks vs Detroit Pistons 2025-04-27": "Knicks lead 3-1",
    "Detroit Pistons vs New York Knicks 2025-04-29": "Knicks lead 3-2",
    "New York Knicks vs Detroit Pistons 2025-05-01": "Knicks win 4-2",
    "Orlando Magic vs Boston Celtics 2025-04-29": "Celtics lead 3-2",
    "LA Clippers vs Denver Nuggets 2025-04-29": "Nuggets lead 3-2",
    "Denver Nuggets vs LA Clippers 2025-05-01": "Series tied 3-3",
    "LA Clippers vs Denver Nuggets 2025-05-03": "Nuggets win 4-3",
    "Houston Rockets vs Golden State Warriors 2025-05-02": "Series tied 3-3",
    "Golden State Warriors vs Houston Rockets 2025-05-04": "Warriors win 4-3",
    "New York Knicks vs Boston Celtics 2025-05-05": "Knicks lead 2-0",
    "Indiana Pacers vs Cleveland Cavaliers 2025-05-04": "Pacers lead 2-0",
    "Golden State Warriors vs Minnesota Timberwolves 2025-05-06": "Series tied 1-1",
    "Indiana Pacers vs Milwaukee Bucks 2025-05-02": "Pacers win 4-1",
    "Boston Celtics vs Orlando Magic 2025-05-01": "Celtics win 4-1",
    "Oklahoma City Thunder vs Memphis Grizzlies 2025-05-01": "Thunder win 4-0",
    "Oklahoma City Thunder vs Denver Nuggets 2025-05-05": "Series tied 1-1",
}

# Jinja2 filter to format dates in templates
def format_date(date_str):
    if not date_str or date_str == 'N/A':
        return 'N/A'
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%B %d, %Y")
    except ValueError:
        logger.debug(f"Invalid date format: {date_str}")
        return date_str

app.jinja_env.filters['format_date'] = format_date

# Normalize team names using fuzzy matching
def normalize_team_name(query):
    if not query or not any(c.isalpha() for c in query):
        safe_query = query.encode('ascii', 'ignore').decode('ascii')
        logger.debug(f"Skipping invalid query for normalization: {safe_query}")
        return None
    words = query.lower().split()
    for word in words:
        if word in TEAM_NAME_MAPPING:
            logger.debug(f"Normalized team: {word} -> {TEAM_NAME_MAPPING[word]}")
            return TEAM_NAME_MAPPING[word]
        match = process.extractOne(word, TEAM_NAME_MAPPING.keys(), score_cutoff=90)
        if match:
            logger.debug(f"Fuzzy matched team: {word} -> {TEAM_NAME_MAPPING[match[0]]}")
            return TEAM_NAME_MAPPING[match[0]]
    logger.debug(f"No team match for query: {query}")
    return None

# Parse date from query
def parse_query_date(query):
    pdt = pytz.timezone('US/Pacific')
    current_date = datetime.now(pdt)
    query_lower = query.lower()

    if "next friday" in query_lower:
        days_until_friday = (4 - current_date.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        next_friday = current_date + timedelta(days=days_until_friday)
        return next_friday.strftime("%Y-%m-%d")
    elif "weekend" in query_lower:
        days_to_saturday = (5 - current_date.weekday()) % 7
        if days_to_saturday == 0:
            days_to_saturday = 7
        next_saturday = current_date + timedelta(days=days_to_saturday)
        return next_saturday.strftime("%Y-%m-%d")
    elif "today" in query_lower or "tonight" in query_lower:
        return current_date.strftime("%Y-%m-%d")
    return current_date.strftime("%Y-%m-%d")  # Default to current date

# Fetch betting odds from Odds API, deduplicating by game ID
def fetch_betting_odds(date_str):
    try:
        pdt = pytz.timezone('US/Pacific')
        date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=pdt)
        timestamp = int(date.timestamp())
        
        url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
        params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'us',
            'markets': 'h2h',
            'date': timestamp
        }
        logger.debug(f"Fetching odds from API for {date_str} with timestamp {timestamp}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        games = response.json()
        
        # Collect odds by unique game ID
        bets_dict = {}
        seen_game_ids = set()
        for game in games:
            game_id = game['id']
            if game_id in seen_game_ids:
                logger.debug(f"Skipping duplicate game ID: {game_id}")
                continue
            seen_game_ids.add(game_id)
            
            home_team = game['home_team']
            away_team = game['away_team']
            commence_time = game.get('commence_time', '')[:10]
            if commence_time != date_str:
                logger.debug(f"Skipping game with commence_time {commence_time} != {date_str}")
                continue
            teams = sorted([home_team, away_team])
            game_key = f"{teams[0]} vs. {teams[1]}_{commence_time}"
            bets_dict[game_key] = {}
            
            # Collect odds from all bookmakers
            for bookmaker in game.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            team = outcome['name']
                            price = outcome['price']
                            if team not in bets_dict[game_key]:
                                bets_dict[game_key][team] = []
                            bets_dict[game_key][team].append(price)
        
        # Format bets with median odds
        bets = []
        for game_key, teams in bets_dict.items():
            game_name = game_key.rsplit('_', 1)[0]
            commence_time = game_key.rsplit('_', 1)[1]
            teams_list = game_name.split(' vs. ')
            if len(teams_list) != 2:
                logger.debug(f"Skipping invalid game name: {game_name}")
                continue
            home_team, away_team = teams_list
            
            for team in teams:
                prices = bets_dict[game_key][team]
                if not prices:
                    continue
                median_price = statistics.median(prices)
                odds = f"+{int(median_price * 100)}" if median_price > 0 else f"{int(median_price * 100)}"
                bets.append({
                    'game': f"{home_team} vs. {away_team}",
                    'date': commence_time,
                    'team': team,
                    'odds': odds
                })
        
        logger.debug(f"Fetched {len(bets)} deduplicated betting odds for {date_str}: {json.dumps(bets, indent=2)}")
        return bets
    except requests.RequestException as e:
        logger.error(f"Failed to fetch betting odds for {date_str}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in fetch_betting_odds for {date_str}: {str(e)}")
        return []

# Update popular bets (called by cron job)
def update_popular_bets():
    pdt = pytz.timezone('US/Pacific')
    current_date = datetime.now(pdt).strftime("%Y-%m-%d")
    current_timestamp = datetime.now(pdt).strftime("%Y-%m-%d %H:%M:%S %Z")
    all_odds = fetch_betting_odds(current_date)
    
    if not all_odds:
        logger.warning(f"No odds available for {current_date}, using fallback")
        all_odds = [
            {
                'game': 'Indiana Pacers vs. Cleveland Cavaliers',
                'date': '2025-05-09',
                'team': 'Indiana Pacers',
                'odds': '+355'
            },
            {
                'game': 'Indiana Pacers vs. Cleveland Cavaliers',
                'date': '2025-05-09',
                'team': 'Cleveland Cavaliers',
                'odds': '-555'
            },
            {
                'game': 'Oklahoma City Thunder vs. Denver Nuggets',
                'date': '2025-05-09',
                'team': 'Oklahoma City Thunder',
                'odds': '-245'
            },
            {
                'game': 'Oklahoma City Thunder vs. Denver Nuggets',
                'date': '2025-05-09',
                'team': 'Denver Nuggets',
                'odds': '+200'
            }
        ]
    
    # Deduplicate bets
    unique_bets = {}
    for bet in all_odds:
        game_key = f"{bet['game']}_{bet['team']}_{bet['date']}"
        if game_key not in unique_bets:
            unique_bets[game_key] = bet
    popular_odds = list(unique_bets.values())
    
    # Save to JSON file
    popular_bets = {
        'last_updated': current_timestamp,
        'bets': popular_odds
    }
    try:
        with open(POPULAR_BETS_FILE, 'w') as f:
            json.dump(popular_bets, f, indent=2)
        logger.info(f"Updated popular_bets.json with {len(popular_odds)} bets at {current_timestamp}")
    except Exception as e:
        logger.error(f"Failed to save popular bets to {POPULAR_BETS_FILE}: {str(e)}")
    
    return popular_odds

# Load popular bets from file
def load_popular_bets():
    try:
        with open(POPULAR_BETS_FILE, 'r') as f:
            popular_bets = json.load(f)
        bets = popular_bets.get('bets', [])
        last_updated = popular_bets.get('last_updated', 'N/A')
        logger.debug(f"Loaded {len(bets)} bets from {POPULAR_BETS_FILE}, last updated: {last_updated}")
        return bets, last_updated
    except FileNotFoundError:
        logger.debug(f"{POPULAR_BETS_FILE} not found, initializing popular bets")
        odds = update_popular_bets()
        try:
            with open(POPULAR_BETS_FILE, 'r') as f:
                popular_bets = json.load(f)
            bets = popular_bets.get('bets', [])
            last_updated = popular_bets.get('last_updated', 'N/A')
            logger.debug(f"Initialized {len(bets)} bets, last updated: {last_updated}")
            return bets, last_updated
        except Exception as e:
            logger.error(f"Failed to read popular bets after initialization: {str(e)}")
            return odds, 'N/A'
    except Exception as e:
        logger.error(f"Error loading popular bets from {POPULAR_BETS_FILE}: {str(e)}")
        return [], 'N/A'

# Route for cron job to update popular bets
@app.route("/update_popular_bets", methods=["POST"])
def cron_update_popular_bets():
    try:
        update_popular_bets()
        logger.info("Cron job successfully updated popular bets")
        return jsonify({"status": "success", "message": "Popular bets updated"}), 200
    except Exception as e:
        logger.error(f"Error updating popular bets in cron job: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Route for rendering the main page

@app.route("/")
def index():
    try:
        pdt = pytz.timezone('US/Pacific')
        current_datetime = datetime.now(pdt).strftime("%B %d, %Y, %I:%M %p %Z")
        current_date = datetime.now(pdt).strftime("%Y-%m-%d")
        logger.debug(f"Rendering index with datetime: {current_datetime}, current_date: {current_date}")

        popular_bets, last_bets_update = load_popular_bets()
        popular_bets_formatted = []
        seen_games = set()
        seen_teams = set()
        
        # Deduplicate bets and ensure both teams
        for bet in popular_bets:
            try:
                game_key = f"{bet['game']}_{bet['team']}_{bet['date']}"
                if game_key not in seen_games and bet['team'] not in seen_teams:
                    seen_games.add(game_key)
                    seen_teams.add(bet['team'])
                    bet_info = {
                        "game": bet['game'],
                        "date": bet.get('date', 'N/A'),
                        "team": bet['team'],
                        "odds": bet['odds']
                    }
                    popular_bets_formatted.append(bet_info)
            except Exception as e:
                logger.debug(f"Skipping invalid bet data: {str(e)}, bet: {bet}")
                continue
        
        # Limit to two bets (one per team)
        final_bets = []
        game_groups = {}
        for bet in popular_bets_formatted:
            game_date = f"{bet['game']}_{bet['date']}"
            if game_date not in game_groups:
                game_groups[game_date] = []
            game_groups[game_date].append(bet)
        
        for game_date, bets in game_groups.items():
            if len(bets) >= 2:
                final_bets.extend(bets[:2])  # Take first two bets (one per team)
            else:
                final_bets.append(bets[0])

        return render_template(
            "index.html",
            popular_bets=final_bets,
            last_bets_update=last_bets_update,
            current_datetime=current_datetime,
            betting_site_url=BETTING_SITE_URL
        )
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# Route for handling chat queries
@app.route("/chat", methods=["GET", "POST"])
def chat():
    logger.debug(f"Handling request to /chat with method: {request.method}")
    if request.method == "GET":
        return jsonify({
            "message": "This endpoint requires a POST request with JSON payload {'message': 'your query'}. Example: curl -X POST -H 'Content-Type: application/json' -d '{\"message\": \"When is the next Lakers game?\"}' http://127.0.0.1:5000/chat"
        })

    data = request.get_json()
    if not data or "message" not in data:
        logger.warning("Invalid JSON payload")
        return jsonify({
            "user": "",
            "grok": "Invalid request. Please provide a JSON payload with 'message'.",
            "bets": [],
            "is_grok_search": False,
            "response_source": "none"
        }), 400

    query = data.get("message", "").lower()
    logger.debug(f"chat - Received prompt: {query}")
    user_teams = [normalize_team_name(word) for word in query.split() if normalize_team_name(word)]
    session.permanent = True
    session['query_timestamp'] = datetime.now(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d %H:%M:%S%z")
    logger.debug(f"Stored query_timestamp in session: {session['query_timestamp']}")

    try:
        grok_response, is_grok_search = search_nba_data(query, user_teams, session['query_timestamp'])
        response = {
            "user": query,
            "grok": grok_response[:600],
            "bets": get_bets(query, grok_response),
            "is_grok_search": is_grok_search,
            "response_source": "deep_search_query" if is_grok_search else "search_nba_data"
        }
        logger.debug(f"Response: {json.dumps(response, indent=2)}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error in search_nba_data: {str(e)}")
        return jsonify({
            "user": query,
            "grok": "Sorry, something went wrong. Try again later.",
            "bets": [],
            "is_grok_search": False,
            "response_source": "none"
        }), 500

# Query XAI API for detailed NBA data
def deep_search_query(query):
    XAI_API_URL = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    pdt = pytz.timezone('US/Pacific')
    current_date = datetime.now(pdt)
    current_date_str = current_date.strftime("%Y-%m-%d")
    days_until_friday = (4 - current_date.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    next_friday = current_date + timedelta(days=days_until_friday)
    next_friday_str = next_friday.strftime("%Y-%m-%d")
    prompt = (
        f"You’re an NBA stats expert. Provide concise, data-driven responses using verified 2024-25 season data from NBA.com or ESPN. "
        f"Current date: {current_date_str}. For past week queries, check games from {current_date_str} back 7 days; exclude future dates. "
        f"For future games, verify dates and times with NBA.com or ESPN in PDT, ensuring no games are missed due to playoff status. "
        f"For today's games (May 9, 2025), use available data. "
        f"For series status, provide current playoff standings (e.g., 'Team A leads 3-1') for the 2024-25 NBA playoffs. "
        f"Known series: Lakers vs. Timberwolves, ended 2025-05-06 (Timberwolves win 4-3); "
        f"Knicks vs. Celtics, Game 2 on 2025-05-07 (Knicks lead 2-0); Pacers vs. Cavaliers, Game 2 on 2025-05-06 (Pacers lead 2-0); "
        f"Thunder vs. Nuggets, Game 2 on 2025-05-07 (Series tied 1-1); Warriors vs. Timberwolves, Game 2 on 2025-05-07 (Series tied 1-1). "
        f"Past series: Heat vs. Cavaliers, ended 2025-04-28 (Cavaliers win 4-0); Clippers vs. Nuggets, ended 2025-05-03 (Nuggets win 4-3); "
        f"Knicks vs. Pistons, ended 2025-05-01 (Knicks win 4-2); Celtics vs. Magic, ended 2025-05-01 (Celtics win 4-1); "
        f"Pacers vs. Bucks, ended 2025-05-02 (Pacers win 4-1); Thunder vs. Grizzlies, ended 2025-05-01 (Thunder win 4-0); "
        f"Warriors vs. Rockets, ended 2025-05-04 (Warriors win 4-3). "
        f"For player stats (e.g., LeBron James' highest scoring game), use verified NBA data (e.g., LeBron's career-high is 61 points on 2014-03-03 vs. Charlotte). "
        f"For season scoring leaders (e.g., Knicks), use 2024-25 season data (e.g., Jalen Brunson, 28.7 PPG). "
        f"For NBA Finals predictions, use current playoff performance and betting odds (Thunder +150, Celtics +190). "
        f"For queries about 'next Friday' games, use May 9, 2025, and include: Pacers vs. Cavaliers (Game 3, 7:30 PM PDT, ESPN; Pacers lead 2-0); "
        f"Thunder vs. Nuggets (Game 3, 10:00 PM PDT, ESPN; Series tied 1-1). "
        f"For 'weekend' games, use May 10-11, 2025, and include: May 10: Knicks vs. Celtics (Game 3, 3:30 PM PDT, ABC), Timberwolves vs. Warriors (Game 3, 8:30 PM PDT, ABC); "
        f"May 11: Pacers vs. Cavaliers (Game 4, 8:00 PM PDT, TNT), Thunder vs. Nuggets (Game 4, 3:30 PM PDT, ABC). "
        f"Exclude games from other dates in the response unless explicitly requested. Max 600 chars."
    )
    payload = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": query}
        ],
        "max_tokens": 600,
        "temperature": 0.7
    }
    for attempt in range(3):
        try:
            response = requests.post(XAI_API_URL, json=payload, headers=headers, timeout=12)
            logger.debug(f"API response status: {response.status_code}, content: {response.text[:200]}")
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"].strip()[:600]
            safe_result = result.encode('ascii', 'ignore').decode('ascii')
            logger.debug(f"DeepSearch response: {safe_result}")
            return result, True
        except requests.RequestException as e:
            logger.warning(f"DeepSearch attempt {attempt + 1} failed: {str(e)}")
            if attempt < 2:
                time.sleep(3)
            else:
                logger.error(f"DeepSearch failed after 3 attempts: {str(e)}")
                if "lebron" in query.lower() and any(phrase in query.lower() for phrase in ["highest score", "high score", "most points"]):
                    return "LeBron James' highest NBA game score is 61 points, achieved on March 3, 2014, against the Charlotte Bobcats.", False
                return "No data available", False
    return "No data available", False

# Process NBA queries
def search_nba_data(query, user_teams, query_timestamp):
    logger.debug(f"user_teams: {user_teams}")
    current_date = datetime.now(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
    current_dt = datetime.strptime(current_date, "%Y-%m-%d")

    year_match = re.search(r'\b(19|20)\d{2}\b', query)
    if year_match and any(word in query.lower() for word in ["won", "champion", "finals"]):
        year = int(year_match.group())
        if year < int(current_date[:4]):
            season = f"{year-1}-{str(year)[2:]}"
            logger.debug(f"Historical query for {season}: DeepSearch")
            return deep_search_query(f"Who won the NBA Finals in the {season} season?")

    if user_teams and any(word in query.lower() for word in ["last", "next", "today", "tonight"]):
        team = user_teams[0]
        series_keys = sorted(
            [key for key in KNOWN_SERIES.keys() if team in key],
            key=lambda x: datetime.strptime(x.split()[-1], "%Y-%m-%d"),
            reverse=True
        )
        logger.debug(f"Series keys for {team}: {series_keys}")
        if "next" in query.lower():
            if team == "Los Angeles Lakers":
                series_key = "Los Angeles Lakers vs Minnesota Timberwolves 2025-05-06"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Lakers: {series_key}")
                    response = f"The Lakers were eliminated by the Timberwolves on 2025-05-06, series ended. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "New York Knicks":
                series_key = "New York Knicks vs Boston Celtics 2025-05-05"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Knicks: {series_key}")
                    response = f"New York Knicks play Boston Celtics on 2025-05-10, 3:30 PM PDT (Game 3). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Boston Celtics":
                series_key = "New York Knicks vs Boston Celtics 2025-05-05"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Celtics: {series_key}")
                    response = f"Boston Celtics play New York Knicks on 2025-05-10, 3:30 PM PDT (Game 3). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Denver Nuggets":
                series_key = "Oklahoma City Thunder vs Denver Nuggets 2025-05-05"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Nuggets: {series_key}")
                    response = f"Denver Nuggets play Oklahoma City Thunder on 2025-05-09, 10:00 PM PDT (Game 3). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Minnesota Timberwolves":
                series_key = "Golden State Warriors vs Minnesota Timberwolves 2025-05-06"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Timberwolves: {series_key}")
                    response = f"The Timberwolves’ next game is Game 3 vs. Warriors on 2025-05-10, 8:30 PM PDT. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Golden State Warriors":
                series_key = "Golden State Warriors vs Minnesota Timberwolves 2025-05-06"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Warriors: {series_key}")
                    response = f"Golden State Warriors play Minnesota Timberwolves on 2025-05-10, 8:30 PM PDT (Game 3). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Indiana Pacers":
                series_key = "Indiana Pacers vs Cleveland Cavaliers 2025-05-04"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Pacers: {series_key}")
                    response = f"Indiana Pacers play Cleveland Cavaliers on 2025-05-09, 7:30 PM PDT (Game 3). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Cleveland Cavaliers":
                series_key = "Indiana Pacers vs Cleveland Cavaliers 2025-05-04"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Cavaliers: {series_key}")
                    response = f"Cleveland Cavaliers play Indiana Pacers on 2025-05-09, 7:30 PM PDT (Game 3). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "LA Clippers":
                series_key = "LA Clippers vs Denver Nuggets 2025-05-03"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Clippers: {series_key}")
                    response = f"The Clippers were eliminated by the Denver Nuggets on 2025-05-03, series ended. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Orlando Magic":
                series_key = "Boston Celtics vs Orlando Magic 2025-05-01"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Magic: {series_key}")
                    response = f"The Orlando Magic were eliminated by the Boston Celtics on 2025-05-01, series ended. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
        if "last" in query.lower() and series_keys:
            series_key = series_keys[0]
            status = KNOWN_SERIES.get(series_key, "No data available")
            logger.debug(f"Using known series for {team}: {series_key}")
            if team == "Miami Heat":
                series_key = "Miami Heat vs Cleveland Cavaliers 2025-04-28"
                if series_key in KNOWN_SERIES:
                    response = f"Miami Heat lost to Cleveland Cavaliers on 2025-04-28, score 83-138. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "LA Clippers":
                series_key = "LA Clippers vs Denver Nuggets 2025-05-03"
                if series_key in KNOWN_SERIES:
                    response = f"LA Clippers lost to Denver Nuggets on 2025-05-03, Game 7. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "New York Knicks":
                series_key = "New York Knicks vs Boston Celtics 2025-05-05"
                if series_key in KNOWN_SERIES:
                    response = f"New York Knicks won vs. Boston Celtics on 2025-05-05, score 108-105 (OT). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Boston Celtics":
                series_key = "New York Knicks vs Boston Celtics 2025-05-05"
                if series_key in KNOWN_SERIES:
                    response = f"Boston Celtics lost to New York Knicks on 2025-05-05, score 105-108 (OT). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Denver Nuggets":
                series_key = "LA Clippers vs Denver Nuggets 2025-05-03"
                if series_key in KNOWN_SERIES:
                    response = f"Denver Nuggets won vs. LA Clippers on 2025-05-03, 120-101, Game 7. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Los Angeles Lakers":
                series_key = "Los Angeles Lakers vs Minnesota Timberwolves 2025-05-06"
                if series_key in KNOWN_SERIES:
                    response = f"The Lakers lost their last game against the Timberwolves on 2025-05-06, score 98-109, Game 7. Anthony Edwards led the Timberwolves with 30 points, and LeBron James had 27 points for the Lakers. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Golden State Warriors":
                series_key = "Golden State Warriors vs Houston Rockets 2025-05-04"
                if series_key in KNOWN_SERIES:
                    response = f"Warriors won vs. Rockets 103-89 in Game 7 on 2025-05-04, series ended. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Minnesota Timberwolves":
                series_key = "Los Angeles Lakers vs Minnesota Timberwolves 2025-05-06"
                if series_key in KNOWN_SERIES:
                    response = f"The Timberwolves won their last game against the Lakers on 2025-05-06, score 109-98, Game 7. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Indiana Pacers":
                series_key = "Indiana Pacers vs Cleveland Cavaliers 2025-05-04"
                if series_key in KNOWN_SERIES:
                    response = f"Indiana Pacers won vs. Cleveland Cavaliers on 2025-05-04, score 121-112. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Cleveland Cavaliers":
                series_key = "Indiana Pacers vs Cleveland Cavaliers 2025-05-04"
                if series_key in KNOWN_SERIES:
                    response = f"Cleveland Cavaliers lost to Indiana Pacers on 2025-05-04, score 112-121. Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Orlando Magic":
                series_key = "Boston Celtics vs Orlando Magic 2025-05-01"
                if series_key in KNOWN_SERIES:
                    response = f"Orlando Magic lost to Boston Celtics on 2025-05-01, score 89-120. Series: {KNOWN_SERIES[series_key]}."
                    return response, False

    logger.debug(f"Routing query to DeepSearch: {query}")
    grok_response, is_grok_search = deep_search_query(query)

    if user_teams:
        team = user_teams[0]
        if team in ["Los Angeles Lakers", "Miami Heat", "LA Clippers", "New York Knicks", "Boston Celtics", "Denver Nuggets", "Golden State Warriors", "Minnesota Timberwolves", "Indiana Pacers", "Cleveland Cavaliers", "Orlando Magic"]:
            if "eliminated" in grok_response.lower() or "no future games" in grok_response.lower():
                logger.warning(f"DeepSearch incorrectly reported {team} eliminated: {grok_response}")
                if team == "Los Angeles Lakers" and "next" in query.lower():
                    response = f"The Lakers were eliminated by the Timberwolves on 2025-05-06, series ended. Series: {KNOWN_SERIES.get('Los Angeles Lakers vs Minnesota Timberwolves 2025-05-06', 'Timberwolves win 4-3')}."
                    return response, False
                if team == "Miami Heat" and "last" in query.lower():
                    response = f"Miami Heat lost to Cleveland Cavaliers on 2025-04-28, score 83-138. Series: {KNOWN_SERIES.get('Miami Heat vs Cleveland Cavaliers 2025-04-28', 'Cavaliers win 4-0')}."
                    return response, False
                if team == "LA Clippers" and "last" in query.lower():
                    response = f"LA Clippers lost to Denver Nuggets on 2025-05-03, Game 7. Series: {KNOWN_SERIES.get('LA Clippers vs Denver Nuggets 2025-05-03', 'Nuggets win 4-3')}."
                    return response, False
                if team == "New York Knicks" and "next" in query.lower():
                    response = f"New York Knicks play Boston Celtics on 2025-05-10, 3:30 PM PDT (Game 3). Series: {KNOWN_SERIES.get('New York Knicks vs Boston Celtics 2025-05-05', 'Knicks lead 2-0')}."
                    return response, False
                if team == "Boston Celtics" and "last" in query.lower():
                    response = f"Boston Celtics lost to New York Knicks on 2025-05-05, score 105-108 (OT). Series: {KNOWN_SERIES.get('New York Knicks vs Boston Celtics 2025-05-05', 'Knicks lead 2-0')}."
                    return response, False
                if team == "Denver Nuggets" and "last" in query.lower():
                    response = f"Denver Nuggets won vs. LA Clippers on 2025-05-03, 120-101, Game 7. Series: {KNOWN_SERIES.get('LA Clippers vs Denver Nuggets 2025-05-03', 'Nuggets win 4-3')}."
                    return response, False
                if team == "Golden State Warriors" and "last" in query.lower():
                    response = f"Warriors won vs. Rockets 103-89 in Game 7 on 2025-05-04, series ended. Series: {KNOWN_SERIES.get('Golden State Warriors vs Houston Rockets 2025-05-04', 'Warriors win 4-3')}."
                    return response, False
                if team == "Minnesota Timberwolves" and "next" in query.lower():
                    response = f"The Timberwolves’ next game is Game 3 vs. Warriors on 2025-05-10, 8:30 PM PDT. Series: {KNOWN_SERIES.get('Golden State Warriors vs Minnesota Timberwolves 2025-05-06', 'Series tied 1-1')}."
                    return response, False
                if team == "Indiana Pacers" and "next" in query.lower():
                    response = f"Indiana Pacers play Cleveland Cavaliers on 2025-05-09, 7:30 PM PDT (Game 3). Series: {KNOWN_SERIES.get('Indiana Pacers vs Cleveland Cavaliers 2025-05-04', 'Pacers lead 2-0')}."
                    return response, False
                if team == "Cleveland Cavaliers" and "next" in query.lower():
                    response = f"Cleveland Cavaliers play Indiana Pacers on 2025-05-09, 7:30 PM PDT (Game 3). Series: {KNOWN_SERIES.get('Indiana Pacers vs Cleveland Cavaliers 2025-05-04', 'Pacers lead 2-0')}."
                    return response, False
                if team == "Orlando Magic" and "last" in query.lower():
                    response = f"Orlando Magic lost to Boston Celtics on 2025-05-01, score 89-120. Series: {KNOWN_SERIES.get('Boston Celtics vs Orlando Magic 2025-05-01', 'Celtics win 4-1')}."
                    return response, False

    return grok_response, is_grok_search

# Get betting odds for specific teams or dates
def get_game_odds(query):
    normalized_teams = [normalize_team_name(query) for query in query.split() if normalize_team_name(query)]
    query_date = parse_query_date(query)
    all_odds = fetch_betting_odds(query_date)
    logger.debug(f"Getting odds for query with teams: {normalized_teams}, date: {query_date}")
    if normalized_teams and any(word in query.lower() for word in ["game", "next", "last", "schedule", "playoffs"]):
        filtered = [game for game in all_odds if any(team in game['game'] for team in normalized_teams)]
        if filtered:
            if "next" in query.lower():
                filtered = [game for game in filtered if game['date'] >= query_date]
            elif "last" in query.lower():
                filtered = [game for game in filtered if game['date'] < query_date]
            logger.debug(f"Filtered odds for teams: {json.dumps(filtered, indent=2)}")
            return filtered[:3]
    if any(word in query.lower() for word in ["today", "tonight", "games", "playoffs", "weekend", "next friday"]):
        filtered = [game for game in all_odds]
        if filtered:
            logger.debug(f"Filtered odds for date {query_date}: {json.dumps(filtered, indent=2)}")
            return filtered[:3]
    logger.debug("No relevant odds found")
    return []

# Generate bets for query responses
def get_bets(query, grok_response):
    safe_response = (grok_response or "").encode('ascii', 'ignore').decode('ascii')
    user_teams = [normalize_team_name(word) for word in (query + " " + safe_response).split() if normalize_team_name(word)]
    odds = get_game_odds(query)
    bets = []
    for game in odds:
        try:
            bet_info = {
                "game": game['game'],
                "date": game.get('date', 'N/A'),
                "moneyline": {game['team']: game['odds']},
                "teams": game['game'].split(' vs. ')
            }
            bets.append(bet_info)
        except Exception as e:
            logger.debug(f"Skipping invalid bet data: {str(e)}, game: {game}")
            continue
    logger.debug(f"Bets generated: {json.dumps(bets, indent=2)}")
    return bets

# Run Flask app locally
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)