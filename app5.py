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

app = Flask(__name__)
app.secret_key = 'nba-chat2-secret-key-2025'
app.permanent_session_lifetime = timedelta(minutes=30)

# Configure logging for Render
logger = logging.getLogger(__name__)
LOG_FILE = 'nba_chat2_app5.log'  # Relative path, writes to /opt/render/project/src
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console logging
        logging.FileHandler(LOG_FILE, mode='a')  # File logging
    ]
)
logger.debug(f"Logging initialized to file: {LOG_FILE}")

# Hardcode keys
XAI_API_KEY = 'xai-lY6JXMlP8jvE3CAgqkn2EiRlMZ444mzFQS0JLKIv4p6ZcoGGxW2Mk6EIMs72dLXylw0Kg4MLyOHGDj6c'
ODDS_API_KEY = '0f33deae4a7f69adbf864b9bbbb395c2'
BETTING_SITE_URL = 'https://www.example.com/bets'
logger.debug(f"Using XAI_API_KEY: {XAI_API_KEY[:10]}...")
logger.debug(f"Using ODDS_API_KEY: {ODDS_API_KEY[:10]}...")

# Team name mapping
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
}

# Team ID to name mapping
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

# Known series statuses for validation
KNOWN_SERIES = {
    "Los Angeles Lakers vs Minnesota Timberwolves 2025-04-30": "Timberwolves lead 3-1",
    "Minnesota Timberwolves vs Los Angeles Lakers 2025-05-02": "Timberwolves lead 3-1",
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
    "Golden State Warriors vs Houston Rockets 2025-05-04": "Warriors lead 3-3"
}

# Define Jinja2 filter for date formatting
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

# Normalize team names
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

# Fetch betting odds from Odds API
def fetch_betting_odds(date_str):
    try:
        # Use PDT timezone for game dates
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
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        games = response.json()
        
        bets = []
        for game in games:
            home_team = game['home_team']
            away_team = game['away_team']
            commence_time = game.get('commence_time', '')[:10]
            if commence_time != date_str:  # Strict date match
                continue
            for bookmaker in game.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            price = outcome['price']
                            odds = f"+{int(price * 100)}" if price > 0 else f"{int(price * 100)}"
                            bets.append({
                                'game': f"{home_team} vs. {away_team}",
                                'date': commence_time,
                                'team': outcome['name'],
                                'odds': odds
                            })
        logger.debug(f"Fetched {len(bets)} betting odds for {date_str}")
        return bets
    except Exception as e:
        logger.error(f"Failed to fetch betting odds: {str(e)}")
        return []

# Store initial bets globally
INITIAL_BETS = []

@app.route("/")
def index():
    global INITIAL_BETS
    try:
        # Use PDT for current time
        pdt = pytz.timezone('US/Pacific')
        current_datetime = datetime.now(pdt).strftime("%B %d, %Y, %I:%M %p %Z")
        current_date = datetime.now(pdt).strftime("%Y-%m-%d")
        logger.debug(f"Rendering index with datetime: {current_datetime}, current_date: {current_date}")

        # Fetch betting odds for current date
        all_odds = fetch_betting_odds(current_date)
        if not all_odds:
            # Fallback odds for May 4, 2025
            all_odds = [
                {
                    'game': 'Cleveland Cavaliers vs. Indiana Pacers',
                    'date': '2025-05-04',
                    'team': 'Cleveland Cavaliers',
                    'odds': '-150'
                },
                {
                    'game': 'Cleveland Cavaliers vs. Indiana Pacers',
                    'date': '2025-05-04',
                    'team': 'Indiana Pacers',
                    'odds': '+130'
                },
                {
                    'game': 'Houston Rockets vs. Golden State Warriors',
                    'date': '2025-05-04',
                    'team': 'Houston Rockets',
                    'odds': '+200'
                },
                {
                    'game': 'Houston Rockets vs. Golden State Warriors',
                    'date': '2025-05-04',
                    'team': 'Golden State Warriors',
                    'odds': '-240'
                }
            ]
        filtered_odds = [game for game in all_odds if game['date'] == current_date]
        logger.debug(f"Filtered odds: {json.dumps(filtered_odds, indent=2)}")

        # Sort odds by game and team
        odds_with_min_price = []
        for game in filtered_odds:
            try:
                price = float(game['odds'].replace('+', '')) if '+' in game['odds'] else float(game['odds'])
                odds_with_min_price.append((game, price))
            except Exception as e:
                logger.debug(f"Error processing odds for game {game.get('game', 'unknown')}: {str(e)}")
                continue
        odds_with_min_price.sort(key=lambda x: x[1], reverse=True)
        odds = [game for game, _ in odds_with_min_price[:4]]
        logger.debug(f"Sorted odds: {json.dumps(odds, indent=2)}")

        INITIAL_BETS = []
        for game in odds:
            try:
                bet_info = {
                    "game": game['game'],
                    "date": game.get('date', 'N/A'),
                    "moneyline": {game['team']: game['odds']},
                    "teams": game['game'].split(' vs. ')
                }
                INITIAL_BETS.append(bet_info)
            except Exception as e:
                logger.debug(f"Skipping invalid game data: {str(e)}, game: {game}")
                continue
        logger.debug(f"Initial bets: {json.dumps(INITIAL_BETS, indent=2)}")

        return render_template(
            "index.html",
            initial_bets=INITIAL_BETS,
            current_datetime=current_datetime,
            betting_site_url=BETTING_SITE_URL
        )
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

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
            "bets": INITIAL_BETS,
            "is_grok_search": False
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
            "is_grok_search": is_grok_search
        }
        logger.debug(f"Response: {json.dumps(response, indent=2)}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error in search_nba_data: {str(e)}")
        return jsonify({
            "user": query,
            "grok": "Sorry, something went wrong. Try again later.",
            "bets": INITIAL_BETS,
            "is_grok_search": False
        }), 500

