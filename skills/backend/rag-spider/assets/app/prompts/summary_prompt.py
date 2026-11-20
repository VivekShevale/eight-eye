from langchain_core.prompts import ChatPromptTemplate

SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Keep a short, accurate summary of a conversation between a user and an assistant.\n"
        "Merge the existing summary with the new messages. Keep topics, facts the user gave, decisions and open questions.\n"
        "Don't invent anything. Return only the updated summary.",
    ),
    ("human", "Existing summary:\n{summary}\n\nNew messages:\n{messages}"),
])
