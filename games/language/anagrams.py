import random
import urllib.request
import json
import re
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

FALLBACK_WORDS = [
    {"word": "python", "clue": "A programming language named after a comedy group."},
    {"word": "database", "clue": "An organized collection of data."},
    {"word": "developer", "clue": "A person who writes computer software."},
    {"word": "algorithm", "clue": "A step-by-step procedure for solving a problem."},
    {"word": "keyboard", "clue": "An input device used to type text."}
]

def fetch_words_from_api(length: int) -> list[dict]:
    pattern = "?" * length
    url = f"https://api.datamuse.com/words?sp={pattern}&md=d&max=50"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            valid_words = []
            for item in data:
                word = item.get("word", "").lower()
                defs = item.get("defs", [])
                if word.isalpha() and defs:
                    raw_def = defs[0]
                    clue = raw_def.split("\t")[-1] if "\t" in raw_def else raw_def
                    valid_words.append({"word": word, "clue": clue})
            return valid_words
    except Exception:
        return []

def fetch_dictionary_clues(word: str) -> dict:
    """Fetches definitions, examples, synonyms, and antonyms from the Free Dictionary API."""
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if not data or not isinstance(data, list):
                return {}
            
            entry = data[0]
            meanings = entry.get("meanings", [])
            if not meanings:
                return {}
            
            part_of_speech = meanings[0].get("partOfSpeech", "")
            definitions = meanings[0].get("definitions", [])
            
            definition = ""
            example = ""
            if definitions:
                definition = definitions[0].get("definition", "")
                example = definitions[0].get("example", "")
                
            synonyms = []
            antonyms = []
            for m in meanings:
                for syn in m.get("synonyms", []):
                    if syn and syn.lower() != word.lower() and syn not in synonyms:
                        synonyms.append(syn)
                for ant in m.get("antonyms", []):
                    if ant and ant.lower() != word.lower() and ant not in antonyms:
                        antonyms.append(ant)
            
            return {
                "part_of_speech": part_of_speech,
                "definition": definition,
                "example": example,
                "synonyms": synonyms[:3],
                "antonyms": antonyms[:3]
            }
    except Exception:
        return {}

def mask_word_in_sentence(sentence: str, word: str) -> str:
    """Masks occurrences of the target word in an example sentence."""
    if not sentence:
        return ""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub("______", sentence)

def play_anagrams(profile: ProfileManager):
    print("\n================ WORD ANAGRAMS ================")
    level = profile.current_user.level
    
    if level == 1:
        lengths = [4, 5]
    elif level == 2:
        lengths = [6, 7]
    else:
        lengths = [8, 9, 10]
        
    print("Fetching words dynamically...")
    word_pool = []
    for l in lengths:
        word_pool.extend(fetch_words_from_api(l))
        
    if not word_pool:
        word_pool = FALLBACK_WORDS.copy()
        
    random.shuffle(word_pool)
    
    input("\nPress Enter to start...")
    
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = min(5, len(word_pool))
    
    for r in range(1, rounds + 1):
        current_item = word_pool[r-1]
        word = current_item["word"]
        clue = current_item["clue"]
        
        chars = list(word)
        attempts = 0
        while attempts < 10:
            random.shuffle(chars)
            scrambled = "".join(chars)
            if scrambled != word:
                break
            attempts += 1
            
        print(f"\nRound {r}/{rounds}: Scrambled word -> [ {scrambled} ]")
        tracker.start_trial()
        
        hints_used = 0
        dict_clues = None
        while True:
            user_input = input("Your guess (type 'hint' for a clue): ").strip().lower()
            
            if user_input == 'hint':
                if dict_clues is None:
                    print("Fetching dictionary clues...")
                    dict_clues = fetch_dictionary_clues(word)
                
                hints_used += 1
                if hints_used == 1:
                    pos_info = f" (Part of Speech: {dict_clues.get('part_of_speech')})" if dict_clues.get('part_of_speech') else ""
                    print(f"💡 HINT 1: The first letter is '{word[0].upper()}'{pos_info}")
                elif hints_used == 2:
                    d_clue = dict_clues.get('definition') or clue
                    print(f"💡 HINT 2: Definition -> {d_clue}")
                elif hints_used == 3:
                    syns = dict_clues.get('synonyms', [])
                    ants = dict_clues.get('antonyms', [])
                    clue_parts = []
                    if syns:
                        clue_parts.append(f"Synonyms: {', '.join(syns)}")
                    if ants:
                        clue_parts.append(f"Antonyms: {', '.join(ants)}")
                    
                    if clue_parts:
                        print(f"💡 HINT 3: " + " | ".join(clue_parts))
                    else:
                        print("💡 HINT 3: No synonyms or antonyms available. The word ends with the letter: " + f"'{word[-1].upper()}'")
                elif hints_used == 4:
                    ex = dict_clues.get('example')
                    if ex:
                        masked_ex = mask_word_in_sentence(ex, word)
                        print(f"💡 HINT 4: Example sentence -> {masked_ex}")
                    else:
                        print("💡 HINT 4: No example sentence available. The second letter is: " + f"'{word[1].upper()}'")
                else:
                    print("No more hints available!")
            else:
                is_correct = (user_input == word)
                break
                
        tracker.end_trial(is_correct)
        
        if is_correct:
            points = max(5, 15 - (hints_used * 5)) + streak*2
            print(f"Correct! (+{points} Points)")
            score += points
            streak += 1
        else:
            print(f"Incorrect. The correct word was: {word.upper()}")
            streak = 0
            
    print("\n================ GAME OVER ================")
    print(f"Total Score: {score}")
    profile.save_game_result("anagrams", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("\nPress Enter to return to main menu...")
