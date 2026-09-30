import random
from core.integrity import answer_floor_ms
from core.profile_manager import ProfileManager
from games.common import finish_game, normalize_symbol
from utils.performance_tracker import PerformanceTracker

ASCII_SHAPES = ['[]', '()', '<>', '||', 'O', '*', '#']
ASCII_ROTS = ['^', '>', 'v', '<']

def pattern_types(diff):
    """Which puzzle kinds a difficulty may draw from: easy ones first, harder ones added as it rises."""
    if diff <= 2:
        return ['rotation', 'progression']
    if diff <= 5:
        return ['rotation', 'progression', 'addition']
    return ['rotation', 'progression', 'addition', 'latin']


def generate_spatial_matrix(used, diff=1):
    while True:
        pattern_type = random.choice(pattern_types(diff))
        
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
        elif pattern_type == 'latin':
            syms = random.sample(ASCII_SHAPES, 3)
            shift = random.choice([1, 2])
            matrix = [[syms[(c + r*shift) % 3] for c in range(3)] for r in range(3)]
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
    base_diff = profile.difficulty("matrix")
    used = set()
    
    for r in range(1, rounds + 1):
        matrix, ans = generate_spatial_matrix(used, base_diff + (streak // 2))
        
        print(f"\nRound {r}/{rounds}:")
        for row in matrix:
            print("   ".join(f"{str(x):<5}" for x in row))
            
        tracker.start_trial()
        
        is_correct = normalize_symbol(input("\nMissing pattern (?): ")) == normalize_symbol(ans)
            
        tracker.end_trial(is_correct, min_plausible_ms=answer_floor_ms(str(ans)))
        if is_correct:
            print("Correct!")
            score += 25 + streak*5
            streak += 1
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            streak = 0
            
    print(f"\nScore: {score}")
    finish_game(profile, "matrix", score, tracker, "Press Enter to return...", difficulty=base_diff)
