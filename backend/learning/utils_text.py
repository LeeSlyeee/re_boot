def check_answer_match(user_answer: str, correct_ans: str) -> bool:
    if str(user_answer).isdigit() and str(correct_ans).isdigit():
        return int(user_answer) == int(correct_ans)
    
    user_answer = str(user_answer).strip()
    correct_ans = str(correct_ans).strip()
    if user_answer == correct_ans:
        return True
    if user_answer.startswith(f"{correct_ans}:") or user_answer.startswith(f"{correct_ans}. ") or user_answer.startswith(f"{correct_ans} "):
        return True
    if user_answer.startswith(correct_ans) and len(user_answer) > len(correct_ans) and user_answer[len(correct_ans)] in [':', '.', ' ', ')', ']']:
        return True
    if user_answer.replace(" ", "").startswith(f"{correct_ans}:"):
        return True
    return False