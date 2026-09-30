import random
import urllib.request
import json
import re
from core.profile_manager import ProfileManager
from games.common import finish_game
from games.language.wordlist import (
    is_valid_anagram,
    lengths_for,
    offline_words,
    pick_words,
    round_difficulties,
)
from utils.performance_tracker import PerformanceTracker

def fetch_words_from_api(length: int) -> list[dict]:
    """Words of exactly `length` letters with their frequency (per million words) and a definition."""
    pattern = "?" * length
    url = f"https://api.datamuse.com/words?sp={pattern}&md=df&max=1000"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
    except Exception:
        return []
    valid_words = []
    for item in data:
        word = item.get("word", "").lower()
        defs = item.get("defs", [])
        freq = next((float(t[2:]) for t in item.get("tags", []) if t.startswith("f:")), None)
        if word.isalpha() and word.isascii() and defs and freq is not None:
            raw_def = defs[0]
            clue = raw_def.split("\t")[-1] if "\t" in raw_def else raw_def
            if word[:4] not in clue.lower():  # a clue containing the word gives it away
                valid_words.append({"word": word, "clue": clue, "freq": freq})
    return valid_words


def is_real_word(word: str) -> bool:
    """Whether the word service knows `word` (used to accept a valid anagram the game did not pick)."""
    url = f"https://api.datamuse.com/words?sp={word}&md=f&max=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
    except Exception:
        return False
    return bool(data) and data[0].get("word", "").lower() == word

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

MIN_POOL = 5  # a game needs at least one full set of rounds' worth of words


def build_word_pool(lengths: list[int], fetch=None) -> tuple[list[dict], bool]:
    """
    Words for the given lengths: from the online word service, topped up with the built-in list when
    the service is unreachable or returns too few. Returns (pool, used_offline_words).
    """
    fetch = fetch or fetch_words_from_api
    pool = []
    for length in lengths:
        pool.extend(fetch(length))
    if len(pool) >= MIN_POOL:
        return pool, False

    seen = {item["word"] for item in pool}
    for length in lengths:
        pool.extend(w for w in offline_words(length) if w["word"] not in seen)
    return pool, True


ROUNDS = 5


def play_anagrams(profile: ProfileManager):
    print("\n================ WORD ANAGRAMS ================")
    level = profile.difficulty("anagrams")

    lengths = sorted({n for d in round_difficulties(level, ROUNDS) for n in lengths_for(d)})
    print("Fetching words dynamically...")
    word_pool, used_offline = build_word_pool(lengths)
    if used_offline:
        print("(Couldn't reach the word service - using the built-in word list.)")

    round_words = pick_words(word_pool, level, ROUNDS)
    pool_words = {item["word"] for item in word_pool}

    input("\nPress Enter to start...")

    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = len(round_words)

    for r in range(1, rounds + 1):
        current_item = round_words[r-1]
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
        print(f"Definition: {clue}")
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
                        print("💡 HINT 3: " + " | ".join(clue_parts))
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
                is_correct = is_valid_anagram(user_input, word, lambda g: g in pool_words or is_real_word(g))
                if is_correct and user_input != word:
                    print(f"(That's a valid word too - the one I had in mind was {word.upper()}.)")
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
    finish_game(profile, "anagrams", score, tracker, "\nPress Enter to return to main menu...", difficulty=level)
