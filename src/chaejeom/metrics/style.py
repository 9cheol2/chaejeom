# Not in any upstream prompt. Only aligns the register of user-facing reasons
# (polite "~습니다" style) and leaves the judging criteria unchanged. Needed
# because, in prompts without upstream reason examples, the model sometimes
# answers in the plain "~다" style.
REASON_STYLE = "이유와 설명은 '~습니다' 체의 존댓말로 쓰세요."
