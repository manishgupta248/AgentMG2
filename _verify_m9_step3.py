from app.core.registry import autodiscover_tools
from app.core.executor import call_tool

autodiscover_tools()

# Search for a handful of recent emails (adjust query if you want)
r1 = call_tool("gmail_search", {"query": "in:inbox", "max_results": 3})
print("Search results:")
for m in r1.data["messages"]:
    print(f"  - [{m['id']}] {m['subject']} (from: {m['from']})")

if r1.data["messages"]:
    first_id = r1.data["messages"][0]["id"]
    r2 = call_tool("gmail_read_message", {"message_id": first_id})
    print("\nFull read of first message:")
    print("Subject:", r2.data["subject"])
    print("From:", r2.data["from"])
    print("Body (first 300 chars):", r2.data["body"][:300])
else:
    print("\nNo messages found to test gmail_read_message with.")