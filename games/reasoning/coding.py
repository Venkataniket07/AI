import random
import string
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

WORDS = ["APPLE", "BALL", "CAT", "DOG", "ELEPHANT", "FISH", "GRAPE", "HOUSE", "IGLOO", "JUMP", "KITE", "LEMON", "MOUSE"]

def play_coding_decoding(profile: ProfileManager):
    print("\n================ CODING-DECODING ================")
    print("Analyze the pattern to decode the target word.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score = 0
    rounds = 5
    
    for r in range(1, rounds + 1):
        cipher_type = random.choice(["alpha_numeric", "offset"])
        w1, w2 = random.sample(WORDS, 2)
        
        if cipher_type == "alpha_numeric":
            # A=1, B=2, etc. with optional offset
            offset = random.randint(0, 5)
            def encode_num(word):
                return "".join(str(ord(c) - 64 + offset) for c in word)
            
            c1 = encode_num(w1)
            ans = encode_num(w2)
        else:
            # Shift cipher
            shift = random.choice([1, 2, 3, -1, -2, -3])
            def encode_shift(word):
                res = ""
                for c in word:
                    val = ord(c) + shift
                    if val > 90: val -= 26
                    if val < 65: val += 26
                    res += chr(val)
                return res
            
            c1 = encode_shift(w1)
            ans = encode_shift(w2)
            
        print(f"\nRound {r}/{rounds}:")
        print(f"If {w1} = {c1}")
        print(f"Find: {w2} = ?")
        
        tracker.start_trial()
        
        user_ans = input("> ").strip().upper()
        is_correct = (user_ans == ans)
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 20
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            
    print(f"\nScore: {score}")
    profile.save_game_result("coding_decoding", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
