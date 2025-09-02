#!/usr/bin/env python3
# DeadBasic.BA
# v0.4.5: Added try catch blocks

import sys, shlex, pathlib
import getpass
import math
import traceback

VERSION = "0.4.5"

# ---------- Error types ----------
class DeadBasicError(Exception):
    """Base interpreter error."""
    pass

class SyntaxDeadBasicError(DeadBasicError):
    """Syntax error (e.g., missing indent, bad keywords)."""
    pass

class RuntimeDeadBasicError(DeadBasicError):
    """Runtime error (e.g., type mismatch, unknown var)."""
    pass


class DeadBasic:
    def __init__(self):
        # Vars: name -> {"type": "int|long|double|str", "value": pyvalue}
        self.vars = {}

        # Commands
        self.commands = {
            "printtext".lower(): self.cmd_printtext,
            "showvars".lower():  self.cmd_showvars,
            "openfile".lower():  self.cmd_openfile,
            "add".lower():       self.cmd_add,
            "help".lower():      self.help,
            "subt".lower():      self.cmd_subt,
            "div".lower() :      self.cmd_div,
            "times".lower():     self.cmd_multiply,
            "sqrt".lower():      self.cmd_squareroot,
            "input".lower():     self.cmd_input,
        }

        # Declarations
        self.type_keywords = {"int", "long", "double", "str"}

        # Flow-control contexts (no nesting by design)
        self.if_ctx = None             # {"cond_true": bool, "in_else": bool}
        self.while_ctx = None          # {"start_pc": int, "cond_tokens": list[str]}
        self.try_ctx = None            # {"has_error": bool, "in_catch": bool, "err_name": str|None, "err_msg": str|None}

        # For better error messages
        self.current_file = "<repl>"

    # ---------- Help Command --------
    @staticmethod
    def help():
        print(f"Welcome to Deadbasic Version: {VERSION}")
        print("Commands are as followed.")
        print("Printtext: Prints anything following that line \n showvars: Shows all varitables in your active file and what they are set to. \n Openfile: Opens any .ba file. \n add: Adds 2 numbers together \n subt: Subtracts 2 numbers \n div: Divides 2 numbers \n times: Multiply 2 numbers together \n sqrt: Squares the number provided")
        print("Flow: if/else/endif, while/endwhile, try/catch [errVar]/endtry")
        print("Copyright 2025. License under MIT please see https://github.com/TheRamDev/DeadBasic-coding-language/blob/main/LICENSE for license info ")

    # ---------- helpers ----------
    def _resolve(self, token, line_no):
        """Resolve token to a Python value (maybe str, int, float)."""
        if token in self.vars:
            return self.vars[token]["value"]
        try:
            if "." in token:
                return float(token)
            return int(token)
        except ValueError:
            pass
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
            return token[1:-1]
        return token

    def _to_number(self, value, line_no, label="value"):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                if "." in value:
                    return float(value)
                return float(int(value))
            except ValueError:
                pass
        sys.stderr.write("\033[91m")
        traceback.print_exc()
        sys.stderr.write("\033[0m")
        raise RuntimeDeadBasicError(self._fmt(line_no,f"{label} is not numeric"))

    def _truthy(self, value):
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value != ""
        return True

    def _fmt(self, line_no, msg):
        return f"[{self.current_file}:line {line_no}] {msg}"

    def _detect_indent(self, line: str):
        """
        Treat any run of leading whitespace (spaces, tabs, NBSP, etc.)
        as a single indent level. No nested blocks in this language,
        so we collapse all leading whitespace to indent=1.
        """
        i = 0
        while i < len(line) and line[i].isspace() and line[i] not in "\r\n":
            i += 1
        if i == 0:
            return 0, line
        return 1, line[i:]

    # ---------- condition evaluation (shared by IF/WHILE) ----------
    def _eval_condition_tokens(self, tokens, line_no):
        if not tokens:
            raise SyntaxDeadBasicError(self._fmt(line_no, "condition required"))
        if tokens[0].lower() == "not":
            if len(tokens) != 2:
                raise SyntaxDeadBasicError(self._fmt(line_no, "'not' expects exactly one value"))
            val = self._resolve(tokens[1], line_no)
            return not self._truthy(val)

        if len(tokens) != 3:
            raise SyntaxDeadBasicError(self._fmt(line_no,
                "condition must be: <lhs> <op> <rhs> or 'not <value>'"))

        lhs_tok, op, rhs_tok = tokens
        lhs_val = self._resolve(lhs_tok, line_no)
        rhs_val = self._resolve(rhs_tok, line_no)

        if op == "=":
            return lhs_val == rhs_val
        if op == "!=":
            return lhs_val != rhs_val

        lnum = self._to_number(lhs_val, line_no, "left side")
        rnum = self._to_number(rhs_val, line_no, "right side")
        if op == "<":
            return lnum < rnum
        if op == ">":
            return lnum > rnum
        if op == "<=":
            return lnum <= rnum
        if op == ">=":
            return lnum >= rnum

        raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown operator '{op}'"))

    def _should_execute_if_body_line(self):
        if self.if_ctx is None:
            return False
        if not self.if_ctx["in_else"] and self.if_ctx["cond_true"]:
            return True
        if self.if_ctx["in_else"] and not self.if_ctx["cond_true"]:
            return True
        return False

    def _should_execute_try_body_line(self):
        if self.try_ctx is None:
            return False
        # in try body (not in catch) only when no error yet
        return not self.try_ctx["in_catch"] and not self.try_ctx["has_error"]

    def _should_execute_catch_body_line(self):
        if self.try_ctx is None:
            return False
        # in catch body only when in_catch and there was an error
        return self.try_ctx["in_catch"] and self.try_ctx["has_error"]

    def _enter_catch_if_needed(self):
        """Assign err var on catch entry if set."""
        if self.try_ctx and self.try_ctx["in_catch"] and self.try_ctx["err_name"]:
            name = self.try_ctx["err_name"]
            msg = self.try_ctx["err_msg"] if self.try_ctx["err_msg"] is not None else ""
            self.vars[name] = {"type": "str", "value": str(msg)}

    # ---------- commands ----------
    def cmd_input(self, args, line_no):
        if len(args) != 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, "input needs: <type> <varname>"))
        vtype, name = args
        prompt = f"Enter {vtype} {name}: "
        raw = input(prompt)

        if vtype == "int":
            try:
                val = int(raw)
            except ValueError:
                raise RuntimeDeadBasicError(self._fmt(line_no, f"'{raw}' is not an integer"))
        elif vtype == "long":
            try:
                val = int(raw)
            except ValueError:
                raise RuntimeDeadBasicError(self._fmt(line_no, f"'{raw}' is not a long integer"))
        elif vtype == "double":
            try:
                val = float(raw)
            except ValueError:
                raise RuntimeDeadBasicError(self._fmt(line_no, f"'{raw}' is not a double"))
        elif vtype == "str":
            val = raw
        else:
            raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown type: {vtype}"))

        self.vars[name] = {"type": vtype, "value": val}

    def cmd_printtext(self, args, line_no):
        if not args:
            raise SyntaxDeadBasicError(self._fmt(line_no, "printtext needs text or var names"))
        out = []
        for tok in args:
            if tok in self.vars:
                out.append(str(self.vars[tok]["value"]))
            else:
                out.append(tok)
        print(" ".join(out))

    def cmd_showvars(self, args=None, line_no=None):
        if not self.vars:
            print("(no vars)")
            return
        for k, meta in self.vars.items():
            print(f"{meta['type']} {k} = {meta['value']}"),

    def cmd_openfile(self, args, line_no):
        if not args:
            raise SyntaxDeadBasicError(self._fmt(line_no, "openfile needs a filename"))
        path = pathlib.Path(args[0])
        # Clear dangling control states before jumping into another file
        self.if_ctx = None
        self.while_ctx = None
        self.try_ctx = None
        self.run_file(path)

    def cmd_add(self, args, line_no):
        if len(args) != 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, "add needs exactly 2 numbers"))
        a = self._to_number(self._resolve(args[0], line_no), line_no, "first argument")
        b = self._to_number(self._resolve(args[1], line_no), line_no, "second argument")
        result = a + b
        print(int(result) if result.is_integer() else result)

    def cmd_squareroot(self, args, line_no):
        if len(args) > 1:
            raise SyntaxDeadBasicError(self._fmt(line_no, "Square root only needs 1 number"))
        a = self._to_number(self._resolve(args[0], line_no), line_no, "first argument")
        result = math.sqrt(a)
        print(int(result) if result.is_integer() else result)

    def cmd_subt(self, args, line_no):
        if len(args) != 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, "Subtract needs exactly 2 numbers"))
        a = self._to_number(self._resolve(args[0], line_no), line_no, "first argument")
        b = self._to_number(self._resolve(args[1], line_no), line_no, "second argument")
        result = a - b
        print(int(result) if result.is_integer() else result)

    def cmd_div(self, args, line_no):
        if len(args) != 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, "Divide needs exactly 2 numbers"))
        a = self._to_number(self._resolve(args[0], line_no), line_no, "first argument")
        b = self._to_number(self._resolve(args[1], line_no), line_no, "second argument")
        try:
            result = a / b
            print(int(result) if result.is_integer() else result)
        except ZeroDivisionError:
            raise RuntimeDeadBasicError(self._fmt(line_no, "You cannot divide by 0."))

    def cmd_multiply(self, args, line_no):
        if len(args) != 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, "Multiply needs exactly 2 numbers"))
        a = self._to_number(self._resolve(args[0], line_no), line_no, "first argument")
        b = self._to_number(self._resolve(args[1], line_no), line_no, "second argument")
        result = a * b
        print(int(result) if result.is_integer() else result)

    def cmd_declare(self, vtype, args, line_no):
        if len(args) < 2:
            raise SyntaxDeadBasicError(self._fmt(line_no, f"{vtype} needs: <name> <value>"))
        name, *raw_value = args
        value_str = " ".join(raw_value)
        if vtype in {"int", "long"}:
            try:
                val = int(value_str)
            except ValueError:
                raise RuntimeDeadBasicError(self._fmt(line_no, f"'{value_str}' is not an integer"))
        elif vtype == "double":
            try:
                val = float(value_str)
            except ValueError:
                raise RuntimeDeadBasicError(self._fmt(line_no, f"'{value_str}' is not a double"))
        elif vtype == "str":
            val = value_str.strip('"')
        else:
            raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown type: {vtype}"))
        if name in self.vars and self.vars[name]["type"] != vtype:
            raise RuntimeDeadBasicError(self._fmt(line_no,
                f"type mismatch: {name} is {self.vars[name]['type']}, not {vtype}"))
        self.vars[name] = {"type": vtype, "value": val}

    # ---------- single-line execution (REPL) ----------
    def execute_line(self, line, line_no):
        """Executes a *single* textual line. Suitable for REPL.
        Loops are not supported here (they need multi-line scan)."""
        indent, content = self._detect_indent(line)
        raw = content.strip()
        if not raw:
            return
        if raw.startswith("#") or raw.startswith("``"):
            return

        try:
            tokens = shlex.split(raw, posix=True)
        except ValueError as e:
            raise SyntaxDeadBasicError(self._fmt(line_no, f"parse error: {e}"))
        if not tokens:
            return

        head, *args = tokens
        head_l = head.lower()

        # REPL: disallow while/endwhile (needs multi-line control)
        if head_l in {"while", "endwhile"}:
            raise SyntaxDeadBasicError(self._fmt(line_no,
                "while/endwhile are only supported in .ba files, not in REPL"))

        # ---- Top-level control in REPL
        if indent == 0:
            # TRY/CATCH/ENDTRY
            if head_l == "try":
                if self.try_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "Nested TRY not supported"))
                if self.if_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "TRY cannot start inside an open IF; close IF first"))
                self.try_ctx = {"has_error": False, "in_catch": False, "err_name": None, "err_msg": None}
                return
            if head_l == "catch":
                if self.try_ctx is None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "'catch' without matching 'try'"))
                if self.try_ctx["in_catch"]:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "multiple 'catch' not allowed"))
                if len(args) > 1:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "catch takes zero or one var name"))
                self.try_ctx["in_catch"] = True
                self.try_ctx["err_name"] = (args[0] if args else None)
                # assign err var on entry
                self._enter_catch_if_needed()
                return
            if head_l == "endtry":
                if self.try_ctx is None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "'endtry' without matching 'try'"))
                self.try_ctx = None
                return

            # IF/ELSE/ENDIF handling at top level in REPL
            if head_l == "if":
                if self.if_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no,
                        "Nested IF not supported (previous IF missing 'endif'?)"))
                if self.try_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "IF cannot start inside an open TRY; close TRY first"))
                cond = self._eval_condition_tokens(args, line_no)
                self.if_ctx = {"cond_true": cond, "in_else": False}
                return
            if head_l == "else":
                if self.if_ctx is None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "'else' without matching 'if'"))
                if self.if_ctx["in_else"]:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "multiple 'else' not allowed"))
                self.if_ctx["in_else"] = True
                return
            if head_l == "endif":
                if self.if_ctx is None:
                    raise SyntaxDeadBasicError(self._fmt(line_no, "'endif' without matching 'if'"))
                self.if_ctx = None
                return

            # If any block is open, only its headers allowed at top level
            if self.if_ctx is not None:
                raise SyntaxDeadBasicError(self._fmt(line_no,
                    "Inside IF: expected an indented line (TAB/4 spaces), 'else', or 'endif'"))
            if self.try_ctx is not None:
                raise SyntaxDeadBasicError(self._fmt(line_no,
                    "Inside TRY: expected an indented line (TAB/4 spaces), 'catch', or 'endtry'"))

            # Decls / commands
            if head_l in self.type_keywords:
                self.cmd_declare(head_l, args, line_no); return
            if head_l not in self.commands:
                raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
            self.commands[head_l](args, line_no); return

        # ---- Indented line (REPL)
        if indent == 1:
            if head_l in {"if", "else", "endif", "while", "endwhile", "try", "catch", "endtry"}:
                raise SyntaxDeadBasicError(self._fmt(line_no, f"'{head_l}' must be at top level (no indent)"))

            # IF body?
            if self.if_ctx is not None:
                if not self._should_execute_if_body_line():
                    return
                if head_l in self.type_keywords:
                    self.cmd_declare(head_l, args, line_no); return
                if head_l not in self.commands:
                    raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                self.commands[head_l](args, line_no); return

            # TRY body?
            if self.try_ctx is not None:
                # skip if not appropriate section
                if self._should_execute_try_body_line():
                    try:
                        if head_l in self.type_keywords:
                            self.cmd_declare(head_l, args, line_no)
                        else:
                            if head_l not in self.commands:
                                raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                            self.commands[head_l](args, line_no)
                    except DeadBasicError as e:
                        # record error & stop executing try body; wait for catch
                        self.try_ctx["has_error"] = True
                        self.try_ctx["err_msg"] = str(e)
                    except Exception as e:
                        self.try_ctx["has_error"] = True
                        self.try_ctx["err_msg"] = f"Internal error: {e}"
                    return
                elif self._should_execute_catch_body_line():
                    # ensure err var exists before first catch line
                    self._enter_catch_if_needed()
                    if head_l in self.type_keywords:
                        self.cmd_declare(head_l, args, line_no); return
                    if head_l not in self.commands:
                        raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                    self.commands[head_l](args, line_no); return
                else:
                    # inside TRY but not running this section
                    return

            # Indent but no block => syntax error
            raise SyntaxDeadBasicError(self._fmt(line_no,
                "You are missing the required 'while/if/try' before this indented line"))

    # ---------- file execution with program counter (supports WHILE, TRY) ----------
    def run_file(self, path: pathlib.Path):
        if not path.exists():
            raise RuntimeDeadBasicError(self._fmt(0, f"file not found: {path}"))
        self.current_file = str(path)
        self.if_ctx = None
        self.while_ctx = None
        self.try_ctx = None

        with path.open("r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f]

        pc = 0
        n = len(lines)

        def parse_tokens(line, lno):
            indent, content = self._detect_indent(line)
            raw = content.strip()
            return indent, raw, (shlex.split(raw, posix=True) if raw and not raw.startswith(("#", "``")) else [])

        while pc < n:
            line_no = pc + 1
            line = lines[pc]
            indent, raw, tokens = parse_tokens(line, line_no)

            if not raw or raw.startswith("#") or raw.startswith("``"):
                pc += 1
                continue

            head, *args = tokens
            head_l = head.lower()

            # ---- Top-level control
            if indent == 0:

                # WHILE
                if head_l == "while":
                    if self.while_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "Nested WHILE not supported"))
                    if self.if_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "WHILE cannot start inside an open IF; close IF first"))
                    if self.try_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "WHILE cannot start inside an open TRY; close TRY first"))
                    cond = self._eval_condition_tokens(args, line_no)
                    # find matching endwhile to allow skipping when false
                    if not cond:
                        j = pc + 1
                        found = False
                        while j < n:
                            i2, raw2, tok2 = parse_tokens(lines[j], j + 1)
                            if i2 == 0 and tok2 and tok2[0].lower() == "endwhile":
                                found = True
                                break
                            j += 1
                        if not found:
                            raise SyntaxDeadBasicError(self._fmt(line_no, "missing 'endwhile' for this 'while'"))
                        pc = j + 1
                        continue
                    self.while_ctx = {"start_pc": pc, "cond_tokens": args}
                    pc += 1
                    continue

                if head_l == "endwhile":
                    if self.while_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'endwhile' without matching 'while'"))
                    cond = self._eval_condition_tokens(self.while_ctx["cond_tokens"], line_no)
                    if cond:
                        pc = self.while_ctx["start_pc"] + 1
                        continue
                    else:
                        self.while_ctx = None
                        pc += 1
                        continue

                # TRY/CATCH/ENDTRY
                if head_l == "try":
                    if self.try_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "Nested TRY not supported"))
                    if self.if_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "TRY cannot start inside an open IF; close IF first"))
                    if self.while_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "TRY cannot start inside an open WHILE; close WHILE first"))
                    self.try_ctx = {"has_error": False, "in_catch": False, "err_name": None, "err_msg": None}
                    pc += 1
                    continue

                if head_l == "catch":
                    if self.try_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'catch' without matching 'try'"))
                    if self.try_ctx["in_catch"]:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "multiple 'catch' not allowed"))
                    if len(args) > 1:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "catch takes zero or one var name"))
                    self.try_ctx["in_catch"] = True
                    self.try_ctx["err_name"] = (args[0] if args else None)
                    # assign err var now
                    self._enter_catch_if_needed()
                    pc += 1
                    continue

                if head_l == "endtry":
                    if self.try_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'endtry' without matching 'try'"))
                    self.try_ctx = None
                    pc += 1
                    continue

                # IF
                if head_l == "if":
                    if self.if_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "Nested IF not supported (previous IF missing 'endif'?)"))
                    if self.while_ctx is not None:
                        pass
                    if self.try_ctx is not None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "IF cannot start inside an open TRY; close TRY first"))
                    cond = self._eval_condition_tokens(args, line_no)
                    self.if_ctx = {"cond_true": cond, "in_else": False}
                    pc += 1
                    continue

                if head_l == "else":
                    if self.if_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'else' without matching 'if'"))
                    if self.if_ctx["in_else"]:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "multiple 'else' not allowed"))
                    self.if_ctx["in_else"] = True
                    pc += 1
                    continue

                if head_l == "endif":
                    if self.if_ctx is None:
                        raise SyntaxDeadBasicError(self._fmt(line_no, "'endif' without matching 'if'"))
                    self.if_ctx = None
                    pc += 1
                    continue

                # If a block is open, limit headers at top level
                if self.if_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no,
                        "Inside IF: expected an indented body line (TAB/4 spaces), 'else', or 'endif'"))
                if self.try_ctx is not None:
                    raise SyntaxDeadBasicError(self._fmt(line_no,
                        "Inside TRY: expected an indented body line (TAB/4 spaces), 'catch', or 'endtry'"))

                # Declarations / Commands
                if head_l in self.type_keywords:
                    self.cmd_declare(head_l, args, line_no)
                    pc += 1
                    continue
                if head_l not in self.commands:
                    raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                self.commands[head_l](args, line_no)
                pc += 1
                continue

            # ---- Indented body line (IF, WHILE, TRY)
            if indent == 1:
                if head_l in {"if", "else", "endif", "while", "endwhile", "try", "catch", "endtry"}:
                    raise SyntaxDeadBasicError(self._fmt(line_no, f"'{head_l}' must be at top level (no indent)"))

                # IF body?
                if self.if_ctx is not None:
                    if not self._should_execute_if_body_line():
                        pc += 1
                        continue
                    if head_l in self.type_keywords:
                        self.cmd_declare(head_l, args, line_no)
                    else:
                        if head_l not in self.commands:
                            raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                        self.commands[head_l](args, line_no)
                    pc += 1
                    continue

                # WHILE body?
                if self.while_ctx is not None:
                    if head_l in self.type_keywords:
                        self.cmd_declare(head_l, args, line_no)
                    else:
                        if head_l not in self.commands:
                            raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                        self.commands[head_l](args, line_no)
                    pc += 1
                    continue

                # TRY body?
                if self.try_ctx is not None:
                    if self._should_execute_try_body_line():
                        try:
                            if head_l in self.type_keywords:
                                self.cmd_declare(head_l, args, line_no)
                            else:
                                if head_l not in self.commands:
                                    raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                                self.commands[head_l](args, line_no)
                        except DeadBasicError as e:
                            self.try_ctx["has_error"] = True
                            self.try_ctx["err_msg"] = str(e)
                        except Exception as e:
                            self.try_ctx["has_error"] = True
                            self.try_ctx["err_msg"] = f"Internal error: {e}"
                        pc += 1
                        continue
                    elif self._should_execute_catch_body_line():
                        # ensure err var present
                        self._enter_catch_if_needed()
                        if head_l in self.type_keywords:
                            self.cmd_declare(head_l, args, line_no)
                        else:
                            if head_l not in self.commands:
                                raise SyntaxDeadBasicError(self._fmt(line_no, f"unknown command: {head}"))
                            self.commands[head_l](args, line_no)
                        pc += 1
                        continue
                    else:
                        # inside TRY but not active section -> skip
                        pc += 1
                        continue

                # Indent but no block => syntax error
                raise SyntaxDeadBasicError(self._fmt(line_no,
                    "You are missing the required 'while/if/try' before this indented line"))

        # End of file: check for dangling blocks
        if self.if_ctx is not None:
            raise SyntaxDeadBasicError(self._fmt(n, "file ended but 'endif' is missing"))
        if self.while_ctx is not None:
            raise SyntaxDeadBasicError(self._fmt(n, "file ended but 'endwhile' is missing"))
        if self.try_ctx is not None:
            raise SyntaxDeadBasicError(self._fmt(n, "file ended but 'endtry' is missing"))

