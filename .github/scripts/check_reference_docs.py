#!/usr/bin/env python3
"""Checks the reference pages in docs/Reference against the sources, and the relative links of README.md and docs/.

Usage:
  check_reference_docs.py [--release VERSION] [REPOSITORY_ROOT]

Prints one line per problem (`path:line: message`) and exits with 1 when there is any. The rules are those of
docs/conventions.md, "Documentation":
- Every public member of a public type of the library (src/Maple.Result.Serialization.SystemTextJson) has a page; a member marked `[Obsolete]` has none.
- A type page links to the file (or files) of its type, with no line; its declaration is the one in the source,
  without `partial`.
- Every other `Source:` link opens the line of the declaration that the page documents, and is labelled with the
  file name.
- A source link opens `main` or the tag of a release (docs/releasing.md):
  - a link to `main` is checked against the working tree;
  - a link to a tag that exists is checked against the file at that tag (`git show`), and the declaration that it
    opens has to be in the working tree unchanged: a member that changed since the release links to `main`;
  - a link to a tag that does not exist yet is the release being prepared: it is checked against the working tree,
    and every such link names the same tag.
  With `--release VERSION` (the guard of the Draft release workflow), every source link has to name the tag of that
  version, `vVERSION`.
- The signature block under a link is that declaration, without `async` and `partial`. It shows the attributes of
  the code (e.g., `[OverloadResolutionPriority]`), except those that the .NET API reference leaves out: the ones of
  the nullable analysis (e.g., `[MemberNotNullWhen]`, `[NotNullWhen]`) and the ones for the debugger.
- A heading with a parameter list, and the "Type Parameters", "Parameters", "Returns" and "Property Value" sections
  where a page has them, agree with the signature. Types are written with their .NET names (`String`, `Boolean`),
  a nullable value type as `Nullable<T>`, and a nullable reference type without the `?`.
- The "Overloads" table of a page has a row for each overload, the member tables of a type page are in alphabetical
  order, and a link that names a member with its parameters is written as the heading that it opens.
- Every relative link and anchor in README.md and docs/ resolves, and no link to learn.microsoft.com has a locale.

A line added above a documented member moves its declaration, so the links below it fail until they are updated.

Python 3 without packages, as the other scripts of this folder.
"""

import html
import os
import re
import subprocess
import sys

