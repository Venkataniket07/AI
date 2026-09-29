import random
from core.profile_manager import ProfileManager
from games.assist import HINT_TIP, RoundHelper
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker

WORDS = ["APPLE", "BALL", "CAT", "DOG", "ELEPHANT", "FISH", "GRAPE", "HOUSE", "IGLOO", "JUMP", "KITE", "LEMON", "MOUSE"]

def play_coding_decoding(profile: ProfileManager):
    print("\n================ CODING-DECODING ================")
    print("Analyze the pattern to decode the target word.")
    print(HINT_TIP)
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

        if cipher_type == "alpha_numeric":
            hints = [
                "Each letter is replaced by a number. Think about the alphabet (A=1, B=2, ...).",
                f"Compare the first letter of {w1} with the first number(s) of its code to find the fixed offset.",
                f"Every letter's alphabet position is increased by {offset}.",
            ]
            explanation = (f"Each letter becomes its alphabet position plus {offset} (A=1+{offset}). "
                           f"{w1} therefore encodes to {c1}, and the same rule turns {w2} into {ans}.")
        else:
            direction = "forward" if shift > 0 else "back"
            hints = [
                "The code is made of letters. Compare the letters of the example with the original word.",
                "Every letter moves the same number of places along the alphabet (wrapping Z to A).",
                f"Each letter moves {abs(shift)} place(s) {direction}.",
            ]
            explanation = (f"Each letter moves {abs(shift)} place(s) {direction} in the alphabet, so {w1} becomes {c1}. "
                           f"Applying the same shift to {w2} gives {ans}.")
        helper = RoundHelper("coding_decoding", f"If {w1} = {c1}, find {w2}.", ans, profile.db,
                             static_hints=hints, explanation=explanation)

        tracker.start_trial()

        user_ans = helper.ask("> ").upper()
        is_correct = (user_ans == ans)

        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += helper.points(20)
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            helper.offer_explanation(user_ans)
            
    print(f"\nScore: {score}")
    finish_game(profile, "coding_decoding", score, tracker, "Press Enter to return...")