# ---------- CLI / REPL ----------
def usage():
    print(
        f"DeadBasic.BA v{VERSION}\n"
        "Usage:\n"
        "  python deadbasic.py <program.ba>\n"
        "  python deadbasic.py        # REPL (no multi-line while)\n"
        "\n"
        "Notes:\n"
        "  - Decls: int x 5 | long big 999999 | double pi 3.14 | str name \"Ryan\"\n"
        "  - Cmds : printtext ... | showvars | openfile \"file.ba\" | add a b\n"
        "  - IF   : if <lhs> <op> <rhs> | if not <val> ; ops: = != < > <= >=\n"
        "  - WHILE: while <cond> ... endwhile   (no nesting; body uses ONE TAB or FOUR SPACES)\n"
        "  - TRY  : try ... catch [errVar] ... endtry   (no nesting; body uses ONE TAB or FOUR SPACES)\n"
        "  - Comments start with # or ``\n"
    )

def repl():
    print(f"DeadBasic.BA Console v{VERSION} — Type exit to exit.")
    db = DeadBasic()
    line_no = 0
    user = getpass.getuser()
    try:
        while True:
            line_no += 1
            line = input(f"DB {user}> ")
            if line.strip().lower() in {"exit", "quit"}:
                break
            try:
                db.execute_line(line, line_no)
            except DeadBasicError as e:
                print(e)
            except Exception as e:
                print(f"Internal error: {e}")
                traceback.print_exc()
    except (EOFError, KeyboardInterrupt):
        print("\nbye")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        repl()
    elif len(sys.argv) == 2:
        prog = pathlib.Path(sys.argv[1])
        db = DeadBasic()
        try:
            db.run_file(prog)
        except DeadBasicError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Internal error: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)
    else:
        usage()
        sys.exit(2)