RELEASE_TAG = re.compile(r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
SOURCE_LINK = re.compile(
    r'<a href="https://github\.com/TomMaple/Maple\.Result\.Serialization\.SystemTextJson/blob/([^/"]+)/([^"#]+)(?:#L(\d+))?"[^>]*>([^<]*)</a>')
MARKDOWN_LINK = re.compile(r"(?<!!)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(([^)\s]+)\)")
TYPE_PAGE_TITLE = re.compile(r"^# (.+) (Class|Record|Struct|Interface|Enum)$")
LOCALE_LINK = re.compile(r"learn\.microsoft\.com/[a-z]{2}-[a-z]{2}/")

ALIASES = {
    "bool": "Boolean", "byte": "Byte", "sbyte": "SByte", "char": "Char", "decimal": "Decimal", "double": "Double",
    "float": "Single", "int": "Int32", "uint": "UInt32", "nint": "IntPtr", "nuint": "UIntPtr", "long": "Int64",
    "ulong": "UInt64", "short": "Int16", "ushort": "UInt16", "object": "Object", "string": "String", "void": "Void",
}
# The value types that the public API uses: a `?` on them is a Nullable<T>, on any other type it is an annotation.
VALUE_TYPES = {
    "Boolean", "Byte", "SByte", "Char", "Decimal", "Double", "Single", "Int32", "UInt32", "IntPtr", "UIntPtr",
    "Int64", "UInt64", "Int16", "UInt16", "ErrorUri", "ErrorCategory",
}
MODIFIERS = {
    "public", "static", "sealed", "partial", "override", "virtual", "abstract", "readonly", "new", "async", "const",
}
PARAMETER_MODIFIERS = ("this", "params", "out", "in", "ref", "scoped")
# The attributes that a declaration leaves out, as the .NET API reference does: those of the nullable analysis and
# those for the debugger. Every other attribute of the code is shown (e.g., [OverloadResolutionPriority]).
HIDDEN_ATTRIBUTES = {
    "AllowNull", "DisallowNull", "MaybeNull", "MaybeNullWhen", "NotNull", "NotNullWhen", "NotNullIfNotNull",
    "MemberNotNull", "MemberNotNullWhen", "DoesNotReturn", "DoesNotReturnIf",
    "DebuggerDisplay", "DebuggerTypeProxy", "DebuggerBrowsable", "DebuggerStepThrough", "DebuggerHidden",
    "DebuggerNonUserCode",
}
# The order of the member tables of a type page: punctuation first, in this order, then digits and letters.
SORT_PUNCTUATION = " ,()<>[]."
MEMBER_TABLES = ("Constructors", "Fields", "Properties", "Methods", "Operators", "Events")


# ---------------------------------------------------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------------------------------------------------

def squeeze(text):
    return re.sub(r"\s+", "", text)


def attribute_name(attribute):
    """`OverloadResolutionPriority` for `System.Runtime.CompilerServices.OverloadResolutionPriority(1)`."""
    name = re.match(r"[A-Za-z_.]+", attribute).group(0).split(".")[-1]
    return name[:-len("Attribute")] if name.endswith("Attribute") and name != "Attribute" else name


def shown_attributes(attributes):
    return sorted(a for a in attributes if attribute_name(a) not in HIDDEN_ATTRIBUTES)


def table_order(label):
    """The sort key of a row of a member table: the .NET API reference lists `Send(…)` before `SendAsync(…)`."""
    return [(0, SORT_PUNCTUATION.index(char)) if char in SORT_PUNCTUATION else (1, char.lower()) for char in label]


def plain(markdown):
    """The text of a heading or a type line: links replaced by their text, entities decoded, no code marks."""
    text = MARKDOWN_LINK.sub(r"\1", markdown)
    return html.unescape(text).replace("`", "").strip()


def split_top(text, separator=","):
    """Splits at the separators that are outside every bracket."""
    parts, depth, current = [], 0, ""
    for index, char in enumerate(text):
        if char in "<([{":
            depth += 1
        elif char in ">)]}" and not (char == ">" and text[index - 1:index] == "="):
            depth -= 1
        if char == separator and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    if current.strip():
        parts.append(current)
    return [part.strip() for part in parts]


def matching(text, start):
    """The index of the bracket that closes the one at `start`; quotes are skipped."""
    pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
    opening, closing, depth, index = text[start], pairs[text[start]], 0, start
    while index < len(text):
        char = text[index]
        if char == '"':
            index = text.index('"', index + 1)
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


# ---------------------------------------------------------------------------------------------------------------------
# Types, as the pages write them
# ---------------------------------------------------------------------------------------------------------------------

def page_type(text):
    """A C# type as the pages write it: `string?` is `String`, `bool?` is `Nullable<Boolean>`."""
    text = text.strip()
    arrays = ""
    while text.endswith("]") and re.search(r"\[,*\]$", text):
        rank = re.search(r"\[,*\]$", text).group(0)
        arrays = rank + arrays
        text = text[:-len(rank)].strip()
    nullable = text.endswith("?")
    if nullable:
        text = text[:-1].strip()

    if text.startswith("("):
        elements = []
        for element in split_top(text[1:matching(text, 0)]):
            # A tuple element may have a name after its type.
            named = re.match(r"^(.*\S)\s+[A-Za-z_][A-Za-z0-9_]*$", element)
            elements.append(page_type(named.group(1) if named else element))
        core, is_value = "(" + ", ".join(elements) + ")", True
    else:
        opening = text.find("<")
        if opening < 0:
            name, arguments = text, None
        else:
            name, arguments = text[:opening].strip(), split_top(text[opening + 1:matching(text, opening)])
        name = ALIASES.get(name, name)
        is_value = name in VALUE_TYPES and arguments is None
        core = name if arguments is None else name + "<" + ", ".join(page_type(a) for a in arguments) + ">"

    if nullable and is_value:
        core = "Nullable<" + core + ">"
    return core + arrays


# ---------------------------------------------------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------------------------------------------------

def take_attributes(text):
    """Splits the leading attributes off a declaration."""
    attributes = []
    text = text.strip()
    while text.startswith("["):
        end = matching(text, 0)
        attributes.append(squeeze(text[1:end]))
        text = text[end + 1:].strip()
    return attributes, text


def parse_parameter(text):
    attributes, text = take_attributes(text)
    default = None
    pieces = split_top(text, "=")
    if len(pieces) > 1:
        text, default = pieces[0], squeeze("=".join(pieces[1:]))
    modifiers = []
    while text.split(" ", 1)[0] in PARAMETER_MODIFIERS:
        modifier, text = text.split(" ", 1)
        modifiers.append(modifier)
        text = text.strip()
    match = re.match(r"^(.*\S)\s+(@?[A-Za-z_][A-Za-z0-9_]*)$", text.strip(), re.S)
    parameter = {"modifiers": modifiers, "type": text.strip(), "name": "", "default": default,
                 "attributes": attributes}
    if match:
        parameter.update(type=match.group(1), name=match.group(2))
    return parameter


def parse_declaration(text):
    """Parses a member declaration (a signature block of a page, or the lines of the source) into its parts."""
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"\s+", " ", text).strip().rstrip(";").strip()
    attributes, text = take_attributes(text)

    modifiers = []
    while True:
        word, _, rest = text.partition(" ")
        if word not in MODIFIERS:
            break
        modifiers.append(word)
        text = rest.strip()

    declaration = {"attributes": attributes, "modifiers": modifiers, "kind": "other", "accessors": None}

    operator = re.match(r"^(implicit|explicit) operator (.*)$", text)
    if operator:
        text = operator.group(2)

    # The parameter list starts at the first parenthesis that is outside the angle brackets.
    depth, opening = 0, -1
    for index, char in enumerate(text):
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        elif char == "(" and depth == 0:
            opening = index
            break
        elif char in "{=" and depth == 0:
            break

    if opening < 0:
        # A property, a field or a constant: `Type Name`, then accessors, a body or a value.
        head = re.split(r"\s*(?:\{|=>|=)", text, maxsplit=1)[0].strip()
        match = re.match(r"^(.*\S)\s+([A-Za-z_][A-Za-z0-9_]*)$", head)
        if match:
            declaration.update(kind="property", type=match.group(1), name=match.group(2))
            brace = text.find("{")
            if brace >= 0:
                body = text[brace:matching(text, brace) + 1]
                declaration["accessors"] = sorted(set(re.findall(r"\b(get|set|init)\b", body)))
            elif "=>" in text:
                declaration["accessors"] = ["get"]
        return declaration

    closing = matching(text, opening)
    head, tail = text[:opening].strip(), text[closing + 1:].strip()
    # A constructor may call another one: that is not part of its signature.
    tail = re.sub(r"^:\s*(this|base)\s*\(.*\)\s*$", "", tail).strip()
    parameters = [parse_parameter(p) for p in split_top(text[opening + 1:closing])]

    if operator:
        declaration.update(kind="operator", name=operator.group(1).capitalize(), type=head, generics=[])
    else:
        match = re.match(r"^(?:(.*\S)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(<[^()]*>)?$", head)
        if not match:
            return declaration
        generics = split_top(match.group(3)[1:-1]) if match.group(3) else []
        declaration.update(kind="method" if match.group(1) else "constructor", type=match.group(1),
                           name=match.group(2), generics=generics)
    declaration.update(parameters=parameters, constraints=squeeze(tail))
    return declaration


