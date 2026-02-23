"""Browser/search tool handlers for AbletonBridge."""
import json
from mcp.server.fastmcp import Context
from MCP_Server.tools._base import _tool_handler, _m4l_result
from MCP_Server.connections.ableton import get_ableton_connection
from MCP_Server.connections.m4l import get_m4l_connection
from MCP_Server.validation import _validate_index, _validate_range
from MCP_Server.cache.browser import resolve_device_uri, resolve_sample_uri, get_browser_cache, populate_browser_cache
import MCP_Server.state as state


# Maps category keys to display names (used by search_browser and get_browser_tree)
_CATEGORY_DISPLAY = {
    "instruments": "Instruments",
    "sounds": "Sounds",
    "drums": "Drums",
    "audio_effects": "Audio Effects",
    "midi_effects": "MIDI Effects",
    "max_for_live": "Max for Live",
    "plugins": "Plug-ins",
    "clips": "Clips",
    "samples": "Samples",
    "packs": "Packs",
    "user_library": "User Library",
}


def register_tools(mcp):

    @mcp.tool()
    @_tool_handler("getting browser tree")
    def get_browser_tree(ctx: Context, category_type: str = "all") -> str:
        """
        Get a hierarchical tree of browser categories from Ableton.

        Uses cached browser data when available for richer results with URIs.

        Parameters:
        - category_type: Type of categories to get ('all', 'instruments', 'sounds', 'drums', 'audio_effects', 'midi_effects')
        """
        # Try to serve from cache first (richer data with URIs)
        cache = get_browser_cache()
        if cache:
            # Filter categories
            if category_type == "all":
                show_categories = list(_CATEGORY_DISPLAY.values())
            else:
                show_categories = [_CATEGORY_DISPLAY.get(category_type, category_type)]

            formatted_output = f"Browser tree for '{category_type}':\n\n"
            for cat_display in show_categories:
                # Use category index for O(1) lookup instead of scanning all items
                with state.browser_cache_lock:
                    cat_items = state.browser_cache_by_category.get(cat_display, [])
                # Top-level items have paths like "sounds/Operator" (2 segments)
                top_items = [
                    item for item in cat_items
                    if item.get("path", "").count("/") == 1
                ]
                if not top_items:
                    continue

                formatted_output += f"**{cat_display}** ({len(top_items)} items):\n"
                for item in sorted(top_items, key=lambda x: x.get("name", "")):
                    loadable = " [loadable]" if item.get("is_loadable", False) else ""
                    folder = " [+]" if item.get("is_folder", False) else ""
                    formatted_output += f"  • {item['name']}{loadable}{folder}"
                    if item.get("uri"):
                        formatted_output += f"  (URI: {item['uri']})"
                    formatted_output += "\n"
                formatted_output += "\n"

            return formatted_output

        # Fallback: fetch from Ableton directly
        ableton = get_ableton_connection()
        result = ableton.send_command("get_browser_tree", {
            "category_type": category_type
        })

        if "available_categories" in result and len(result.get("categories", [])) == 0:
            available_cats = result.get("available_categories", [])
            return (f"No categories found for '{category_type}'. "
                   f"Available browser categories: {', '.join(available_cats)}")

        total_folders = result.get("total_folders", 0)
        formatted_output = f"Browser tree for '{category_type}' (showing {total_folders} folders):\n\n"

        def format_tree(item, indent=0):
            output = ""
            if item:
                prefix = "  " * indent
                name = item.get("name", "Unknown")
                path = item.get("path", "")
                has_more = item.get("has_more", False)
                output += f"{prefix}• {name}"
                if path:
                    output += f" (path: {path})"
                if has_more:
                    output += " [...]"
                output += "\n"
                for child in item.get("children", []):
                    output += format_tree(child, indent + 1)
            return output

        for category in result.get("categories", []):
            formatted_output += format_tree(category)
            formatted_output += "\n"

        return formatted_output

    @mcp.tool()
    @_tool_handler("getting browser items at path")
    def get_browser_items_at_path(ctx: Context, path: str) -> str:
        """
        Get browser items at a specific path in Ableton's browser.

        Parameters:
        - path: Path in the format "category/folder/subfolder"
                where category is one of the available browser categories in Ableton
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("get_browser_items_at_path", {
            "path": path
        })

        # Check if there was an error with available categories
        if "error" in result and "available_categories" in result:
            error = result.get("error", "")
            available_cats = result.get("available_categories", [])
            return (f"Error: {error}\n"
                   f"Available browser categories: {', '.join(available_cats)}")

        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("searching browser")
    def search_browser(ctx: Context, query: str, category: str = "all") -> str:
        """
        Search the Ableton browser for items matching a query.

        Uses a cached browser index for instant results. The cache is built
        automatically on first use and refreshed every 5 minutes.

        Parameters:
        - query: Search string to find items (searches by name)
        - category: Limit search to category ('all', 'instruments', 'sounds', 'drums', 'audio_effects', 'midi_effects', 'max_for_live', 'plugins', 'clips', 'samples', 'packs', 'user_library')
        """
        cache = get_browser_cache()
        if not cache:
            return "Browser cache is empty. Make sure Ableton is running and try again."

        query_lower = query.lower()

        # Use category index for filtered search (smaller list to scan)
        filter_display = _CATEGORY_DISPLAY.get(category) if category != "all" else None
        with state.browser_cache_lock:
            search_list = state.browser_cache_by_category.get(filter_display, cache) if filter_display else cache

        results = []
        for item in search_list:
            # Substring match using pre-lowercased search_name
            if query_lower in item.get("search_name", item.get("name", "").lower()):
                results.append(item)

        if not results:
            return f"No results found for '{query}' in category '{category}'"

        # Sort: loadable items first, then by name
        results.sort(key=lambda x: (not x.get("is_loadable", False), x.get("name", "").lower()))

        # Limit to 50 results
        results = results[:50]

        formatted_output = f"Found {len(results)} results for '{query}':\n\n"
        for item in results:
            loadable = " [loadable]" if item.get("is_loadable", False) else ""
            folder = " [folder]" if item.get("is_folder", False) else ""
            formatted_output += f"• {item.get('name', 'Unknown')}{loadable}{folder}\n"
            formatted_output += f"  Category: {item.get('category', '?')} | Path: {item.get('path', '?')}\n"
            if item.get("uri"):
                formatted_output += f"  URI: {item.get('uri')}\n"

        return formatted_output

    @mcp.tool()
    @_tool_handler("refreshing browser cache")
    def refresh_browser_cache_tool(ctx: Context) -> str:
        """
        Force a refresh of the browser cache.

        Use this after installing new packs, instruments, or effects so that
        search_browser can find them. The cache is also auto-refreshed every
        5 minutes.
        """
        success = populate_browser_cache(force=True)
        if success:
            with state.browser_cache_lock:
                count = len(state.browser_cache_flat)
                cats = len(state.browser_cache_by_category)
                devices = len(state.device_uri_map)
            return f"Browser cache refreshed: {count} items across {cats} categories, {devices} device names mapped (saved to disk)"
        return "Failed to refresh browser cache. Make sure Ableton is running."

    # Register under the original tool name
    refresh_browser_cache_tool.__name__ = "refresh_browser_cache"

    @mcp.tool()
    @_tool_handler("loading sample")
    def load_sample(ctx: Context, track_index: int, sample_uri: str) -> str:
        """
        Load an audio sample onto a track from the browser.

        Accepts a full browser URI, a ``query:UserLibrary#...`` style URI, or
        just a filename (resolved automatically via the browser cache).

        Parameters:
        - track_index: The index of the track to load the sample onto
        - sample_uri: The URI or filename of the sample (use get_user_library or search_browser to find URIs)
        """
        _validate_index(track_index, "track_index")
        resolved_uri = resolve_sample_uri(sample_uri)
        ableton = get_ableton_connection()
        result = ableton.send_command("load_sample", {
            "track_index": track_index,
            "sample_uri": resolved_uri
        })
        if result.get("loaded", False):
            return f"Loaded sample '{result.get('item_name', result.get('sample_name', 'unknown'))}' onto track {track_index}"
        return f"Failed to load sample"

    @mcp.tool()
    @_tool_handler("loading drum kit")
    def load_drum_kit(ctx: Context, track_index: int, rack_uri: str, kit_path: str) -> str:
        """
        Load a drum rack and then load a specific drum kit into it.

        Specialized two-step loader: creates a Drum Rack then loads a kit into it.
        For loading individual instruments, use load_instrument_or_effect instead.

        Parameters:
        - track_index: The index of the track to load on
        - rack_uri: The URI of the drum rack to load (e.g., 'Drums/Drum Rack')
        - kit_path: Path to the drum kit inside the browser (e.g., 'drums/acoustic/kit1')
        """
        _validate_index(track_index, "track_index")
        ableton = get_ableton_connection()

        # Step 1: Load the drum rack
        result = ableton.send_command("load_browser_item", {
            "track_index": track_index,
            "item_uri": rack_uri
        })

        if not result.get("loaded", False):
            return f"Failed to load drum rack with URI '{rack_uri}'"

        # Step 2: Get the drum kit items at the specified path
        kit_result = ableton.send_command("get_browser_items_at_path", {
            "path": kit_path
        })

        if "error" in kit_result:
            return f"Loaded drum rack but failed to find drum kit: {kit_result.get('error')}"

        # Step 3: Find a loadable drum kit
        kit_items = kit_result.get("items", [])
        loadable_kits = [item for item in kit_items if item.get("is_loadable", False)]

        if not loadable_kits:
            return f"Loaded drum rack but no loadable drum kits found at '{kit_path}'"

        # Step 4: Load the first loadable kit
        kit_uri = loadable_kits[0].get("uri")
        load_result = ableton.send_command("load_browser_item", {
            "track_index": track_index,
            "item_uri": kit_uri
        })

        return f"Loaded drum rack and kit '{loadable_kits[0].get('name')}' on track {track_index}"

    @mcp.tool()
    @_tool_handler("getting user library")
    def get_user_library(ctx: Context) -> str:
        """
        Get the user library browser tree, including user folders and samples.
        Returns the browser structure for user-added content.
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("get_user_library")
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("getting user folders")
    def get_user_folders(ctx: Context) -> str:
        """
        Get user-configured sample folders from Ableton's browser.
        Note: Returns browser items (URIs), not raw filesystem paths.
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("get_user_folders")
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("previewing browser item")
    def preview_browser_item(ctx: Context, uri: str = None, action: str = "preview") -> str:
        """Preview (audition) a browser item before loading it, or stop the current preview.

        Parameters:
        - uri: The URI of the browser item to preview (required for 'preview' action).
               Use search_browser or get_browser_tree to find URIs.
        - action: 'preview' to start previewing, 'stop' to stop the current preview. Default: 'preview'
        """
        if action not in ("preview", "stop"):
            return "action must be 'preview' or 'stop'"
        params = {"action": action}
        if uri is not None:
            params["uri"] = uri
        ableton = get_ableton_connection()
        result = ableton.send_command("preview_browser_item", params)
        if action == "stop":
            return "Preview stopped"
        name = result.get("name", "?")
        return f"Previewing: '{name}'"

    @mcp.tool()
    @_tool_handler("getting device presets")
    def get_device_presets(ctx: Context, track_index: int, device_index: int, track_type: str = "track") -> str:
        """Get available presets for a specific device.

        Lists presets from Ableton's browser for the given device.
        Note: VST/AU plugin internal presets are NOT accessible through the API.

        Parameters:
        - track_index: Track containing the device
        - device_index: Index of the device
        - track_type: "track", "return", or "master"
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        ableton = get_ableton_connection()
        result = ableton.send_command("get_device_presets", {
            "track_index": track_index,
            "device_index": device_index,
            "track_type": track_type,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("loading device preset")
    def load_device_preset(ctx: Context, track_index: int, device_index: int, preset_uri: str, track_type: str = "track") -> str:
        """Load a preset onto a device using its URI.

        Use get_device_presets to find available presets and their URIs first.
        Note: This only works with Ableton native device presets, not VST/AU internal presets.

        Parameters:
        - track_index: Track containing the device
        - device_index: Index of the device
        - preset_uri: URI of the preset to load (from get_device_presets)
        - track_type: "track", "return", or "master"
        """
        _validate_index(track_index, "track_index")
        _validate_index(device_index, "device_index")
        if not preset_uri:
            raise ValueError("preset_uri is required")
        ableton = get_ableton_connection()
        result = ableton.send_command("load_device_preset", {
            "track_index": track_index,
            "device_index": device_index,
            "preset_uri": preset_uri,
            "track_type": track_type,
        })
        return json.dumps(result)

    @mcp.tool()
    @_tool_handler("listing presets")
    def list_instrument_rack_presets(ctx: Context) -> str:
        """List Instrument Rack presets saved in the user library.

        This is the recommended workaround for loading VST/AU plugins, since
        Ableton's API does not support loading third-party plugins directly.

        Workflow:
          1. Load your VST/AU plugin manually in Ableton
          2. Group it into an Instrument Rack (Cmd+G / Ctrl+G)
          3. Save the rack to your User Library
          4. Use this tool to find it, then load_instrument_or_effect() to load it

        This tool searches the user library for saved device presets (.adg files)
        that can be loaded onto tracks.
        """
        ableton = get_ableton_connection()
        result = ableton.send_command("get_user_library")

        if not result:
            return "Could not retrieve user library."

        # Recursively collect loadable items from the user library
        presets = []

        def collect_loadable(items, path=""):
            if isinstance(items, list):
                for item in items:
                    collect_loadable(item, path)
            elif isinstance(items, dict):
                name = items.get("name", "")
                is_loadable = items.get("is_loadable", False)
                uri = items.get("uri", "")
                current_path = f"{path}/{name}" if path else name

                if is_loadable and uri:
                    presets.append({
                        "name": name,
                        "path": current_path,
                        "uri": uri
                    })

                # Recurse into children
                children = items.get("children", [])
                if children:
                    collect_loadable(children, current_path)

        collect_loadable(result)

        if not presets:
            return (
                "No loadable presets found in the user library.\n\n"
                "To create a VST/AU wrapper preset:\n"
                "  1. Load your VST/AU plugin manually in Ableton\n"
                "  2. Group it into an Instrument Rack (Cmd+G / Ctrl+G)\n"
                "  3. Save the rack to your User Library (Ctrl+S / Cmd+S on the rack)\n"
                "  4. Run this tool again to find it"
            )

        output = f"Found {len(presets)} loadable preset(s) in user library:\n\n"
        for p in presets:
            output += f"  - {p['name']}\n"
            output += f"    Path: {p['path']}\n"
            output += f"    URI: {p['uri']}\n"
            output += f"    Load with: load_instrument_or_effect(track_index, \"{p['uri']}\")\n\n"

        return output
