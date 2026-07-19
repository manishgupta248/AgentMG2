from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler

autodiscover_tools()

result = call_tool(
    "gmail_send",
    {
        "to": "manish.gupta248@gmail.com",
        "subject": "Agent MG — M9 gmail_send test",
        "body": "This is a real test email sent by the Personal AI Agent during M9 verification. If you're reading this, gmail_send works correctly.",
    },
    approval_handler=AutoApprovalHandler(),  # explicit opt-in, since gmail_send is MODIFY permission
)

print("Send result:", result.data)