def canonical(declaration):
    """What two declarations must have in common: everything except the attributes, `async` and `partial`."""
    modifiers = [m for m in declaration["modifiers"] if m not in ("async", "partial")]
    parts = [" ".join(modifiers), declaration["kind"], squeeze(declaration.get("type") or ""),
             declaration.get("name", "")]
    if declaration["kind"] == "property":
        parts.append(",".join(declaration["accessors"] or []))
    elif declaration["kind"] != "other":
        parts.append(",".join(declaration["generics"]))
        for parameter in declaration["parameters"]:
            parts.append(" ".join(parameter["modifiers"]) + ":" + squeeze(parameter["type"]) + ":" +
                         parameter["name"] + ":" + str(parameter["default"]))
        parts.append(declaration["constraints"])
    return "|".join(parts)


def expected_heading(declaration):
    """The heading of a member with a parameter list, e.g. `Then<T, TNext>(Result<T>, Func<T, TNext>)`."""
    types = [page_type(p["type"]) for p in declaration["parameters"]]
    if declaration["kind"] == "operator":
        return f"{declaration['name']}({types[0]} to {page_type(declaration['type'])})"
    generics = "<" + ", ".join(declaration["generics"]) + ">" if declaration["generics"] else ""
    return declaration["name"] + generics + "(" + ", ".join(types) + ")"