def deep_search_query(query):
    XAI_API_URL = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    current_date = datetime.now(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
    prompt = (
        f"You’re an NBA stats expert. Provide concise, data-driven responses using verified 2024-25 season data from NBA.com or ESPN. "
        f"Current date: {current_date}. For past week queries, check games from {current_date} back 7 days; exclude future dates. "
        f"For future games, verify dates and times with NBA.com or ESPN in PDT, ensuring no games are missed due to playoff status. "
        f"For today's games (May 4, 2025), include: Cavaliers vs. Pacers (Game 1, 7:00 PM PDT), Rockets vs. Warriors (Game 7, 8:30 PM PDT). "
        f"For series status, provide current playoff standings (e.g., 'Team A leads 3-1') for the 2024-25 NBA playoffs. "
        f"Known series: Lakers vs. Timberwolves, Game 5 on 2025-04-30 at 7:00 PM PDT (Timberwolves lead 3-1), Game 6 on 2025-05-02 at 10:00 AM PDT (if necessary); "
        f"Heat vs. Cavaliers, ended 2025-04-28 (Cavaliers win 4-0); Clippers vs. Nuggets, ended 2025-05-03 (Nuggets win 4-3); "
        f"Knicks vs. Pistons, ended 2025-05-01 (Knicks win 4-2); Celtics vs. Magic, Game 5 on 2025-04-29 (Celtics lead 3-2). "
        f"For player stats (e.g., LeBron James' highest scoring game), use verified NBA data (e.g., LeBron's career-high is 61 points on 2014-03-03 vs. Charlotte). "
        f"If no data is found or teams are eliminated, provide last game details or confirm elimination with series result. Max 600 chars."
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
    for attempt in range(3):  # Increased retries
        try:
            response = requests.post(XAI_API_URL, json=payload, headers=headers, timeout=10)
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
                # Fallback for LeBron high score
                if "lebron" in query.lower() and "highest score" in query.lower():
                    return "LeBron James' highest NBA game score is 61 points, achieved on March 3, 2014, against the Charlotte Bobcats.", False
                return "No data available", False
    return "No data available", False

def search_nba_data(query, user_teams, query_timestamp):
    logger.debug(f"user_teams: {user_teams}")
    current_date = datetime.now(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
    current_dt = datetime.strptime(current_date, "%Y-%m-%d")

    # Handle historical queries
    year_match = re.search(r'\b(19|20)\d{2}\b', query)
    if year_match and any(word in query.lower() for word in ["won", "champion", "finals"]):
        year = int(year_match.group())
        if year < int(current_date[:4]):
            season = f"{year-1}-{str(year)[2:]}"
            logger.debug(f"Historical query for {season}: DeepSearch")
            return deep_search_query(f"Who won the NBA Finals in the {season} season?")

    # Check known series for team-specific queries
    if user_teams and any(word in query.lower() for word in ["last", "next", "today", "tonight"]):
        team = user_teams[0]
        if "next" in query.lower():
            if team == "Los Angeles Lakers":
                target_date = "2025-05-06"  # Game 7, if necessary
                series_key = "Los Angeles Lakers vs Minnesota Timberwolves 2025-05-04"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Lakers: {series_key}")
                    response = f"Los Angeles Lakers may play Minnesota Timberwolves on 2025-05-06, TBD (Game 7, if necessary). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "New York Knicks":
                series_key = "New York Knicks vs Detroit Pistons 2025-05-01"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Knicks: {series_key}")
                    response = f"New York Knicks won the series against Detroit Pistons on 2025-05-01, 4-2. No next game scheduled."
                    return response, False
            if team == "Boston Celtics":
                target_date = "2025-05-05"  # Game 6, if necessary
                series_key = "Orlando Magic vs Boston Celtics 2025-04-29"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Celtics: {series_key}")
                    response = f"Boston Celtics may play Orlando Magic on 2025-05-05, TBD (Game 6, if necessary). Series: {KNOWN_SERIES[series_key]}."
                    return response, False
            if team == "Denver Nuggets":
                series_key = "LA Clippers vs Denver Nuggets 2025-05-03"
                if series_key in KNOWN_SERIES:
                    logger.debug(f"Using known series for Nuggets: {series_key}")
                    response = f"Denver Nuggets play Oklahoma City Thunder on 2025-05-05, Game 1, second round, TBD PDT. Series: {KNOWN_SERIES[series_key]} ended."
                    return response, False
        if "last" in query.lower():
            for series_key, status in KNOWN_SERIES.items():
                if team in series_key:
                    logger.debug(f"Using known series for {team}: {series_key}")
                    if team == "Miami Heat":
                        response = f"Miami Heat lost to Cleveland Cavaliers on 2025-04-28, score 83-138. Series: {status}."
                        return response, False
                    if team == "LA Clippers":
                        response = f"LA Clippers lost to Denver Nuggets on 2025-05-03, Game 7. Series: {status}."
                        return response, False
                    if team == "New York Knicks":
                        if "2025-04-29" in series_key:
                            response = f"New York Knicks lost to Detroit Pistons on 2025-04-29, score 103-106. Series: {status}."
                            return response, False
                        elif "2025-04-27" in series_key:
                            response = f"New York Knicks won vs. Detroit Pistons on 2025-04-27, score 94-93. Series: {status}."
                            return response, False
                        elif "2025-04-24" in series_key:
                            response = f"New York Knicks won vs. Detroit Pistons on 2025-04-24, score 118-116. Series: {status}."
                            return response, False
                    if team == "Boston Celtics":
                        response = f"Boston Celtics won vs. Orlando Magic on 2025-04-29, score 120-89. Series: {status}."
                        return response, False
                    if team == "Denver Nuggets":
                        if "2025-05-03" in series_key:
                            response = f"Denver Nuggets won vs. LA Clippers on 2025-05-03, Game 7. Series: {status}."
                            return response, False
                        elif "2025-05-01" in series_key:
                            response = f"Denver Nuggets lost to LA Clippers on 2025-05-01, score 105-111. Series: {status}."
                            return response, False
                        elif "2025-04-29" in series_key:
                            response = f"Denver Nuggets won vs. LA Clippers on 2025-04-29, score 131-115. Series: {status}."
                            return response, False

    # All other queries route to DeepSearch
    logger.debug(f"Routing query to DeepSearch: {query}")
    grok_response, is_grok_search = deep_search_query(query)

    # Validate DeepSearch response
    if user_teams and team in ["Los Angeles Lakers", "Miami Heat", "LA Clippers", "New York Knicks", "Boston Celtics", "Denver Nuggets"]:
        if "eliminated" in grok_response.lower() or "no future games" in grok_response.lower():
            logger.warning(f"DeepSearch incorrectly reported {team} eliminated: {grok_response}")
            if team == "Los Angeles Lakers" and "next" in query.lower():
                response = "Los Angeles Lakers may play Minnesota Timberwolves on 2025-05-06, TBD (Game 7, if necessary). Series: Timberwolves lead 3-1."
                return response, False
            if team == "Miami Heat" and "last" in query.lower():
                response = "Miami Heat lost to Cleveland Cavaliers on 2025-04-28, score 83-138. Series: Cavaliers win 4-0."
                return response, False
            if team == "LA Clippers" and "last" in query.lower():
                response = "LA Clippers lost to Denver Nuggets on 2025-05-03, Game 7. Series: Nuggets win 4-3."
                return response, False
            if team == "New York Knicks" and "next" in query.lower():
                response = "New York Knicks won the series against Detroit Pistons on 2025-05-01, 4-2. No next game scheduled."
                return response, False
            if team == "Boston Celtics" and "last" in query.lower():
                response = "Boston Celtics won vs. Orlando Magic on 2025-04-29, score 120-89. Series: Celtics lead 3-2."
                return response, False
            if team == "Denver Nuggets" and "last" in query.lower():
                response = "Denver Nuggets won vs. LA Clippers on 2025-05-03, Game 7. Series: Nuggets win 4-3."
                return response, False

    return grok_response, is_grok_search

def get_game_odds(query):
    normalized_teams = [normalize_team_name(query) for query in query.split() if normalize_team_name(query)]
    current_date = datetime.now(pytz.timezone('US/Pacific')).strftime("%Y-%m-%d")
    all_odds = fetch_betting_odds(current_date)
    logger.debug(f"Getting odds for query with teams: {normalized_teams}")
    if normalized_teams and any(word in query.lower() for word in ["game", "next", "last", "schedule", "playoffs"]):
        filtered = [game for game in all_odds if any(team in game['game'] for team in normalized_teams)]
        if filtered:
            if "next" in query.lower():
                filtered = [game for game in filtered if game['date'] >= current_date]
            elif "last" in query.lower():
                filtered = [game for game in filtered if game['date'] < current_date]
            logger.debug(f"Filtered odds for teams: {json.dumps(filtered, indent=2)}")
            return filtered[:3]
    if any(word in query.lower() for word in ["today", "tonight", "games", "playoffs"]):
        filtered = [game for game in all_odds if game['date'] == current_date]
        if filtered:
            logger.debug(f"Filtered odds for today: {json.dumps(filtered, indent=2)}")
            return filtered[:3]
    logger.debug("No relevant odds found")
    return []

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

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
    #nbachat25 app5.py 05/04/2025 6:24PM