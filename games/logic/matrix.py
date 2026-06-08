import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

ASCII_SHAPES = ['[]', '()', '<>', '||', 'O', '*', '#']
ASCII_ROTS = ['^', '>', 'v', '<']

def generate_spatial_matrix(used):
    while True:
        pattern_type = random.choice(['rotation', 'addition', 'progression'])
        
        if pattern_type == 'rotation':
            start = random.randint(0, 3)
            step = random.choice([1, -1])
            matrix = []
            for r in range(3):
                row = []
                for c in range(3):
                    idx = (start + (r*3 + c)*step) % 4
                    row.append(ASCII_ROTS[idx])
                matrix.append(row)
            ans = matrix[2][2]
        elif pattern_type == 'addition':
            s1, s2 = random.sample(ASCII_SHAPES, 2)
            matrix = [
                [s1, s1, s1+s1],
                [s2, s2, s2+s2],
                [s1, s2, s1+s2]
            ]
            ans = matrix[2][2]
        else:
            char = random.choice(['*', '#', '@', '+', '='])
            matrix = []
            for r in range(3):
                row = [char * (r*3 + c + 1) for c in range(3)]
                matrix.append(row)
            ans = matrix[2][2]
            
        mat_str = str(matrix)
        if mat_str not in used:
            used.add(mat_str)
            matrix[2][2] = "?"
            return matrix, ans

def play_matrix_reasoning(profile: ProfileManager):
    print("\n================ MATRIX REASONING ================")
    print("Find the missing symbol (?) in the 3x3 matrix based on the spatial pattern.")
    input("Press Enter to start...")
    
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 4
    used = set()
    
    for r in range(1, rounds + 1):
        matrix, ans = generate_spatial_matrix(used)
        
        print(f"\nRound {r}/{rounds}:")
        for row in matrix:
            print("   ".join(f"{str(x):<5}" for x in row))
            
        tracker.start_trial()
        
        user_ans = input("\nMissing pattern (?): ").strip()
        is_correct = (user_ans == ans)
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 25 + streak*5
            streak += 1
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            streak = 0
            
    print(f"\nScore: {score}")
    profile.save_game_result("matrix", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