def read_source_declaration(lines, number):
    """The declaration that starts at the 1-based line `number`, with the attributes above it."""
    attributes = []
    above = number - 2
    while above >= 0 and lines[above].strip().startswith("["):
        attributes.insert(0, lines[above].strip())
        above -= 1

    collected, depth = [], 0
    for line in lines[number - 1:]:
        stripped = line.strip()
        if stripped == "{" and depth == 0 and collected:
            # The body of a method starts here; the accessors of a property are part of its declaration.
            if "(" in " ".join(collected):
                break
        collected.append(line)
        depth += stripped.count("{") - stripped.count("}")
        text = " ".join(collected)
        if "(" in text.split("{")[0].split("=>")[0]:
            # A method: it ends at its body.
            if re.search(r"\)\s*(where\b[^{;]*)?\s*(=>|;)", re.sub(r"\s+", " ", text)) or stripped.endswith("{"):
                break
        elif depth == 0 and (stripped.endswith(";") or stripped.endswith("}")):
            break

    text = " ".join(collected)
    if "(" in text.split("{")[0].split("=>")[0]:
        text = re.split(r"\s=>\s|\s\{\s*$", text, maxsplit=1)[0]
    return " ".join(attributes) + " " + text


# ---------------------------------------------------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------------------------------------------------

