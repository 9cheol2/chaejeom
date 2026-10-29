# Command line

**English | [한국어](cli.ko.md)**

Chaejeom installs one command under three names: `chaejeom`, `Chaejeom` and `채점`.

| Command | What it does |
|---|---|
| `chaejeom` | Opens the interactive terminal. `-c FILE` starts it with a config file |
| `chaejeom run` | Runs one evaluation from a config file and a data file |
| `chaejeom compare` | Compares two result files |
| `chaejeom list` | Lists the metrics and the inputs each one needs |
| `chaejeom --version` | Prints the version |

The API key is read from `OPENAI_API_KEY` in a `.env` file in the working directory or in your environment.

## `chaejeom run`

```bash
chaejeom run --config examples/eval.yaml --data examples/samples.jsonl
```

| Option | Description |
|---|---|
| `--config FILE` | Config file (YAML). Required. See [Configuration](configuration.md) |
| `--data FILE` | Evaluation data: JSONL, JSON or CSV. Defaults to the only data file in `input/`. See [Data format](data-format.md) |
| `--out FILE` | Result file, default `output/<data file name>_<date-time>.json`. A CSV with the same name is written too |
| `--runs N` | Number of runs; overrides `runs` in the config (default 3). `--repeats` also works |
| `--limit N` | Evaluate only the first N samples, for example to check the real cost on your data |
| `--label TEXT` | A name for this run, stored in the result file, such as `retriever v1.3` |
| `--no-cache` | Ignore cached responses and call the model again |

Before evaluating, Chaejeom prints the estimated cost and warns when Chaejeom metrics run without a domain file or
when text would be sent to a different endpoint than the judge. Afterwards it prints the axis × framework table, the
per-metric scores, and the actual token usage and cost.

`chaejeom run` exits with code 1 and writes no result file when every evaluation failed, for example because the API
key or the model name is wrong, so a CI job can catch it. It exits with code 2 when `--data` is omitted and `input/`
does not hold exactly one data file.

## `chaejeom compare`

```bash
chaejeom run --config eval.yaml --data samples.jsonl --label "retriever v1.3" --out v1.3.json
chaejeom compare v1.2.json v1.3.json
```

`compare` shows the axis × framework scores of both results with the change, then the samples whose score moved by
0.25 or more. Samples are matched by `id`, so give your samples stable ids.

It warns when the two results are not directly comparable: different data, a different judge or embedding model,
a different domain file or custom prompt, a different number of runs, or metrics present in only one file. Each
result file records a fingerprint of all of these. An axis average is compared only when both results averaged the
same metrics.

## Interactive mode

```bash
chaejeom                  # or: chaejeom -c eval.yaml
```

Type `/` to open the command menu, or type a data file path to load it. The interface is in English by default;
`/language ko` switches it to Korean. Judge explanations are always in Korean.

| Command | What it does |
|---|---|
| `/data [file]` | Load evaluation data. Typing a path alone does the same; without a path, you pick a file in `input/` or type a path with Tab completion |
| `/metrics [ids]` | Select metrics and the number of runs on an axis × framework grid |
| `/model [model] [value]` | Select the judge model, then its temperature or reasoning effort |
| `/temperature [0-2]` | Set the judge temperature. Shown only for non-reasoning models |
| `/effort [low\|medium\|high]` | Set the judge reasoning effort. Shown only for reasoning models |
| `/embedding [model]` | Select the embedding model |
| `/domain [file\|off]` | Create, load, show or turn off the domain file |
| `/prompt [metric\|file]` | View any metric's judge prompt; revise the Chaejeom prompts |
| `/run [n]` | Run the evaluation; with a number, only the first n samples |
| `/show [all\|sample [framework\|axis]]` | List samples, lowest score first, or show one sample's scores, verdicts and reasons |
| `/runs [n]` | Set the number of runs |
| `/config [file\|save]` | Load a config file, or save the current settings as one |
| `/language [en\|ko]` | Select the interface language; remembered for the next start |
| `/help` | Show all commands |
| `/exit` | Exit. Pressing Ctrl+C twice on an empty input also exits |

Leave the value out and most commands open a picker or an input box. Pressing Enter on a partial command runs it only
when it matches a single command, so `/r` does not start `/run` by accident.

### Selecting metrics

`/metrics` opens a grid with one row per axis and one column per framework. Move with the arrow keys and press Space
to toggle a cell, a whole axis, a whole framework, or everything; set the number of runs on the `Runs` row with ←→.
You can also pass metric ids directly, for example `/metrics ragas.*,chaejeom.groundedness`. The line under the input
box always shows the current selection.

### Models

`/model` offers gpt-4o-mini, gpt-4.1-mini (default), gpt-5-mini, gpt-5.4-mini, gpt-5.6-luna and gpt-6-luna. After
choosing a model you set its temperature (non-reasoning models, default 0) or its reasoning effort (reasoning models,
default `low`); a model takes one or the other. `/embedding` selects text-embedding-3-small or text-embedding-3-large
(default), used only by RAGAS ResponseRelevancy.

For a cheaper first look, use `/model gpt-4o-mini` (about a third of the price, though it follows domain
rules less reliably) or `/runs 1`.

### Domain files

`/domain` lets you describe your service in your own words, as briefly or as fully as you like. Chaejeom organizes
what you wrote into the service and one set of rules per metric, shows the items and the lines they change in each
judge prompt, and saves the result as a YAML file after you confirm. It adds nothing you
did not say and leaves unmentioned items empty. Values that could act as answers, such as `5일` or `3%`, are rewritten
as types of information; if any remain, you are asked to describe them again.

The menu also loads, shows or turns off a domain file, and selects the model that organizes descriptions (default
gpt-4.1-mini, separate from the judge). `/domain <file>` loads a file directly; `/domain off` turns it off. When you
run Chaejeom metrics without a domain file, you are asked whether to set one up or run with general criteria.

### Prompts

`/prompt` shows a summary of the prompts a metric sends to the judge, including the input slots such as `{query}`;
choose *Show the full prompt* to read all of it.

- **RAGAS, DeepEval, TruLens**: read-only, as ported from the original frameworks.
- **Chaejeom**: choose *Edit with a request* and describe the change. The prompt is revised to match and saved to
  `prompts/<metric>.yaml`, and the next `/run` uses it. What the metric measures and the output format stay the same.
  With a domain set, the edit starts from the domain's prompt.
  You can also load a prompt file or reset to the default.

Saved files appear as clickable links in terminals that support them, such as Windows Terminal and VS Code.

### Running and inspecting

`/run` shows the planned number of evaluations and the estimated cost, and starts when you press Enter (Esc cancels).
Results are saved as JSON and CSV in `output/`. Ctrl+C during a run stops only the run; finished verdicts
stay in the cache, so running again continues from them at no cost. If the API key or the model name is wrong, the
run stops with one clear message instead of saving a table of errors.

Below the score tables, *Samples without a score* lists each sample a metric left unscored, in how many runs, and
why. Most are by design, such as an answer with no factual statement for groundedness; errors are shown in red.

`/show` lists the samples with their score on each axis, lowest average first, and flags samples with a missing
score or an error (`/show all` lists every sample). `/show q08` opens one sample: its scores, then each verdict and
its reason. `/show q08 chaejeom` or `/show q08 groundedness` narrows it to a framework or an axis. With several runs,
a metric whose runs differ shows each run's score next to it. `/config save` writes the current
models, metrics, domain file and prompts to a config file that `/config <file>` or `chaejeom -c <file>` loads again.
