from string import Template


### rag prompts 


### system prompt
system_prompt = Template("\n".join([

"You are an assistant to genrate a response for the user.",
"You will be provided by a set of documents associated with the user's query.",
"you have to generate a response based on the documents provided.Ignore the documents that are not relevant to the query.",
"You should not make up any information that is not present in the documents provided.",
"Be ploite and professional in your response to the user.",
"Be concise and to the point in your response.",
"You have to respond in the same language as the user query.",
"Avoid unnecessary repetition in your response.",
"Avoid unnecessary information in your response.",
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
        "## Based only on the above documents, generate a response to the user query.",
        "## Response: ",
    ]))
