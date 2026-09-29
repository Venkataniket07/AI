import random
from core.profile_manager import ProfileManager
from games.assist import HINT_TIP, RoundHelper
from games.common import finish_game
from utils.performance_tracker import PerformanceTracker

def play_direction_sense(profile: ProfileManager):
    print("\n================ DIRECTION SENSE ================")
    print("Calculate the shortest distance from the starting point.")
    print(HINT_TIP)
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score = 0
    rounds = 5
    
    # Pre-calculated pythagorean triples for clean answers
    triples = [(3, 4, 5), (5, 12, 13), (6, 8, 10), (8, 15, 17), (9, 12, 15), (12, 16, 20)]
    
    for r in range(1, rounds + 1):
        dx_target, dy_target, ans = random.choice(triples)
        if random.choice([True, False]):
            dx_target, dy_target = dy_target, dx_target
            
        dx_target *= random.choice([1, -1])
        dy_target *= random.choice([1, -1])
        
        # Break down into 3-4 moves
        moves = []
        
        # We need to end at dx_target, dy_target.
        # Let's do random intermediate moves.
        m1_x = random.randint(0, abs(dx_target)) * (1 if dx_target > 0 else -1)
        m1_y = random.randint(0, abs(dy_target)) * (1 if dy_target > 0 else -1)
        
        if m1_x != 0:
            moves.append(("East" if m1_x > 0 else "West", abs(m1_x)))
        if m1_y != 0:
            moves.append(("North" if m1_y > 0 else "South", abs(m1_y)))
            
        rem_x = dx_target - m1_x
        rem_y = dy_target - m1_y
        
        if rem_x != 0:
            moves.append(("East" if rem_x > 0 else "West", abs(rem_x)))
        if rem_y != 0:
            moves.append(("North" if rem_y > 0 else "South", abs(rem_y)))
            
        random.shuffle(moves)
        
        name = random.choice(["John", "Alice", "Bob", "Emma", "David"])
        
        print(f"\nRound {r}/{rounds}:")
        print(f"{name} walks:")
        for direction, dist in moves:
            print(f"  {dist}m {direction}")
            
        print("\nQuestion: How far is he/she from the starting point? (in meters)")

        ew, ns = abs(dx_target), abs(dy_target)
        helper = RoundHelper(
            "direction_sense",
            f"{name} walks: " + ", ".join(f"{dist}m {direction}" for direction, dist in moves) + ". How far from the start?",
            str(ans), profile.db,
            static_hints=[
                "Add up the East and West moves (opposite directions cancel), then the North and South moves.",
                f"The net East-West distance is {ew}m and the net North-South distance is {ns}m.",
                "The two net distances are the legs of a right triangle. Use Pythagoras for the straight-line distance.",
            ],
            explanation=(f"Net East-West = {ew}m, net North-South = {ns}m. "
                         f"Distance = sqrt({ew}^2 + {ns}^2) = sqrt({ew * ew + ns * ns}) = {ans}m."),
        )
        tracker.start_trial()

        raw = helper.ask("> ")
        try:
            user_ans = int(raw)
            is_correct = (user_ans == ans)
        except ValueError:
            is_correct = False

        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += helper.points(20)
        else:
            print(f"Incorrect. The correct answer was {ans}m.")
            helper.offer_explanation(raw)
            
    print(f"\nScore: {score}")
    finish_game(profile, "direction_sense", score, tracker, "Press Enter to return...")
