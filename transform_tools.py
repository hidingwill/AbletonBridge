"""
Transform all @mcp.tool() functions in server.py to use @_tool_handler decorator.
"""
import re
import sys

INPUT = r"C:\Users\akioo\.claude-worktrees\ableton-bridge\nervous-almeida\MCP_Server\server.py"

with open(INPUT, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split("\n")

# ---- Step 1: Find all tool function ranges ----
# A tool starts with @mcp.tool() and its function body ends at the next
# @mcp.tool(), or another top-level def/class, or end-of-file.

# First, find all @mcp.tool() lines (0-indexed)
tool_deco_lines = [i for i, l in enumerate(lines) if l.strip() == "@mcp.tool()"]

print(f"Found {len(tool_deco_lines)} @mcp.tool() decorators")

# Already refactored tools (they already have @_tool_handler on the next line)
ALREADY_DONE = set()
for idx in tool_deco_lines:
    if idx + 1 < len(lines) and "@_tool_handler(" in lines[idx + 1]:
        ALREADY_DONE.add(idx)

print(f"Already refactored: {len(ALREADY_DONE)}")
print(f"Need to refactor: {len(tool_deco_lines) - len(ALREADY_DONE)}")

# ---- Step 2: Build error prefix for each tool ----
# We extract the error message from the except blocks.

def extract_error_prefix(func_lines):
    """Extract the error prefix from an existing error handler in the function."""
    for line in reversed(func_lines):
        stripped = line.strip()
        # Look for patterns like:
        # logger.error(f"Error doing X: {str(e)}")
        # return f"Error doing X: {str(e)}"
        # return "Error doing X. Please check..."
        # return f"Error doing X."
        m = re.search(r'(?:logger\.error|return)\s*\(?\s*f?"Error\s+(.+?)(?::\s*\{|\.|\s*Please)', stripped)
        if m:
            prefix = m.group(1).strip()
            # Clean up: remove trailing punctuation, quotes
            prefix = prefix.rstrip(".:\"'")
            return prefix
        # Also match: return "Error: Could not..." etc - skip these
        # Match: return f"Error {desc}: {str(e)}"
        m2 = re.search(r'return\s+f?"Error\s+(.+?)(?::\s*\{)', stripped)
        if m2:
            prefix = m2.group(1).strip().rstrip(".:\"'")
            return prefix
    return None


def find_outer_try(func_body_lines, func_indent):
    """Check if the function body starts with 'try:' and find matching except blocks.

    Returns (try_line_idx, except_blocks, has_standard_pattern) or None if no outer try.
    func_body_lines are the lines AFTER the def line (and docstring).
    """
    # Find the first non-empty, non-docstring line
    first_code = None
    for i, line in enumerate(func_body_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('"""') and not stripped.startswith("'''"):
            first_code = i
            break

    if first_code is None:
        return None

    if func_body_lines[first_code].strip() != "try:":
        return None

    return first_code


def get_func_name(lines, deco_idx):
    """Get function name from def line."""
    for i in range(deco_idx, min(deco_idx + 5, len(lines))):
        m = re.match(r'\s*def\s+(\w+)\s*\(', lines[i])
        if m:
            return m.group(1)
    return "unknown"


# ---- Step 3: Process each tool ----
# We'll work backwards to avoid line number shifts

changes = []  # list of (start_line, end_line, new_lines)

for tool_idx in tool_deco_lines:
    if tool_idx in ALREADY_DONE:
        continue

    func_name = get_func_name(lines, tool_idx)

    # Find the def line
    def_line_idx = None
    for i in range(tool_idx + 1, min(tool_idx + 5, len(lines))):
        if lines[i].strip().startswith("def "):
            def_line_idx = i
            break

    if def_line_idx is None:
        print(f"WARNING: Could not find def line for tool at line {tool_idx + 1}")
        continue

    # Find function indent
    func_indent = len(lines[def_line_idx]) - len(lines[def_line_idx].lstrip())
    body_indent = func_indent + 4  # Standard 4-space indent

    # Find the end of this function (next def at same or lower indent, or @mcp.tool, or end of file)
    func_end = len(lines) - 1
    for i in range(def_line_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped:
            continue
        line_indent = len(lines[i]) - len(lines[i].lstrip())
        # A line at func_indent or less that is a decorator, def, class, or comment section
        if line_indent <= func_indent and stripped and not stripped.startswith('#'):
            if stripped.startswith('@') or stripped.startswith('def ') or stripped.startswith('class '):
                func_end = i - 1
                break
        # Also break at section comments at column 0
        if line_indent == 0 and stripped.startswith('#'):
            # Check if this is followed by @mcp.tool or a def
            # Only break if it's a section divider (common pattern: # ==== or # ---)
            if '====' in stripped or '----' in stripped:
                func_end = i - 1
                break

    # Trim trailing blank lines
    while func_end > def_line_idx and not lines[func_end].strip():
        func_end -= 1

    # Get all function lines
    func_lines = lines[tool_idx:func_end + 1]

    # Extract the error prefix
    error_prefix = extract_error_prefix(func_lines)
    if error_prefix is None:
        # Derive from function name
        error_prefix = func_name.replace("_", " ")
        # Convert to gerund-like: "get_session_info" -> "getting session info"
        words = func_name.split("_")
        if words[0] in ("get", "set", "create", "delete", "add", "load", "fire", "stop",
                         "start", "clear", "duplicate", "quantize", "transpose", "search",
                         "refresh", "apply", "capture", "freeze", "unfreeze", "arm", "disarm",
                         "group", "reverse", "analyze", "observe", "compare", "morph",
                         "snapshot", "restore", "list", "generate", "navigate", "select",
                         "trigger", "move", "manage", "preview", "crop", "remove", "jump",
                         "copy", "insert"):
            verb = words[0]
            gerund_map = {
                "get": "getting", "set": "setting", "create": "creating", "delete": "deleting",
                "add": "adding", "load": "loading", "fire": "firing", "stop": "stopping",
                "start": "starting", "clear": "clearing", "duplicate": "duplicating",
                "quantize": "quantizing", "transpose": "transposing", "search": "searching",
                "refresh": "refreshing", "apply": "applying", "capture": "capturing",
                "freeze": "freezing", "unfreeze": "unfreezing", "arm": "arming",
                "disarm": "disarming", "group": "grouping", "reverse": "reversing",
                "analyze": "analyzing", "observe": "observing", "compare": "comparing",
                "morph": "morphing", "snapshot": "snapshotting", "restore": "restoring",
                "list": "listing", "generate": "generating", "navigate": "navigating",
                "select": "selecting", "trigger": "triggering", "move": "moving",
                "manage": "managing", "preview": "previewing", "crop": "cropping",
                "remove": "removing", "jump": "jumping", "copy": "copying",
                "insert": "inserting",
            }
            gerund = gerund_map.get(verb, verb + "ing")
            rest = " ".join(words[1:])
            error_prefix = f"{gerund} {rest}".strip()

    # Find the docstring range
    docstring_end = def_line_idx
    in_docstring = False
    docstring_delim = None
    for i in range(def_line_idx + 1, func_end + 1):
        stripped = lines[i].strip()
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_delim = stripped[:3]
                if stripped.count(docstring_delim) >= 2 and len(stripped) > 3:
                    # Single-line docstring
                    docstring_end = i
                    break
                else:
                    in_docstring = True
            else:
                break  # No docstring
        else:
            if docstring_delim in stripped:
                docstring_end = i
                in_docstring = False
                break

    # Body starts after docstring
    body_start = docstring_end + 1

    # Get body lines
    body_lines = lines[body_start:func_end + 1]

    if not body_lines:
        continue

    # Check if body has outer try
    first_code_idx = None
    for bi, bl in enumerate(body_lines):
        if bl.strip():
            first_code_idx = bi
            break

    if first_code_idx is None:
        continue

    has_outer_try = body_lines[first_code_idx].strip() == "try:"

    if not has_outer_try:
        # No try block - just add decorator, no body changes needed
        # This handles tools like list_snapshots, delete_snapshot, etc.
        # that have no try/except at all
        new_lines = lines[tool_idx:func_end + 1]
        # Insert @_tool_handler after @mcp.tool()
        insert_pos = 1  # after @mcp.tool()
        handler_line = " " * func_indent + f'@_tool_handler("{error_prefix}")'
        new_lines.insert(insert_pos, handler_line)
        changes.append((tool_idx, func_end, new_lines))
        continue

    # Find the except blocks
    try_indent = len(body_lines[first_code_idx]) - len(body_lines[first_code_idx].lstrip())

    # Find matching except blocks at the same indent level
    first_except_idx = None
    for bi in range(first_code_idx + 1, len(body_lines)):
        bl = body_lines[bi]
        stripped = bl.strip()
        if not stripped:
            continue
        line_indent = len(bl) - len(bl.lstrip())
        if line_indent == try_indent and stripped.startswith("except "):
            first_except_idx = bi
            break

    if first_except_idx is None:
        # try with no except? Shouldn't happen but add decorator anyway
        new_lines = lines[tool_idx:func_end + 1]
        insert_pos = 1
        handler_line = " " * func_indent + f'@_tool_handler("{error_prefix}")'
        new_lines.insert(insert_pos, handler_line)
        changes.append((tool_idx, func_end, new_lines))
        continue

    # Check if there are inner try/excepts or non-standard except handlers
    # We need to check if any except catches something non-standard
    except_types = []
    for bi in range(first_except_idx, len(body_lines)):
        bl = body_lines[bi]
        stripped = bl.strip()
        line_indent = len(bl) - len(bl.lstrip())
        if line_indent == try_indent and stripped.startswith("except "):
            m = re.match(r'except\s+(\w+)', stripped)
            if m:
                except_types.append(m.group(1))

    # Standard except types that _tool_handler handles
    standard_types = {"ValueError", "ConnectionError", "Exception"}
    has_nonstandard = False
    for et in except_types:
        if et not in standard_types:
            has_nonstandard = True
            break

    # Get the try body (between try: and first except)
    try_body_lines = body_lines[first_code_idx + 1:first_except_idx]

    # Check for json.JSONDecodeError or ImportError in except blocks (non-standard)
    has_json_decode_except = False
    has_import_error = False
    for bi in range(first_except_idx, len(body_lines)):
        stripped = body_lines[bi].strip()
        if "json.JSONDecodeError" in stripped:
            has_json_decode_except = True
        if "ImportError" in stripped:
            has_import_error = True

    if has_json_decode_except or has_import_error or has_nonstandard:
        # Non-standard exception handling - keep inner try/except structure
        # but still add the decorator
        # For these, we add the decorator but DON'T remove the try/except
        # We still remove the outer standard excepts (ValueError, ConnectionError, Exception)
        # but keep the non-standard ones

        # Actually, per instructions: "still apply the decorator but preserve any internal
        # try/except that catches non-standard exceptions"
        # For tools with json.JSONDecodeError or ImportError, we need to keep
        # those specific excepts but remove the standard boilerplate ones.

        # Build new body: try block content + non-standard excepts only
        new_body_lines = []
        # Remove the try: line, keep content de-indented by one level (4 spaces)
        for bl in try_body_lines:
            if bl.strip():
                # De-indent by 4 spaces
                if bl.startswith(" " * (try_indent + 4)):
                    new_body_lines.append(bl[4:])
                else:
                    new_body_lines.append(bl)
            else:
                new_body_lines.append(bl)

        # Now check which except blocks to keep
        # Walk through except blocks
        bi = first_except_idx
        while bi < len(body_lines):
            stripped = body_lines[bi].strip()
            line_indent = len(body_lines[bi]) - len(body_lines[bi].lstrip())

            if line_indent == try_indent and stripped.startswith("except "):
                # Determine if this is a standard or non-standard except
                is_standard = False
                for st in standard_types:
                    if f"except {st}" in stripped:
                        is_standard = True
                        break

                if is_standard:
                    # Skip this except block entirely
                    bi += 1
                    while bi < len(body_lines):
                        next_stripped = body_lines[bi].strip()
                        next_indent = len(body_lines[bi]) - len(body_lines[bi].lstrip())
                        if next_indent <= try_indent and next_stripped:
                            break
                        bi += 1
                    continue
                else:
                    # Keep this non-standard except (but we need to keep the try too then)
                    # Actually this means we need the try/except structure
                    # This is complex - for simplicity, just add the decorator and
                    # DON'T modify the body
                    new_lines = lines[tool_idx:func_end + 1]
                    insert_pos = 1
                    handler_line = " " * func_indent + f'@_tool_handler("{error_prefix}")'
                    new_lines.insert(insert_pos, handler_line)

                    # Still need to replace indent=2 in json.dumps and M4L patterns
                    for ni in range(len(new_lines)):
                        new_lines[ni] = new_lines[ni].replace("json.dumps(result, indent=2)", "json.dumps(result)")

                    # Remove only the standard except blocks
                    # This is getting complex - let's handle it differently
                    # For tools with non-standard excepts mixed with standard ones,
                    # we keep the try, keep the non-standard except, remove standard excepts
                    # Actually... let's just add the decorator and remove only
                    # ValueError/ConnectionError/Exception excepts
                    break
            else:
                bi += 1
        else:
            # We went through all excepts and they were all standard - shouldn't reach here
            # if has_nonstandard was True, but just in case
            pass

        # For complex cases (ImportError, JSONDecodeError mixed with standard),
        # just add decorator, remove standard except blocks, keep the rest
        # Let's handle this properly:

        # Rebuild the function with:
        # 1. @mcp.tool()
        # 2. @_tool_handler("...")
        # 3. def line
        # 4. docstring
        # 5. try: body de-indented + non-standard excepts

        # Build new function lines
        new_func_lines = []
        # @mcp.tool()
        new_func_lines.append(lines[tool_idx])
        # @_tool_handler(...)
        new_func_lines.append(" " * func_indent + f'@_tool_handler("{error_prefix}")')
        # def line through docstring
        for i in range(def_line_idx, body_start):
            new_func_lines.append(lines[i])

        # Now process the body: remove try: and standard excepts, de-indent try body,
        # keep non-standard excepts with their try
        # If there are non-standard excepts, keep the try/except structure for those

        # Determine if we need to keep the try at all
        non_standard_excepts = []
        bi = first_except_idx
        while bi < len(body_lines):
            stripped = body_lines[bi].strip()
            line_indent = len(body_lines[bi]) - len(body_lines[bi].lstrip())

            if line_indent == try_indent and stripped.startswith("except "):
                is_standard = any(f"except {st}" in stripped for st in standard_types)

                # Collect this except block
                except_block = [body_lines[bi]]
                bi += 1
                while bi < len(body_lines):
                    next_stripped = body_lines[bi].strip()
                    next_indent = len(body_lines[bi]) - len(body_lines[bi].lstrip())
                    if next_indent <= try_indent and next_stripped:
                        break
                    except_block.append(body_lines[bi])
                    bi += 1

                if not is_standard:
                    non_standard_excepts.append(except_block)
                continue
            bi += 1

        if non_standard_excepts:
            # Keep the try/except but remove standard excepts
            # Output try: line de-indented
            new_func_lines.append(" " * body_indent + "try:")
            # try body (already at correct indent)
            for bl in try_body_lines:
                if bl.strip():
                    new_func_lines.append(bl)
                else:
                    new_func_lines.append(bl)
            # Non-standard except blocks
            for block in non_standard_excepts:
                for bl in block:
                    if bl.strip():
                        new_func_lines.append(bl)
                    else:
                        new_func_lines.append(bl)
        else:
            # All excepts are standard - remove try/except, de-indent
            for bl in try_body_lines:
                if bl.strip():
                    if bl.startswith(" " * (try_indent + 4)):
                        new_func_lines.append(bl[4:])
                    else:
                        new_func_lines.append(bl)
                else:
                    new_func_lines.append(bl)

        # Replace json.dumps indent=2
        for ni in range(len(new_func_lines)):
            new_func_lines[ni] = new_func_lines[ni].replace("json.dumps(result, indent=2)", "json.dumps(result)")

        # Replace M4L result patterns
        # This handles: if result.get("status") == "success": ... return f"M4L bridge error: ..."
        # We'll handle M4L pattern replacement in a separate pass since it's more complex

        changes.append((tool_idx, func_end, new_func_lines))
        continue

    # Standard case: all excepts are ValueError/ConnectionError/Exception
    # Remove try/except, de-indent, add decorator

    new_func_lines = []
    # @mcp.tool()
    new_func_lines.append(lines[tool_idx])
    # @_tool_handler(...)
    new_func_lines.append(" " * func_indent + f'@_tool_handler("{error_prefix}")')
    # def line through docstring
    for i in range(def_line_idx, body_start):
        new_func_lines.append(lines[i])

    # De-indent try body by 4 spaces
    for bl in try_body_lines:
        if bl.strip():
            if bl.startswith(" " * (try_indent + 4)):
                new_func_lines.append(bl[4:])
            else:
                new_func_lines.append(bl)
        else:
            new_func_lines.append(bl)

    # Replace json.dumps indent=2
    for ni in range(len(new_func_lines)):
        new_func_lines[ni] = new_func_lines[ni].replace("json.dumps(result, indent=2)", "json.dumps(result)")

    changes.append((tool_idx, func_end, new_func_lines))

# ---- Step 4: Apply changes (in reverse order to preserve line numbers) ----
changes.sort(key=lambda x: x[0], reverse=True)

print(f"\nApplying {len(changes)} changes...")

for start, end, new_lines in changes:
    func_name = get_func_name(lines, start)
    old_count = end - start + 1
    new_count = len(new_lines)
    lines[start:end + 1] = new_lines

output = "\n".join(lines)

# ---- Step 5: Handle M4L result patterns ----
# Replace the pattern:
#   if result.get("status") == "success":
#       data = result.get("result", {})
#       ... use data ...
#       return ...
#   return f"M4L bridge error: {result.get('message', 'Unknown error')}"
# with:
#   data = _m4l_result(result)
#   ... use data ...
#   return ...
#
# This is too complex for regex on multi-line patterns, so we'll handle it
# as a separate manual pass - but for simple one-liners we can do:
# Pattern: `return json.dumps(result.get("result", {}), indent=2)` after success check

# Actually, we need to be more careful. The M4L tools have various patterns.
# Let's just handle json.dumps(result, indent=2) -> json.dumps(result) which we already did.
# The M4L result pattern changes need careful per-function handling, which the
# decorator + _m4l_result helper are designed for.

# For now, let's at least handle the most common M4L pattern replacements.
# We'll do a second pass looking for the M4L patterns.

with open(INPUT, "w", encoding="utf-8") as f:
    f.write(output)

print(f"Done! Wrote {len(lines)} lines to {INPUT}")
print(f"Changes applied: {len(changes)} tools refactored")
