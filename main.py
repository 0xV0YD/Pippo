from server import mcp

# Import tools so they get registered via decorators
import tools.calendar_tools
import tools.csv_tools
import tools.linear_tools
import tools.parquet_tools

# Entry point to run the server
if __name__ == "__main__":
    mcp.run()
