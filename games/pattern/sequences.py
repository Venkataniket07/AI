import random
from core.profile_manager import ProfileManager
from utils.performance_tracker import PerformanceTracker

def generate_sequence(diff_level, used_seqs):
    while True:
        seq_type = random.choice(['arithmetic', 'geometric', 'fibonacci', 'squares', 'primes', 'alternating'])
        
        if seq_type == 'squares':
            start = random.randint(1, 10)
            seq = [(start+i)**2 for i in range(5)]
            ans = (start+5)**2
        elif seq_type == 'primes':
            primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]
            start = random.randint(0, len(primes) - 6)
            seq = primes[start:start+5]
            ans = primes[start+5]
        elif seq_type == 'alternating':
            start = random.randint(5, 20)
            s1, s2 = random.randint(1, 5), random.randint(-5, -1)
            seq = []
            curr = start
            for i in range(5):
                seq.append(curr)
                curr += s1 if i % 2 == 0 else s2
            ans = curr
        elif seq_type == 'arithmetic':
            start = random.randint(1, 20)
            step = random.randint(2, 10 + diff_level*2)
            seq = [start + i*step for i in range(5)]
            ans = seq[-1] + step
        elif seq_type == 'geometric':
            start = random.randint(1, 5)
            step = random.randint(2, 3 + min(diff_level, 2))
            seq = [start * (step**i) for i in range(5)]
            ans = seq[-1] * step
        else: # fibonacci
            a, b = random.randint(1, 5), random.randint(1, 5)
            seq = [a, b]
            for _ in range(3):
                seq.append(seq[-1] + seq[-2])
            ans = seq[-1] + seq[-2]
            
        seq_str = tuple(seq)
        if seq_str not in used_seqs:
            used_seqs.add(seq_str)
            return seq, ans

def play_sequence_prediction(profile: ProfileManager):
    print("\n================ SEQUENCE PREDICTION ================")
    input("Press Enter to start...")
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 5
    used = set()
    
    for r in range(1, rounds + 1):
        diff = profile.current_user.level + (streak // 2)
        seq, ans = generate_sequence(diff, used)
        
        print(f"\nRound {r}/{rounds}: {' '.join(map(str, seq))} ?")
        tracker.start_trial()
        
        try:
            user_ans = int(input("Next number: ").strip())
            is_correct = (user_ans == ans)
        except ValueError:
            is_correct = False
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 20 + streak*5
            streak += 1
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            streak = 0
            
    print(f"\nScore: {score}")
    profile.save_game_result("seq_predict", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")

def play_pattern_completion(profile: ProfileManager):
    print("\n================ PATTERN COMPLETION ================")
    input("Press Enter to start...")
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 5
    used = set()
    
    for r in range(1, rounds + 1):
        diff = profile.current_user.level + (streak // 2)
        while True:
            if diff < 3:
                start = random.randint(65, 75)
                step = random.randint(2, 4)
                seq = [chr(start + i*step) for i in range(4)]
                ans = chr(start + 4*step)
            else:
                start_l = random.randint(65, 75)
                start_n = random.randint(1, 5)
                step_l = random.randint(1, 3)
                step_n = random.randint(2, 4)
                seq = [f"{chr(start_l + i*step_l)}{start_n + i*step_n}" for i in range(4)]
                ans = f"{chr(start_l + 4*step_l)}{start_n + 4*step_n}"
                
            seq_tuple = tuple(seq)
            if seq_tuple not in used:
                used.add(seq_tuple)
                break
                
        print(f"\nRound {r}/{rounds}: {' '.join(seq)} ?")
        tracker.start_trial()
        
        user_ans = input("Next pattern: ").strip().upper()
        is_correct = (user_ans == ans)
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 20 + streak*5
            streak += 1
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            streak = 0
            
    print(f"\nScore: {score}")
    profile.save_game_result("pattern_comp", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")

def play_missing_number(profile: ProfileManager):
    print("\n================ MISSING NUMBER ================")
    input("Press Enter to start...")
    tracker = PerformanceTracker()
    score, streak = 0, 0
    rounds = 5
    used = set()
    
    for r in range(1, rounds + 1):
        diff = profile.current_user.level + (streak // 2)
        seq, ans_val = generate_sequence(diff, used)
        seq.append(ans_val)
        
        missing_idx = random.randint(1, 4)
        ans = seq[missing_idx]
        seq_str = [str(x) if i != missing_idx else "?" for i, x in enumerate(seq)]
        
        print(f"\nRound {r}/{rounds}: {' '.join(seq_str)}")
        tracker.start_trial()
        
        try:
            user_ans = int(input("Missing number: ").strip())
            is_correct = (user_ans == ans)
        except ValueError:
            is_correct = False
            
        tracker.end_trial(is_correct)
        if is_correct:
            print("Correct!")
            score += 20 + streak*5
            streak += 1
        else:
            print(f"Incorrect. The correct answer was {ans}.")
            streak = 0
            
    print(f"\nScore: {score}")
    profile.save_game_result("missing_num", score, tracker.accuracy, tracker.avg_reaction_time_ms)
    input("Press Enter to return...")
