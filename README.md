# Lumi: a tiny functional + logic programming language

Lumi is a small language we built for our **Logic & Functional Programming** class.
It has two halves that work together:

- a **functional core** (ML-style): `let`, lambdas, currying, recursion, pattern matching, lists, and higher-order functions
- a **logic engine** (Prolog-style): facts, rules, queries, unification, and backtracking

```lumi
let rec quicksort xs = match xs with
  | [] -> []
  | p :: rest -> quicksort (filter (fn x => x < p) rest) ++ [p]
                   ++ quicksort (filter (fn x => x >= p) rest)
print (quicksort [5, 3, 8, 1])            -- [1, 3, 5, 8]

fact parent(tom, bob).
fact parent(bob, ann).
rule grandparent(X, Z) :- parent(X, Y), parent(Y, Z).
query grandparent(tom, Who)?               -- Who = ann

let kids = solve parent(tom, C) |> map (fn r => r.C)
print kids                                 -- [bob]
```

📖 **Read the full design document: open [`docs/index.html`](docs/index.html) in your browser.**

## Quick start

Requires Python 3.10 or newer. There are no runtime dependencies.

```bash
pip install -e ".[dev]"          # installs the `lumi` command + pytest
python -m lumi examples/01_basics.lumi
python -m lumi                   # interactive REPL (:help, :kb, :quit)
python -m pytest -q              # run the tests
```

Two debugging flags help you see how the interpreter works:

```bash
python -m lumi examples/01_basics.lumi --tokens   # lexer output
python -m lumi examples/01_basics.lumi --ast      # parser output
```

## Project layout

| Path                | What it is                                                         |
| ------------------- | ------------------------------------------------------------------ |
| `lumi/tokens.py`    | token types and keywords                                           |
| `lumi/lexer.py`     | source text → tokens                                               |
| `lumi/syntax.py`    | AST node classes                                                   |
| `lumi/parser.py`    | tokens → AST (recursive descent + precedence climbing)             |
| `lumi/evaluator.py` | runs the AST: environments, closures, pattern matching, tail calls |
| `lumi/logic.py`     | logic engine: terms, unification, SLD resolution                   |
| `lumi/values.py`    | runtime values and printing                                        |
| `lumi/builtins.py`  | built-in functions (`print`, `map`, `filter`, `fold`, …)           |
| `lumi/repl.py`      | interactive prompt                                                 |
| `examples/`         | example programs, with golden outputs in `examples/expected/`      |
| `tests/`            | pytest suite                                                       |
| `docs/index.html`   | human-friendly design document                                     |

## Contributing (team workflow)

1. Pick a task from the roadmap in `docs/index.html`.
2. Add a test first (`tests/`), then implement it.
3. If you add an example, also add its golden output:
   `python -m lumi examples/NAME.lumi > examples/expected/NAME.out`
4. Run `python -m pytest -q` before you push.