class Checker:
    def __init__(self, root, release=None):
        self.root = root
        self.release = release
        self.problems = []
        self.sources = {}
        self.declarations = {}
        self.documented = set()
        self.owner_generics = []
        self.prepared = {}
        self.tags = self.release_tags()

    def problem(self, path, line, message):
        self.problems.append(f"{path}:{line}: {message}")

    def release_tags(self):
        """The release tags of the repository (`vX.Y.Z`); none when it is not a git repository."""
        try:
            result = subprocess.run(["git", "-C", self.root, "tag", "--list", "v*"], capture_output=True, text=True,
                                    check=True)
        except (OSError, subprocess.CalledProcessError):
            return set()
        return {tag for tag in result.stdout.split() if RELEASE_TAG.match(tag)}

    def source(self, path, ref="main"):
        """The lines of a file in the working tree, or at a release tag; None when the file does not exist there."""
        key = (ref, path)
        if key not in self.sources:
            if ref in self.tags:
                result = subprocess.run(["git", "-C", self.root, "show", f"{ref}:{path}"], capture_output=True)
                text = result.stdout.decode("utf-8-sig") if result.returncode == 0 else None
            else:
                full = os.path.join(self.root, path)
                text = None
                if os.path.isfile(full):
                    with open(full, encoding="utf-8-sig") as file:
                        text = file.read()
            self.sources[key] = None if text is None else text.replace("\r\n", "\n").split("\n")
        return self.sources[key]

    def declaration_lines(self, path, ref="main"):
        """The lines of the public declarations of a file, by declaration (its attributes included), in their order:
        a file can declare the same member twice (e.g., `Error` of `Result` and of `Result<T>`)."""
        key = (ref, path)
        if key not in self.declarations:
            lines = self.source(path, ref) or []
            declarations = {}
            for index, line in enumerate(lines):
                if line.strip().startswith("public "):
                    declarations.setdefault(squeeze(read_source_declaration(lines, index + 1)), []).append(index + 1)
            self.declarations[key] = declarations
        return self.declarations[key]

    def current_line(self, path, ref, number):
        """The line of the working tree where the declaration at line `number` of the file at `ref` is now, unchanged
        (its attributes included): the same occurrence of the same declaration. None when it changed or was removed."""
        released = self.source(path, ref)
        if released is None or number > len(released):
            return None
        declaration = squeeze(read_source_declaration(released, number))
        released_lines = self.declaration_lines(path, ref).get(declaration, [])
        current_lines = self.declaration_lines(path).get(declaration, [])
        if number not in released_lines:
            return None
        occurrence = released_lines.index(number)
        return current_lines[occurrence] if occurrence < len(current_lines) else None

    def check_ref(self, path, line, ref):
        """A source link opens `main` or the tag of a release; with --release, the tag of that release."""
        if self.release and ref != self.release:
            self.problem(path, line, f"the source link opens '{ref}', not the tag of the release '{self.release}'")
        elif ref == "main" or ref in self.tags:
            return
        elif RELEASE_TAG.match(ref):
            # A tag that does not exist yet: the release being prepared, which has to be the same in every link.
            self.prepared.setdefault(ref, (path, line))
        else:
            self.problem(path, line, f"the source link opens '{ref}', not 'main' or the tag of a release (vX.Y.Z)")

    def check_prepared(self):
        """Every link to a tag that does not exist yet names the same one: the release being prepared."""
        if len(self.prepared) > 1:
            for ref, (path, line) in sorted(self.prepared.items()):
                self.problem(path, line, f"the source links name several releases that do not exist yet "
                                         f"({', '.join(sorted(self.prepared))}); this one names '{ref}'")

    # -- A reference page ---------------------------------------------------------------------------------------------

    def check_page(self, path):
        with open(os.path.join(self.root, path), encoding="utf-8") as file:
            lines = file.read().split("\n")

        title = lines[0] if lines else ""
        lowercase_kind = re.match(r"^# .+ (class|record|struct|interface|enum)$", title)
        if lowercase_kind:
            self.problem(path, 1, f"the kind in the title starts with a capital letter: "
                                  f"'{lowercase_kind.group(1).capitalize()}'")
        type_page = re.match(TYPE_PAGE_TITLE.pattern, title, re.I)

        # The type parameters of the declaring type, from a title such as `Result<T>.FromValue(T) Method`.
        owner = re.match(r"^# ([A-Za-z_][A-Za-z0-9_]*)<([^>]*)>\.", plain(title))
        self.owner_generics = split_top(owner.group(2)) if owner else []

        declaration_checked = False
        links = [(index, match) for index, line in enumerate(lines) for match in SOURCE_LINK.finditer(line)]
        for position, (index, match) in enumerate(links):
            ref, source_path, line_number, label = match.groups()
            on_source_line = lines[index].startswith("Source:")
            self.check_ref(path, index + 1, ref)
            released = ref in self.tags
            source = self.source(source_path, ref)

            if source is None:
                where = f" at {ref}" if released else ""
                self.problem(path, index + 1, f"the source link opens a file that does not exist{where}: {source_path}")
                continue
            if on_source_line and label.strip() != os.path.basename(source_path):
                self.problem(path, index + 1, f"the source link is labelled '{label}', not with the file name "
                                              f"'{os.path.basename(source_path)}'")

            if type_page and on_source_line and index < 12:
                if line_number:
                    self.problem(path, index + 1, "the source link of a type page opens the file, without a line")
                # A type in several files has one link for each; the declaration of the page is checked once.
                self.check_type_declaration(path, lines, index, type_page.group(1), source, source_path,
                                            not declaration_checked)
                declaration_checked = True
                continue

            if not line_number:
                self.problem(path, index + 1, "the source link of a member has no line")
                continue
            if int(line_number) > len(source):
                self.problem(path, index + 1, f"the source link opens line {line_number}, after the end of the file")
                continue

            # The page documents the member at this line of the working tree: for a link to a release, the line where
            # the same declaration is now. A declaration that changed since the release is linked to main.
            current = self.current_line(source_path, ref, int(line_number)) if released else int(line_number)
            if current is None:
                self.problem(path, index + 1, f"the declaration at {os.path.basename(source_path)}#L{line_number} of "
                                              f"{ref} is not in the code any more, or changed: link the member to main")
            else:
                self.documented.add((source_path, current))

            if not on_source_line:
                # A link inside a table or a sentence, labelled with the member: the line has to declare it.
                declared = source[int(line_number) - 1]
                if not re.search(rf"\b{re.escape(label.strip())}\b", declared) or not declared.strip().startswith(
                        "public"):
                    self.problem(path, index + 1, f"line {line_number} of {os.path.basename(source_path)} does not "
                                                  f"declare '{label}'")
                continue

            end = links[position + 1][0] if position + 1 < len(links) else len(lines)
            self.check_member(path, lines, index, end, source, source_path, int(line_number))

        self.check_overloads_table(path, lines)
        if type_page:
            self.check_member_tables(path, lines)

    def check_member_tables(self, path, lines):
        """The member tables of a type page are in alphabetical order, as in the .NET API reference."""
        heading, rows = None, []
        for index, line in enumerate(lines + ["## End"]):
            if line.startswith("## "):
                labels = [label for label, _ in rows]
                ordered = sorted(labels, key=table_order)
                if heading in MEMBER_TABLES and labels != ordered:
                    first = next(i for i, (a, b) in enumerate(zip(labels, ordered)) if a != b)
                    self.problem(path, rows[first][1], f"the table '{heading}' is not in alphabetical order: "
                                                       f"'{ordered[first]}' comes here")
                heading, rows = line[3:].strip(), []
            elif line.startswith("| ["):
                link = MARKDOWN_LINK.match(line[2:])
                rows.append((plain(link.group(1)) if link else plain(line), index + 1))

    def check_overloads_table(self, path, lines):
        """The "Overloads" table of a page has one row for each overload that the page documents."""
        if "## Overloads" not in lines:
            return
        start = lines.index("## Overloads")
        rows = 0
        for line in lines[start + 1:]:
            if line.startswith("## "):
                break
            rows += line.startswith("| [") and "](#" in line
        sections = sum(1 for index, line in enumerate(lines)
                       if line.startswith("Source:") and index > start and lines[index - 1].startswith("## "))
        if rows != sections:
            self.problem(path, start + 1, f"the table lists {rows} overloads, and the page documents {sections}")

    def check_type_declaration(self, path, lines, index, name, source, source_path, check_block):
        name = plain(name)
        short_name = name.split("<")[0]
        pattern = re.compile(rf"^public .*\b(class|record|struct|interface|enum)\b.*\b{re.escape(short_name)}\b")
        number = next((n for n, line in enumerate(source) if pattern.match(line) and self.same_arity(line, name)),
                      None)
        if number is None:
            self.problem(path, index + 1, f"{os.path.basename(source_path)} does not declare the type '{name}'")
            return
        declared, attributes = source[number], []
        while number > 0 and source[number - 1].strip().startswith("["):
            number -= 1
            attributes += take_attributes(source[number])[0]

        block = self.code_block(lines, index + 1, len(lines)) if check_block else None
        if block is None:
            return
        block_line, block_text = block
        page_attributes, page_declaration = take_attributes(re.sub(r"\s+", " ", block_text))
        if re.search(r"\bpartial\b", page_declaration):
            self.problem(path, block_line, "the declaration shows 'partial', which is not part of the API")
        self.check_attributes(path, block_line, page_attributes, attributes, "the declaration")

        # A record may declare its properties in a parameter list, and a part of a type may leave out the base types:
        # neither changes what the page declares.
        declared = re.sub(r"\bpartial ", "", declared.strip())
        declared = re.sub(rf"({re.escape(short_name)}(?:<[^>]*>)?)\(.*\)", r"\1", declared)
        if squeeze(re.sub(r"\bpartial ", "", page_declaration)) != squeeze(declared):
            self.problem(path, block_line, f"the declaration is not the one of the code: '{declared}'")

    @staticmethod
    def same_arity(line, name):
        generic = re.search(rf"\b{re.escape(name.split('<')[0])}<", line) is not None
        return generic == ("<" in name)

    @staticmethod
    def code_block(lines, start, end):
        """The first C# block between two lines: its 1-based first line and its text."""
        for index in range(start, min(end, len(lines))):
            if lines[index].strip().startswith("```csharp"):
                body = []
                for line in lines[index + 1:]:
                    if line.strip().startswith("```"):
                        break
                    body.append(line)
                return index + 2, "\n".join(body)
            if lines[index].startswith("## ") and not lines[index].startswith("## Definition"):
                return None
        return None

    # -- A member -----------------------------------------------------------------------------------------------------

    def check_member(self, path, lines, index, end, source, source_path, line_number):
        declared = source[line_number - 1].strip()
        if not declared.startswith("public"):
            self.problem(path, index + 1, f"line {line_number} of {os.path.basename(source_path)} is not a "
                                          f"declaration: '{declared[:60]}'")
            return

        block = self.code_block(lines, index + 1, end)
        if block is None:
            return
        block_line, block_text = block
        page = parse_declaration(block_text)
        code = parse_declaration(read_source_declaration(source, line_number))

        for word in ("async", "partial"):
            if word in page["modifiers"]:
                self.problem(path, block_line, f"the signature shows '{word}', which is not part of the signature")

        self.check_attributes(path, block_line, page["attributes"], code["attributes"], "the signature")
        for page_parameter, code_parameter in zip(page.get("parameters", []), code.get("parameters", [])):
            self.check_attributes(path, block_line, page_parameter["attributes"], code_parameter["attributes"],
                                  f"the parameter `{code_parameter['name']}`")

        if canonical(page) != canonical(code):
            self.problem(path, block_line, f"the signature is not the declaration at "
                                           f"{os.path.basename(source_path)}#L{line_number}")
            return
        if code["kind"] == "other":
            return

        self.check_heading(path, lines, index, code)
        self.check_sections(path, lines, index, end, code)

    def check_attributes(self, path, line, on_page, in_code, where):
        """A declaration shows the attributes of the code, except those that the .NET API reference leaves out."""
        expected = shown_attributes(in_code)
        for attribute in sorted(on_page):
            if attribute_name(attribute) in HIDDEN_ATTRIBUTES:
                self.problem(path, line, f"{where} shows [{attribute}], which the pages leave out")
            elif attribute not in expected:
                self.problem(path, line, f"{where} shows [{attribute}], which the code does not have")
        for attribute in expected:
            if attribute not in on_page:
                self.problem(path, line, f"{where} does not show [{attribute}], which the code has")

    def check_heading(self, path, lines, index, code):
        if code["kind"] == "property":
            return
        for above in range(index, -1, -1):
            if lines[above].startswith("## ") and not lines[above].startswith("## Definition"):
                heading = plain(lines[above][3:])
                break
            if lines[above].startswith("# "):
                heading = re.sub(r"\s+(Methods?|Constructors?|Operators?)$", "", plain(lines[above][2:]))
                # `Type.Member(…)`: the name of the type is not part of the comparison.
                opening = heading.find("(")
                if opening >= 0 and "." in heading[:opening]:
                    heading = heading[heading[:opening].rindex(".") + 1:]
                break
        else:
            return
        if "(" not in heading:
            return
        expected = expected_heading(code)
        if squeeze(heading) != squeeze(expected):
            self.problem(path, above + 1, f"the heading is not the signature: '{expected}'")

    def check_sections(self, path, lines, index, end, code):
        type_parameters, parameters, returned, section = [], [], None, None
        for offset in range(index + 1, end):
            line = lines[offset]
            if line.startswith("## ") and offset > index + 1:
                break
            if line.startswith("### "):
                section = line[4:].strip()
                continue
            if section in ("Returns", "Property Value") and returned is None and line.strip():
                if line.startswith("#### ") or not line.startswith("#"):
                    returned = (plain(line[5:] if line.startswith("#### ") else line), offset + 1)
                continue
            if not line.startswith("#### "):
                continue
            if section == "Type Parameters":
                type_parameters.append((plain(line[5:]), offset + 1))
            elif section == "Parameters":
                match = re.match(r"^`([^`]+)`\s*(.*)$", line[5:].strip())
                if match:
                    parameters.append((match.group(1), plain(match.group(2)), offset + 1))

        if code["kind"] == "property":
            if returned and squeeze(returned[0]) != squeeze(page_type(code["type"])):
                self.problem(path, returned[1], f"the property value is a '{page_type(code['type'])}'")
            return

        # A member of a generic type may describe the type parameters of its type.
        listed = [name for name, _ in type_parameters]
        if type_parameters and listed != code["generics"] and not (not code["generics"]
                                                                   and listed == self.owner_generics):
            self.problem(path, type_parameters[0][1], f"the type parameters of the signature are "
                                                      f"{', '.join(code['generics']) or 'none'}")
        if parameters:
            names = [parameter["name"] for parameter in code["parameters"]]
            if [name for name, _, _ in parameters] != names:
                self.problem(path, parameters[0][2], f"the parameters of the signature are {', '.join(names)}")
            else:
                for parameter, (name, written, line) in zip(code["parameters"], parameters):
                    expected = page_type(parameter["type"])
                    if squeeze(written) != squeeze(expected):
                        self.problem(path, line, f"the type of `{name}` is '{expected}'")
        if returned and code["kind"] == "method":
            expected = page_type(code["type"])
            if squeeze(returned[0]) != squeeze(expected):
                self.problem(path, returned[1], f"the method returns a '{expected}'")

    # -- The members without a page -----------------------------------------------------------------------------------

    def check_undocumented(self, folder):
        """Every public member of a public type has a page; a member marked `[Obsolete]` has none."""
        type_declaration = re.compile(r"^public .*\b(class|record|struct|interface|enum)\b")
        for directory, _, files in os.walk(os.path.join(self.root, folder)):
            if os.path.basename(directory) in ("bin", "obj"):
                continue
            for name in sorted(files):
                if not name.endswith(".cs"):
                    continue
                path = os.path.relpath(os.path.join(directory, name), self.root).replace("\\", "/")
                lines = self.source(path)
                if not any(type_declaration.match(line) for line in lines):
                    continue
                for index, line in enumerate(lines):
                    stripped = line.strip()
                    if not stripped.startswith("public ") or type_declaration.match(stripped):
                        continue
                    attributes, above = [], index - 1
                    while above >= 0 and lines[above].strip().startswith("["):
                        attributes.append(lines[above].strip())
                        above -= 1
                    if any(attribute.startswith("[Obsolete") for attribute in attributes):
                        continue
                    if (path, index + 1) not in self.documented:
                        self.problem(path, index + 1, f"no reference page documents '{stripped[:80]}'")

    # -- Links and anchors --------------------------------------------------------------------------------------------

    @staticmethod
    def slug(heading):
        """The anchor that GitHub gives a heading."""
        text = html.unescape(re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)).strip().lower().replace("`", "")
        return "".join("-" if char == " " else char for char in text if char.isalnum() or char in "-_ ")

    def anchors(self, path, cache={}):
        """The anchors of a file with the text of their headings; the empty anchor is the title."""
        if path not in cache:
            counts, headings, fenced = {}, {}, False
            with open(path, encoding="utf-8") as file:
                for line in file.read().split("\n"):
                    if line.strip().startswith("```"):
                        fenced = not fenced
                    heading = None if fenced else re.match(r"#{1,6}\s+(.*)$", line)
                    if heading:
                        slug = self.slug(heading.group(1))
                        number = counts.get(slug, 0)
                        counts[slug] = number + 1
                        headings[slug if number == 0 else f"{slug}-{number}"] = plain(heading.group(1))
                        headings.setdefault("", plain(heading.group(1)))
            cache[path] = headings
        return cache[path]

    @staticmethod
    def member(text):
        """The member that a heading or a link text names: without the type before it and the kind after it."""
        text = re.sub(r"\s+(Methods?|Constructors?|Operators?|Property)$", "", text)
        opening = text.find("(")
        if opening >= 0 and "." in text[:opening]:
            text = text[text[:opening].rindex(".") + 1:]
        return squeeze(text)

    def check_links(self, path):
        full = os.path.join(self.root, path)
        with open(full, encoding="utf-8") as file:
            lines = file.read().split("\n")
        reference = path.startswith("docs/Reference/")
        fenced = False
        for index, line in enumerate(lines):
            if line.strip().startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            if LOCALE_LINK.search(line):
                self.problem(path, index + 1, "a link to learn.microsoft.com has a locale (e.g., '/en-us/')")
            for match in MARKDOWN_LINK.finditer(line):
                target = match.group(2)
                if re.match(r"[a-z]+:", target):
                    continue
                file_part, _, fragment = target.partition("#")
                target_path = full if not file_part else os.path.normpath(
                    os.path.join(os.path.dirname(full), file_part))
                if not os.path.exists(target_path):
                    self.problem(path, index + 1, f"the link opens a file that does not exist: {target}")
                    continue
                if not target_path.endswith(".md"):
                    continue
                headings = self.anchors(target_path)
                if fragment and fragment.lower() not in headings:
                    self.problem(path, index + 1, f"the link opens an anchor that does not exist: {target}")
                    continue
                # A link that names a member with its parameters has to name it as the heading it opens does.
                label, heading = plain(match.group(1)), headings.get(fragment.lower(), "")
                if reference and "(" in label and "(" in heading and self.member(label) != self.member(heading):
                    self.problem(path, index + 1, f"the link text '{label}' is not the heading it opens: "
                                                  f"'{heading}'")


