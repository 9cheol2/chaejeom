"""CLI strings in English (``en``) and Korean (``ko``), selected with `set_language`.

Only sentences and guidance are translated. Names that appear as keys in config and result files (model, embedding,
temperature, effort, metrics, runs, axis names, table headers, input field names) stay in English in both languages
so users can find them in the files under the same name.

Shortcuts, commands (/data, ...), framework names, model names and original metric names are never translated.
Evaluation content such as judge reasons is always Korean, independent of this table.
"""

LANGUAGES = {"en": "English", "ko": "한국어"}

_current = "en"

MESSAGES: dict[str, dict[str, str]] = {
    # Start screen and input box
    "placeholder": {"en": "Type a data file path or a command", "ko": "데이터 파일 경로나 명령을 입력하세요"},
    "header.preview": {"en": "Preview", "ko": "프리뷰"},
    "header.alpha": {"en": "Alpha", "ko": "알파"},
    "header.beta": {"en": "Beta", "ko": "베타"},
    "header.rc": {"en": "Release Candidate", "ko": "출시 후보"},
    "header.greeting": {"en": "Welcome to Chaejeom, a Korean RAG evaluator.", "ko": "안녕하세요, 한국어 RAG 평가기 채점입니다."},
    "header.tip": {"en": "Start with /data, or type /help", "ko": "/data로 데이터를 불러오거나 /help로 명령을 확인하세요"},
    "footer.hint": {"en": "/ for commands · Ctrl+C to exit", "ko": "/ 명령 목록 · Ctrl+C 종료"},
    # Axis names and results table
    "results.title": {"en": "Results (mean over samples)", "ko": "결과 (샘플 평균)"},
    "results.title_runs": {
        "en": "Results (mean over samples, mean ± std over {n} runs)",
        "ko": "결과 (샘플 평균, {n}회 반복의 평균 ± 표준편차)",
    },
    "results.custom_prompt": {
        "en": "* Measured with a custom prompt (/prompt): {metrics}",
        "ko": "* 수정본 프롬프트(/prompt)로 잰 지표: {metrics}",
    },
    "results.dropped": {
        "en": "Some samples lacked a score in at least one run and were left out of the mean ± std: {metrics}",
        "ko": "어느 회차엔가 점수가 없는 샘플은 평균 ± 표준편차 계산에서 뺐습니다: {metrics}",
    },
    "results.cost": {
        "en": "LLM calls {calls}, tokens {tokens}, cache hits {hits}",
        "ko": "LLM 호출 {calls}회, 토큰 {tokens}개, 캐시 재사용 {hits}회",
    },
    "cost.actual": {
        "en": "Estimated cost {usd} ({model}, prices as of {date}; cached responses are free)",
        "ko": "예상 비용 {usd} ({model}, {date} 단가 기준. 캐시에서 재사용한 응답은 비용 없음)",
    },
    "cost.unknown": {"en": "Estimated cost unknown: no price for {model}", "ko": "예상 비용을 알 수 없습니다: {model}의 단가가 없습니다"},
    "cost.estimate": {
        "en": "Estimated cost about {usd} ({model}, without cache; the actual cost depends on text length)",
        "ko": "예상 비용 약 {usd} ({model}, 캐시를 쓰지 않을 때 기준. 실제 비용은 글 길이에 따라 달라집니다)",
    },
    "unit.fact": {"en": "fact", "ko": "사실"},
    "unit.evasive": {"en": "evasive", "ko": "회피"},
    "unit.failed": {"en": "failed", "ko": "실패"},
    "sample.not_found": {
        "en": "Sample not found: {key} (index 0 to {last})",
        "ko": "샘플을 찾을 수 없습니다: {key} (번호는 0부터 {last}까지입니다)",
    },
    "sample.title": {"en": "Sample", "ko": "샘플"},
    "sample.none": {"en": "(none)", "ko": "(없음)"},
    "sample.first_run": {"en": "Reasons below are from run 1 of {n}.", "ko": "아래 판정 근거는 전체 {n}회 중 1회차 결과입니다."},
    "sample.runs": {"en": "(runs: {runs})", "ko": "(회차별: {runs})"},
    "sample.no_score": {"en": "none", "ko": "없음"},
    "sample.error": {"en": "Error:", "ko": "오류:"},
    "results.unscored_title": {"en": "Samples without a score", "ko": "점수 없는 샘플"},
    "results.unscored_more": {"en": "… {n} more. Type /show to find them.", "ko": "… {n}건 더 있습니다. /show로 찾아볼 수 있습니다."},
    "results.unscored_no_reason": {"en": "no score from the metric", "ko": "지표가 점수를 내지 않음"},
    # Command descriptions. Use "Select" for picking from a list, "Set" for entering a value, "Load" for files.
    "cmd./data": {"en": "Load evaluation data", "ko": "평가 데이터 불러오기"},
    "cmd./metrics": {"en": "Select metrics and runs", "ko": "평가 지표와 반복 횟수 선택"},
    "cmd./model": {"en": "Select the judge model", "ko": "평가 모델 선택"},
    "cmd./temperature": {"en": "Set the judge model temperature", "ko": "평가 모델 temperature 설정"},
    "cmd./effort": {"en": "Set the judge model reasoning effort", "ko": "평가 모델 reasoning effort 설정"},
    "cmd./embedding": {"en": "Select the embedding model", "ko": "임베딩 모델 선택"},
    "cmd./domain": {"en": "Set up domain information for the Chaejeom metrics", "ko": "채점 지표의 도메인 정보 설정"},
    "cmd./prompt": {"en": "View metric prompts, or edit the Chaejeom prompts", "ko": "지표 프롬프트 보기, 채점 프롬프트 수정"},
    "cmd./run": {"en": "Run the evaluation and save the results", "ko": "평가 실행과 결과 저장"},
    "cmd./show": {"en": "List samples by score, or show one sample's scores and reasons", "ko": "샘플을 점수순으로 보거나, 샘플 하나의 점수와 판정 근거 보기"},
    "cmd./runs": {"en": "Set the number of runs", "ko": "반복 횟수 설정"},
    "cmd./config": {"en": "Load a config file, or save the current settings", "ko": "설정 파일 불러오기, 현재 설정 저장"},
    "cmd./language": {"en": "Select the interface language", "ko": "화면 언어 선택"},
    "cmd./help": {"en": "Show all commands", "ko": "전체 명령 보기"},
    "cmd./exit": {"en": "Exit", "ko": "종료"},
    "help.usage": {"en": "Usage", "ko": "사용법"},
    "help.description": {"en": "Description", "ko": "설명"},
    "help.results": {
        "en": "Results are saved to {folder}/ as JSON and CSV, named <data file name>_<date-time>.",
        "ko": "결과는 {folder}/ 폴더에 JSON과 CSV로, <데이터 파일 이름>_<날짜-시각> 이름으로 저장됩니다.",
    },
    # Messages
    "unknown_command": {"en": "Unknown command: {command}  (type /help to see commands)", "ko": "알 수 없는 명령입니다: {command}  (/help로 명령 목록을 볼 수 있습니다)"},
    "provider_error": {
        "en": "LLM provider error: {error}\nCheck {env} in .env or your environment variables, and the model name.",
        "ko": "LLM 제공자 오류: {error}\n.env 파일이나 환경 변수의 {env} 값과 모델 이름을 확인하세요.",
    },
    "unexpected_error": {
        "en": "Something went wrong: {error}. Your data and settings are kept.",
        "ko": "예상하지 못한 오류가 났습니다: {error}. 불러온 데이터와 설정은 그대로 있습니다.",
    },
    "bare_command": {"en": "Did you mean {command}? Commands start with /.", "ko": "{command} 명령을 찾으시나요? 명령은 /로 시작합니다."},
    "exit.confirm": {"en": "Press Ctrl+C again to exit.", "ko": "종료하려면 Ctrl+C를 한 번 더 누르세요."},
    "status.custom_prompt": {"en": "custom ({metrics})", "ko": "수정본 ({metrics})"},
    "cancelled": {"en": "Cancelled.", "ko": "취소했습니다."},
    "data.ask": {"en": "Path to the data file", "ko": "데이터 파일 경로"},
    "data.hint": {
        "en": "A JSONL, JSON or CSV file. Press Tab to complete the path.",
        "ko": "JSONL, JSON, CSV 파일입니다. Tab으로 경로를 자동 완성할 수 있습니다.",
    },
    "data.not_found": {"en": "File not found: {path}", "ko": "파일을 찾을 수 없습니다: {path}"},
    "data.pick": {"en": "Select a data file in {folder}/", "ko": "{folder}/ 폴더의 데이터 파일을 고르세요"},
    "data.other": {"en": "Enter another path", "ko": "다른 경로 입력"},
    "data.loaded": {"en": "Loaded", "ko": "불러왔습니다:"},
    "data.count": {"en": "{n} samples", "ko": "샘플 {n}개"},
    "dataflow.embedding": {
        "en": "Note: the embedding model ({provider} {model}) receives answers and questions, while the judge runs on {judge}.",
        "ko": "참고: 평가 모델은 {judge}에서 돌지만, 임베딩 모델({provider} {model})로 답변과 질문이 전송됩니다.",
    },
    "dataflow.domain_model": {
        "en": "Note: this sends your text to the domain model ({provider} {model}), while the judge runs on {judge}.",
        "ko": "참고: 평가 모델은 {judge}에서 돌지만, 이 작업은 도메인 정리 모델({provider} {model})로 내용을 보냅니다.",
    },
    "compare.title": {"en": "Comparing", "ko": "비교:"},
    "compare.changed": {"en": "Samples whose score changed by 0.25 or more", "ko": "점수가 0.25 이상 바뀐 샘플"},
    "compare.no_changes": {"en": "No sample changed by 0.25 or more.", "ko": "점수가 0.25 이상 바뀐 샘플이 없습니다."},
    "compare.unmatched": {"en": "{n} samples appear in only one of the files (matched by id).", "ko": "한쪽 파일에만 있는 샘플이 {n}개입니다 (id로 맞춤)."},
    "compare.diff_dataset": {"en": "The two results were measured on different data.", "ko": "두 결과의 평가 데이터가 다릅니다."},
    "compare.diff_model": {"en": "Different {what}: {before} → {after}", "ko": "{what} 설정이 다릅니다: {before} → {after}"},
    "compare.diff_fingerprint": {
        "en": "{metric} used a different domain file or custom prompt.",
        "ko": "{metric} 지표의 도메인 정보나 수정본 프롬프트가 다릅니다.",
    },
    "compare.diff_runs": {"en": "Different number of runs: {before} → {after}", "ko": "반복 횟수가 다릅니다: {before} → {after}"},
    "compare.diff_metrics": {
        "en": "Metrics in only one file: {metrics}. Averages of axes measured with different metrics are not compared.",
        "ko": "한쪽 파일에만 있는 지표: {metrics}. 지표 구성이 다른 축의 평균은 차이를 내지 않습니다.",
    },
    "data.notice.reference_fields": {
        "en": "Ignored {detail}: Chaejeom is reference-free and evaluates with the query, contexts and answer only.",
        "ko": "{detail} 필드는 쓰지 않습니다. 채점은 레퍼런스 프리라서 정답 없이 질문, 문맥, 답변만으로 평가합니다.",
    },
    "data.notice.metadata_fields": {"en": "Moved {detail} to metadata.", "ko": "{detail} 필드는 metadata로 옮겼습니다."},
    "data.notice.cp949": {
        "en": "Read the file as CP949 (the default of Korean Excel). Saving it as CSV UTF-8 is recommended.",
        "ko": "파일을 CP949(한국어 엑셀 기본 형식)로 읽었습니다. CSV UTF-8로 저장하는 것을 권합니다.",
    },
    "data.fields": {"en": "(query {query}, contexts {contexts}, answer {answer})", "ko": "(query {query}, contexts {contexts}, answer {answer})"},
    "data.missing": {
        "en": "{metric}: {n} samples are missing required inputs and will be recorded as errors.",
        "ko": "{metric}: 필요한 입력이 없는 샘플 {n}개는 오류로 기록됩니다.",
    },
    "metrics.none": {"en": "Select at least one metric.", "ko": "지표를 하나 이상 선택하세요."},
    "metrics.unknown": {
        "en": "No metric matches {patterns}. Type /metrics to select from the grid, or run chaejeom list for metric ids.",
        "ko": "{patterns} 와 맞는 지표가 없습니다. /metrics로 격자에서 선택하거나 chaejeom list로 지표 id를 확인하세요.",
    },
    "runs.many": {"en": "{n} (mean ± std)", "ko": "{n}회 (평균 ± 표준편차)"},
    "runs.one": {"en": "1", "ko": "1회"},
    "model.select": {"en": "Select a judge model", "ko": "평가 모델을 선택하세요"},
    "model.unsupported": {"en": "Unsupported judge model: {model}\nAvailable: {models}", "ko": "지원하지 않는 평가 모델입니다: {model}\n사용할 수 있는 모델: {models}"},
    "model.set": {"en": "Judge model:", "ko": "평가 모델:"},
    "temperature.ask": {"en": "Temperature for {model}", "ko": "{model}의 temperature"},
    "temperature.hint": {"en": "Enter a number from 0 to 2. The default is 0.", "ko": "0에서 2 사이의 숫자를 입력하세요. 기본값은 0입니다."},
    "temperature.not_number": {
        "en": "{model} takes a temperature (0 to 2), not a reasoning effort.",
        "ko": "{model} 모델은 reasoning effort가 아니라 temperature(0~2)로 조절합니다.",
    },
    "temperature.range": {"en": "Temperature must be between 0 and 2.", "ko": "temperature는 0에서 2 사이로 입력하세요."},
    "temperature.reasoning_model": {
        "en": "{model} is a reasoning model and has no temperature. Use /effort instead.",
        "ko": "{model} 모델은 추론 모델이라 temperature를 쓸 수 없습니다. /effort를 사용하세요.",
    },
    "effort.ask": {"en": "Reasoning effort for {model}", "ko": "{model}의 reasoning effort"},
    "effort.hint": {"en": "Enter low, medium or high. The default is low.", "ko": "low, medium, high 중 하나를 입력하세요. 기본값은 low입니다."},
    "effort.invalid": {
        "en": "{model} is a reasoning model and takes a reasoning effort ({efforts}), not a temperature.",
        "ko": "{model} 모델은 추론 모델이라 temperature가 아니라 reasoning effort({efforts})로 조절합니다.",
    },
    "effort.not_reasoning_model": {
        "en": "{model} is not a reasoning model and has no reasoning effort. Use /temperature instead.",
        "ko": "{model} 모델은 추론 모델이 아니라 reasoning effort를 쓸 수 없습니다. /temperature를 사용하세요.",
    },
    "embedding.select": {"en": "Select an embedding model", "ko": "임베딩 모델을 선택하세요"},
    "embedding.unsupported": {
        "en": "Unsupported embedding model: {model}\nAvailable: {models}",
        "ko": "지원하지 않는 임베딩 모델입니다: {model}\n사용할 수 있는 모델: {models}",
    },
    "embedding.set": {"en": "Embedding model:", "ko": "임베딩 모델:"},
    "run.no_data": {"en": "Load data first with /data.", "ko": "먼저 /data로 데이터를 불러오세요."},
    "run.plan": {
        "en": "{samples} samples × {metrics} metrics × {runs} run(s) = {total} evaluations",
        "ko": "샘플 {samples}개 × 지표 {metrics}개 × {runs}회 = 평가 {total}건",
    },
    "run.progress": {"en": "Evaluating", "ko": "평가 중"},
    "run.confirm": {"en": "Start the evaluation?", "ko": "평가를 시작할까요?"},
    "run.start": {"en": "Start", "ko": "시작"},
    "run.cancel": {"en": "Cancel", "ko": "취소"},
    "run.invalid_limit": {
        "en": "Give the number of samples as a whole number of 1 or more. e.g. /run 20",
        "ko": "샘플 수는 1 이상의 정수로 입력하세요. 예: /run 20",
    },
    "run.interrupted": {
        "en": "Evaluation stopped. Finished judgments are cached, so /run continues from them at no cost.",
        "ko": "평가를 멈췄습니다. 끝난 판정은 캐시에 남아 있어서, 다시 /run하면 그 부분은 비용 없이 이어집니다.",
    },
    "run.data_needed": {
        "en": "Pass --data FILE, or keep exactly one data file in {folder}/ (found: {files}).",
        "ko": "--data FILE 로 데이터 파일을 지정하거나, {folder}/ 폴더에 데이터 파일을 하나만 두세요 (지금 있는 파일: {files}).",
    },
    "run.all_failed": {
        "en": "Every evaluation failed, so nothing was saved. First error: {error}",
        "ko": "모든 평가가 실패해서 결과를 저장하지 않았습니다. 첫 오류: {error}",
    },
    "run.invalid_number": {"en": "--runs and --limit must be 1 or more.", "ko": "--runs 와 --limit 은 1 이상이어야 합니다."},
    "run.saved": {"en": "Saved", "ko": "저장했습니다:"},
    "run.show_hint": {
        "en": "Type /show to list samples, lowest score first, or /show <id> to see one sample's reasons.",
        "ko": "/show로 점수가 낮은 샘플부터 보고, /show <id>로 샘플 하나의 판정 근거를 볼 수 있습니다.",
    },
    "show.no_result": {"en": "No results yet. Run /run first.", "ko": "아직 결과가 없습니다. 먼저 /run으로 평가하세요."},
    "show.list_title": {"en": "Samples, lowest average first", "ko": "샘플 (평균이 낮은 순)"},
    "show.flag_unscored": {"en": "no score", "ko": "점수 없음"},
    "show.flag_error": {"en": "error", "ko": "오류"},
    "show.more": {"en": "… {n} more. Type /show all to list every sample.", "ko": "… {n}개 더 있습니다. /show all로 모두 볼 수 있습니다."},
    "show.list_hint": {
        "en": "Type /show <id> to see the reasons, or /show <id> <framework|axis> to narrow it down (e.g. /show q08 chaejeom).",
        "ko": "/show <id>로 판정 근거를 보고, /show <id> <프레임워크|축>으로 좁혀 볼 수 있습니다 (예: /show q08 chaejeom).",
    },
    "show.no_metric": {
        "en": "No metric matches {filter}. Use a framework (ragas, deepeval, trulens, chaejeom), an axis (groundedness, context_relevance, answer_relevance) or a metric id.",
        "ko": "{filter}에 맞는 지표가 없습니다. 프레임워크(ragas, deepeval, trulens, chaejeom), 축(groundedness, context_relevance, answer_relevance), 지표 이름 중 하나를 쓰세요.",
    },
    "repeats.invalid": {"en": "The number of runs must be a whole number of 1 or more. e.g. /runs 3", "ko": "반복 횟수는 1 이상의 정수로 입력하세요. 예: /runs 3"},
    "repeats.many": {
        "en": "Number of runs: {n}. Scores are reported as mean ± std.",
        "ko": "반복 횟수: {n}회. 점수는 평균 ± 표준편차로 계산합니다.",
    },
    "repeats.one": {"en": "Number of runs: 1.", "ko": "반복 횟수: 1회."},
    "config.ask": {"en": "Path to the config file", "ko": "설정 파일 경로"},
    "config.hint": {
        "en": "A YAML file. Press Tab to complete the path.",
        "ko": "YAML 파일입니다. Tab으로 경로를 자동 완성할 수 있습니다.",
    },
    "config.loaded": {"en": "Config loaded.", "ko": "설정을 불러왔습니다."},
    "config.menu": {"en": "Config", "ko": "설정"},
    "config.load": {"en": "Load a config file", "ko": "설정 파일 불러오기"},
    "config.save": {"en": "Save the current settings", "ko": "현재 설정 저장"},
    "config.save_ask": {"en": "Path to save the config file", "ko": "설정 파일을 저장할 경로"},
    "config.save_hint": {
        "en": "A YAML file. Load it later with /config <file> or chaejeom -c <file>.",
        "ko": "YAML 파일입니다. 나중에 /config <파일>이나 chaejeom -c <파일>로 불러올 수 있습니다.",
    },
    "config.saved": {"en": "Saved the current settings to", "ko": "현재 설정을 저장했습니다:"},
    "config.invalid": {"en": "The file could not be read: {error}", "ko": "파일을 읽을 수 없습니다: {error}"},
    "help.note": {"en": "You can also type a file path without a command to load data.", "ko": "명령 없이 파일 경로만 입력해도 데이터를 불러옵니다."},
    "language.select": {"en": "Select the interface language", "ko": "화면 언어를 선택하세요"},
    "language.unsupported": {
        "en": "Unsupported language: {language}. Select English or 한국어.",
        "ko": "지원하지 않는 언어입니다: {language}. English 또는 한국어를 선택하세요.",
    },
    "repeats.ask": {"en": "Number of runs", "ko": "반복 횟수"},
    "repeats.hint": {
        "en": "Enter a whole number of 1 or more. With 2 or more, scores are reported as mean ± std.",
        "ko": "1 이상의 정수를 입력하세요. 2 이상이면 점수를 평균 ± 표준편차로 계산합니다.",
    },
    "input.help": {"en": "Enter to confirm · Esc to cancel", "ko": "Enter 확인 · Esc 취소"},
    "language.set": {"en": "Language: English", "ko": "언어: 한국어"},
    # Domain information
    "domain.menu": {"en": "Domain information", "ko": "도메인 정보"},
    "domain.new": {"en": "Create from a description", "ko": "설명으로 새로 만들기"},
    "domain.load": {"en": "Load a domain file", "ko": "도메인 파일 불러오기"},
    "domain.show": {"en": "Show the current domain", "ko": "지금 도메인 정보 보기"},
    "domain.off": {"en": "Turn off the domain", "ko": "도메인 정보 끄기"},
    "domain.ask": {"en": "Describe the domain of the RAG to evaluate", "ko": "평가할 RAG의 도메인을 설명해 주세요"},
    "domain.hint": {
        "en": "What the service is, what must be exact, and which targets count as the same or different (e.g. asking about memory chips can be answered with HBM, but NAND and HBM are different). Write types, not actual values.",
        "ko": "어떤 서비스인지, 정확해야 하는 정보, 같은 대상과 다른 대상으로 볼 것을 적어 주세요 (예: 메모리 반도체를 물으면 HBM으로 답해도 되지만 낸드와 HBM은 다른 대상). 실제 값이 아니라 정보의 종류로 적어 주세요.",
    },
    "domain.empty_text": {"en": "(empty)", "ko": "(비어 있음)"},
    "domain.removed": {"en": "Removed because they could act as answers: {values}", "ko": "정답이 될 수 있어 뺀 값: {values}"},
    "domain.ignored": {"en": "Not used, because the metrics do not measure it: {items}", "ko": "지표가 재지 않는 요구라 반영하지 않음: {items}"},
    "domain.confirm": {"en": "Save this domain information?", "ko": "이 도메인 정보를 저장할까요?"},
    "domain.values_left": {
        "en": "Values that could act as answers are still in the items: {values}. Describe them as types of information instead (for example, fee rate rather than 3%).",
        "ko": "정답이 될 수 있는 값이 항목에 남아 있습니다: {values}. 값 대신 정보의 종류로 적어 주세요 (예: 3% 대신 수수료율).",
    },
    "domain.values_title": {"en": "Values remain in the domain information", "ko": "도메인 정보에 값이 남아 있습니다"},
    "domain.redo": {"en": "Describe again", "ko": "다시 설명하기"},
    "domain.save": {"en": "Save", "ko": "저장"},
    "domain.discard": {"en": "Discard", "ko": "저장하지 않음"},
    "domain.path_ask": {"en": "Path to save the domain file", "ko": "도메인 파일을 저장할 경로"},
    "domain.path_hint": {
        "en": "A YAML file. You can edit it and load it again with /domain <file>.",
        "ko": "YAML 파일입니다. 고친 뒤 /domain <파일>로 다시 불러올 수 있습니다.",
    },
    "domain.load_ask": {"en": "Path to the domain file", "ko": "도메인 파일 경로"},
    "domain.load_hint": {"en": "A YAML file. Press Tab to complete the path.", "ko": "YAML 파일입니다. Tab으로 경로를 자동 완성할 수 있습니다."},
    "domain.set": {"en": "Domain: {name}", "ko": "도메인: {name}"},
    "domain.status_missing": {"en": "not found: {path}", "ko": "찾을 수 없음: {path}"},
    "domain.applies": {"en": "Domain information is used only by the Chaejeom metrics.", "ko": "도메인 정보는 채점(Chaejeom) 지표에만 쓰입니다."},
    "domain.cleared": {
        "en": "Domain turned off. The Chaejeom metrics use the general criteria.",
        "ko": "도메인 정보를 껐습니다. 채점 지표는 일반 기준으로 판정합니다.",
    },
    "domain.model": {"en": "Select the model that organizes domain information", "ko": "도메인 정보를 정리할 모델 선택"},
    "domain.model_select": {"en": "Model that organizes domain information", "ko": "도메인 정보를 정리할 모델"},
    "domain.model_set": {"en": "Domain model: {model}", "ko": "도메인 정리 모델: {model}"},
    "domain.using_model": {"en": "Organizing with {model}...", "ko": "{model} 모델로 정리하는 중입니다..."},
    "domain.missing_title": {
        "en": "The Chaejeom metrics judge with your domain information, but none is set.",
        "ko": "채점 지표는 도메인 정보를 바탕으로 판정하는데, 설정된 도메인 정보가 없습니다.",
    },
    "domain.setup_now": {"en": "Set up domain information now", "ko": "지금 도메인 정보 설정하기"},
    "domain.run_general": {"en": "Run with the general criteria", "ko": "일반 기준으로 실행하기"},
    "domain.cancel_run": {"en": "Cancel", "ko": "취소"},
    "domain.missing_warning": {
        "en": "Note: the Chaejeom metrics run without domain information, using the general criteria. Set domain in the config file.",
        "ko": "참고: 도메인 정보 없이 채점 지표를 일반 기준으로 실행합니다. 설정 파일에 domain 을 지정하세요.",
    },
    "domain.not_set": {"en": "No domain information is set.", "ko": "설정된 도메인 정보가 없습니다."},
    "domain.changes": {"en": "Changed lines in the {metric} prompt", "ko": "{metric} 프롬프트에서 바뀐 줄"},
    "domain.no_changes": {"en": "{metric}: uses the default prompt", "ko": "{metric}: 기본 프롬프트 그대로"},
    # Metric prompts
    "prompt.select": {"en": "Select a metric", "ko": "지표를 선택하세요"},
    "prompt.default": {"en": "default", "ko": "기본"},
    "prompt.custom": {"en": "custom", "ko": "수정본"},
    "prompt.read_only": {
        "en": "RAGAS, DeepEval and TruLens prompts are read-only. They stay as ported from the original frameworks.",
        "ko": "RAGAS, DeepEval, TruLens 프롬프트는 볼 수만 있습니다. 원본 프레임워크에서 옮긴 그대로 둡니다.",
    },
    "prompt.menu": {"en": "Prompt for {metric}", "ko": "{metric} 프롬프트"},
    "prompt.edit": {"en": "Edit with a request", "ko": "요청으로 수정하기"},
    "prompt.load": {"en": "Load a prompt file", "ko": "프롬프트 파일 불러오기"},
    "prompt.reset": {"en": "Reset to the default prompt", "ko": "기본 프롬프트로 되돌리기"},
    "prompt.close": {"en": "Close", "ko": "닫기"},
    "prompt.full": {"en": "Show the full prompt", "ko": "전체 프롬프트 보기"},
    "prompt.summary_more": {"en": "… {n} more lines. Select Show the full prompt to see all.", "ko": "… {n}줄 더 있습니다. 전체 프롬프트 보기로 모두 볼 수 있습니다."},
    "prompt.slots": {"en": "Inputs: {slots}", "ko": "입력 자리: {slots}"},
    "prompt.folded": {"en": "… ({n} characters, folded)", "ko": "… ({n}자, 접음)"},
    "prompt.edit_ask": {"en": "Describe how to change the {metric} prompt", "ko": "{metric} 프롬프트를 어떻게 바꿀지 적어 주세요"},
    "prompt.edit_hint": {
        "en": "Write as much or as little as you like; the prompt is revised to match. What the metric measures and the output format stay the same.",
        "ko": "짧게 적든 자세히 적든 적은 만큼 반영합니다. 지표가 재는 것과 출력 형식은 바뀌지 않습니다.",
    },
    "prompt.using_model": {"en": "Revising with {model}...", "ko": "{model} 모델로 고치는 중입니다..."},
    "prompt.changes": {"en": "Changes: {summary}", "ko": "바꾼 점: {summary}"},
    "prompt.saved": {"en": "Saved to", "ko": "저장한 곳:"},
    "prompt.loaded": {"en": "Loaded", "ko": "불러온 파일:"},
    "prompt.file": {"en": "File:", "ko": "파일:"},
    "prompt.applies": {
        "en": "{metric} uses this prompt from the next /run. Open the file to edit it directly.",
        "ko": "다음 /run부터 {metric} 지표에 이 프롬프트를 씁니다. 파일을 열어 직접 고칠 수도 있습니다.",
    },
    "prompt.reset_done": {"en": "{metric} uses the default prompt again.", "ko": "{metric} 지표가 다시 기본 프롬프트를 씁니다."},
    "prompt.failed": {
        "en": "Could not revise the prompt without changing what the metric measures or its output format. Try rephrasing the request.",
        "ko": "지표가 재는 것이나 출력 형식을 바꾸지 않고는 요청을 반영하지 못했습니다. 요청을 바꿔 다시 적어 주세요.",
    },
    "prompt.load_ask": {"en": "Path to the prompt file", "ko": "프롬프트 파일 경로"},
    "prompt.load_hint": {"en": "A YAML file made with /prompt. Press Tab to complete the path.", "ko": "/prompt로 만든 YAML 파일입니다. Tab으로 경로를 자동 완성할 수 있습니다."},
    "prompt.in_use": {"en": "Custom prompt: {metric}", "ko": "수정본 프롬프트: {metric}"},
    # Pickers
    "picker.help": {"en": "↑↓ to move · Enter to select · Esc to cancel", "ko": "↑↓ 이동 · Enter 선택 · Esc 취소"},
    "picker.current": {"en": "current", "ko": "현재"},
    "grid.title": {"en": "Select metrics and runs", "ko": "평가 지표와 반복 횟수를 선택하세요"},
    "grid.help": {
        "en": "↑↓←→ to move · Space to toggle · Enter to confirm · Esc to cancel",
        "ko": "↑↓←→ 이동 · Space 선택/해제 · Enter 확인 · Esc 취소",
    },
    "grid.runs_many": {"en": "←→ to change the number of runs. Scores are the mean ± std over runs.", "ko": "←→로 반복 횟수를 바꿉니다. 점수는 회차별 평균 ± 표준편차로 계산합니다."},
    "grid.runs_one": {"en": "←→ to change the number of runs. A single run gives one score.", "ko": "←→로 반복 횟수를 바꿉니다. 한 번만 실행하면 점수가 하나 나옵니다."},
    "grid.toggle_all": {"en": "Toggle all metrics", "ko": "모든 지표를 선택하거나 해제합니다"},
    "grid.toggle_framework": {"en": "Toggle all {name} metrics", "ko": "{name} 지표를 모두 선택하거나 해제합니다"},
    "grid.toggle_axis": {"en": "Toggle all {name} metrics", "ko": "{name} 지표를 모두 선택하거나 해제합니다"},
    "grid.needs": {"en": "needs {inputs}", "ko": "필요한 입력: {inputs}"},
    "grid.count": {"en": "{n} of {total} metrics selected", "ko": "지표 {total}개 중 {n}개 선택"},
    # Input data format errors
    "format.where_line": {"en": "line {n}", "ko": "{n}번째 줄"},
    "format.where_sample": {"en": "sample {n}", "ko": "{n}번째 샘플"},
    "format.extension": {
        "en": "{file}: unsupported file type. Use a JSONL, JSON or CSV file.",
        "ko": "{file}: 지원하지 않는 파일 형식입니다. JSONL, JSON, CSV 파일로 넣어 주세요.",
    },
    "format.encoding": {
        "en": "{file}: the file is not UTF-8. Save it with UTF-8 encoding and try again.",
        "ko": "{file}: UTF-8 파일이 아닙니다. UTF-8 인코딩으로 저장한 뒤 다시 불러와 주세요.",
    },
    "format.empty": {"en": "{file}: the file has no samples.", "ko": "{file}: 파일에 샘플이 없습니다."},
    "format.json": {"en": "{file} {where}: not valid JSON ({detail}).", "ko": "{file} {where}: 올바른 JSON이 아닙니다 ({detail})."},
    "format.not_list": {"en": "{file}: a JSON file must contain a list of samples.", "ko": "{file}: JSON 파일에는 샘플 목록([...])이 들어 있어야 합니다."},
    "format.not_object": {"en": "{file} {where}: each sample must be a JSON object ({{...}}).", "ko": "{file} {where}: 샘플은 JSON 객체({{...}})여야 합니다."},
    "format.csv_row": {
        "en": "{file} {where}: the row has more cells than the header.",
        "ko": "{file} {where}: 이 행의 칸 수가 첫 줄의 열 이름 수보다 많습니다.",
    },
    "format.no_fields": {
        "en": "{file} {where}: none of query, contexts or answer was found.",
        "ko": "{file} {where}: query, contexts, answer 중 어느 것도 없습니다.",
    },
    "format.invalid": {"en": "{file} {where}: wrong value type in {detail}.", "ko": "{file} {where}: {detail} 값의 형식이 맞지 않습니다."},
    "format.guide_title": {"en": "Please provide the data in one of these formats.", "ko": "아래 형식 중 하나에 맞춰 데이터를 넣어 주세요."},
    "format.guide_jsonl": {"en": "JSONL (one sample per line; JSON takes a list of the same objects)", "ko": "JSONL (한 줄에 샘플 하나. JSON은 같은 객체의 목록)"},
    "format.guide_csv": {"en": "CSV (a header row, then one sample per row)", "ko": "CSV (첫 줄은 열 이름, 그다음부터 한 행에 샘플 하나)"},
    "format.guide_query": {"en": "the user's question", "ko": "사용자 질문"},
    "format.guide_contexts": {
        "en": "retrieved passages: a list of strings in JSONL, context_1, context_2, ... columns in CSV",
        "ko": "검색된 문맥: JSONL은 문자열 목록, CSV는 context_1, context_2, … 열",
    },
    "format.guide_answer": {"en": "the generated answer", "ko": "생성된 답변"},
    "format.guide_optional": {
        "en": "id and metadata are optional. RAGAS and DeepEval field names (user_input, response, ...) also work.",
        "ko": "id와 metadata는 넣지 않아도 됩니다. RAGAS와 DeepEval 필드 이름(user_input, response 등)도 쓸 수 있습니다.",
    },
}


def set_language(language: str) -> None:
    """Set the UI language. Raises ValueError if it is not in `LANGUAGES`."""
    global _current
    if language not in LANGUAGES:
        raise ValueError(t("language.unsupported", language=language))
    _current = language


def get_language() -> str:
    return _current


def t(key: str, **kwargs) -> str:
    """Return the message for ``key`` in the current language, formatted with ``kwargs``."""
    return MESSAGES[key][_current].format(**kwargs)
