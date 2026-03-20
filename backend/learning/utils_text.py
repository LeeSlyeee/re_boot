def check_answer_match(user_answer: str, correct_ans: str) -> bool:
    if str(user_answer).isdigit() and str(correct_ans).isdigit():
        return int(user_answer) == int(correct_ans)
    
    user_answer = str(user_answer).strip()
    correct_ans = str(correct_ans).strip()
    
    if user_answer == correct_ans:
        return True
    
    # 1. 특수 문자 (콜론, 마침표, 스페이스, 괄호 등)로 분리되어 시작하는지 확인
    if user_answer.startswith(f"{correct_ans}:") or        user_answer.startswith(f"{correct_ans}. ") or        user_answer.startswith(f"{correct_ans} ") or        user_answer.startswith(f"{correct_ans})") or        user_answer.startswith(f"{correct_ans}]"):
        return True
        
    # 2. 공백 제거 후 다시 한번 확인 (프론트에서 이상한 여백을 던졌을 때 방어)
    user_no_space = user_answer.replace(" ", "").replace("\n", "").replace("\t", "")
    if user_no_space.startswith(f"{correct_ans}:") or        user_no_space.startswith(f"{correct_ans}.") or        user_no_space.startswith(f"{correct_ans})") or        user_no_space.startswith(f"{correct_ans}]"):
        return True

    # 3. 만약 위에서 처리하지 못한 "특수문자 없는 무작위 문자열"이 붙어버린 경우
    # 예: 정답이 B인데, 옵션이 B입니다 인 경우
    # (단, BB처럼 정답 자체의 확장인 경우는 오답 처리해야 함)
    # 정답 옵션이 A, B, C, D 처럼 단일 문자이고 뒤에 바로 한글이 올 경우 허용
    if len(correct_ans) == 1 and correct_ans.isalpha():
         if user_answer.startswith(correct_ans) and len(user_answer) > 1:
             # B로 시작하고 그 다음 글자가 알파벳/숫자가 아닌 한글/특수문자이면 정답
             if not user_answer[1].encode().isalpha() and not user_answer[1].isdigit():
                  # 영문자나 숫자가 이어지면 오답 (예 BB, B1)
                  # 한글이나 기호가 오면 정답 (예 B입니다, B가나다)
                  return True
                  
    return False