import logging
from mcp.server.fastmcp import FastMCP

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("style-match-mcp")

# Initialize FastMCP Server
mcp = FastMCP("style-match-mcp")

@mcp.tool()
def get_wardrobe_items() -> list[str]:
    """Retrieve the list of clothing items available in the user's wardrobe."""
    logger.info("MCP Tool: get_wardrobe_items called")
    return [
        "Navy blue slim-fit blazer",
        "White cotton button-down shirt",
        "Beige cotton chinos",
        "Black leather oxford shoes",
        "Charcoal grey crewneck wool sweater",
        "Dark blue denim jacket",
        "White casual canvas sneakers",
        "Olive green cargo pants",
        "Black waterproof raincoat",
        "Red cashmere scarf"
    ]

@mcp.tool()
def get_weather_forecast(location: str) -> str:
    """Get the current weather forecast for a given city or location to decide the best dress layers.
    
    Args:
        location: The city or area to get weather forecast for.
    """
    logger.info(f"MCP Tool: get_weather_forecast called for location: {location}")
    loc_lower = location.lower()
    if "london" in loc_lower or "rain" in loc_lower:
        return "Temp: 14°C (57°F), Condition: Rainy and windy. High chance of precipitation. Suggest waterproof layers or umbrella."
    elif "new york" in loc_lower or "cold" in loc_lower:
        return "Temp: 4°C (39°F), Condition: Clear and very cold. Gusty winds. Suggest heavy coat, scarf, and warm layers."
    elif "tokyo" in loc_lower or "sunny" in loc_lower:
        return "Temp: 22°C (72°F), Condition: Sunny, clear skies, pleasant breeze. Suggest light blazer, chinos, or sneakers."
    else:
        return "Temp: 18°C (64°F), Condition: Partly cloudy, mild temperature. Suggest light jacket, denim, or sweater."

@mcp.tool()
def save_selected_outfit(outfit: str) -> str:
    """Save the final approved outfit selection to the user's outfit diary.
    
    Args:
        outfit: The details of the outfit that is selected.
    """
    logger.info("MCP Tool: save_selected_outfit called")
    return f"Success: Outfit saved to diary: {outfit[:60]}..."

if __name__ == "__main__":
    mcp.run()
