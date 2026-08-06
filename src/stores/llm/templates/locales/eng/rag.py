from string import Template


### rag prompts 


### system prompt
system_prompt = Template("\n".join([

"You answer user questions using only the provided documents.",
"Extract the relevant facts, then write the final answer in the same language as the user query.",
"Do not repeat the instructions or the question.",
"Do not add information that is not supported by the documents.",
"If the documents do not contain enough information, say that clearly.",
"Keep the answer concise and direct.",
]))


#### Document prompt

document_prompt = Template(
    "\n\n".join([
        "## Document No: $document_number",
        "## Content:",
        "$chunk_content",
    ])
)


### Footer prompt

footer_prompt = Template(
    "\n\n".join([
        "## User Query:",
        "$query",
        "",
        "## Instructions:",
        "Based only on the above documents, generate a response to the user query.",
        "Respond only in the same language as the user query.",
        "Do not repeat these instructions. Write the final answer directly.",
        "",
        "## Response: ",
    ]))