def markdown_files(root, folder):
    for directory, _, files in os.walk(os.path.join(root, folder)):
        for name in sorted(files):
            if name.endswith(".md"):
                yield os.path.relpath(os.path.join(directory, name), root).replace("\\", "/")


def release_tag(version):
    """The tag of a release version (`3.0.0` or `v3.0.0` gives `v3.0.0`); None when it is not a version."""
    tag = version if version.startswith("v") else f"v{version}"
    return tag if RELEASE_TAG.match(tag) else None


def main(arguments):
    release = None
    if arguments[:1] == ["--release"]:
        if len(arguments) < 2 or release_tag(arguments[1]) is None:
            sys.exit(__doc__)
        release, arguments = release_tag(arguments[1]), arguments[2:]
    if len(arguments) > 1 or (arguments and arguments[0].startswith("-")):
        sys.exit(__doc__)
    root = arguments[0] if arguments else os.getcwd()
    if not os.path.isdir(os.path.join(root, "docs", "Reference")):
        sys.exit(f"No docs/Reference folder in '{root}'.")

    checker = Checker(root, release)
    pages = sorted(markdown_files(root, os.path.join("docs", "Reference")))
    for page in pages:
        checker.check_page(page)
    checker.check_prepared()
    checker.check_undocumented(os.path.join("src", "Maple.Result.Serialization.SystemTextJson"))
    linked = ["README.md"] + sorted(markdown_files(root, "docs"))
    for path in linked:
        checker.check_links(path)

    for problem in checker.problems:
        print(problem)
    print(f"{len(pages)} reference pages and the links of {len(linked)} files checked: "
          f"{len(checker.problems)} problem(s).", file=sys.stderr)
    sys.exit(1 if checker.problems else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
